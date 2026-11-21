"""Short-lived, encrypted server-response evidence; never request credentials."""
import base64
import hashlib
import json
import re
import time

_DOMAIN = b'kontrol-login-evidence-v1\0'


def _redact(value, password):
    if isinstance(value, dict):
        return {key:('[redacted]' if str(key).lower() in ('password','encrypted_password','code','verification_code')
                     else _redact(child,password)) for key,child in value.items()}
    if isinstance(value, list):
        return [_redact(child,password) for child in value]
    if isinstance(value, str):
        if password:value=value.replace(password,'[redacted]')
        return re.sub(r'#PWD_[A-Za-z0-9_]+:\d+:\d+:[A-Za-z0-9+/=]+','[redacted]',value)
    return value


def capture(flow_id, response, password='', *, now=None):
    from Cryptodome.Cipher import AES
    from app_core.config import SECRET_KEY
    raw=json.dumps(_redact(response,password),ensure_ascii=False).encode('utf-8')
    if len(raw)>2_000_000:
        return {'omitted':'response_too_large'}
    cipher=AES.new(hashlib.sha256(_DOMAIN+SECRET_KEY.encode()).digest(),AES.MODE_GCM)
    cipher.update(flow_id.encode())
    ciphertext,tag=cipher.encrypt_and_digest(raw)
    encode=lambda data:base64.b64encode(data).decode('ascii')
    return dict(version=1,expires=(time.time() if now is None else now)+900,
                nonce=encode(cipher.nonce),tag=encode(tag),ciphertext=encode(ciphertext))


def open_evidence(flow_id, evidence, *, secret=None, now=None):
    from Cryptodome.Cipher import AES
    if evidence.get('version')!=1 or evidence.get('expires',0)<(time.time() if now is None else now):
        raise ValueError('Login evidence expired or unavailable')
    if secret is None:
        from app_core.config import SECRET_KEY
        secret=SECRET_KEY
    decode=lambda name:base64.b64decode(evidence[name],validate=True)
    cipher=AES.new(hashlib.sha256(_DOMAIN+secret.encode()).digest(),AES.MODE_GCM,nonce=decode('nonce'))
    cipher.update(flow_id.encode())
    return json.loads(cipher.decrypt_and_verify(decode('ciphertext'),decode('tag')))


def purge_expired(conn):
    for row in conn.execute("SELECT key,value FROM key_value WHERE key LIKE 'luma-flow:%'").fetchall():
        value=json.loads(row['value']);evidence=value.get('response_evidence')
        if evidence and evidence.get('expires',0)<time.time():
            value.pop('response_evidence',None)
            conn.execute('UPDATE key_value SET value=? WHERE key=?',(json.dumps(value),row['key']))
