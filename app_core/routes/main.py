import html
import logging
import random
import time
import datetime
import pytz
import json
from flask import Blueprint, jsonify, render_template, request, session, redirect, url_for
from donustur import donustur
from log_in import giris_yap, LoginError

from app_core.instagram_api import get_post_sender, get_media_taken_at, get_post_details, comments_cover_total
from app_core.storage import load_exemptions, save_exemptions, load_global_exemptions, add_global_exemption, add_audit_log, _connect
from app_core.validators import normalize_username
from app_core.token_service import (
    fetch_comments_with_failover,
    fetch_likers_with_failover,
    get_working_active_token,
    upsert_login_token,
    fetch_group_threads_with_failover,
    fetch_group_members_with_failover,
    fetch_group_media_with_failover
)

logger = logging.getLogger(__name__)

main_bp = Blueprint("main", __name__)


class ControlUnavailable(ValueError):
    pass


def require_complete_result(result):
    if isinstance(result, dict) and (not result.get("ok") or result.get("rate_limited")):
        raise ControlUnavailable("Kontrol edilemedi: Instagram verileri alınamadı. Lütfen tekrar deneyin.")


def require_complete_likers(details, usernames, missing):
    # Positive matches are conclusive; absence requires a complete liker list.
    if missing and (not details.get('like_count_verified') or
                    len(usernames) < details.get('like_count', 0)):
        raise ControlUnavailable("Beğeni listesi eksik alındı; üyeler eksik olarak işaretlenmedi. Lütfen tekrar deneyin.")


def incomplete_comment_post(link, details, sender, comments):
    return dict(details, post_link=link, sender=sender, eksikler=[], commenters=[],
                comments_list=comments,
                commenters_normalized={normalize_username(u) for u, _ in comments},
                error='Doğrulanamadı: Bazı yorumların kullanıcı bilgisi veya yorum listesi alınamadı. Bu paylaşım için kesin eksik listesi oluşturulmadı.')


def get_db_value(key):
    from app_core.jobs import get_job, public_status
    for prefix in ("task_status_", "manual_run_inputs_", "manual_run_result_"):
        if key.startswith(prefix):
            job = get_job(key[len(prefix):])
            if job:
                value = public_status(job) if prefix == "task_status_" else job["payload"] if prefix == "manual_run_inputs_" else job["result"]
                return json.dumps(value, ensure_ascii=False) if value is not None else None
            break
    conn = _connect()
    try:
        row = conn.execute("SELECT value FROM key_value WHERE key=?", (key,)).fetchone()
        return row["value"] if row else None
    except Exception as e:
        logger.error(f"get_db_value error for {key}: {e}")
        return None
    finally:
        conn.close()

def set_db_value(key, value):
    conn = _connect()
    try:
        conn.execute("INSERT OR REPLACE INTO key_value (key, value) VALUES (?, ?)", (key, str(value)))
        conn.commit()
        return True
    except Exception as e:
        logger.error(f"set_db_value error for {key}: {e}")
        return False
    finally:
        conn.close()

def clean_surrogates(text):
    if not isinstance(text, str):
        return text
    try:
        # Pair surrogate characters correctly
        return text.encode('utf-16', 'surrogatepass').decode('utf-16')
    except Exception:
        try:
            return text.encode('utf-8', 'ignore').decode('utf-8')
        except Exception:
            return "".join(c for c in text if not (0xD800 <= ord(c) <= 0xDFFF))

