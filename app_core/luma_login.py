"""Account-isolated Luma CAA login, resumable across PythonAnywhere requests.

No background thread, password replay, captured security proof or console prompt.
Only SDK-issued contexts are continued; credentials/codes never enter storage.
"""
import copy
import hashlib
import json
import re
import time
import uuid

from app_core.jobs import transaction
from app_core.login_client import make_client, apply_profile, device_profile

APPROVAL = 'com.bloks.www.two_step_verification.has_been_allowed.async'
VERIFY = 'com.bloks.www.two_step_verification.verify_code.async'
WHATSAPP = 'com.bloks.www.two_step_verification.enter_whatsapp_code'


class LoginFailure(ValueError):
    def __init__(self, message, status=400):
        super().__init__(message)
        self.status = status


def _get(conn, key):
    row = conn.execute('SELECT value FROM key_value WHERE key=?', (key,)).fetchone()
    return json.loads(row['value']) if row else None


def _put(conn, key, value):
    conn.execute('INSERT OR REPLACE INTO key_value(key,value) VALUES (?,?)', (key, json.dumps(value)))


def public(flow):
    return {key: flow.get(key) for key in ('id', 'username', 'stage', 'message', 'methods', 'device', 'expires')}


def _flow(conn, flow_id, owner):
    flow = _get(conn, 'luma-flow:' + flow_id)
    if not flow or flow.get('owner') != owner:
        raise LoginFailure('Giriş işlemi bulunamadı.', 404)
    if flow['expires'] < time.time() and flow['stage'] not in ('done','failed','cancelled'):
        raise LoginFailure('Giriş isteğinin süresi doldu. Yeni giriş başlatın.', 410)
    return flow


def status(flow_id, owner):
    with transaction() as conn:
        return public(_flow(conn, flow_id, owner))


def _snapshot(client):
    return copy.deepcopy(client.get_settings())


def _save(flow, client):
    flow['settings'] = _snapshot(client)
    flow['caa_aac'] = getattr(client, 'caa_aac', '')
    with transaction() as conn:
        current = _get(conn, 'luma-flow:' + flow['id'])
        profile = _get(conn, 'luma-account:' + flow['username']) or {}
        if (not current or current.get('operation') != flow.get('operation')
                or current['stage'] == 'cancelled' or profile.get('flow_id') != flow['id']):
            raise LoginFailure('Giriş işlemi iptal edildi veya daha yeni bir işlem var.', 409)
        _put(conn, 'luma-flow:' + flow['id'], flow)
        profile.update(settings=flow['settings'], device=flow['device'], owner=flow['username'])
        if flow['stage'] == 'failed' and flow.get('attempted_password'):
            profile['retry_after'] = time.time() + 180
        _put(conn, 'luma-account:' + flow['username'], profile)


def _close(client):
    client.password = ''
    client.challenge_code_handler = lambda *a, **kw: ''
    client.challenge_code_or_raised = lambda *a, **kw: ''
    for name in ('private','public','graphql'):
        transport = getattr(client, name, None)
        if transport is not None:
            transport.close()


def _message(error):
    kind = type(error).__name__
    if isinstance(error, LoginFailure):
        return str(error)
    if kind in ('BadPassword','InvalidUser','BadCredentials'):
        return 'Kullanıcı adı veya parola hatalı.'
    if kind in ('LoginRequired','ClientUnauthorizedError'):
        return 'Kayıtlı oturumun süresi dolmuş. Parolanızı girerek yeniden deneyin; kayıtlı cihazınız korunur.'
    if kind in ('TwoFactorRequired','ChallengeRequired','ChallengeError','SelectContactPointRecoveryForm'):
        return 'Instagram ek doğrulama istedi; sunucunun açtığı doğrulama adımlarıyla devam edin veya resmî uygulamadan hesabı kontrol edin.'
    if 'Timeout' in kind or 'Connection' in kind:
        return 'Instagram bağlantısı tamamlanamadı. Cihaz ve varsa alınmış oturum korundu; giriş otomatik tekrarlanmadı.'
    if kind in ('PleaseWaitFewMinutes','ClientThrottledError','RateLimitError'):
        return 'Instagram girişleri sınırlandırdı. Bir süre bekleyip yeniden deneyin.'
    return 'Giriş tamamlanamadı. Cihaz ve varsa alınmış oturum korundu; giriş otomatik tekrarlanmadı.'


