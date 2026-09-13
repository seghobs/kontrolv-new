import datetime
import json
import logging
import os
import random
import time
import uuid

import pytz
import requests

logger = logging.getLogger(__name__)

# Otomasyon yapılandırma dosyasının yolu
_AUTO_FILE = None


def _get_auto_file():
    global _AUTO_FILE
    if _AUTO_FILE is None:
        try:
            from app_core.config import DB_FILE
            _AUTO_FILE = os.path.join(os.path.dirname(DB_FILE), "automations.json")
        except Exception:
            _AUTO_FILE = os.path.join(os.path.dirname(__file__), "automations.json")
    return _AUTO_FILE


def load_automations():
    """Grup otomasyon yapılandırmalarını veritabanından okur."""
    try:
        from app_core.storage import load_automations as db_load_automations
        return db_load_automations()
    except Exception as e:
        logger.error("Otomasyon yukleme hatasi: %s", e)
        return {}


def save_automations(data):
    """Grup otomasyon yapılandırmalarını veritabanına kaydeder."""
    try:
        from app_core.storage import save_automations as db_save_automations
        return db_save_automations(data)
    except Exception as e:
        logger.error("Otomasyon kayit hatasi: %s", e)
        return False


IG_APP_ID = "567067343352427"


def _get_user_id_by_username(username, token_record):
    """Instagram kullanıcı adından user_id alır."""
    token = token_record.get("token", "")
    user_agent = token_record.get("user_agent", "")
    android_id = token_record.get("android_id_yeni", "")
    device_id = token_record.get("device_id", "")
    my_username = token_record.get("username", "")
    from app_core.instagram_api import build_auth_headers, _get_http_session, _update_session_from_response
    headers = build_auth_headers(token, user_agent, android_id, device_id, username=my_username)
    try:
        resp = _get_http_session(my_username).get(
            f"https://i.instagram.com/api/v1/users/{username}/usernameinfo/",
            headers=headers,
            timeout=10,
        )
        _update_session_from_response(my_username, resp)
        data = resp.json()
        user_id = data.get("user", {}).get("pk")
        return str(user_id) if user_id else None
    except Exception as e:
        logger.error("User ID alima hatasi (%s): %s", username, e)
        return None


def _send_dm_to_user(recipient_user_id, text, token_record):
    """Belirli bir kullanıcıya (thread yeriıne user ID ile) DM gönderir."""
    token = token_record.get("token", "")
    user_agent = token_record.get("user_agent", "")
    android_id = token_record.get("android_id_yeni", "")
    device_id = token_record.get("device_id", "")
    username = token_record.get("username", "")
    from app_core.instagram_api import build_auth_headers, _get_http_session, _update_session_from_response
    headers = build_auth_headers(token, user_agent, android_id, device_id, username=username)
    headers["content-type"] = "application/x-www-form-urlencoded"
    payload = {
        "text": text,
        "recipient_users": f"[[{recipient_user_id}]]",
        "action": "send_item",
        "client_context": str(uuid.uuid4()),
    }
    try:
        resp = _get_http_session(username).post(
            "https://i.instagram.com/api/v1/direct_v2/threads/broadcast/text/",
            headers=headers,
            data=payload,
            timeout=15,
        )
        _update_session_from_response(token_record.get("username", ""), resp)
        logger.info("Bildirim DM sonucu user=%s status=%s", recipient_user_id, resp.status_code)
        return resp.status_code == 200
    except Exception as e:
        logger.error("Bildirim DM hatasi: %s", e)
        return False


def _send_dm(thread_id, text, token_record):
    token = token_record.get("token", "")
    user_agent = token_record.get("user_agent", "")
    android_id = token_record.get("android_id_yeni", "")
    device_id = token_record.get("device_id", "")
    username = token_record.get("username", "")
    from app_core.instagram_api import build_auth_headers, _get_http_session, _update_session_from_response
    headers = build_auth_headers(token, user_agent, android_id, device_id, username=username)
    headers["content-type"] = "application/x-www-form-urlencoded"
    payload = {
        "text": text,
        "thread_ids": f"[{thread_id}]",
        "action": "send_item",
        "client_context": str(uuid.uuid4()),
    }
    try:
        resp = _get_http_session(username).post(
            "https://i.instagram.com/api/v1/direct_v2/threads/broadcast/text/",
            headers=headers,
            data=payload,
            timeout=15,
        )
        _update_session_from_response(token_record.get("username", ""), resp)
        logger.info("DM sonucu thread=%s status=%s", thread_id, resp.status_code)
        return resp.status_code == 200
    except Exception as e:
        logger.error("DM gonderme hatasi: %s", e)
        return False


