"""Android profile presets, without shared account or device identifiers.

Model/device pairs: https://storage.googleapis.com/play_public/supported_devices.csv
Android 14 and display settings are profile configuration, not device attestation.
The SDK supplies the coherent application version, version code and Bloks hash.
"""
import secrets
import uuid


# key, display name, Android model, device codename, CPU family, display resolution
_MODELS = (
    ('pixel8','Google Pixel 8 Pro · Luma varsayılanı','Pixel 8 Pro','husky','husky','1344x2992'),
    ('pixel6','Google Pixel 6','Pixel 6','oriole','oriole','1080x2400'),
    ('pixel6pro','Google Pixel 6 Pro','Pixel 6 Pro','raven','raven','1440x3120'),
    ('pixel6a','Google Pixel 6a','Pixel 6a','bluejay','bluejay','1080x2400'),
    ('pixel7','Google Pixel 7','Pixel 7','panther','panther','1080x2400'),
    ('pixel7pro','Google Pixel 7 Pro','Pixel 7 Pro','cheetah','cheetah','1440x3120'),
    ('pixel7a','Google Pixel 7a','Pixel 7a','lynx','lynx','1080x2400'),
    ('pixel8standard','Google Pixel 8','Pixel 8','shiba','shiba','1080x2400'),
    ('pixel8a','Google Pixel 8a','Pixel 8a','akita','akita','1080x2400'),
    ('pixel9','Google Pixel 9','Pixel 9','tokay','tokay','1080x2424'),
    ('pixel9pro','Google Pixel 9 Pro','Pixel 9 Pro','caiman','caiman','1280x2856'),
    ('s21','Samsung Galaxy S21','SM-G991B','o1s','exynos2100','1080x2400'),
    ('s21plus','Samsung Galaxy S21+','SM-G996B','t2s','exynos2100','1080x2400'),
    ('s21ultra','Samsung Galaxy S21 Ultra','SM-G998B','p3s','exynos2100','1440x3200'),
    ('s22','Samsung Galaxy S22','SM-S901B','r0s','exynos2200','1080x2340'),
    ('s22plus','Samsung Galaxy S22+','SM-S906B','g0s','exynos2200','1080x2340'),
    ('s22ultra','Samsung Galaxy S22 Ultra','SM-S908B','b0s','exynos2200','1440x3088'),
    ('s23','Samsung Galaxy S23','SM-S911B','dm1q','qcom','1080x2340'),
    ('s23plus','Samsung Galaxy S23+','SM-S916B','dm2q','qcom','1080x2340'),
    ('s23ultra','Samsung Galaxy S23 Ultra','SM-S918B','dm3q','qcom','1440x3088'),
    ('s24','Samsung Galaxy S24','SM-S921B','e1s','exynos2400','1080x2340'),
    ('s24plus','Samsung Galaxy S24+','SM-S926B','e2s','exynos2400','1440x3120'),
    ('s24ultra','Samsung Galaxy S24 Ultra','SM-S928B','e3q','qcom','1440x3120'),
    ('a54','Samsung Galaxy A54','SM-A546B','a54x','exynos1380','1080x2340'),
    ('a55','Samsung Galaxy A55','SM-A556B','a55x','exynos1480','1080x2340'),
)

DEVICE_PROFILES = {key: dict(label=label, device_settings=dict(
    android_version=34, android_release='14', dpi='480dpi', resolution=resolution,
    manufacturer='Google/google' if key.startswith('pixel') else 'samsung',
    model=model, device=device, cpu=cpu))
    for key,label,model,device,cpu,resolution in _MODELS}

IDENTITY_FIELDS = ('uuid','phone_id','advertising_id','client_session_id','request_id','tray_session_id')


def new_identity():
    result = {key:str(uuid.uuid4()) for key in IDENTITY_FIELDS}
    result['android_device_id'] = 'android-' + secrets.token_hex(8)
    return result


def identity_values(ids):
    return {str(value).removeprefix('android-') for value in ids.values() if value}


def ensure_unused_identity(conn, ids):
    """Serialize collision checks with the transaction reserving a new profile."""
    import json
    from app_core.luma_login import LoginFailure
    values=identity_values(ids)
    if len(values)!=len(ids):
        raise LoginFailure('Cihaz kimlikleri birbirinden farklı olmalı.')
    for row in conn.execute("SELECT value FROM key_value WHERE key LIKE 'luma-account:%'"):
        settings=json.loads(row['value']).get('settings') or {}
        if values & identity_values(settings.get('uuids') or {}):
            raise LoginFailure('Bu cihaz kimlikleri kayıtlı bir profile ait; farklı kimliklerle yeni profil oluşturun.')
    for row in conn.execute('SELECT device_id,android_id_yeni FROM tokens'):
        if values & identity_values(dict(row)):
            raise LoginFailure('Bu cihaz kimlikleri token havuzunda zaten kullanılıyor.')
