import json
import logging
import threading

logger = logging.getLogger(__name__)

# Her token için session state sakla (memory)
_store = {}
_lock = threading.Lock()

# Takip edilecek response header'lari
# Bloks endpoint'i bu degerleri HTTP header'lari yerine
# body'nin icindeki nested JSON'da gonderiyor.
# Tum varyantlari buraya ekliyoruz:
TRACKED_HEADERS = {
    # Standart HTTP header varyantlari
    "ig-set-ig-u-rur": "rur",
    "ig-set-ig-u-ds-user-id": "ds_user_id",
    "ig-set-ig-u-shbid": "shbid",
    "ig-set-ig-u-shbts": "shbts",
    "ig-set-ig-u-ig-direct-region-hint": "direct_region_hint",
    # Bloks body'sinden gelen kisa varyantlar
    "ig-u-rur": "rur",
    "ig-u-ds-user-id": "ds_user_id",
    "ig-u-shbid": "shbid",
    "ig-u-shbts": "shbts",
    "ig-u-ig-direct-region-hint": "direct_region_hint",
    # www-claim (x-ig-set-www-claim veya ig-set-www-claim)
    "x-ig-set-www-claim": "www_claim",
    "ig-set-www-claim": "www_claim",
}


def get_session(username):
    """Kullanıcının session state'ini döndürür."""
    try:
        from app_core.storage import _connect
        conn = _connect()
        try:
            row = conn.execute(
                "SELECT value FROM key_value WHERE key=?",
                (f"session_state_{username}",),
            ).fetchone()
            if row:
                return json.loads(row["value"])
        finally:
            conn.close()
    except Exception as error:
        logger.warning("Session state okuma hatasi: %s", error)
    return {}


def update_session(username, response_headers, expected_token=None, cookies=None, expected_revision=None):
    """Apply all response state in one transaction; delayed responses cannot roll it back."""
    if not username or (not response_headers and not cookies):
        return
    import time
    from app_core.storage import _connect
    headers = {str(k).lower(): v for k, v in (response_headers or {}).items()}
    conn = _connect()
    try:
        conn.execute('BEGIN IMMEDIATE')
        token_row = conn.execute('SELECT token FROM tokens WHERE username=?', (username,)).fetchone()
        current = token_row['token'] if token_row else None
        if expected_token is not None and current is not None and expected_token != current:
            return
        key = 'session_state_' + username
        record = conn.execute('SELECT value FROM key_value WHERE key=?', (key,)).fetchone()
        state = json.loads(record['value']) if record else {}
        before = json.dumps(state, sort_keys=True)
        if type(expected_revision) is int and expected_revision != int(state.get('revision', 0)):
            return
        replacement = headers.get('ig-set-authorization')
        if replacement and current:
            if not _token_identity(replacement) or _token_identity(replacement) != _token_identity(current):
                return
            _rotate_in_transaction(conn, username, current, replacement)
        for name, field in TRACKED_HEADERS.items():
            value = headers.get(name)
            if value is not None and str(value).strip():
                state[field] = str(value).strip()
        if cookies:
            jar = {(c['name'], c['domain'], c['path']): c for c in state.get('http_cookies', [])}
            for cookie in cookies:
                jar[(cookie['name'], cookie['domain'], cookie['path'])] = cookie
            state['http_cookies'] = [c for c in jar.values() if c.get('expires') is None or c['expires'] > time.time()]
        if before == json.dumps(state, sort_keys=True) and (not replacement or replacement == current):
            return
        state['revision'] = int(state.get('revision', 0)) + 1
        conn.execute('INSERT OR REPLACE INTO key_value(key,value) VALUES (?,?)', (key, json.dumps(state)))
        conn.commit()
    finally:
        conn.close()


def response_cookies(response):
    """Serialize cookie attributes from requests or aiohttp without logging values."""
    from urllib.parse import urlsplit
    from email.utils import parsedate_to_datetime
    import time
    jar = getattr(response, 'cookies', None)
    if jar is None:
        return []
    from requests.cookies import RequestsCookieJar
    from http.cookies import BaseCookie
    if isinstance(jar, RequestsCookieJar):
        return [dict(name=c.name, value=c.value, domain=c.domain, path=c.path,
                     secure=c.secure, expires=c.expires, rest=dict(c._rest)) for c in jar]
    if not isinstance(jar, BaseCookie):
        return []
    url = urlsplit(str(response.url))
    default_path = url.path.rsplit('/', 1)[0] or '/'
    result = []
    for name, c in jar.items():
        expires = None
        try:
            if c['max-age']: expires = time.time() + int(c['max-age'])
            elif c['expires']: expires = parsedate_to_datetime(c['expires']).timestamp()
        except (ValueError, TypeError, OverflowError):
            pass
        result.append(dict(name=name, value=c.value, domain=c['domain'] or url.hostname,
                           path=c['path'] or default_path, secure=bool(c['secure']),
                           expires=expires, rest={'HttpOnly': None} if c['httponly'] else {}))
    return result