def _fetch_comment_usernames(media_id, token_record):
    token = token_record.get("token", "")
    user_agent = token_record.get("user_agent", "")
    android_id = token_record.get("android_id_yeni", "")
    device_id = token_record.get("device_id", "")
    username = token_record.get("username", "")
    from app_core.instagram_api import build_auth_headers, _get_http_session, _update_session_from_response
    headers = build_auth_headers(token, user_agent, android_id, device_id, username=username)
    try:
        resp = _get_http_session(username).get(
            f"https://i.instagram.com/api/v1/media/{media_id}/stream_comments/",
            headers=headers,
            timeout=10,
        )
        _update_session_from_response(token_record.get("username", ""), resp)
        data = resp.json()
        users = set()
        for c in data.get("comments", []):
            u = c.get("user", {}).get("username")
            if u:
                users.add(u.lower())
        return users
    except Exception:
        return set()


from app_core.validators import normalize_username

def _normalize(u):
    return normalize_username(u)


def _fetch_comment_details(media_id, token_record):
    from app_core.instagram_api import get_post_details, fetch_comment_usernames
    details = get_post_details(media_id, token_record)
    if not details or not details.get('sender'):
        raise RuntimeError('Paylaşım ayrıntıları alınamadı.')
    if details.get('comments_disabled'):
        return set(), 0, False, []
    result = fetch_comment_usernames(media_id, token_record)
    if not result.get('ok'):
        raise RuntimeError('Yorumlar eksiksiz alınamadı.')
    comments = result.get('comments', [])
    return {_normalize(u) for u, _ in comments}, details.get('comment_count',len(comments)), True, comments