def clean_data_recursive(data):
    if isinstance(data, dict):
        return {k: clean_data_recursive(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [clean_data_recursive(x) for x in data]
    elif isinstance(data, str):
        return clean_surrogates(data)
    else:
        return data



@main_bp.route("/api/get_groups", methods=["GET"])
def get_groups():
    result = fetch_group_threads_with_failover()
    return jsonify(result)


@main_bp.route("/api/get_group_members/<thread_id>", methods=["GET"])
def get_group_members(thread_id):
    result = fetch_group_members_with_failover(thread_id)
    if result.get('ok'):
        from app_core.followup import track_members
        result['changes'] = track_members(thread_id, result.get('members', []))
    return jsonify(result)


@main_bp.route("/api/get_group_posts/<thread_id>", methods=["GET"])
def get_group_posts(thread_id):
    date_filter = request.args.get("date", "today")
    tz = pytz.timezone('Europe/Istanbul')
    now = datetime.datetime.now(tz)
    
    if date_filter == "yesterday":
        target_date = now - datetime.timedelta(days=1)
    elif date_filter == "today":
        target_date = now
    else:
        try:
            target_date = datetime.datetime.strptime(date_filter, "%Y-%m-%d")
            target_date = tz.localize(target_date)
        except Exception:
            target_date = now
    
    result = fetch_group_media_with_failover(thread_id, target_date)
    if result.get('ok'):
        from app_core.followup import write, read, link_key
        dates=read('shared-dates:'+thread_id,{})
        dates.update({link_key(p['url']):p['shared_at'] for p in result.get('posts',[]) if p.get('url') and p.get('shared_at')})
        write('shared-dates:'+thread_id,dates)
    return jsonify(result)


def get_exempted_users(post_link, exemptions=None):
    if exemptions is None:
        exemptions = load_exemptions()
    post_link_decoded = html.unescape(post_link)
    raw_usernames = exemptions.get(post_link_decoded, [])
    return {normalize_username(u) for u in raw_usernames}

def get_global_exempted_users():
    exemptions = load_global_exemptions()
    return {normalize_username(e["username"]) for e in exemptions}


def has_emoji(text):
    if not text:
        return False
    for char in text:
        cp = ord(char)
        if (0x1F600 <= cp <= 0x1F64F) or \
           (0x1F300 <= cp <= 0x1F5FF) or \
           (0x1F680 <= cp <= 0x1F6FF) or \
           (0x1F1E0 <= cp <= 0x1F1FF) or \
           (0x2600 <= cp <= 0x27BF) or \
           (0x1F900 <= cp <= 0x1F9FF) or \
           (0x1FA70 <= cp <= 0x1FAFF):
            return True
    return False


def clean_word_count(text):
    if not text:
        return 0
    cleaned_chars = []
    for char in text:
        cp = ord(char)
        if not ((0x1F600 <= cp <= 0x1F64F) or \
                (0x1F300 <= cp <= 0x1F5FF) or \
                (0x1F680 <= cp <= 0x1F6FF) or \
                (0x1F1E0 <= cp <= 0x1F1FF) or \
                (0x2600 <= cp <= 0x27BF) or \
                (0x1F900 <= cp <= 0x1F9FF) or \
                (0x1FA70 <= cp <= 0x1FAFF)):
            cleaned_chars.append(char)
    cleaned_text = "".join(cleaned_chars)
    words = [w for w in cleaned_text.split() if len(w) > 0]
    return len(words)


def run_manual_control(link, grup_uye, thread_id, post_senders_raw, check_likes, only_missing=False, prev_result=None, progress_callback=None, unknown_only=False, checkpoints=None, save_checkpoint=None, shared_dates=None):
    active_working_token = get_working_active_token()
    if not active_working_token:
        raise ValueError("Tum hesaplar cikis yapmis gorunuyor. Lutfen admin panelden gecerli bir token girin.")

    grup_uye_kullanicilar = {normalize_username(u) for u in grup_uye.split() if u.strip()}
    from app_core.followup import rules_for, link_key
    rules = rules_for(thread_id)
    if shared_dates is None:
        from app_core.followup import read
        shared_dates=read('shared-dates:'+str(thread_id),{})
    links_raw = list(dict.fromkeys(l.strip().rstrip('/') for l in link.split("\n") if l.strip()))
    if not links_raw or any(donustur(url) is None for url in links_raw):
        raise ControlUnavailable("Geçersiz paylaşım bağlantısı var. Bağlantıları kontrol edin.")
    
    if progress_callback:
        progress_callback(0, max(1, len(links_raw)), "Denetim motoru (aiohttp) başlatıldı, gönderiler sorgulanıyor...")

    all_commented = set()
    user_missing_posts = {}  # {username: [post_link1, post_link2, ...]}
    user_comments_map = {}  # {username: [comment_text1, comment_text2, ...]}
    link_results = []
    
    working_token = active_working_token
    global_exempted = get_global_exempted_users()
    exemptions = load_exemptions()
    exemptions_by_link = {url: get_exempted_users(url, exemptions) for url in links_raw}

    post_senders = {}
    for ps in post_senders_raw:
        if "|" in ps:
            url, sender = ps.rsplit("|", 1)
            url = url.strip().rstrip('/')  # Remove trailing slash for matching
            post_senders[url] = normalize_username(sender)

    # ⚡ AIOHTTP İLE ASENKRON PARALEL TARAMA
    async def _async_run_all():
        import aiohttp
        import asyncio
        semaphore = asyncio.Semaphore(4) # 4 Gönderiyi aynı anda paralel tara
        tracker = {"done": 0, "total": len(links_raw)}
        
        async def _fetch_single(link_single):
            if link_key(link_single) in {link_key(u) for u in rules['excluded']}:
                return dict(post_link=link_single,eksikler=[],commenters=[],comments_list=[],skipped_reason='Paylaşım kapsam dışında')
            if checkpoints and link_single in checkpoints:
                restored = dict(checkpoints[link_single])
                restored['commenters_normalized'] = set(restored.get('commenters_normalized', []))
                restored['source'] = 'checkpoint'
                return restored
            if (only_missing or unknown_only) and prev_result:
                prev_link_res = next((lr for lr in prev_result.get("links", []) if lr.get("post_link", "").strip().rstrip('/') == link_single), None)
                if prev_link_res and not prev_link_res.get("error") and (unknown_only or not prev_link_res.get("eksikler")):
                    tracker["done"] += 1
                    if progress_callback:
                        progress_callback(tracker["done"], tracker["total"], f"Gönderi {tracker['done']}/{tracker['total']} atlandı (Tamamlanmış)")
                    reused = dict(prev_link_res)
                    reused['source'] = 'previous'
                    reused['comments_list'] = [
                        (comment['username'], comment['text']) if isinstance(comment, dict) else tuple(comment)
                        for comment in prev_link_res.get('comments_list', [])
                    ]
                    reused['commenters_normalized'] = {
                        normalize_username(username) for username, _ in reused['comments_list']
                    } if not check_likes else set(prev_link_res.get('likers_list', []))
                    return reused

            async with semaphore:
                media_id = donustur(link_single)
                if media_id is None:
                    tracker["done"] += 1
                    if progress_callback:
                        progress_callback(tracker["done"], tracker["total"], f"Gönderi {tracker['done']}/{tracker['total']} tamamlandı")
                    return {
                        "post_link": link_single,
                        "eksikler": list(grup_uye_kullanicilar),
                        "commenters": [],
                        "error": "Gecersiz link",
                        "comments_list": []
                    }
                
                from app_core.instagram_api import get_post_details_async, fetch_comment_usernames_async, fetch_liker_usernames_async
                
                post_details = await get_post_details_async(media_id, working_token, session) or {}
                post_sender = post_senders.get(link_single) or (normalize_username(post_details.get("sender")) if post_details.get("sender") else None)
                
                izinli_uyeler = exemptions_by_link[link_single]
                all_exempted_for_link = izinli_uyeler | global_exempted
                if post_sender and rules['skip_owner']:
                    all_exempted_for_link.add(post_sender)

                commenters_normalized = set()
                comments_list = []
                
                if check_likes:
                    like_count = post_details.get("like_count", 0)
                    if like_count > 90:
                        tracker["done"] += 1
                        if progress_callback:
                            progress_callback(tracker["done"], tracker["total"], f"Gönderi {tracker['done']}/{tracker['total']} tamamlandı")
                        return {
                            "post_link": link_single,
                            "eksikler": [],
                            "commenters": [],
                            "sender": post_sender,
                            "owner_fullname": post_details.get("owner_fullname"),
                            "like_count": like_count,
                            "comment_count": post_details.get("comment_count", 0),
                            "caption": post_details.get("caption", ""),
                            "error": f"Bu gönderi 90'dan fazla beğeni aldığı için ({like_count} beğeni) kontrol edilmedi.",
                            "comments_list": []
                        }
                    all_result = await fetch_liker_usernames_async(media_id, working_token, session)
                    commenters_normalized = {normalize_username(u) for u in all_result.get("usernames", set())}
                else:
                    all_result = await fetch_comment_usernames_async(media_id, working_token, session)
                    comments_list = all_result.get("comments", [])
                    for uname, text in comments_list:
                        norm_uname = normalize_username(uname)
                        commenters_normalized.add(norm_uname)
                
                if not check_likes and (all_result.get('incomplete') or ((grup_uye_kullanicilar - all_exempted_for_link - commenters_normalized) and not comments_cover_total(post_details, comments_list))):
                    tracker['done'] += 1
                    if progress_callback:
                        progress_callback(tracker['done'], tracker['total'], 'Paylaşım doğrulanamadı; diğer kontroller sürüyor.')
                    return incomplete_comment_post(link_single, post_details, post_sender, comments_list)
                require_complete_result(all_result)
                eksikler = grup_uye_kullanicilar - all_exempted_for_link - commenters_normalized
                if check_likes:
                    require_complete_likers(post_details, commenters_normalized, eksikler)
                tamamlayanlar = grup_uye_kullanicilar - all_exempted_for_link - eksikler
                
                # Güvenli 0.5 - 1.0 saniye bekleme
                await asyncio.sleep(0.6)
                
                tracker["done"] += 1
                if progress_callback:
                    progress_callback(tracker["done"], tracker["total"], f"Gönderi {tracker['done']}/{tracker['total']} tamamlandı")
                    
                return {
                    "post_link": link_single,
                    "eksikler": list(eksikler),
                    "commenters": list(tamamlayanlar),
                    "sender": post_sender,
                    "owner_fullname": post_details.get("owner_fullname"),
                    "like_count": post_details.get("like_count", 0),
                    "comment_count": post_details.get("comment_count", 0),
                    "caption": post_details.get("caption", ""),
                    "profile_pic_url": post_details.get("profile_pic_url", ""),
                    "thumbnail_url": post_details.get("thumbnail_url", ""),
                    "is_video": post_details.get("is_video", False),
                    "video_url": post_details.get("video_url", ""),
                    "comments_list": comments_list,
                    "commenters_normalized": commenters_normalized
                }

        conn = aiohttp.TCPConnector(limit=15)
        timeout = aiohttp.ClientTimeout(total=12)
        async with aiohttp.ClientSession(
            cookie_jar=aiohttp.DummyCookieJar(),
            connector=conn, 
            timeout=timeout,
            headers={"Accept-Encoding": "gzip, deflate"},
            skip_auto_headers={"Accept-Encoding", "accept-encoding"}
        ) as session:
            async def saved(url):
                try:
                    row = await _fetch_single(url)
                except ControlUnavailable as error:
                    row = dict(post_link=url, eksikler=[], commenters=[], comments_list=[], error=str(error))
                import time
                row.setdefault('checked_at', time.time())
                row.setdefault('source', 'live')
                if save_checkpoint:
                    save_checkpoint(url, {**row, 'commenters_normalized': list(row.get('commenters_normalized', []))})
                return row
            tasks = [saved(l) for l in links_raw]
            return await asyncio.gather(*tasks)

    # Execute async loop
    try:
        import asyncio
        fetched_results = asyncio.run(_async_run_all())
    except ControlUnavailable:
        raise
    except Exception as e:
        from app_core.jobs import ControlStopped
        if isinstance(e, ControlStopped): raise
        logger.warning(f"aiohttp paralel çalıştırma hatası ({e}), sıralı moda geçiliyor...")
        fetched_results = []
        # Fallback sync
        for link_single in links_raw:
            if link_key(link_single) in {link_key(u) for u in rules['excluded']}:
                fetched_results.append(dict(post_link=link_single,eksikler=[],commenters=[],comments_list=[],skipped_reason='Paylaşım kapsam dışında'))
                continue
            media_id = donustur(link_single)
            if not media_id: continue
            post_details = get_post_details(media_id, working_token) or {}
            post_sender = post_senders.get(link_single) or (normalize_username(post_details.get("sender")) if post_details.get("sender") else None)
            izinli_uyeler = exemptions_by_link[link_single]
            all_exempted_for_link = izinli_uyeler | global_exempted
            if post_sender and rules['skip_owner']: all_exempted_for_link.add(post_sender)
            if check_likes:
                if post_details.get('like_count', 0) > 90:
                    fetched_results.append(dict(post_details, post_link=link_single, sender=post_sender,
                        eksikler=[], commenters=[], comments_list=[],
                        error="Bu gönderi 90'dan fazla beğeni aldığı için kontrol edilmedi."))
                    continue
                all_result = fetch_likers_with_failover(media_id, token_record=working_token)
                commenters_normalized = {normalize_username(u) for u in (all_result if isinstance(all_result, set) else all_result.get("usernames", set()))}
                comments_list = []
            else:
                all_result = fetch_comments_with_failover(media_id, token_record=working_token)
                comments_list = all_result if isinstance(all_result, list) else all_result.get("comments", [])
                commenters_normalized = {normalize_username(uname) for uname, _ in comments_list}
            if not check_likes and ((isinstance(all_result, dict) and all_result.get('incomplete')) or ((grup_uye_kullanicilar - all_exempted_for_link - commenters_normalized) and not comments_cover_total(post_details, comments_list))):
                fetched_results.append(incomplete_comment_post(link_single, post_details, post_sender, comments_list))
                continue
            try:
                require_complete_result(all_result)
                eksikler = grup_uye_kullanicilar - all_exempted_for_link - commenters_normalized
                if check_likes:
                    require_complete_likers(post_details, commenters_normalized, eksikler)
            except ControlUnavailable as error:
                fetched_results.append(dict(post_details, post_link=link_single, eksikler=[], commenters=[], comments_list=[], error=str(error)))
                continue
            tamamlayanlar = grup_uye_kullanicilar - all_exempted_for_link - eksikler
            fetched_results.append({
                "post_link": link_single,
                "eksikler": list(eksikler),
                "commenters": list(tamamlayanlar),
                "sender": post_sender,
                "owner_fullname": post_details.get("owner_fullname"),
                "like_count": post_details.get("like_count", 0),
                "comment_count": post_details.get("comment_count", 0),
                "caption": post_details.get("caption", ""),
                "profile_pic_url": post_details.get("profile_pic_url", ""),
                "thumbnail_url": post_details.get("thumbnail_url", ""),
                "is_video": post_details.get("is_video", False),
                "video_url": post_details.get("video_url", ""),
                "comments_list": comments_list,
                "commenters_normalized": commenters_normalized
            })

    from app_core.storage import score_and_save_comment_logs
    comment_records = []
    import re

    for res in fetched_results:
        link_single = res.get("post_link")
        link_results.append({
            "post_link": link_single,
            "checked_at": res.get('checked_at', __import__('time').time()),
            "source": res.get('source', 'live'),
            "skipped_reason": res.get('skipped_reason'),
            "eksikler": res.get("eksikler", []),
            "commenters": res.get("commenters", []),
            "sender": res.get("sender"),
            "owner_fullname": res.get("owner_fullname"),
            "like_count": res.get("like_count", 0),
            "comment_count": res.get("comment_count", 0),
            "caption": res.get("caption", ""),
            "profile_pic_url": res.get("profile_pic_url", ""),
            "thumbnail_url": res.get("thumbnail_url", ""),
            "is_video": res.get("is_video", False),
            "video_url": res.get("video_url", ""),
            "comments_list": [{"username": u, "text": t} for u, t in res.get("comments_list", [])],
            "likers_list": list(res.get("commenters_normalized", set())) if check_likes else [],
            "error": res.get("error")
        })
        
        commenters_norm = res.get("commenters_normalized", set())
        all_commented.update(commenters_norm)
        
        match = re.search(r"instagram\.com/(?:share/)?(?:p|reels?|tv)/([a-zA-Z0-9\-_]+)", link_single)
        post_code = match.group(1) if match else "unknown"
        
        for uname, text in res.get("comments_list", []):
            norm_uname = normalize_username(uname)
            if norm_uname not in user_comments_map:
                user_comments_map[norm_uname] = []
            user_comments_map[norm_uname].append(text)
            
            if norm_uname in grup_uye_kullanicilar and thread_id:
                is_valid = 1 if ((not rules['require_emoji'] or has_emoji(text)) and clean_word_count(text) >= rules['min_words']) else 0
                comment_records.append((thread_id, norm_uname, post_code, text, is_valid))

        for eksik in res.get("eksikler", []):
            if eksik not in user_missing_posts:
                user_missing_posts[eksik] = []
            user_missing_posts[eksik].append(link_single)
    
    if comment_records:
        score_and_save_comment_logs(comment_records)

    if not link_results:
        raise ValueError("Gecerli link bulunamadi.")

    # Kopya yorum tespiti
    duplicate_comment_users = set()
    for user, comments in user_comments_map.items():
        if len(comments) > 1:
            seen = set()
            for c in comments:
                if not c: continue
                c_clean = c.strip().lower()
                if c_clean in seen:
                    duplicate_comment_users.add(user)
                    break
                seen.add(c_clean)

    # Yorum formatı/kuralı kontrolü (en az 2 kelime + emoji)
    invalid_comment_users = set()
    for user, comments in user_comments_map.items():
        has_any_valid = False
        for comment in comments:
            if (not rules['require_emoji'] or has_emoji(comment)) and clean_word_count(comment) >= rules['min_words']:
                has_any_valid = True
                break
        if not has_any_valid and all(comments):
            invalid_comment_users.add(user)

    from app_core.followup import apply_rules
    adjusted = apply_rules({'links':link_results, 'group':list(grup_uye_kullanicilar)}, thread_id, shared_dates)
    user_missing_posts = adjusted['user_missing_posts']

    # Collect all exempted users from all links + global exemptions
    all_exempted = global_exempted.copy()
    eksikler_all = set()
    for lr in link_results:
        all_exempted.update(exemptions_by_link[lr["post_link"]])
        eksikler_all.update(lr.get("eksikler", []))
    
    responsibility_unknown = {u for lr in link_results for u in lr.get('unknown_members', [])}
    completed_any = {u for lr in link_results for u in lr.get('commenters', [])}
    tamamlayanlar_genel = completed_any - all_exempted - eksikler_all - responsibility_unknown
    if any(lr.get('error') for lr in link_results):
        # Skipped/unverified posts cannot establish completion of the whole run.
        tamamlayanlar_genel = set()
    
    user_missing_formatted = {user: posts for user, posts in user_missing_posts.items()}
    
    # Audit log
    tz = pytz.timezone('Europe/Istanbul')
    now_dt = datetime.datetime.now(tz)
    now_str = now_dt.strftime('%H:%M:%S')
    for lr in link_results:
        post_link = lr["post_link"]
        eksik_sayisi = len(lr.get("eksikler", []))
        grup_sayisi = len(grup_uye_kullanicilar)
        kontrol_tipi = "Beğeni" if check_likes else "Yorum"
        sender_uname = lr.get("sender") or ""
        sender_prefix = f"@{sender_uname} | " if sender_uname else ""
        add_audit_log(
            entity_type="manuel_kontrol",
            entity_id=post_link,
            action="kontrol_dogrulanamadi" if lr.get("error") else "kontrol_yapildi",
            details=lr.get("error") or f"{sender_prefix}Saat {now_str} - {kontrol_tipi} Kontrolü: {grup_sayisi} üyeden {eksik_sayisi} eksik tespit edildi."
        )

    # Cache run result in DB if thread_id
    if thread_id:
        today_str = now_dt.strftime('%Y-%m-%d')
        cache_data = {
            "links": link_results,
            "all_commented": list(tamamlayanlar_genel),
            "group": list(grup_uye_kullanicilar),
            "user_missing_posts": user_missing_formatted,
            "duplicate_comment_users": list(duplicate_comment_users),
            "invalid_comment_users": list(invalid_comment_users),
            "user_comments": user_comments_map,
            "check_likes": check_likes
        }
        from app_core.storage import set_cached_run_result
        set_cached_run_result(thread_id, today_str, cache_data)

    return {
        "links": link_results,
        "all_commented": list(tamamlayanlar_genel),
        "group": list(grup_uye_kullanicilar),
        "user_missing_posts": user_missing_formatted,
        "duplicate_comment_users": list(duplicate_comment_users),
        "invalid_comment_users": list(invalid_comment_users),
        "user_comments": user_comments_map,
        "thread_id": thread_id,
        "check_likes": check_likes
    }


@main_bp.route("/result/<post_code>", methods=["GET"])
def result_page_new(post_code):
    from app_core.jobs import get_job_state
    state = get_job_state(post_code)
    if state and state['kind'] == 'member':
        return redirect('/member-analysis/' + post_code)
    task_status_json = get_db_value(f"task_status_{post_code}")
    if not task_status_json:
        return redirect("/")
        
    try:
        task_status = json.loads(task_status_json)
    except Exception:
        return redirect("/")
        
    status = task_status.get("status")
    
    if status == "completed":
        result_json = get_db_value(f"manual_run_result_{post_code}")
        if not result_json:
            return redirect("/")
        try:
            result = json.loads(result_json)
            result = clean_data_recursive(result)
        except Exception:
            return redirect("/")
            
        return render_template(
            "result.html",
            links=result.get("links"),
            all_commented=result.get("all_commented"),
            group=result.get("group"),
            user_missing_posts=result.get("user_missing_posts"),
            duplicate_comment_users=result.get("duplicate_comment_users"),
            invalid_comment_users=result.get("invalid_comment_users"),
            user_comments=result.get("user_comments"),
            thread_id=result.get("thread_id"),
            check_likes=result.get("check_likes", False),
            post_code=post_code,
            is_loading=False
        )
        
    elif status == "running":
        return redirect(url_for('main.index', task=post_code))

    else: # failed
        return render_template(
            "result.html",
            is_loading=False,
            error_message=task_status.get('message', 'Denetim iptal edildi.') if status == 'cancelled' else f"Hata oluştu: {task_status.get('error', 'Bilinmeyen hata')}",
            post_code=post_code,
            links=[]
        )


@main_bp.route("/api/task_status/<post_code>", methods=["GET"])
def task_status_route(post_code):
    from app_core.jobs import get_job_state, public_status
    job = get_job_state(post_code)
    if job:
        data = public_status(job)
        data['execute_in_request'] = job['kind'] in ('manual','preset','member') or bool(job['kind'] == 'automation' and session.get('admin_logged_in'))
        return jsonify(clean_data_recursive(data))
    # Preserve links to historical records not yet imported.
    task_status_json = get_db_value(f"task_status_{post_code}")
    if not task_status_json:
        return jsonify({"status": "not_found", "progress": 0, "error": "Görev bulunamadı"})
    try:
        return jsonify(clean_data_recursive(json.loads(task_status_json)))
    except (TypeError, ValueError):
        return jsonify({"status": "failed", "error": "Denetim durumu okunamadı."})


@main_bp.route('/api/task_run/<post_code>', methods=['POST'])
def task_run_route(post_code):
    from app_core.web_jobs import execute_job
    result, status = execute_job(post_code, allow_automation=bool(session.get('admin_logged_in')))
    return jsonify(result), status


@main_bp.route("/api/recheck/<post_code>", methods=["POST"])
def recheck_post(post_code):
    from app_core.jobs import enqueue, get_job
    data = request.get_json() or {}
    source = get_job(post_code)
    inputs_json = get_db_value(f"manual_run_inputs_{post_code}")
    if not inputs_json:
        return jsonify({"success": False, "message": "Denetim girdileri bulunamadı."}), 404
    if source and source['state'] in ('queued', 'running', 'cancelling'):
        return jsonify({"success": False, "message": "Denetim zaten sırada veya çalışıyor."}), 409
    if source and source['kind'] not in ('manual','preset'):
        return jsonify({"success": False, "message": "Otomasyonu yönetim panelinden yeniden başlatın."}), 400
    inputs = json.loads(inputs_json)
    if source and source['kind']=='preset':
        result=source['result'] or {}
        inputs=dict(link='\n'.join(p['post_link'] for p in result.get('links',[])),grup_uye=' '.join(result.get('group',[])),thread_id=result.get('thread_id',''),
                    post_senders_raw=[p['post_link']+'|'+p['sender'] for p in result.get('links',[]) if p.get('sender')],check_likes=bool(result.get('check_likes')))
    inputs['only_missing'] = bool(data.get('only_missing', False))
    inputs['unknown_only'] = bool(data.get('unknown_only', False))
    job_id = enqueue('manual', inputs, parent_id=post_code if source else None)
    return jsonify({"success": True, "result_url": url_for('main.result_page_new', post_code=job_id)})


@main_bp.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        from app_core.followup import extract_links, rules_for
        link = request.form.get('post_link', '').strip()
        def invalid_input(message):
            if request.accept_mimetypes.best == 'application/json':
                return jsonify(success=False, message=message), 400
            return render_template("form.html", token_error_message=message), 400
        if not link:
            return invalid_input("Paylaşım linki zorunludur.")

        grup_uye = request.form.get("grup_uye", "")
        thread_id = request.form.get("thread_id", "").strip()
        post_senders_raw = request.form.getlist("post_senders")
        check_likes = request.form.get("check_likes") == "on"
        policy = rules_for(thread_id)
        if policy['mode'] != 'selected': check_likes = policy['mode'] == 'likes'

        # Post kodunu ayıkla
        import re
        match = re.search(r"instagram\.com/(?:share/)?(?:p|reels?|tv)/([a-zA-Z0-9\-_]+)", link)
        if not match or any(donustur(item) is None for item in link.splitlines() if item.strip()):
            return invalid_input("Geçersiz Instagram linki formatı. Tüm bağlantıları kontrol edin.")
        post_code = match.group(1)

        # Girdileri kaydet
        inputs = {
            "link": link,
            "grup_uye": grup_uye,
            "thread_id": thread_id,
            "post_senders_raw": post_senders_raw,
            "check_likes": check_likes
        }
        from app_core.jobs import enqueue
        job_id = enqueue('manual', inputs)
        if request.accept_mimetypes.best == 'application/json':
            return jsonify(success=True, job_id=job_id)
        return redirect(url_for("main.result_page_new", post_code=job_id))

    refresh = request.args.get("refresh") == "1"
    link_param = request.args.get("link", "")
    group_param = request.args.get("group", "")
    return render_template("form.html", refresh=refresh, link_param=link_param, group_param=group_param)


@main_bp.route("/add_exemption", methods=["POST"])
def add_exemption():
    try:
        data = request.get_json() or {}
        post_link = data.get("post_link")
        username = data.get("username")
        days = data.get("days", 0)

        if not username:
            return jsonify({"success": False, "message": "Kullanıcı adı gereklidir"}), 400

        try:
            days = int(days)
        except (ValueError, TypeError):
            days = 0

        username = normalize_username(username)

        # Audit log helper
        tz = pytz.timezone('Europe/Istanbul')
        now_dt = datetime.datetime.now(tz)
        now_str = now_dt.strftime('%H:%M:%S')

        if days > 0:
            # Multi-day global exemption
            success = add_global_exemption(username, days=days)
            if not success:
                return jsonify({"success": False, "message": "Süreli izin veritabanına kaydedilemedi"}), 500

            # Also ensure current post is recorded if post_link is given
            if post_link:
                try:
                    post_link_decoded = html.unescape(post_link)
                    exemptions = load_exemptions()
                    if post_link_decoded not in exemptions:
                        exemptions[post_link_decoded] = []
                    if username not in exemptions[post_link_decoded]:
                        exemptions[post_link_decoded].append(username)
                        save_exemptions(exemptions)
                except Exception as e:
                    logger.warning("Post-specific exemption fallback error: %s", e)

            day_text = f"{days} gün" if days > 1 else "1 gün"
            add_audit_log(
                entity_type="muafiyet",
                entity_id=f"@{username}",
                action="sureli_izin_verildi",
                details=f"Saat {now_str} - @{username} kullanıcısına {day_text} süreyle genel muafiyet tanımlandı."
            )

            return jsonify({
                "success": True,
                "message": f"@{username} kullanıcısına {day_text} süreyle izin verildi!",
                "days": days,
                "is_multi_day": True,
                "username": username
            })
        else:
            # Single post exemption
            if not post_link:
                return jsonify({"success": False, "message": "Paylaşım linki gereklidir"}), 400

            post_link_decoded = html.unescape(post_link)
            exemptions = load_exemptions()

            if post_link_decoded not in exemptions:
                exemptions[post_link_decoded] = []

            if username not in exemptions[post_link_decoded]:
                exemptions[post_link_decoded].append(username)
                save_exemptions(exemptions)

            add_audit_log(
                entity_type="muafiyet",
                entity_id=f"@{username}",
                action="tekil_izin_verildi",
                details=f"Saat {now_str} - @{username} kullanıcısına bu gönderi için izin verildi."
            )

            return jsonify({
                "success": True,
                "message": f"@{username} bu gönderi için izinli sayıldı!",
                "days": 0,
                "is_multi_day": False,
                "username": username
            })
    except Exception as error:
        logger.error("İzinli ekleme hatası: %s", error)
        return jsonify({"success": False, "message": f"Hata: {error}"}), 500


@main_bp.route("/token_al")
def token_page():
    return render_template("token.html")


@main_bp.route("/giris_yaps", methods=["POST"])
def login_and_get_token():
    username = request.form.get("kullanici_adi", "").strip()
    password = request.form.get("sifre", "").strip()
    android_id = request.form.get("android_id", "").strip()
    user_agent = request.form.get("user_agent", "").strip()
    device_id = request.form.get("device_id", "").strip()

    if not username or not password or not android_id or not user_agent or not device_id:
        return jsonify({"token": None, "message": "kullanici_adi, sifre, android_id, user_agent ve device_id zorunludur"}), 400

    try:
        token_value, android_id, user_agent, device_id = giris_yap(
            username, password, android_id, user_agent, device_id
        )
    except LoginError as error:
        logger.error("Login hatasi: @%s | %s | Tip: %s", username, error.message, error.error_type)
        return jsonify({
            "token": None,
            "message": error.message,
            "error_type": error.error_type,
        }), 400
    except Exception as error:
        logger.error("Beklenmeyen login hatasi: @%s | %s", username, error)
        return jsonify({
            "token": None,
            "message": f"Giris sirasinda hata olustu: {error}",
            "error_type": "UNKNOWN",
        }), 500

    if token_value:
        upsert_login_token(username, password, token_value, android_id, user_agent, device_id)

    return jsonify(
        {
            "token": token_value,
            "android_id_yeni": android_id,
            "user_agent": user_agent,
            "device_id": device_id,
        }
    )

@main_bp.route("/api/relogin_active", methods=["POST"])
def relogin_active():
    from app_core.storage import load_tokens
    from app_core.token_service import relogin_saved_user
    tokens = load_tokens(include_deleted=False)
    if not tokens:
        return jsonify({"ok": False, "message": "Sistemde kayitli token bulunamadi."})
    
    # Ilk aktif olani veya ilk tokeni sec
    target_token = next((t for t in tokens if t.get("status") == "active"), None)
    if not target_token:
        target_token = tokens[0]
        
    username = target_token.get("username")
    if not username:
        return jsonify({"ok": False, "message": "Gecerli bir kullanici adi bulunamadi."})
        
    result = relogin_saved_user(username)
    return jsonify({
        "ok": result.get("ok", False),
        "message": result.get("message", "Bilinmeyen hata")
    })


@main_bp.route("/api/get_selected_post", methods=["GET"])
def get_selected_post():
    thread_id = request.args.get("thread_id", "").strip()
    date_str = request.args.get("date", "").strip()
    if not thread_id or not date_str:
        return jsonify({"success": False, "message": "thread_id ve date parametreleri zorunludur"}), 400
    
    from app_core.storage import get_selected_post_for_group
    post_url = get_selected_post_for_group(thread_id, date_str)
    return jsonify({"success": True, "post_url": post_url})


@main_bp.route("/api/save_selected_post", methods=["POST"])
def save_selected_post():
    data = request.get_json() or {}
    thread_id = data.get("thread_id", "").strip()
    date_str = data.get("date", "").strip()
    post_url = data.get("post_url", "").strip()
    
    if not thread_id or not date_str:
        return jsonify({"success": False, "message": "thread_id ve date zorunludur"}), 400
        
    from app_core.storage import set_selected_post_for_group
    success = set_selected_post_for_group(thread_id, date_str, post_url)
    return jsonify({"success": success})


@main_bp.route("/api/check_cached_result", methods=["GET"])
def check_cached_result():
    thread_id = request.args.get("thread_id", "").strip()
    date_str = request.args.get("date", "").strip()
    if not thread_id or not date_str:
        return jsonify({"success": False, "message": "thread_id ve date parametreleri zorunludur"}), 400
    
    from app_core.storage import get_cached_run_result
    result = get_cached_run_result(thread_id, date_str)
    return jsonify({"success": True, "has_cache": result is not None})


@main_bp.route("/result/cached", methods=["GET"])
def cached_result():
    thread_id = request.args.get("thread_id", "").strip()
    date_str = request.args.get("date", "").strip()
    if not thread_id or not date_str:
        return redirect("/")
    
    from app_core.storage import get_cached_run_result
    result = get_cached_run_result(thread_id, date_str)
    result = clean_data_recursive(result)
    if not result:
        return redirect("/")
        
    return render_template(
        "result.html",
        links=result.get("links"),
        all_commented=result.get("all_commented"),
        group=result.get("group"),
        user_missing_posts=result.get("user_missing_posts"),
        duplicate_comment_users=result.get("duplicate_comment_users"),
        invalid_comment_users=result.get("invalid_comment_users"),
        user_comments=result.get("user_comments"),
        thread_id=thread_id,
        check_likes=result.get("check_likes", False),
    )


@main_bp.route("/debug_logs")
def debug_logs():
    if not session.get("admin_logged_in"):
        return jsonify({"success": False, "message": "Yetkisiz erişim. Lütfen admin girişi yapın."}), 401
    import os
    try:
        log_path = "/var/log/kontrolyeni.pythonanywhere.com.error.log"
        if os.path.exists(log_path):
            with open(log_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
                return "<pre>" + "".join(lines[-150:]) + "</pre>"
        else:
            return f"Log file not found at {log_path}"
    except Exception as e:
        return "Error reading log: " + str(e)


@main_bp.route("/api/user_avatar/<username>")
def get_user_avatar_api(username):
    """Kullanıcının profil resmini getirir."""
    from app_core.token_service import get_working_active_token
    from app_core.instagram_api import build_auth_headers, _get_http_session, _get_username
    working_token = get_working_active_token(skip_validation=True)
    if not working_token:
        return jsonify({"ok": False, "error": "No token"}), 404
        
    token = working_token.get("token", "")
    user_agent = working_token.get("user_agent", "")
    android_id = working_token.get("android_id_yeni", "")
    device_id = working_token.get("device_id", "")
    uname = _get_username(working_token)
    
    headers = build_auth_headers(token, user_agent, android_id, device_id, username=uname)
    clean_username = username.strip().lstrip('@')
    url = f"https://i.instagram.com/api/v1/users/{clean_username}/usernameinfo/"
    try:
        resp = _get_http_session(uname).get(url, headers=headers, timeout=6)
        if resp.status_code == 200:
            u_data = resp.json().get("user", {})
            pic_url = u_data.get("profile_pic_url") or u_data.get("hd_profile_pic_url_info", {}).get("url") or ""
            return jsonify({"ok": True, "profile_pic_url": pic_url, "username": clean_username})
    except Exception as e:
        logger.warning("Avatar getirme hatasi: %s", e)
        
    return jsonify({"ok": False, "error": "Not found"}), 404


@main_bp.route("/api/proxy_image")
def proxy_image_api():
    from flask import Response
    from app_core.media_proxy import fetch_media, InvalidMedia
    try:
        content, content_type = fetch_media(request.args.get("url", ""))
        return Response(content, mimetype=content_type, headers={
            "X-Content-Type-Options": "nosniff",
            "Content-Security-Policy": "default-src 'none'; sandbox",
        })
    except InvalidMedia:
        return "Geçersiz medya adresi veya içeriği", 400
    except Exception:
        logger.warning("Medya proxy isteği başarısız")
        return "Medya alınamadı", 502


@main_bp.route("/api/get_post_thumbnail")
def get_post_thumbnail_api():
    """Gönderinin thumbnail görselini anlık sorgular."""
    post_link = request.args.get("link", "").strip()
    if not post_link:
        return jsonify({"ok": False, "error": "No link"}), 400
    from donustur import donustur
    from app_core.token_service import get_working_active_token
    from app_core.instagram_api import get_post_details
    media_id = donustur(post_link)
    if not media_id:
        return jsonify({"ok": False, "error": "Invalid link"}), 400
    working_token = get_working_active_token(skip_validation=True)
    if not working_token:
        return jsonify({"ok": False, "error": "No token"}), 400
    details = get_post_details(media_id, working_token) or {}
    return jsonify({
        "ok": True,
        "thumbnail_url": details.get("thumbnail_url", ""),
        "profile_pic_url": details.get("profile_pic_url", ""),
        "is_video": details.get("is_video", False),
        "video_url": details.get("video_url", "")
    })


@main_bp.route("/api/get_post_interactions")
def get_post_interactions_api():
    """Gönderiye ait tüm beğenenleri veya yorumları döndürür."""
    post_link = request.args.get("link", "").strip()
    action = request.args.get("type", "comments").strip() # 'likes' or 'comments'
    if not post_link:
        return jsonify({"ok": False, "error": "Link gerekli"}), 400
        
    from donustur import donustur
    from app_core.token_service import get_working_active_token, fetch_comments_with_failover, fetch_likers_with_failover
    media_id = donustur(post_link)
    if not media_id:
        return jsonify({"ok": False, "error": "Geçersiz link"}), 400
        
    working_token = get_working_active_token(skip_validation=True)
    if not working_token:
        return jsonify({"ok": False, "error": "Aktif token bulunamadı"}), 400
        
    try:
        if action == "likes":
            res = fetch_likers_with_failover(media_id, token_record=working_token)
            require_complete_result(res)
            likers = list(res if isinstance(res, (set, list)) else res.get("usernames", []))
            return jsonify({"ok": True, "type": "likes", "likers": likers, "count": len(likers)})
        else:
            res = fetch_comments_with_failover(media_id, token_record=working_token)
            require_complete_result(res)
            comments = res if isinstance(res, list) else res.get("comments", [])
            formatted = [{"username": u, "text": t} for u, t in comments]
            return jsonify({"ok": True, "type": "comments", "comments": formatted, "count": len(formatted)})
    except Exception as e:
        logger.error("get_post_interactions_api error: %s", e)
        return jsonify({"ok": False, "error": str(e)}), 500


@main_bp.route("/debug_db/<post_code>")
def debug_db(post_code):
    if not session.get("admin_logged_in"):
        return jsonify({"success": False, "message": "Yetkisiz erişim. Lütfen admin girişi yapın."}), 401
    try:
        status_val = get_db_value(f"task_status_{post_code}")
        result_val = get_db_value(f"manual_run_result_{post_code}")
        inputs_val = get_db_value(f"manual_run_inputs_{post_code}")
        return jsonify({
            "post_code": post_code,
            "task_status": json.loads(status_val) if status_val else None,
            "manual_run_result_length": len(result_val) if result_val else 0,
            "manual_run_result": json.loads(result_val) if result_val else None,
            "manual_run_inputs": json.loads(inputs_val) if inputs_val else None
        })
    except Exception as e:
        return jsonify({"error": str(e)})