import re

def _search_headers_in_body(body):
    """
    Instagram Bloks JSON gövdelerinde çok katmanlı escaping ve hatalı parantez dizilimi (nested strings)
    olduğu için, json.loads ve recursive çözümler patlayabilir (örneğin X-IG-Reload-Proxy-Request-Info içinde).
    Bu yüzden en 'fail-proof' yöntem olan DOĞRUDAN REGEX DEĞER AYIKLAMA yöntemi kullanılır.
    """
    raw_text = json.dumps(body, ensure_ascii=False) if not isinstance(body, str) else body
    found_headers = {}

    # 1. Bearer Token (IG-Set-Authorization)
    # Token base64 chars icindedir, surpluslu tırnaklar hareket etmez.
    m_auth = re.search(r'ig-set-authorization[^A-Za-z]{1,40}(Bearer IGT:[a-zA-Z0-9:_\-=]+)', raw_text, re.IGNORECASE)
    if m_auth:
        found_headers["ig-set-authorization"] = m_auth.group(1)

    # 2. RUR - Degeri kisa bir bölge kodu (LDC, RVA, vb.) - tırnak/backslash kalabalığı arasından çıkar
    m_rur = re.search(r'ig-set-ig-u-rur[^A-Za-z]{1,40}([A-Z]{2,6})', raw_text, re.IGNORECASE)
    if m_rur:
        found_headers["ig-set-ig-u-rur"] = m_rur.group(1)

    # 3. DS_USER_ID - Sayısal değer, tırnak arasında gelemez zaten
    m_ds = re.search(r'ig-set-ig-u-ds-user-id[^\d]{1,30}(\d+)', raw_text, re.IGNORECASE)
    if m_ds:
        found_headers["ig-set-ig-u-ds-user-id"] = m_ds.group(1)

    # 4. WWW-CLAIM - "hmac." ile başlar, her zaman
    m_claim = re.search(r'x-ig-set-www-claim[^h]{1,30}(hmac\.[A-Za-z0-9_\-\.]+)', raw_text, re.IGNORECASE)
    if m_claim:
        found_headers["x-ig-set-www-claim"] = m_claim.group(1)

    return [found_headers] if found_headers else []


def update_session_from_body(username, response_body, expected_token=None):
    """
    Response body icerisindeki gizli headers JSON stringlerini tarar.
    Bloks endpointlerinde gercek session degerleri body icindedir.
    """
    if not username or not response_body or not isinstance(response_body, dict):
        logger.debug("update_session_from_body: Gecersiz input")
        return

    found_headers_list = _search_headers_in_body(response_body)
    if not found_headers_list:
        logger.debug("update_session_from_body: HICBİR HEADER BULUNAMADI")
        return

    # Birden fazla bulunduysa hepsini sirali isle (ilk login_response > diger)
    for header_dict in found_headers_list:
        update_session(username, header_dict, expected_token=expected_token)

    logger.debug("Body'den session header'lari islendi: @%s (%d blok)", username, len(found_headers_list))


    logger.debug("Body'den session header'lari islendi: @%s (%d blok)", username, len(found_headers_list))




def get_auth_headers(username, token, user_agent, android_id, device_id):
    """Guncel session state ile auth header'lari olusturur.
    Orijinal Instagram mobil uygulamasinin gonderdigi tum kritik header'lar dahildir.
    """
    from app_core.config import IG_APP_ID

    state = get_session(username)

    # Kullanici ID'sini token veya session'dan cek
    ds_user_id = state.get("ds_user_id")
    if not ds_user_id or ds_user_id == "0":
        try:
            from app_core.instagram_api import extract_user_id_from_token
            ds_user_id = extract_user_id_from_token(token) or "0"
        except Exception:
            ds_user_id = "0"


    headers = {
        "authorization": token,
        "user-agent": user_agent,
        "x-ig-app-id": IG_APP_ID,
        "x-ig-android-id": f"android-{android_id}",
        "x-ig-device-id": device_id,
        # Orijinal mobil uygulamayla eslesen kritik header'lar:
        "ig-intended-user-id": ds_user_id,
        "x-ig-capabilities": "3brTv10=",
        "x-ig-connection-type": "WIFI",
        "x-fb-connection-type": "WIFI",
        "x-ig-app-locale": "tr_TR",
        "x-ig-device-locale": "tr_TR",
        "x-ig-mapped-locale": "tr_TR",
        "x-ig-device-languages": '{"system_languages":"tr-TR"}',
        "x-ig-timezone-offset": "10800",   # UTC+3 (Turkiye)
        "x-ig-is-foldable": "false",
        "x-ig-transfer-encoding": "chunked",
        "accept-language": "tr-TR, en-US",
        # Bloks version + prism UI flags
        "x-bloks-version-id": "dd9727564fa874f2ebf47e9eca5d00c86c1bf1eef22fcba4fd1e05edab8ec6e0",
        "x-bloks-is-layout-rtl": "false",
        "x-bloks-prism-button-version": "INDIGO_PRIMARY_BORDERED_SECONDARY",
        "x-bloks-prism-colors-enabled": "true",
        "x-bloks-prism-extended-palette-gray": "false",
        "x-bloks-prism-extended-palette-indigo": "true",
        "x-bloks-prism-extended-palette-polish-enabled": "false",
        "x-bloks-prism-extended-palette-red": "true",
        "x-bloks-prism-extended-palette-rest-of-colors": "true",
        "x-bloks-prism-font-enabled": "true",
        "x-bloks-prism-indigo-link-version": "1",
    }

    # Session'dan gelen dinamik degerler
    if state.get("rur"):
        headers["ig-u-rur"] = state["rur"]
    if state.get("ds_user_id"):
        headers["ig-u-ds-user-id"] = state["ds_user_id"]
    if state.get("shbid"):
        headers["ig-u-shbid"] = state["shbid"]
    if state.get("shbts"):
        headers["ig-u-shbts"] = state["shbts"]
    if state.get("direct_region_hint"):
        headers["ig-set-ig-u-ig-direct-region-hint"] = state["direct_region_hint"]
    if state.get("www_claim"):
        headers["x-ig-www-claim"] = state["www_claim"]

    return headers