def run_automation_for_thread(thread_id, test_mode=False, target_date=None, before_send=None, on_result=None):
    def deliver(sender, *args):
        if before_send:
            before_send()
        if not sender(*args):
            raise RuntimeError("Mesajın gönderildiği doğrulanamadı. Yeniden göndermeden önce kontrol edin.")

    logger.info("Otomasyon baslatildi: %s (test_mode=%s)", thread_id, test_mode)

    try:
        from app_core.token_service import get_working_active_token
        from app_core.instagram_api import fetch_group_members, fetch_group_media
        from app_core.storage import is_global_exempted, load_exemptions
    except Exception as import_err:
        logger.error("Otomasyon import hatasi: %s", import_err)
        raise

    token_record = get_working_active_token()
    if not token_record:
        raise RuntimeError("Otomasyon için aktif token bulunamadı.")

    # 1. Grup üyeleri
    members_res = fetch_group_members(token_record, thread_id)
    if not members_res.get("ok"):
        raise RuntimeError("Otomasyon grup üyelerini alamadı.")
    member_usernames = {_normalize(u) for u in members_res.get("usernames", []) if u}
    logger.info("Otomasyon: %d grup uyesi bulundu.", len(member_usernames))

    # 2. DÜN'ün postlarını çek (GMT+3)
    tz = pytz.timezone("Europe/Istanbul")
    now = tz.localize(datetime.datetime.strptime(target_date, "%Y-%m-%d")) if target_date else datetime.datetime.now(tz)
    yesterday = now - datetime.timedelta(days=1)
    logger.info("Otomasyon: %s tarihli postlar aranıyor.", yesterday.strftime("%Y-%m-%d"))

    media_res = fetch_group_media(token_record, thread_id, yesterday)
    if not media_res.get("ok"):
        raise RuntimeError("Otomasyon paylaşımları alamadı.")

    posts = media_res.get("posts", [])
    if not posts:
        logger.info("Otomasyon: dun atilan paylasim yok, iptal.")
        return {"summary": "Seçili tarihte paylaşım bulunamadı.", "links": []}

    logger.info("Otomasyon: dunden %d paylasim bulundu, filtre uygulanıyor.", len(posts))

    # 3. Uygun postu bul: yorumlar açık VE en az 2 yorum var
    MIN_COMMENT_COUNT = 2
    hedef_post = None
    hedef_commenters = set()
    hedef_comments_list = []
    
    for post in posts:
        media_id = post.get("id")
        if not media_id:
            continue
            
        commenters, comment_count, comments_open, comments_list = _fetch_comment_details(media_id, token_record)
        time.sleep(1)  # rate limit

        logger.info(
            "Post %s: yorum_sayisi=%d, acik=%s",
            post.get("code"), comment_count, comments_open
        )

        if not comments_open:
            logger.info("Post %s: yorumlar kapali, atlaniyor.", post.get("code"))
            continue

        if comment_count < MIN_COMMENT_COUNT:
            logger.info(
                "Post %s: yorum sayisi yetersiz (%d < %d), atlaniyor.",
                post.get("code"), comment_count, MIN_COMMENT_COUNT
            )
            continue

        # İlk uygun postu seç
        hedef_post = post
        hedef_commenters = commenters
        hedef_comments_list = comments_list
        break

    if not hedef_post:
        logger.info(
            "Otomasyon: Uygun paylasim bulunamadi "
            "(yorumlar acik ve en az %d yorum olacak).", MIN_COMMENT_COUNT
        )
        return {"summary": "Kontrole uygun paylaşım bulunamadı.", "links": []}

    logger.info(
        "Otomasyon: Hedef post secildi: %s (yorum yapanlar: %d kisi)",
        hedef_post.get("code"), len(hedef_commenters)
    )

    # 3.5. Yorumları analiz et ve veritabanına kaydet
    try:
        from app_core.nlp_scorer import calculate_comment_spam_score
        from app_core.storage import save_comment_log
        from app_core.routes.main import has_emoji, clean_word_count
        
        post_code = hedef_post.get("code")
        for u, text in hedef_comments_list:
            u_norm = u.lower().strip()
            # Yalnızca grup üyelerinin yorumlarını kaydet
            if u_norm in member_usernames:
                is_valid = 1 if (has_emoji(text) and clean_word_count(text) >= 2) else 0
                spam_score = calculate_comment_spam_score(u_norm, text)
                save_comment_log(thread_id, u_norm, post_code, text, spam_score, is_valid)
        logger.info("Otomasyon yorum analiz kayıtları başarıyla tamamlandı.")
    except Exception as spam_log_err:
        logger.error("Otomasyon yorum analiz kayit hatasi: %s", spam_log_err)

    # Otomasyonun seçtiği postu veritabanına kaydet (grup seçildiğinde gelmesi için)
    try:
        from app_core.storage import set_selected_post_for_group
        today_str = datetime.datetime.now(pytz.timezone('Europe/Istanbul')).strftime('%Y-%m-%d')
        post_url = f"https://www.instagram.com/p/{hedef_post.get('code', '')}/"
        set_selected_post_for_group(thread_id, today_str, post_url)
        logger.info("Otomasyon secimi veritabanina kaydedildi: %s", post_url)
    except Exception as e:
        logger.error("Otomasyon secimini kaydetme hatasi: %s", e)

    # 4. Muafları hesapla
    exemptions_data = load_exemptions()
    all_exempted = set()

    # Post sahibi muaf
    sender = hedef_post.get("username")
    if sender:
        all_exempted.add(_normalize(sender))

    # Post'a özel muaflar
    post_link = f"https://www.instagram.com/p/{hedef_post.get('code', '')}/"
    for ex_user in exemptions_data.get(post_link, []):
        all_exempted.add(_normalize(ex_user))

    # Global muaflar
    for member in member_usernames:
        if is_global_exempted(member):
            all_exempted.add(member)

    # 5. Eksikler hesapla
    from app_core.automation import load_automations
    automations = load_automations()
    config = automations.get(str(thread_id), {})
    control_method = config.get("control_method", "all_members")
    
    if control_method == "post_senders":
        post_senders = {_normalize(p.get("username", "")) for p in posts if p.get("username")}
        base_users = post_senders
        logger.info("Otomasyon: 'Sadece Paylasim Yapanlar' yontemi kullaniliyor. %d kisi bekleniyor.", len(base_users))
    else:
        base_users = member_usernames
        logger.info("Otomasyon: 'Tum Uyeler' yontemi kullaniliyor. %d kisi bekleniyor.", len(base_users))

    eksikler = base_users - all_exempted - hedef_commenters

    report = {
        "thread_id": str(thread_id), "check_likes": False,
        "group": sorted(base_users), "all_commented": sorted(base_users - all_exempted - eksikler),
        "links": [{"post_link": f"https://www.instagram.com/p/{hedef_post.get('code', '')}/",
                   "eksikler": sorted(eksikler), "commenters": sorted(base_users - all_exempted - eksikler),
                   "sender": hedef_post.get("username", "")}],
        "user_missing_posts": {u: [f"https://www.instagram.com/p/{hedef_post.get('code', '')}/"] for u in eksikler},
        "user_comments": {}, "duplicate_comment_users": [], "invalid_comment_users": []
    }
    if on_result:
        on_result(report)
    if not eksikler:
        logger.info("Otomasyon: herkes yorumunu yapmis, eksik yok.")
        return report

    logger.info("Otomasyon: %d eksik bulundu, DM gönderiliyor.", len(eksikler))

    # 6. Mesajları hazırla ve gönder
    from app_core.storage import get_global_automation_settings
    global_settings = get_global_automation_settings()
    
    group_name = config.get("group_name", str(thread_id))
    post_url = f"https://www.instagram.com/p/{hedef_post.get('code', '')}/"
    toplam_uye_str = str(len(member_usernames))
    eksik_sayisi_str = str(len(eksikler))
    saat_str = datetime.datetime.now(pytz.timezone('Europe/Istanbul')).strftime('%H:%M')
    post_tarihi_str = hedef_post.get("date", "Bilinmiyor")
    
    # Eksik listesini @ işaretiyle alt alta oluştur
    eksik_listesi_str = "\n".join(f"@{u}" for u in sorted(eksikler)) if eksikler else "Eksik yok"

    def _format_template(text):
        if not text: return ""
        return text.replace("{grup_ismi}", group_name) \
                   .replace("[Grubun İsmi]", group_name) \
                   .replace("{post_url}", post_url) \
                   .replace("{toplam_uye}", toplam_uye_str) \
                   .replace("{eksik_sayisi}", eksik_sayisi_str) \
                   .replace("{saat}", saat_str) \
                   .replace("{post_tarihi}", post_tarihi_str) \
                   .replace("{eksik_listesi}", eksik_listesi_str)

    template_raw = global_settings.get(
        "template",
        "@everyone merhaba arkadaşlar eksik listesindeki tüm arkadaşlarımıza dm yazdık dönüş yapmayanları aramızdan çıkarmak durumunda kalacağız."
    )
    template_formatted = _format_template(template_raw)
    combined_msg = f"{eksik_listesi_str}\n\neksikler\n\n{template_formatted}" if eksikler else ""

    send_to_group = global_settings.get("send_to_group", True)
    if send_to_group and not test_mode:
        if combined_msg:
            deliver(_send_dm, thread_id, combined_msg, token_record)
            time.sleep(2)
            logger.info("Otomasyon: Eksik listesi gruba gonderildi.")
    else:
        logger.info("Otomasyon: Gruba mesaj atma kapali veya test modunda, atlanildi.")

    # 6.5 Eksiklere DM at (Anti-Ban Korumalı)
    send_dm_to_missing = global_settings.get("send_dm_to_missing", True)
    if send_dm_to_missing and not test_mode:
        dm_template_raw = global_settings.get("dm_template", "Merhaba, {grup_ismi} grubumuzda eksiğiniz bulunmaktadır. Lütfen dönüş yapalım..")
        dm_message = _format_template(dm_template_raw)
        
        MAX_INDIVIDUAL_DMS = 15  # Hesap sağlığı ve ban önleme için tek turda maksimum DM limiti
        eksikler_list = sorted(list(eksikler))
        total_missing = len(eksikler_list)
        dm_targets = eksikler_list[:MAX_INDIVIDUAL_DMS]
        
        logger.info("Otomasyon: Eksik kişilere DM gönderimi başlıyor (Toplam Eksik: %d, Gönderilecek: %d)...", total_missing, len(dm_targets))
        
        sent_count = 0
        for idx, u in enumerate(dm_targets, 1):
            uid = _get_user_id_by_username(u, token_record)
            if uid:
                deliver(_send_dm_to_user, uid, dm_message, token_record)
                sent_count += 1
                logger.info("Otomasyon: [%d/%d] @%s kullanıcısına DM gönderildi.", idx, len(dm_targets), u)
                
                # Son kullanıcı değilse hafif doğal bekleme (2.5 - 5.0 saniye)
                if idx < len(dm_targets):
                    delay = round(random.uniform(2.5, 5.0), 2)
                    logger.info("Otomasyon Hızlı/Güvenli: Sonraki DM için %s saniye bekleniyor...", delay)
                    time.sleep(delay)
            else:
                raise RuntimeError(f"@{u} için kullanıcı kimliği alınamadı.")
                
        if total_missing > MAX_INDIVIDUAL_DMS:
            logger.warning(
                "Otomasyon Anti-Ban: Güvenlik kotası aşıldı! Kalan %d kullanıcıya hesap sağlığını korumak için bireysel DM atılmadı (grup mesajı üzerinden uyarıldı).",
                total_missing - MAX_INDIVIDUAL_DMS
            )
    else:
        logger.info("Otomasyon: Bireysel DM atma kapalı veya test modunda, atlanıldı.")

    # 7. Admin / sahip hesabına bildirim gönder
    notify_username = config.get("notify_username", "seghob")
    if notify_username:
        admin_notify_template = global_settings.get("admin_notify_template", "✅ Otomasyon tamamlandı!\n\n📌 Grup: {grup_ismi}\n🔗 Post: {post_url}\n\n👥 Toplam üye: {toplam_uye}\n❌ Eksik: {eksik_sayisi}\n⏰ Saat: {saat}")
        notify_text = _format_template(admin_notify_template)
        user_id = _get_user_id_by_username(notify_username, token_record)
        if user_id:
            # Önce kopyalanabilir eksik listesini atalim
            if eksikler and combined_msg:
                deliver(_send_dm_to_user, user_id, combined_msg, token_record)
                logger.info("Eksik listesi ve grup sablonu @%s hesabina gonderildi.", notify_username)
                time.sleep(3)
                
            # Ardından ana bildirim raporunu atalim
            deliver(_send_dm_to_user, user_id, notify_text, token_record)
            logger.info("Bildirim raporu @%s hesabina gonderildi.", notify_username)
        else:
            raise RuntimeError(f"@{notify_username} için bildirim gönderilemedi.")

    # Otomasyon sonuçlarını veritabanında cache'le (grup id'si varsa)
    try:
        today_str = datetime.datetime.now(pytz.timezone('Europe/Istanbul')).strftime('%Y-%m-%d')
        tamamlayanlar = base_users - all_exempted - eksikler
        link_results = [{
            "post_link": f"https://www.instagram.com/p/{hedef_post.get('code', '')}/",
            "eksikler": sorted(list(eksikler)),
            "commenters": sorted(list(tamamlayanlar)),
            "sender": hedef_post.get("username", "")
        }]
        cache_data = {
            "links": link_results,
            "all_commented": sorted(list(tamamlayanlar)),
            "group": sorted(list(member_usernames)),
            "user_missing_posts": {u: [link_results[0]["post_link"]] for u in eksikler},
            "duplicate_comment_users": [],
            "check_likes": False
        }
        from app_core.storage import set_cached_run_result, add_audit_log
        set_cached_run_result(thread_id, today_str, cache_data)
        logger.info("Otomasyon sonuclari veritabanina cache'lendi.")
        
        now_str = datetime.datetime.now(pytz.timezone('Europe/Istanbul')).strftime('%H:%M:%S')
        sender_user = hedef_post.get("username", "")
        sender_prefix = f"@{sender_user} | " if sender_user else ""
        add_audit_log(
            entity_type="otomasyon",
            entity_id=link_results[0]["post_link"],
            action="kontrol_yapildi",
            details=f"{sender_prefix}Saat {now_str} - Otomasyon Yorum Kontrolü: {len(member_usernames)} üyeden {len(eksikler)} eksik tespit edildi."
        )
    except Exception as cache_err:
        logger.error("Otomasyon sonuclarini cache'leme hatasi: %s", cache_err)

    logger.info("Otomasyon tamamlandi: %s", thread_id)
    return report