def _prepare_profile_code(client, result, **kwargs):
    # Same SDK steps as Luma's bloks_caa_login; pause BEFORE requesting a code.
    from instagrapi.mixins.bloks import AP_2SV_ENTRYPOINT, AP_2SV_CODE_ENTRY, AP_2SV_CODE_ENTRY_ASYNC
    context = client.bloks_extract_context_data(result, AP_2SV_ENTRYPOINT)
    if not context:
        raise LoginFailure('Instagram kod doğrulama bağlamını döndürmedi.')
    entry = client.bloks_ap_two_step_verification_entrypoint(context, domain='i.instagram.com')
    context = client.bloks_extract_context_data(entry, AP_2SV_CODE_ENTRY)
    if not context:
        raise LoginFailure('Instagram kod ekranını açmadı.')
    screen = client.bloks_ap_two_step_verification_code_entry(context, domain='i.instagram.com')
    context = client.bloks_extract_context_data(screen, AP_2SV_CODE_ENTRY_ASYNC)
    if not context:
        raise LoginFailure('Instagram kod gönderme bağlamını döndürmedi.')
    return {'logged_in': False, 'profile_code_context': context, 'result': screen}


def _accept(flow, client):
    # Persist returned authentication BEFORE account verification, just like Luma.
    flow.update(stage='verify', message='Alınan oturumun hesap kimliği doğrulanıyor.')
    _save(flow, client)
    user = client.account_info()
    pk = str(getattr(user, 'pk', '') or '')
    name = str(getattr(user, 'username', '') or '')
    if not pk.isdecimal() or pk != str(client.user_id) or name.casefold() != flow['username'].casefold():
        raise LoginFailure('Dönen hesap kimliği giriş yapılan hesapla eşleşmedi.')
    token = client.authorization
    if not token:
        raise LoginFailure('Instagram kullanılabilir bir oturum döndürmedi.')
    # Publish token, scoped session and the successful flow atomically. Do not
    # batch-save other accounts or expose a token before identity verification.
    from app_core.storage import upsert_token
    from datetime import datetime
    cookies = [dict(name=c.name,value=c.value,domain=c.domain,path=c.path,secure=c.secure,expires=c.expires)
               for c in client.private.cookies]
    with transaction() as conn:
        current = _flow(conn, flow['id'], flow['owner'])
        profile = _get(conn,'luma-account:'+flow['username']) or {}
        if (current.get('operation') != flow['operation'] or current['stage'] == 'cancelled'
                or profile.get('flow_id') != flow['id']):
            raise LoginFailure('Giriş iptal edildi veya yeni bir giriş başlatıldı.', 409)
        existing = conn.execute('SELECT * FROM tokens WHERE username=?',(flow['username'],)).fetchone()
        record = dict(existing) if existing else {'added_at':str(datetime.now())}
        record.update(username=flow['username'],full_name=getattr(user,'full_name',''),password='',token=token,
                      android_id_yeni=client.android_device_id.removeprefix('android-'),
                      user_agent=client.user_agent,device_id=client.uuid,is_active=True,
                      logout_reason='',logout_time='',last_relogin_failed_at='',deleted_at='',relogin_attempts=0)
        if not upsert_token(record,conn=conn):
            raise LoginFailure('Doğrulanan oturum kaydedilemedi; önceki kayıtlar korundu.')
        key='session_state_'+flow['username']
        prior=_get(conn,key) or {}
        state=dict(ds_user_id=pk,rur=client.ig_u_rur or '',www_claim=client.ig_www_claim or '',
                   http_cookies=cookies,revision=int(prior.get('revision',0))+1,
                   bloks_versioning_id=client.bloks_versioning_id,phone_id=client.phone_id,
                   locale=client.locale,country=client.country,timezone_offset=client.timezone_offset,mid=client.mid)
        _put(conn,key,state)
        flow.update(stage='done',message='Hesap doğrulandı ve kontrol programına bağlandı.',methods=[],settings=_snapshot(client))
        _put(conn,'luma-flow:'+flow['id'],flow)
        profile.update(settings=flow['settings'],device=flow['device'],owner=flow['username'],retry_after=0,
                       published_digest=hashlib.sha256(token.encode()).hexdigest())
        _put(conn,'luma-account:'+flow['username'],profile)
    from app_core.instagram_api import clear_http_session
    clear_http_session(flow['username'])


