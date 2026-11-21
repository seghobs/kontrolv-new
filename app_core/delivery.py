"""Classify Direct responses without treating transport success as delivery."""
from dataclasses import dataclass


@dataclass(frozen=True)
class DeliveryResult:
    state: str
    message: str
    code: str
    item_id: str = ''

    def __bool__(self):
        return self.state == 'accepted'


def classify_dm(response, *, expected_context=None, expected_thread=None, require_thread=False):
    try:
        data = response.json()
    except (ValueError, TypeError):
        data = None
    if not isinstance(data, dict):
        return DeliveryResult('unknown', 'Mesaj sonucu okunamadı. Yeniden göndermeden önce konuşmayı kontrol edin.', 'invalid_response')
    markers = {str(data.get(key) or '').lower() for key in ('message', 'error_type')}
    if markers & {'login_required', 'invalid_session', 'session_expired', 'invalid_token', 'user_has_logged_out'}:
        return DeliveryResult('rejected', 'DM isteğinde oturum reddedildi; hesap girişini kontrol edin.', 'login_required')
    if 'challenge_required' in markers:
        return DeliveryResult('rejected', 'Instagram ek doğrulama istiyor. Hesabı Instagram üzerinden doğrulayın.', 'challenge_required')
    if response.status_code == 429 or markers & {'feedback_required', 'please_wait_a_few_minutes', 'sentry_block'} or any('please wait a few minutes' in marker for marker in markers):
        return DeliveryResult('rejected', 'Instagram mesaj gönderimini kısıtladı. Gönderimler durduruldu.', 'restricted')
    if data.get('status') == 'fail' or data.get('errors') or data.get('error') or response.status_code >= 400:
        return DeliveryResult('rejected', 'Instagram mesaj isteğini kabul etmedi. Gönderimler durduruldu.', 'rejected')
    payload = data.get('payload')
    item_id = payload.get('item_id') if isinstance(payload, dict) else None
    if response.status_code == 200 and data.get('status') == 'ok' and isinstance(item_id, (str, int)) and not isinstance(item_id, bool) and str(item_id):
        if expected_context is not None:
            context = payload.get('client_context')
            thread = payload.get('thread_id')
            valid_thread = isinstance(thread, (str, int)) and not isinstance(thread, bool) and str(thread).isdigit()
            if (not str(item_id).isdigit()
                    or (context is not None and str(context) != str(expected_context))
                    or (require_thread and not valid_thread)
                    or (thread is not None and (not valid_thread or
                        (expected_thread is not None and str(thread) != str(expected_thread))))):
                return DeliveryResult('unknown', 'Mesaj yanıtının sohbet veya gönderim kimliği eşleşmedi; tekrar göndermeden önce konuşmayı kontrol edin.', 'ack_mismatch')
        return DeliveryResult('accepted', 'Mesaj Instagram tarafından kabul edildi.', 'accepted', str(item_id))
    return DeliveryResult('unknown', 'Mesajın gönderildiği doğrulanamadı. Yeniden göndermeden önce konuşmayı kontrol edin.', 'unconfirmed')