def load_from_db(username):
    """DB'den session state'i yükler."""
    try:
        from app_core.storage import _connect
        conn = _connect()
        try:
            row = conn.execute(
                "SELECT value FROM key_value WHERE key=?",
                (f"session_state_{username}",),
            ).fetchone()
            if row:
                with _lock:
                    _store[username] = json.loads(row["value"])
                logger.debug("Session state DB'den yüklendi: @%s", username)
        finally:
            conn.close()
    except Exception as error:
        logger.warning("Session state yükleme hatasi: %s", error)


def _save_to_db(username):
    """Session state'i DB'ye kaydeder."""
    try:
        from app_core.storage import _connect
        state = get_session(username)
        if not state:
            return
        conn = _connect()
        try:
            conn.execute(
                "INSERT OR REPLACE INTO key_value (key, value) VALUES (?, ?)",
                (f"session_state_{username}", json.dumps(state, ensure_ascii=False)),
            )
            conn.commit()
        finally:
            conn.close()
    except Exception as error:
        logger.warning("Session state kaydetme hatasi: %s", error)


def clear_session(username):
    """Kullanıcının session state'ini DB ve memory'den temizler."""
    if not username:
        return
    try:
        from app_core.storage import _connect
        conn = _connect()
        try:
            conn.execute(
                "DELETE FROM key_value WHERE key=?",
                (f"session_state_{username}",),
            )
            conn.commit()
            logger.info("Session state DB'den temizlendi: @%s", username)
        finally:
            conn.close()
    except Exception as error:
        logger.warning("Session state silme hatasi: %s", error)

    with _lock:
        if username in _store:
            del _store[username]



def get_current_token(username, fallback):
    """Resolve a previously rotated token without replacing new login input."""
    if not username or not isinstance(fallback, str):
        return fallback
    import hashlib
    from app_core.storage import _connect
    conn = _connect()
    try:
        row = conn.execute("SELECT value FROM key_value WHERE key=?",
                           ('token_rotations_' + username,)).fetchone()
        if row and hashlib.sha256(fallback.encode()).hexdigest() in json.loads(row['value']):
            token = conn.execute("SELECT token FROM tokens WHERE username=?", (username,)).fetchone()
            if token:
                return token['token']
        return fallback
    finally:
        conn.close()


def _token_identity(value):
    import base64
    try:
        payload = value.split(':', 2)[2]
        data = json.loads(base64.b64decode(payload + '=' * (-len(payload) % 4)))
        return str(data.get('ds_user_id') or data.get('user_id') or '') if data.get('sessionid') else ''
    except Exception:
        return ''


def _rotate_in_transaction(conn, username, old, replacement):
    import hashlib
    if old == replacement:
        return
    key = 'token_rotations_' + username
    record = conn.execute('SELECT value FROM key_value WHERE key=?', (key,)).fetchone()
    previous = json.loads(record['value']) if record else []
    previous = (previous + [hashlib.sha256(old.encode()).hexdigest()])[-100:]
    conn.execute('UPDATE tokens SET token=? WHERE username=? AND token=?', (replacement, username, old))
    conn.execute('INSERT OR REPLACE INTO key_value(key,value) VALUES (?,?)', (key,json.dumps(previous)))


def rotate_token(username, replacement, expected_token=None):
    if not isinstance(replacement, str) or not replacement.startswith('Bearer IGT:') or not _token_identity(replacement):
        return
    update_session(username, {'ig-set-authorization': replacement}, expected_token)