def _approval_screen(flow, client, result, context, *, open_entry=True):
    if open_entry and APPROVAL not in client._bloks_all_text(result):
        result = client.bloks_two_step_verification_entrypoint(context)
        if client.bloks_apply_login_response(result):
            return _accept(flow, client)
    if open_entry and APPROVAL not in client._bloks_all_text(result):
        # The server may offer a code method instead of app approval.
        flow.update(stage='method', message='Instagram’ın sunduğu doğrulama yöntemini seçin.', context=context)
        return _methods(flow, client)
    context = client.bloks_extract_two_step_verification_context(result) or context
    server = dict(flow.get('server') or {'device_id':client.android_device_id, 'spectra_reg_login_data':None,
              'flow_source':'two_factor_login'})
    server['two_step_verification_context'] = context
    for key in ('two_step_verification_context','network_bssid'):
        value = client._bloks_extract_context_value(result, APPROVAL, key)
        if isinstance(value,str) and value:
            server[key] = value
    flow.update(stage='approval', context=server['two_step_verification_context'], server=server,
                message='Instagram uygulamasındaki giriş isteğini onaylayın. Aynı giriş isteğinin sonucu bekleniyor.',
                methods=['approval'])


def _methods(flow, client):
    result = client.bloks_two_step_verification_method_picker(flow['context'])
    if client.bloks_apply_login_response(result):
        return _accept(flow, client)
    text = client._bloks_all_text(result)
    offered = [m for m in ('whatsapp','totp','sms','backup') if re.search(r'"' + m + r'"',text)]
    if not offered:
        raise LoginFailure('Instagram bu giriş için kullanılabilir bir kod yöntemi sunmadı.')
    flow.update(stage='method', methods=offered, message='Instagram’ın sunduğu doğrulama yöntemini seçin.')


def start(username, password='', *, owner, fresh=False, profile_name='saved', custom_profile=None, new_device=False):
    if not isinstance(username,str):raise LoginFailure('Kullanıcı adı geçersiz.')
    username = username.strip().lstrip('@').lower()
    if not re.fullmatch(r'[a-z0-9._]{1,30}',username) or not isinstance(password,str) or len(password)>1024:
        raise LoginFailure('Kullanıcı adı veya parola geçersiz.')
    client = make_client()
    flow = None
    try:
        with transaction() as conn:
            saved = _get(conn,'luma-account:' + username) or {}
            if saved.get('retry_after',0) > time.time():
                raise LoginFailure('Son giriş denemesi başarısız oldu. Yeniden denemeden önce üç dakika bekleyin.',429)
            active = _get(conn,'luma-flow:' + saved.get('flow_id',''))
            if active and active['expires']>time.time() and active['stage'] not in ('done','failed','cancelled'):
                raise LoginFailure('Bu hesap için devam eden giriş var; mevcut işlemi tamamlayın veya iptal edin.',409)
        selected = device_profile('pixel8' if profile_name == 'saved' else profile_name, custom_profile)
        saved_settings = saved.get('settings') or {}
        if profile_name == 'saved' and saved_settings:
            selected = {key:copy.deepcopy(saved_settings[key]) for key in
                ('device_settings','user_agent','locale','country','country_code','timezone_offset','device_status')
                if saved_settings.get(key) is not None}
        if saved_settings and profile_name != 'saved':
            selected_model = selected.get('device_settings',{}).get('model')
            saved_model = saved_settings.get('device_settings',{}).get('model')
            if profile_name == 'custom' or selected_model != saved_model:
                new_device = True
        if new_device and not password:
            raise LoginFailure('Seçtiğiniz cihazla giriş yapmak için parolanızı girin. Kayıtlı oturum değiştirilmedi.')
        settings = saved.get('settings') if not new_device else None
        creating_device = not bool(settings)
        if settings:
            if custom_profile is not None:
                raise LoginFailure('Kayıtlı cihazı değiştirmek için “Yeni cihaz profili” seçeneğini açın.')
            client.set_settings(settings)
            # Keep the latest token/cookies produced by the control program.
            from app_core.storage import load_tokens
            existing = next((t for t in load_tokens() if t['username']==username),None)
            if (existing and existing.get('token') and client.user_id
                    and saved.get('published_digest')==hashlib.sha256(client.authorization.encode()).hexdigest()):
                parsed = client.parse_authorization(existing['token'])
                if str(parsed.get('ds_user_id')) == str(client.user_id):
                    client.authorization_data = parsed
                    if parsed.get('sessionid'):client.private.cookies.set('sessionid',parsed['sessionid'])
                    from app_core.session_state import get_session
                    import requests
                    state=get_session(username)
                    for cookie in state.get('http_cookies',[]):
                        client.private.cookies.set_cookie(requests.cookies.create_cookie(**cookie))
        else:
            from app_core.device_profiles import new_identity
            client.set_uuids(new_identity())
            apply_profile(client, selected)
        # An explicitly supplied password requests a new login. Never ignore it
        # just because the browser did not also check the advanced fresh option.
        if fresh or new_device or password:
            settings = client.get_settings()
            settings.update(authorization_data={},cookies={},last_login=None)
            client.set_settings(settings)
        if not client.user_id and not password:
            raise LoginFailure('Bu hesap için parolanızı girin.')
        ids = client.get_settings().get('uuids',{})
        client.set_uuids(dict(ids,client_session_id=str(uuid.uuid4()),request_id=str(uuid.uuid4())))
        client.username = username
        flow = dict(id=uuid.uuid4().hex, username=username, owner=owner, operation=uuid.uuid4().hex,
                    stage='running',message='Instagram giriş isteği işleniyor.',methods=[],expires=time.time()+600,busy_until=time.time()+150,
                    device=client.get_settings().get('device_settings',{}).get('model',''), settings=_snapshot(client),
                    attempted_password=not bool(client.user_id))
        with transaction() as conn:
            # Another worker may have reserved this account while its client was prepared.
            current = _get(conn,'luma-account:' + username) or {}
            active = _get(conn,'luma-flow:' + current.get('flow_id',''))
            if active and active['expires']>time.time() and active['stage'] not in ('done','failed','cancelled'):
                raise LoginFailure('Bu hesap için başka giriş işlemi başladı.',409)
            if creating_device:
                from app_core.device_profiles import ensure_unused_identity
                ensure_unused_identity(conn, client.get_settings().get('uuids',{}))
            current.update(flow_id=flow['id'],settings=flow['settings'],device=flow['device'],owner=username)
            _put(conn,'luma-account:' + username,current)
            _put(conn,'luma-flow:' + flow['id'],flow)
        if client.user_id:
            _accept(flow, client)  # Saved session verification never resends credentials.
        else:
            client.password = password
            client.bloks_caa_resolve_two_step_verification = lambda result,**kw: _prepare_profile_code(client,result,**kw)
            outcome = client.bloks_caa_login(domain='i.instagram.com',verification_code='')
            client.password = ''; password = ''
            if outcome.get('logged_in'):
                _accept(flow,client)
            elif (outcome.get('two_step') or {}).get('profile_code_context'):
                flow.update(stage='code', profile_code_context=outcome['two_step']['profile_code_context'],
                            methods=['email'],message='Instagram’ın gönderdiği doğrulama kodunu girin.')
            elif outcome.get('two_step_verification_context'):
                _approval_screen(flow,client,outcome.get('result') or {},outcome['two_step_verification_context'])
            else:
                raise LoginFailure('Instagram oturum veya devam edilebilir onay bilgisi döndürmedi. Resmî uygulamadan hesabı kontrol edin.')
    except Exception as error:
        if flow is None:
            raise
        flow.update(stage='failed',message=_message(error),methods=[])
    finally:
        password = ''; client.password = ''
        try:
            if flow is not None:
                _save(flow,client)
        finally:
            _close(client)
    return public(flow)


