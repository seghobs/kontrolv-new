"""Text/link Direct sends with one persisted identity and no transport replay."""
from contextlib import contextmanager
from contextvars import ContextVar
import hashlib
import json
import logging
import re
import time
import uuid

from requests.adapters import HTTPAdapter

from app_core.delivery import DeliveryResult, classify_dm
from app_core import instagram_api as api
from app_core.jobs import transaction

logger = logging.getLogger(__name__)
_scope = ContextVar('dm_send_scope', default=None)


@contextmanager
def send_scope(scope):
    token = _scope.set(str(scope))
    try:
        yield
    finally:
        _scope.reset(token)


def _digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=True).encode()).hexdigest()


def build_payload(target, text, token_record, context, *, to_user=False):
    if not str(target).isdigit() or int(target) <= 0 or not isinstance(text, str) or not text.strip():
        raise ValueError('Geçerli bir hedef ve mesaj gerekli.')
    android_id = str(token_record.get('android_id_yeni') or '')
    device_id = str(token_record.get('device_id') or '')
    if not android_id or not device_id:
        raise ValueError('Hesabın cihaz bilgileri eksik; mesaj gönderilmedi.')
    data = dict(action='send_item', is_x_transport_forward='false', send_silently='false',
                is_shh_mode='0', client_context=context, mutation_token=context,
                offline_threading_id=context, _uuid=device_id,
                device_id=android_id if android_id.startswith('android-') else 'android-' + android_id,
                btt_dual_send='false', is_ae_dual_send='false')
    data['recipient_users' if to_user else 'thread_ids'] = json.dumps(
        [[int(target)]] if to_user else [int(target)], separators=(',', ':'))
    urls = re.findall(r'https?://[^\s]+', text)
    if urls:
        data.update(link_text=text, link_urls=json.dumps(urls, ensure_ascii=False))
    else:
        data['text'] = text
    # Like the reference app's ordinary send path, do not invent a nav_chain
    # or attribution for a user action that never happened in a native screen.
    return 'direct_v2/threads/broadcast/' + ('link/' if urls else 'text/'), data


def _claim(account, request_id, fingerprint):
    key = 'dm-send-v1:' + _digest([account, request_id])
    with transaction() as conn:
        row = conn.execute('SELECT value FROM key_value WHERE key=?', (key,)).fetchone()
        if row:
            previous = json.loads(row['value'])
            if previous['fingerprint'] != fingerprint:
                return key, previous, DeliveryResult('rejected', 'Gönderim kimliği farklı bir mesaj için kullanılmış.', 'identity_conflict')
            if previous['state'] in ('accepted', 'rejected'):
                return key, previous, DeliveryResult(previous['state'], previous['message'], previous['code'], previous.get('item_id', ''))
            return key, previous, DeliveryResult('unknown', 'Önceki gönderimin sonucu belirsiz; tekrar gönderilmedi. Konuşmayı kontrol edin.', 'already_submitted')
        record = dict(fingerprint=fingerprint, context=str(uuid.uuid4().int & ((1 << 63) - 1)),
                      state='sending', updated=time.time())
        conn.execute('INSERT INTO key_value(key,value) VALUES (?,?)', (key, json.dumps(record)))
    return key, record, None


def _finish(key, record, result):
    record = dict(record, state=result.state, message=result.message, code=result.code,
                  item_id=result.item_id, updated=time.time())
    with transaction() as conn:
        conn.execute('UPDATE key_value SET value=? WHERE key=?', (json.dumps(record), key))


def _post_once(username, url, headers, payload):
    # Reuse the account's scoped cookie preparation, but give this write its own
    # adapters. Never alter shared read sessions or replay an ambiguous POST.
    client = api.PersistedSession()
    client.account_username = username
    client.mount('https://', HTTPAdapter(max_retries=0))
    client.mount('http://', HTTPAdapter(max_retries=0))
    try:
        return client.post(url, headers=headers, data=payload, timeout=(5, 15), allow_redirects=False)
    finally:
        client.close()


def send_text(target, text, token_record, *, to_user=False, request_id=None):
    account = str(token_record.get('username') or '')
    try:
        # Queued work can still hold the account's PREVIOUS login and device.
        # Resolve the entire verified record, not just a rotated bearer token.
        with transaction() as conn:
            saved = conn.execute('SELECT * FROM tokens WHERE username=?', (account,)).fetchone()
        if not saved or not saved['is_active'] or saved['deleted_at']:
            raise ValueError('Hesap aktif değil veya silinmiş; mesaj gönderilmedi.')
        token_record = dict(saved)
        # Validate before reserving or touching the transport.
        if not account or not token_record.get('token') or not token_record.get('user_agent'):
            raise ValueError('Hesabın oturum bilgileri eksik; mesaj gönderilmedi.')
        build_payload(target, text, token_record, '1', to_user=to_user)
        fingerprint = _digest([str(target), bool(to_user), text])
        request_id = request_id or (_digest([_scope.get(), fingerprint]) if _scope.get() else uuid.uuid4().hex)
        account_id = api.extract_user_id_from_token(api.current_token(account, token_record['token'])) or account
        key, record, previous = _claim(account_id, request_id, fingerprint)
        if previous is not None:
            return previous
    except ValueError as error:
        return DeliveryResult('rejected', str(error), 'invalid_send')
    except Exception:
        logger.exception('DM identity could not be persisted; no send attempted')
        return DeliveryResult('unknown', 'Gönderim kaydı oluşturulamadı; mesaj gönderilmedi.', 'storage_error')

    endpoint, payload = build_payload(target, text, token_record, record['context'], to_user=to_user)
    try:
        headers = api.build_auth_headers(token_record.get('token', ''), token_record.get('user_agent', ''),
            token_record.get('android_id_yeni', ''), token_record.get('device_id', ''), username=account)
        headers.update({'content-type': 'application/x-www-form-urlencoded',
                        'Accept-Encoding': 'gzip, deflate', 'X-FB-Friendly-Name': 'IgApi: ' + endpoint})
        response = _post_once(account, 'https://i.instagram.com/api/v1/' + endpoint, headers, payload)
        # A local state persistence error must not erase a valid server ACK.
        try:
            api._update_session_from_response(account, response)
        except Exception:
            logger.exception('DM session update failed after response')
        result = classify_dm(response, expected_context=record['context'],
                             expected_thread=None if to_user else str(int(target)), require_thread=to_user)
    except Exception as error:
        logger.warning('DM send outcome unknown; transport type=%s', type(error).__name__)
        result = DeliveryResult('unknown', 'Bağlantı kesildi; mesaj sonucu belirsiz. Yeniden göndermeden önce konuşmayı kontrol edin.', 'transport_error')
    try:
        _finish(key, record, result)
    except Exception:
        logger.exception('DM result could not be persisted; send will not be replayed')
    return result
