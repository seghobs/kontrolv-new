"""Administrator-only, CSRF-protected continuation of server-issued login steps."""
import secrets
from urllib.parse import urlsplit
from flask import Blueprint, jsonify, request, session
from flask_wtf.csrf import validate_csrf
from wtforms.validators import ValidationError
from app_core import luma_login as engine

login_bp = Blueprint('luma_login', __name__, url_prefix='/api/luma-login')


def owner():
    if not session.get('luma_login_owner'):
        session['luma_login_owner'] = secrets.token_hex(24)
    return session['luma_login_owner']


@login_bp.before_request
def authorize():
    if not session.get('admin_logged_in'):
        return jsonify(success=False,message='Yönetici girişi gerekli.'),401
    if request.method=='POST':
        origin=request.headers.get('Origin')
        if origin and urlsplit(origin).netloc!=request.host:
            return jsonify(success=False,message='Geçersiz istek kaynağı.'),403
        try:validate_csrf(request.headers.get('X-CSRFToken') or request.form.get('csrf_token'))
        except ValidationError:
            return jsonify(success=False,message='Oturum doğrulaması yenilenmeli; sayfayı yenileyin.'),400


@login_bp.errorhandler(engine.LoginFailure)
def failed(error):
    return jsonify(success=False,message=str(error)),error.status


@login_bp.route('/runtime')
def runtime():
    try:
        client=engine.make_client()
        try:
            return jsonify(success=True,revision='62f962e3dba41d43237061635d2946ac93cc5be0',
                           app_version=client.device_settings.get('app_version'))
        finally:engine._close(client)
    except Exception:
        return jsonify(success=False,message='Luma giriş bağımlılıkları hazır değil.'),503


@login_bp.route('/start',methods=['POST'])
def start():
    data=request.get_json(silent=True)
    if not isinstance(data,dict):raise engine.LoginFailure('Geçerli giriş bilgisi gerekli.')
    if any(type(data.get(k,False)) is not bool for k in ('fresh','new_device')):
        raise engine.LoginFailure('Giriş seçenekleri geçersiz.')
    try:
        flow=engine.start(data.get('username',''),data.get('password',''),owner=owner(),
            fresh=data.get('fresh',False),profile_name=data.get('profile','saved'),
            custom_profile=data.get('custom_profile'),new_device=data.get('new_device',False))
    except engine.LoginFailure:raise
    except (ValueError,TypeError):raise engine.LoginFailure('Cihaz profili veya giriş bilgisi geçersiz.')
    except Exception:return jsonify(success=False,message='Giriş başlatılamadı; bağımlılıkları ve cihaz profilini kontrol edin.'),503
    return jsonify(success=True,flow=flow)


@login_bp.route('/probe-session',methods=['POST'])
def probe_session():
    """Admin-only, nonpublishing account read for cross-environment diagnosis."""
    import re
    if request.content_length and request.content_length>128000:
        raise engine.LoginFailure('Oturum verisi çok büyük.',413)
    data=request.get_json(silent=True) or {}
    name=data.get('username','')
    settings=data.get('settings')
    if not isinstance(name,str) or not re.fullmatch(r'[a-zA-Z0-9._]{1,30}',name) or not isinstance(settings,dict):
        raise engine.LoginFailure('Geçerli hesap ve oturum bilgisi gerekli.')
    allowed={'uuids','authorization_data','cookies','device_settings','user_agent','locale',
        'country','country_code','timezone_offset','ig_u_rur','ig_www_claim','mid','usdid'}
    if set(settings)-allowed:
        raise engine.LoginFailure('Oturumda desteklenmeyen alan var.')
    auth=settings.get('authorization_data') or {}
    if not isinstance(auth,dict) or not str(auth.get('ds_user_id','')).isdigit() or not auth.get('sessionid'):
        raise engine.LoginFailure('Doğrulanacak kayıtlı oturum gerekli.')
    client=engine.make_client()
    try:
        client.set_settings(settings);client.username=name
        client.set_tls_verify(True)
        client.set_retry_config(request_timeout=0, public_request_retries_count=1, session_retry_total=0)
        user=client.account_info()
        matches=str(user.pk)==str(auth['ds_user_id']) and user.username.casefold()==name.casefold()
        return jsonify(success=True,verified=matches,published=False)
    except Exception as error:
        return jsonify(success=True,verified=False,published=False,error_type=type(error).__name__)
    finally:engine._close(client)


@login_bp.route('/active')
def active():
    username=request.args.get('username','').strip().lstrip('@').lower()
    with engine.transaction() as conn:
        profile=engine._get(conn,'luma-account:'+username) or {}
        flow=engine._flow(conn,profile.get('flow_id',''),owner())
        return jsonify(success=True,flow=engine.public(flow))


@login_bp.route('/<flow_id>')
def status(flow_id):
    return jsonify(success=True,flow=engine.status(flow_id,owner()))


@login_bp.route('/<flow_id>/step',methods=['POST'])
def step(flow_id):
    data=request.get_json(silent=True) or {}
    try:flow=engine.advance(flow_id,owner(),data.get('action'),data.get('code',''),data.get('method',''))
    except engine.LoginFailure:raise
    except Exception:return jsonify(success=False,message='Giriş adımı tamamlanamadı; mevcut durum korundu.'),503
    return jsonify(success=True,flow=flow)
