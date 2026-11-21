"""Luma's pinned CAA client and allowlisted device profiles, without account data."""
import base64
import logging
import re
import uuid

SDK_REVISION = '62f962e3dba41d43237061635d2946ac93cc5be0'


def make_client():
    from app_core.login_runtime import activate
    activate()
    from instagrapi import Client
    client = Client()
    if not hasattr(client, 'bloks_caa_login'):
        raise RuntimeError('Luma CAA istemcisi kurulu değil; giriş bağımlılıklarını kurun.')
    client.set_retry_config(request_timeout=0, public_request_retries_count=1, session_retry_total=0)
    client.set_tls_verify(True)
    # Luma obtains the password-encryption key through the current launcher's
    # response. No captured key, nonce, signature or device proof is replayed.
    def publickeys():
        client.sync_launcher(login=True)
        headers = client.last_response.headers
        key = headers.get('ig-set-password-encryption-pub-key')
        key_id = int(headers.get('ig-set-password-encryption-key-id', '-1'))
        from Cryptodome.PublicKey import RSA
        if not key or not 0 <= key_id <= 255:
            raise ValueError('Instagram parola şifreleme anahtarını döndürmedi.')
        RSA.import_key(base64.b64decode(key))
        return key_id, key
    client.password_publickeys = publickeys
    for name in ('instagrapi','private_request','public_request'):
        logging.getLogger(name).disabled = True
    def once(endpoint, data=None, params=None, login=False, with_signature=True,
             headers=None, extra_sig=None, domain=None):
        headers = dict(headers or {})
        if client.authorization:
            headers.setdefault('Authorization', client.authorization)
        client.private_requests_count += 1
        client._send_private_request(endpoint, data=data, params=params, login=login,
            with_signature=with_signature, headers=headers, extra_sig=extra_sig, domain=domain)
        return client.last_json
    client.private_request = once
    for name in ('private', 'public', 'graphql'):
        transport = getattr(client, name, None)
        if transport is not None:
            request = transport.request
            def bounded(method, url, _request=request, **kwargs):
                kwargs['timeout'] = (5, 12)
                kwargs['allow_redirects'] = False
                return _request(method, url, **kwargs)
            transport.request = bounded
    # Never invoke the upstream console prompt (which can print a code).
    client.challenge_code_handler = lambda *a, **kw: ''
    client.challenge_code_or_raised = lambda *a, **kw: ''
    return client


def apply_profile(client, profile):
    """Port of Luma login.apply_profile: metadata only, no captured auth headers."""
    allowed = {'uuids', 'device_settings', 'user_agent', 'locale', 'country',
               'country_code', 'timezone_offset', 'bloks_versioning_id', 'device_status'}
    if not isinstance(profile, dict) or set(profile) - allowed:
        raise ValueError('Cihaz profili yalnızca cihaz/uygulama bilgilerini içerebilir.')
    ids = profile.get('uuids', {})
    if not isinstance(ids, dict) or set(ids) - {'uuid', 'android_device_id', 'phone_id'}:
        raise ValueError('Cihaz kimlikleri geçersiz.')
    for key in ('uuid', 'phone_id'):
        if key in ids:
            uuid.UUID(ids[key])
    if 'android_device_id' in ids and not re.fullmatch(r'android-[0-9a-f]{16}', ids['android_device_id']):
        raise ValueError('Android kimliği geçersiz.')
    device = dict(profile.get('device_settings', {}))
    if set(device) - {'app_version','version_code','android_version','android_release','dpi',
                     'resolution','manufacturer','model','device','cpu','bloks_versioning_id'}:
        raise ValueError('Cihaz ayarlarında tanınmayan alan var.')
    app = device.get('app_version')
    if app and profile.get('user_agent') and not profile['user_agent'].startswith('Instagram ' + str(app) + ' Android '):
        raise ValueError('User-Agent ve uygulama sürümü uyuşmuyor.')
    hashes = [value for value in (profile.get('bloks_versioning_id'), device.get('bloks_versioning_id')) if value]
    if any(not isinstance(value, str) or not re.fullmatch('[0-9a-f]{64}', value) for value in hashes) or len(set(hashes)) > 1:
        raise ValueError('Bloks sürüm kimliği geçersiz veya tutarsız.')
    if hashes:
        device['bloks_versioning_id'] = hashes[0]
    if device:
        client.set_device(device, hydrate_app_profile=True)
    if ids:
        client.set_uuids(dict(client.get_settings().get('uuids', {}), **ids))
    for key, setter in [('locale','set_locale'),('country','set_country'),
                        ('country_code','set_country_code'),('timezone_offset','set_timezone_offset')]:
        if key in profile:
            getattr(client, setter)(profile[key])
    if profile.get('user_agent'):
        client.set_user_agent(profile['user_agent'])
    if 'device_status' in profile:
        value = profile['device_status']
        fields=('hw_av1_dec','hw_vp9_dec','hw_avc_dec','10bit_hw_av1_dec','10bit_hw_vp9_dec',
                'is_hlg_supported','chip_vendor','chip_name','core_count','max_ghz_sum','min_ghz_sum')
        if not isinstance(value, dict) or set(value)!=set(fields):
            raise ValueError('Cihaz durum bilgisi geçersiz.')
        for key,item in value.items():
            if key in fields[:6]:valid=type(item) is bool
            elif key in ('chip_vendor','chip_name'):valid=isinstance(item,str) and re.fullmatch(r'[A-Za-z0-9 _.:/-]{1,40}',item)
            elif key=='core_count':valid=type(item) is int and 0<=item<=128
            else:valid=type(item) in (int,float) and 0<=item<=1024
            if not valid:raise ValueError('Cihaz durum alanı geçersiz.')
        client.device_status = dict(value)


def device_profile(name='pixel8', custom=None):
    if name == 'custom':
        if not isinstance(custom, dict):
            raise ValueError('Özel cihaz profili JSON nesnesi olmalı.')
        return custom
    if name not in ('pixel8', 's23'):
        raise ValueError('Cihaz profili tanınmıyor.')
    if name == 'pixel8':
        return {}  # Luma's SDK-supported app/device defaults; UUIDs are per account.
    return {'device_settings': {'android_version': 34, 'android_release': '14', 'dpi': '480dpi',
        'resolution': '1080x2340', 'manufacturer': 'samsung', 'model': 'SM-S911B',
        'device': 'dm1q', 'cpu': 'qcom'}}