def advance(flow_id, owner, action, code='', method=''):
    with transaction() as conn:
        flow = _flow(conn,flow_id,owner)
        if flow['stage'] in ('done','failed','cancelled'):
            return public(flow)
        if action == 'cancel':
            if flow['stage']=='running' and flow.get('busy_until',0)>time.time():
                raise LoginFailure('Giriş adımı işleniyor; sonucu bekleyip tekrar deneyin.',409)
            flow.update(stage='cancelled',message='Giriş iptal edildi.',context=None,server=None,result=None)
            _put(conn,'luma-flow:' + flow_id,flow)
            return public(flow)
        if flow['stage'] in ('done','failed','cancelled'):
            return public(flow)
        if flow['stage']=='running':
            raise LoginFailure('Bu giriş adımı zaten işleniyor.',409)
        previous = flow['stage']
        if action not in ('poll','methods','select','code','verify'):
            raise LoginFailure('Giriş adımı geçersiz.')
        if action=='code' and (previous!='code' or not re.fullmatch(r'[A-Za-z0-9 -]{4,32}',str(code))):
            raise LoginFailure('Doğrulama kodunu kontrol edin.')
        if action=='select' and (previous!='method' or method not in flow.get('methods',[])):
            raise LoginFailure('Instagram bu yöntemi sunmadı.')
        if action=='poll' and previous!='approval':
            raise LoginFailure('Bu giriş uygulama onayı beklemiyor.')
        if action=='methods' and previous not in ('approval','method'):
            raise LoginFailure('Bu giriş yöntem seçimi beklemiyor.')
        if action=='verify' and previous!='verify':
            raise LoginFailure('Bu giriş hesap doğrulama aşamasında değil.')
        flow.update(stage='running',operation=uuid.uuid4().hex,busy_until=time.time()+150)
        _put(conn,'luma-flow:' + flow_id,flow)
    client = make_client()
    try:
        client.set_settings(flow['settings']);client.username=flow['username'];client.caa_aac=flow.get('caa_aac','')
        if action=='verify':
            _accept(flow,client)
        elif action=='methods':
            _methods(flow,client)
        elif action=='poll':
            endpoint='bloks/async_action/' + APPROVAL + '/'
            result=client.private_request(endpoint,data=client._bloks_payload({
                'client_input_params':{'auth_secure_device_id':'','block_store_machine_id':'',
                    'family_device_id':client.phone_id,'should_trust_device':1,
                    'device_id':client.android_device_id,'cloud_trust_token':None,'machine_id':client.mid},
                'server_params':flow['server']}),with_signature=False,domain='i.instagram.com',login=True,
                headers={'X-FB-Friendly-Name':'IgApi: '+endpoint})
            if client.bloks_apply_login_response(result):
                _accept(flow,client)
            else:
                _approval_screen(flow,client,result,flow['context'],open_entry=False)
        elif action=='select':
            result=client.bloks_two_step_verification_select_method(flow['context'],method)
            if client.bloks_apply_login_response(result):
                _accept(flow,client)
            else:
                flow['method']=method
                flow['context']=client.bloks_extract_two_step_verification_context(result) or flow['context']
                if method=='whatsapp':
                    if WHATSAPP not in client._bloks_all_text(result):
                        raise LoginFailure('Instagram WhatsApp kod ekranını açmadı.')
                    context=client._bloks_extract_context_value(result,WHATSAPP,'two_step_verification_context') or flow['context']
                    screen=client.bloks_app(WHATSAPP,{'client_input_params':{'cloud_trust_token':None},
                        'server_params':{'device_id':client.android_device_id,'two_step_verification_context':context,
                                         'flow_source':'two_factor_login'}},domain='i.instagram.com',login=True)
                    if client.bloks_apply_login_response(screen):
                        _accept(flow,client)
                    else:
                        if VERIFY not in client._bloks_all_text(screen):
                            raise LoginFailure('Instagram kod doğrulama adımını döndürmedi.')
                        server={'device_id':client.android_device_id,'spectra_reg_login_data':None,
                                'challenge':'whatsapp','two_step_verification_context':context,'flow_source':'two_factor_login'}
                        for key in ('two_step_verification_context','masked_cp','network_bssid'):
                            value=client._bloks_extract_context_value(screen,VERIFY,key)
                            if isinstance(value,str) and value:server[key]=value
                        flow.update(stage='code',server=server,message='WhatsApp’a gelen Instagram doğrulama kodunu girin.')
                else:
                    if method in ('totp','backup'):
                        screen=(client.bloks_two_step_verification_enter_totp_code(flow['context']) if method=='totp'
                                else client.bloks_two_step_verification_enter_backup_code(flow['context']))
                        if client.bloks_apply_login_response(screen):
                            _accept(flow,client)
                        else:
                            flow['context']=client.bloks_extract_two_step_verification_context(screen) or flow['context']
                    if flow['stage']=='done':
                        return public(flow)
                    flow.update(stage='code',message='Seçtiğiniz yöntemin doğrulama kodunu girin.')
        elif action=='code':
            if flow.get('profile_code_context'):
                result=client.bloks_ap_two_step_verification_submit_code(flow['profile_code_context'],code,domain='i.instagram.com')
            elif flow.get('method')=='whatsapp':
                result=client.bloks_async_action(VERIFY,{'client_input_params':{
                    'auth_secure_device_id':'','block_store_machine_id':'','code':code,'should_trust_device':1,
                    'family_device_id':client.phone_id,'device_id':client.android_device_id,
                    'cloud_trust_token':None,'machine_id':client.mid},'server_params':flow['server']},domain='i.instagram.com',login=True)
            else:
                result=client.bloks_two_step_verification_verify_code(flow['context'],code,challenge=flow['method'])
            code=''
            if not client.bloks_apply_login_response(result):
                raise LoginFailure('Instagram kodu kabul etmedi veya kodun süresi doldu. Kod otomatik tekrar gönderilmedi.')
            _accept(flow,client)
    except Exception as error:
        flow.update(stage='failed',message=_message(error),methods=[])
    finally:
        code=''
        try:_save(flow,client)
        finally:_close(client)
    return public(flow)
