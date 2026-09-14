import base64
import json
import logging
import threading

import requests

from app_core.config import IG_APP_ID

logger = logging.getLogger(__name__)

MAX_COMMENT_PAGES = 50


def parse_comment_page(body):
    """Keep attributable comments; never turn malformed/anonymous data into absence."""
    records = set()
    last = None
    incomplete = False
    saw_comments = False
    for line in (body or '').splitlines():
        if not line.strip():
            continue
        try:
            data = json.loads(line)
        except (ValueError, TypeError):
            incomplete = True
            continue
        if not isinstance(data, dict):
            incomplete = True
            continue
        last = data
        if 'comments' not in data:
            continue
        saw_comments = True
        comments = data['comments']
        if not isinstance(comments, list):
            incomplete = True
            continue
        for comment in comments:
            user = comment.get('user') if isinstance(comment, dict) else None
            name = user.get('username') if isinstance(user, dict) else None
            if not isinstance(name, str) or not name.strip():
                incomplete = True
                continue
            from app_core.validators import is_valid_username
            if not is_valid_username(name):
                incomplete = True
                continue
            text = comment.get('text')
            # A known author establishes presence even when the text is unavailable.
            records.add((name.strip(), text if isinstance(text, str) else ''))
    return last, records, incomplete or not saw_comments

_http_sessions = {}
_session_lock = threading.Lock()

def _get_http_session(username=None):
    if not username:
        username = "_default_"
    with _session_lock:
        session = _http_sessions.get(username)
        if session is None:
            session = requests.Session()
            adapter = requests.adapters.HTTPAdapter(
                pool_connections=15,
                pool_maxsize=15,
                max_retries=1,
            )
            session.mount("https://", adapter)
            session.mount("http://", adapter)
            _http_sessions[username] = session
        return session

def clear_http_session(username=None):
    if not username:
        username = "_default_"
    with _session_lock:
        if username in _http_sessions:
            try:
                _http_sessions[username].close()
            except Exception:
                pass
            del _http_sessions[username]
            logger.info("HTTP session registry cleared for: @%s", username)



def get_post_sender(media_id, token_record):
    """Verilen media_id'nin göndericisini (owner) bulur."""
    username = _get_username(token_record)
    token = current_token(username, token_record.get("token", ""))
    user_agent = token_record.get("user_agent", "")
    android_id = token_record.get("android_id_yeni", "")
    device_id = token_record.get("device_id", "")
    
    if not all([token, user_agent, android_id, device_id]):
        return None
    
    user_id = extract_user_id_from_token(token)
    if not user_id:
        return None
    
    headers = build_auth_headers(token, user_agent, android_id, device_id, username=username)
    headers.update({
        "x-ig-app-locale": "tr_TR",
        "x-ig-device-locale": "tr_TR",
        "x-ig-mapped-locale": "tr_TR",
        "x-ig-capabilities": "3brTv10=",
        "x-ig-connection-type": "WIFI",
        "x-fb-connection-type": "WIFI",
        "accept-language": "tr-TR, en-US",
    })
    
    # Önce /media/{id}/info/ dene
    try:
        response = _get_http_session(username).get(
            f"https://i.instagram.com/api/v1/media/{media_id}/info/",
            headers=headers,
            timeout=10,
        )
        _update_session_from_response(username, response)
        if response.status_code == 200:
            data = response.json()
            items = data.get("items", [])
            if items:
                user = items[0].get("user", {})
                return user.get("username", "")
    except Exception as e:
        logger.warning("get_post_sender info hatası: %s", e)
    
    # Alternatif: /media/infos/ endpoint
    try:
        response = _get_http_session(username).get(
            f"https://i.instagram.com/api/v1/media/infos/",
            params={"media_ids": f"[{media_id}]"},
            headers=headers,
            timeout=10,
        )
        _update_session_from_response(username, response)
        if response.status_code == 200:
            data = response.json()
            items = data.get("items", [])
            if items:
                user = items[0].get("user", {})
                return user.get("username", "")
    except Exception as e:
        logger.warning("get_post_sender infos hatası: %s", e)
    
    # Son çare: Yorumlardan post sahibini bul
    try:
        response = _get_http_session(username).get(
            f"https://i.instagram.com/api/v1/media/{media_id}/comments/",
            params={"can_support_threading": "true"},
            headers=headers,
            timeout=10,
        )
        _update_session_from_response(username, response)
        if response.status_code == 200:
            data = response.json()
            comments = data.get("comments", [])
            if comments:
                # İlk yorum genelde post sahibindir
                user = comments[0].get("user", {})
                return user.get("username", "")
    except Exception as e:
        logger.warning("get_post_sender comments hatası: %s", e)
    
    logger.warning("Post gönderici bulunamadı: %s", media_id)
    return None


def get_post_details(media_id, token_record):
    """Verilen media_id'nin detayli bilgilerini (gönderici, beğeni sayısı, yorum sayısı, başlık) çeker."""
    username = _get_username(token_record)
    token = current_token(username, token_record.get("token", ""))
    user_agent = token_record.get("user_agent", "")
    android_id = token_record.get("android_id_yeni", "")
    device_id = token_record.get("device_id", "")
    
    res = {
        "sender": None,
        "owner_fullname": None,
        "like_count": 0,
        "like_count_verified": False,
        "comment_count": 0,
        "comments_disabled": False,
        "caption": "",
        "profile_pic_url": "",
        "thumbnail_url": "",
        "is_video": False,
        "video_url": ""
    }
    
    if not all([token, user_agent, android_id, device_id]):
        return res
        
    headers = build_auth_headers(token, user_agent, android_id, device_id, username=username)
    headers.update({
        "x-ig-app-locale": "tr_TR",
        "x-ig-device-locale": "tr_TR",
        "x-ig-mapped-locale": "tr_TR",
        "x-ig-capabilities": "3brTv10=",
        "x-ig-connection-type": "WIFI",
        "x-fb-connection-type": "WIFI",
        "accept-language": "tr-TR, en-US",
    })
    
    # 1. Önce /media/{id}/info/ ile çekmeyi dene (Beğeni sayısı, yorum sayısı ve göndericiyi tek adımda al)
    try:
        response = _get_http_session(username).get(
            f"https://i.instagram.com/api/v1/media/{media_id}/info/",
            headers=headers,
            timeout=10,
        )
        _update_session_from_response(username, response)
        if response.status_code == 200:
            data = response.json()
            items = data.get("items", [])
            if items:
                item = items[0]
                user = item.get("user", {})
                res["sender"] = user.get("username")
                res["owner_fullname"] = user.get("full_name")
                res["profile_pic_url"] = user.get("profile_pic_url", "")
                res["like_count"] = item.get("like_count", 0)
                res["like_count_verified"] = isinstance(item.get("like_count"), int)
                res["comment_count"] = item.get("comment_count", 0)
                res["comments_disabled"] = item.get("comments_disabled", False)
                caption = item.get("caption") or {}
                res["caption"] = caption.get("text", "")
                
                # Thumbnail
                image_versions = item.get("image_versions2", {}).get("candidates", [])
                if image_versions:
                    res["thumbnail_url"] = image_versions[0].get("url") or image_versions[-1].get("url") or ""
                elif item.get("carousel_media"):
                    first_c = item.get("carousel_media")[0]
                    c_versions = first_c.get("image_versions2", {}).get("candidates", [])
                    if c_versions:
                        res["thumbnail_url"] = c_versions[0].get("url") or c_versions[-1].get("url") or ""
                
                # Video / Reels
                is_video = bool(item.get("is_video") or item.get("media_type") == 2 or item.get("video_versions"))
                video_url = ""
                video_versions = item.get("video_versions", [])
                if video_versions:
                    video_url = video_versions[0].get("url", "")
                elif item.get("carousel_media"):
                    for cm in item.get("carousel_media"):
                        if cm.get("video_versions"):
                            video_url = cm.get("video_versions")[0].get("url", "")
                            is_video = True
                            break
                res["is_video"] = is_video
                res["video_url"] = video_url
                return res
    except Exception as e:
        logger.warning("get_post_details info hatası: %s", e)
        
    # 2. Alternatif: stream_comments/ ile çekmeyi dene (Yorum sayısı, göndericiyi al)
    try:
        response = _get_http_session(username).get(
            f"https://i.instagram.com/api/v1/media/{media_id}/stream_comments/",
            headers=headers,
            timeout=10,
        )
        _update_session_from_response(username, response)
        if response.status_code == 200:
            for line in response.text.splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    if "comment_count" in data:
                        res["comment_count"] = data.get("comment_count", 0)
                    caption = data.get("caption")
                    if caption:
                        user = caption.get("user", {})
                        res["sender"] = user.get("username")
                        res["owner_fullname"] = user.get("full_name")
                        res["profile_pic_url"] = user.get("profile_pic_url", "")
                        res["caption"] = caption.get("text", "")
                        return res
                except Exception:
                    continue
    except Exception as e:
        logger.warning("get_post_details stream_comments hatası: %s", e)
        
    return res


def extract_user_id_from_token(token):
    if not token or not token.startswith("Bearer IGT:2:"):
        return None
    try:
        token_data = token.replace("Bearer IGT:2:", "")
        missing_padding = len(token_data) % 4
        if missing_padding:
            token_data += "=" * (4 - missing_padding)
        import base64
        decoded = base64.b64decode(token_data)
        data = json.loads(decoded)
        return str(data.get("ds_user_id") or data.get("user_id") or "")
    except Exception as e:
        logger.warning("Token'dan user_id cikarma hatasi: %s", e)
        return None

def build_auth_headers(token, user_agent, android_id, device_id, username=None):
    from app_core.session_state import get_auth_headers
    token = current_token(username, token)
    if username:
        headers = get_auth_headers(username, token, user_agent, android_id, device_id)
    else:
        headers = {
            "authorization": token,
            "user-agent": user_agent,
            "x-ig-app-id": IG_APP_ID,
            "x-ig-android-id": f"android-{android_id}",
            "x-ig-device-id": device_id,
        }
        
    # Extract and inject cookie header automatically from token JSON structure
    try:
        if token and token.startswith("Bearer IGT:2:"):
            token_data = token.replace("Bearer IGT:2:", "").strip()
            missing_padding = len(token_data) % 4
            if missing_padding:
                token_data += "=" * (4 - missing_padding)
            import base64
            import json
            decoded_bytes = base64.b64decode(token_data)
            decoded_str = decoded_bytes.decode("utf-8", errors="ignore")
            data = json.loads(decoded_str)
            
            cookie_val = data.get("cookies")
            if not cookie_val:
                sessionid = data.get("sessionid")
                ds_user_id = data.get("ds_user_id") or data.get("user_id")
                if sessionid and ds_user_id:
                    cookie_val = f"sessionid={sessionid}; ds_user_id={ds_user_id}"
            
            if cookie_val:
                headers["cookie"] = cookie_val
    except Exception as e:
        logger.warning("build_auth_headers cookie injection error: %s", e)
        
    return headers

def _update_session_from_response(username, response):
    """
    Response'dan session state'i gunceller.
    Iki kaynagi kontrol eder:
      1. HTTP response header'lari (normal API endpoint'leri)
      2. Response body icindeki nested 'headers' JSON string'i
         (Bloks endpoint'leri gercek degerleri buraya gomor)
    """
    if not username or response is None:
        return
    try:
        from app_core.session_state import update_session, update_session_from_body
        # 1) HTTP response header'lari
        update_session(username, response.headers, expected_token=getattr(getattr(response, "request", None), "headers", {}).get("authorization"))
        # 2) Body icindeki gizli header'lar (JSON parse edilebiliyorsa)
        try:
            body = response.json()
            if isinstance(body, dict):
                update_session_from_body(username, body, expected_token=getattr(getattr(response, "request", None), "headers", {}).get("authorization"))
        except Exception:
            pass  # JSON degilse veya parse hatasi varsa sessizce gec
    except Exception as e:
        logger.warning("_update_session_from_response hatası: %s", e)

def _get_username(token_record):
    """Token record'dan username'i çıkarır."""
    return token_record.get("username", "") if token_record else ""


def fetch_current_user(token, user_agent, android_id, device_id, username=None, timeout=5):
    headers = build_auth_headers(token, user_agent, android_id, device_id, username=username)
    response = _get_http_session(username).get(
        "https://i.instagram.com/api/v1/accounts/current_user/?edit=true",
        headers=headers,
        timeout=timeout,
    )
    return response

def response_has_invalid_session(response):
    """Only an explicit session rejection may deactivate an account."""
    try:
        data = response.json()
    except Exception:
        return False
    if not isinstance(data, dict):
        return False
    markers = {'login_required', 'invalid_session', 'session_expired', 'invalid_token'}
    return any(str(data.get(key, '')).strip().lower() in markers
               for key in ('message', 'error_type'))


def current_token(username, fallback):
    from app_core.session_state import get_current_token
    return get_current_token(username, fallback)


def validate_token(token_record):
    username = _get_username(token_record)
    token = current_token(username, token_record.get("token", ""))
    user_agent = token_record.get("user_agent", "")
    android_id = token_record.get("android_id_yeni", "")
    device_id = token_record.get("device_id", "")
    
    if not token or not user_agent or not android_id or not device_id:
        return False
    
    user_id = extract_user_id_from_token(token)
    if not user_id:
        return True
    
    # Birincil: GraphQL profile timeline (doğal görünür, inbox kadar sıklıkla kullanılmaz)
    try:
        from urllib.parse import quote as _urlquote
        headers = {
            "authorization": token,
            "user-agent": user_agent,
            "x-ig-app-id": IG_APP_ID,
            "x-ig-android-id": f"android-{android_id}",
            "x-ig-device-id": device_id,
            "x-fb-friendly-name": "IGProfileTimelineQuery",
            "x-ig-bloks-serialize-payload": "true",
            "x-ig-validate-null-in-legacy-dict": "true",
            "content-type": "application/x-www-form-urlencoded",
        }
        variables = json.dumps({"user_id": user_id, "count": 1}, separators=(",", ":"))
        data = (
            "method=post&pretty=false&format=json&server_timestamps=true"
            "&locale=user&purpose=refresh"
            "&fb_api_req_friendly_name=IGProfileTimelineQuery"
            "&client_doc_id=56030350817877850088506871007"
            "&enable_canonical_naming=true"
            f"&variables={_urlquote(variables)}"
        )
        response = _get_http_session(username).post(
            "https://i.instagram.com/graphql/query",
            headers=headers,
            data=data,
            timeout=10,
        )
        _update_session_from_response(username, response)
        if response_has_invalid_session(response):
            logger.warning("Token reddedildi (graphql): %d", response.status_code)
            return False
        if response.status_code == 200:
            logger.info("Token dogrulandi (graphql): %s", device_id[:8])
            return True
    except Exception as error:
        logger.warning("Token dogrulama hatasi (graphql): %s", error)
    
    # Fallback: inbox
    try:
        headers = build_auth_headers(token, user_agent, android_id, device_id, username=username)
        response = _get_http_session(username).get(
            "https://i.instagram.com/api/v1/direct_v2/inbox/",
            headers=headers,
            timeout=10,
        )
        _update_session_from_response(username, response)
        if response_has_invalid_session(response):
            logger.warning("Token reddedildi (inbox fallback): %d", response.status_code)
            return False
        if response.status_code == 200:
            logger.info("Token dogrulandi (inbox fallback): %s", device_id[:8])
            return True
    except Exception as error:
        logger.warning("Token dogrulama hatasi (inbox fallback): %s", error)
    
    return True


def fetch_comment_usernames(media_id, token_record, min_id=None, progress_callback=None):
    username = _get_username(token_record)
    token = current_token(username, token_record.get("token", ""))
    user_agent = token_record.get("user_agent", "")
    android_id = token_record.get("android_id_yeni", "")
    device_id = token_record.get("device_id", "")

    headers = build_auth_headers(token, user_agent, android_id, device_id, username=username)
    headers.update({
        "x-ig-app-locale": "tr_TR",
        "x-ig-device-locale": "tr_TR",
        "x-ig-mapped-locale": "tr_TR",
        "x-ig-capabilities": "3brTv10=",
        "x-ig-connection-type": "WIFI",
        "x-fb-connection-type": "WIFI",
        "accept-language": "tr-TR, en-US",
        "x-fb-http-engine": "Liger",
        "x-fb-client-ip": "True",
        "x-fb-server-cluster": "True",
    })

    params = {
        "min_id": min_id,
        "sort_order": "popular",
        "analytics_module": "comments_v2_feed_contextual_profile",
        "can_support_threading": "true",
        "is_carousel_bumped_post": "false",
        "feed_position": "0",
    }

    usernames = set()
    incomplete = False
    page_count = 0

    while page_count < MAX_COMMENT_PAGES:
        page_count += 1

        try:
            response = _get_http_session(username).get(
                f"https://i.instagram.com/api/v1/media/{media_id}/stream_comments/",
                params=params,
                headers=headers,
                timeout=10,
            )
            _update_session_from_response(username, response)
            headers.update(build_auth_headers(token, user_agent, android_id, device_id, username=username))
        except Exception as error:
            logger.error("Yorum API istegi basarisiz (sayfa %d): %s", page_count, error)
            return {"ok": False, "status": 502, "comments": list(usernames)}

        if response.status_code in [401, 403]:
            return {"ok": False, "status": response.status_code, "invalid_session": response_has_invalid_session(response), "usernames": usernames}

        if response.status_code == 429:
            return {"ok": False, "status": 429, "rate_limited": True, "usernames": usernames}

        if response.status_code != 200:
            return {"ok": False, "status": response.status_code, "invalid_session": response_has_invalid_session(response), "usernames": usernames}

        json_data, page_comments, page_incomplete = parse_comment_page(response.text)
        usernames.update(page_comments)
        incomplete = incomplete or page_incomplete

        if progress_callback:
            try:
                progress_callback(page_count, MAX_COMMENT_PAGES)
            except Exception:
                pass

        if not json_data or json_data.get("status") == "fail":
            return {"ok": False, "status": 502, "comments": list(usernames)}

        next_min_id = json_data.get("next_min_id")
        if not next_min_id:
            break
        params["min_id"] = next_min_id

    if page_count >= MAX_COMMENT_PAGES:
        logger.warning("Maksimum sayfa limitine ulasildi (%d)", MAX_COMMENT_PAGES)

    if page_count >= MAX_COMMENT_PAGES and json_data.get("next_min_id"):
        return {"ok": False, "status": 502, "comments": list(usernames)}
    return {"ok": not incomplete, "status": 200, "incomplete": incomplete, "comments": list(usernames)}


def fetch_liker_usernames(media_id, token_record, progress_callback=None):
    username = _get_username(token_record)
    token = current_token(username, token_record.get("token", ""))
    user_agent = token_record.get("user_agent", "")
    android_id = token_record.get("android_id_yeni", "")
    device_id = token_record.get("device_id", "")

    headers = build_auth_headers(token, user_agent, android_id, device_id, username=username)
    headers.update({
        "x-ig-app-locale": "tr_TR",
        "x-ig-device-locale": "tr_TR",
        "x-ig-mapped-locale": "tr_TR",
        "x-ig-capabilities": "3brTv10=",
        "x-ig-connection-type": "WIFI",
        "x-fb-connection-type": "WIFI",
        "accept-language": "tr-TR, en-US",
        "x-fb-http-engine": "Liger",
        "x-fb-client-ip": "True",
        "x-fb-server-cluster": "True",
    })

    usernames = set()
    try:
        response = _get_http_session(username).get(
            f"https://i.instagram.com/api/v1/media/{media_id}/likers/",
            headers=headers,
            timeout=15,
        )
        _update_session_from_response(username, response)

        if response.status_code == 429 or (response.status_code == 400 and "feedback_required" in response.text):
            return {"ok": False, "status": response.status_code, "rate_limited": True, "usernames": usernames}

        if response.status_code in [401, 403]:
            return {"ok": False, "status": response.status_code, "invalid_session": response_has_invalid_session(response), "usernames": usernames}

        if response.status_code != 200:
            return {"ok": False, "status": response.status_code, "invalid_session": response_has_invalid_session(response), "usernames": usernames}

        json_data = response.json()
        if json_data.get("status") == "fail" or not isinstance(json_data.get("users"), list):
            return {"ok": False, "status": 502, "usernames": usernames}
        for user in json_data.get("users", []):
            uname = user.get("username")
            if uname:
                usernames.add(uname)
                
    except Exception as error:
        logger.error("Begeni API istegi basarisiz: %s", error)
        return {"ok": False, "status": 502, "usernames": usernames}

    return {"ok": True, "status": 200, "usernames": usernames}


def fetch_group_threads(token_record):
    username = _get_username(token_record)
    token = current_token(username, token_record.get("token", ""))
    user_agent = token_record.get("user_agent", "")
    android_id = token_record.get("android_id_yeni", "")
    device_id = token_record.get("device_id", "")
    
    if not all([token, user_agent, android_id, device_id]):
        return {"ok": False, "error": "Eksik token bilgileri"}
    
    headers = build_auth_headers(token, user_agent, android_id, device_id, username=username)
    headers.update({
        "x-ig-app-locale": "tr_TR",
        "x-ig-device-locale": "tr_TR",
        "x-ig-mapped-locale": "tr_TR",
        "x-ig-capabilities": "3brTv10=",
        "x-ig-connection-type": "WIFI",
        "x-fb-connection-type": "WIFI",
        "accept-language": "tr-TR, en-US",
    })
    
    try:
        response = _get_http_session(username).get(
            "https://i.instagram.com/api/v1/direct_v2/inbox/",
            headers=headers,
            timeout=15,
        )
        _update_session_from_response(username, response)
        if response.status_code != 200:
            return {"ok": False, "error": f"HTTP {response.status_code}", "invalid_session": response_has_invalid_session(response)}
        
        data = response.json()
        threads = data.get("inbox", {}).get("threads", [])
        
        groups = []
        for thread in threads:
            thread_id = thread.get("thread_id")
            thread_title = thread.get("thread_title", "")
            users = thread.get("users", [])
            
            if thread_title:
                group_name = thread_title.encode('utf-8', errors='replace').decode('utf-8')
            else:
                usernames = [u.get("username", "") for u in users if u.get("username")]
                group_name = ", ".join(usernames[:3]) + ("..." if len(usernames) > 3 else "")
            
            # Group thumbnail extraction
            group_pic_url = None
            if thread.get("image_versions2", {}).get("candidates"):
                cands = thread["image_versions2"]["candidates"]
                group_pic_url = cands[-1].get("url") or cands[0].get("url")
            elif thread.get("thread_image", {}).get("image_versions2", {}).get("candidates"):
                cands = thread["thread_image"]["image_versions2"]["candidates"]
                group_pic_url = cands[-1].get("url") or cands[0].get("url")
            elif thread.get("custom_photo"):
                group_pic_url = thread.get("custom_photo")
            
            # Fallback: ilk üyenin profil resmi
            if not group_pic_url and users:
                for u in users:
                    pic = u.get("profile_pic_url")
                    if pic:
                        group_pic_url = pic
                        break
            
            if not group_pic_url and thread.get("inviter"):
                group_pic_url = thread["inviter"].get("profile_pic_url")
            
            if group_name and len(users) > 1:
                groups.append({
                    "id": thread_id,
                    "name": group_name,
                    "member_count": len(users),
                    "group_pic_url": group_pic_url,
                })
        
        from app_core.storage import cache_group_names
        cache_group_names(groups)
        logger.info(f"Bulunan grup sayisi: {len(groups)}")
        return {"ok": True, "groups": groups}
    except Exception as e:
        logger.error("Grup cekme hatasi: %s", e)
        import traceback
        traceback.print_exc()
        return {"ok": False, "error": str(e)}


def fetch_group_members(token_record, thread_id):
    username = _get_username(token_record)
    token = current_token(username, token_record.get("token", ""))
    user_agent = token_record.get("user_agent", "")
    android_id = token_record.get("android_id_yeni", "")
    device_id = token_record.get("device_id", "")
    
    if not all([token, user_agent, android_id, device_id]):
        return {"ok": False, "error": "Eksik token bilgileri"}
    
    headers = build_auth_headers(token, user_agent, android_id, device_id, username=username)
    headers.update({
        "x-ig-app-locale": "tr_TR",
        "x-ig-device-locale": "tr_TR",
        "x-ig-mapped-locale": "tr_TR",
        "x-ig-capabilities": "3brTv10=",
        "x-ig-connection-type": "WIFI",
        "x-fb-connection-type": "WIFI",
        "accept-language": "tr-TR, en-US",
    })
    
    try:
        response = _get_http_session(username).get(
            f"https://i.instagram.com/api/v1/direct_v2/threads/{thread_id}/",
            headers=headers,
            timeout=15,
        )
        _update_session_from_response(username, response)
        if response.status_code != 200:
            return {"ok": False, "error": f"HTTP {response.status_code}", "invalid_session": response_has_invalid_session(response)}
        
        data = response.json()
        thread = data.get("thread", {})
        users = thread.get("users", [])
        admin_user_ids = set(str(uid) for uid in thread.get("admin_user_ids", []))
        
        usernames = []
        members = []
        for user in users:
            user_id = str(user.get("pk", ""))
            uname = user.get("username", "")
            pic_url = user.get("profile_pic_url", "")
            fname = user.get("full_name", "")
            if uname and user_id not in admin_user_ids:
                usernames.append(uname)
                members.append({
                    "username": uname,
                    "id": user_id,
                    "profile_pic_url": pic_url,
                    "full_name": fname
                })
        
        return {"ok": True, "usernames": usernames, "members": members}
    except Exception as e:
        logger.error("Grup uyeleri cekme hatasi: %s", e)
        return {"ok": False, "error": str(e)}


def fetch_group_media(token_record, thread_id, target_date=None, complete=False):
    import datetime
    import pytz
    
    class GMT3(datetime.tzinfo):
        def utcoffset(self, _):
            return datetime.timedelta(hours=3)
        def tzname(self, _):
            return "GMT+3"
        def dst(self, _):
            return datetime.timedelta(0)
    
    gmt3 = GMT3()
    utc = pytz.UTC
    
    if target_date is None:
        target_date = datetime.datetime.now(gmt3)
    
    username = _get_username(token_record)
    token = current_token(username, token_record.get("token", ""))
    user_agent = token_record.get("user_agent", "")
    android_id = token_record.get("android_id_yeni", "")
    device_id = token_record.get("device_id", "")
    
    user_id = extract_user_id_from_token(token)
    if not user_id:
        return {"ok": False, "error": "Token'dan user_id alinamadi"}
    
    if not all([token, user_agent, android_id, device_id]):
        return {"ok": False, "error": "Eksik token bilgileri"}
    
    headers = build_auth_headers(token, user_agent, android_id, device_id, username=username)
    headers.update({
        "x-ig-app-locale": "tr_TR",
        "x-ig-device-locale": "tr_TR",
        "x-ig-mapped-locale": "tr_TR",
        "x-ig-capabilities": "3brTv10=",
        "x-ig-connection-type": "WIFI",
        "x-fb-connection-type": "WIFI",
        "accept-language": "tr-TR, en-US",
        "ig-intended-user-id": user_id,
        "ig-u-ds-user-id": user_id,
        "priority": "u=3",
        "x-fb-friendly-name": "IgApi: direct_v2_threads_media",
    })
    
    target_start = target_date.replace(hour=0, minute=0, second=0, microsecond=0, tzinfo=gmt3)
    target_end = target_date.replace(hour=23, minute=59, second=59, microsecond=999999, tzinfo=gmt3)
    
    max_ts = int(target_end.timestamp() * 1000000)
    min_ts = int(target_start.timestamp() * 1000000)
    
    t_data = None
    thread_users_map = {}
    try:
        try:
            t_resp = _get_http_session(username).get(
                f"https://i.instagram.com/api/v1/direct_v2/threads/{thread_id}/",
                headers=headers,
                timeout=10,
            )
            if t_resp.status_code == 200:
                t_data = t_resp.json()
                for u in t_data.get("thread", {}).get("users", []):
                    thread_users_map[str(u.get("pk", ""))] = u.get("username", "")
                inviter = t_data.get("thread", {}).get("inviter", {})
                if inviter:
                    thread_users_map[str(inviter.get("pk", ""))] = inviter.get("username", "")
        except Exception:
            pass

        response = _get_http_session(username).get(
            f"https://i.instagram.com/api/v1/direct_v2/threads/{thread_id}/media/",
            params={
                "max_timestamp": max_ts,
                "limit": "50",
                "media_type": "media_shares",
            },
            headers=headers,
            timeout=15,
        )
        _update_session_from_response(username, response)
        if response.status_code != 200:
            return {"ok": False, "error": f"HTTP {response.status_code}", "invalid_session": response_has_invalid_session(response)}
        
        data = response.json()
        items = data.get("items", [])
        
        if complete:
            if data.get('status') == 'fail' or not isinstance(data.get('items'), list):
                raise ValueError('Paylaşım listesi doğrulanamadı.')
            import time
            pagination_started = time.monotonic()
            # Continue through the selected day; never report a truncated day as complete.
            for page in range(40):
                if time.monotonic()-pagination_started > 110: raise ValueError('Günün tamamı istek süresi içinde alınamadı.')
                stamps = [int(i.get('timestamp',0)) for i in data.get('items',[])]
                if not stamps or min(stamps) <= min_ts or (len(stamps) < 50 and not data.get('has_more')):
                    break
                next_ts = min(stamps) - 1
                response = _get_http_session(username).get(
                    f"https://i.instagram.com/api/v1/direct_v2/threads/{thread_id}/media/",
                    params={'max_timestamp':next_ts,'limit':'50','media_type':'media_shares'},headers=headers,timeout=15)
                if response.status_code != 200: raise ValueError('Günün tüm paylaşımları alınamadı.')
                data=response.json()
                if data.get('status') == 'fail' or not isinstance(data.get('items'),list): raise ValueError('Paylaşım sayfası doğrulanamadı.')
                newer=data.get('items',[])
                if newer and min(int(i.get('timestamp',0)) for i in newer) >= next_ts+1:
                    raise ValueError('Paylaşım sayfalaması ilerlemedi.')
                items.extend(newer)
            else: raise ValueError('Günlük paylaşım sınırına ulaşıldı; tam liste doğrulanamadı.')
            if not t_data or not isinstance(t_data.get('thread'),dict): raise ValueError('Grup mesajları alınamadı.')
            thread=t_data.get('thread',{})
            all_messages=list(thread.get('items',[]))
            seen_cursors=set()
            for page in range(40):
                if time.monotonic()-pagination_started > 110: raise ValueError('Günün tamamı istek süresi içinde alınamadı.')
                stamps=[int(i.get('timestamp',0)) for i in thread.get('items',[])]
                if (stamps and min(stamps)<=min_ts) or not thread.get('has_older'): break
                cursor=thread.get('oldest_cursor')
                if not cursor or cursor in seen_cursors: raise ValueError('Grup mesajlarının tamamı alınamadı.')
                seen_cursors.add(cursor)
                response=_get_http_session(username).get(f"https://i.instagram.com/api/v1/direct_v2/threads/{thread_id}/",
                    params={'cursor':cursor,'direction':'older'},headers=headers,timeout=15)
                if response.status_code!=200: raise ValueError('Grup mesaj sayfası alınamadı.')
                thread=response.json().get('thread')
                if not isinstance(thread,dict): raise ValueError('Mesaj sayfası doğrulanamadı.')
                all_messages.extend(thread.get('items',[]))
            else: raise ValueError('Mesaj sınırına ulaşıldı; tam liste doğrulanamadı.')
            t_data['thread']['items']=all_messages

        posts = []
        for item in items:
            media = item.get("media") or {}
            code = media.get("code")
            if not code:
                continue
            
            timestamp = item.get("timestamp", 0)
            
            if timestamp < min_ts or timestamp > max_ts:
                continue
            
            timestamp_sec = int(timestamp / 1000000)
            dt_utc = datetime.datetime.utcfromtimestamp(timestamp_sec)
            dt_utc = utc.localize(dt_utc)
            dt = dt_utc.astimezone(gmt3)
            
            turkish_months = {
                1: "Ocak", 2: "Şubat", 3: "Mart", 4: "Nisan",
                5: "Mayıs", 6: "Haziran", 7: "Temmuz", 8: "Ağustos",
                9: "Eylül", 10: "Ekim", 11: "Kasım", 12: "Aralık"
            }
            
            taken_at = media.get("taken_at", 0)
            if taken_at:
                dt_taken = datetime.datetime.utcfromtimestamp(taken_at)
                dt_taken = utc.localize(dt_taken)
                dt_taken = dt_taken.astimezone(gmt3)
                upload_date = f"{dt_taken.day} {turkish_months[dt_taken.month]} Yüklendi"
            else:
                upload_date = f"{dt.day} {turkish_months[dt.month]} Yüklendi"
            
            date = f"({upload_date}) {dt.day} {turkish_months[dt.month]} {dt.strftime('%H:%M')}"
            
            sender_pk = str(item.get("user_id", "") or item.get("sender_id", ""))
            post_owner_pk = str(media.get("user", {}).get("pk", "") or media.get("user", {}).get("id", ""))
            post_owner_username = media.get("user", {}).get("username", "") or item.get("media_share", {}).get("user", {}).get("username", "")
            
            final_sender = post_owner_username
            
            # Postun sahibiyle posta atan ayni degilse, atan kisinin kullanici adini bulalim
            if sender_pk and post_owner_pk and sender_pk != post_owner_pk:
                if sender_pk in thread_users_map:
                    final_sender = thread_users_map[sender_pk]
                else:
                    # Eger thread icinde user objesi olarak gelmisse (nadir)
                    alt_user = item.get("user", {}).get("username", "")
                    if alt_user:
                        final_sender = alt_user
            
            sender_username = final_sender
            
            like_count = media.get("like_count", -1)
            comment_count = media.get("comment_count", -1)
            comments_disabled = media.get("comments_disabled", False)
            
            # Yüklenme tarihinin bugün veya dün olup olmadığını kontrol et (Istanbul saatiyle)
            today_date = datetime.datetime.now(gmt3).date()
            yesterday_date = today_date - datetime.timedelta(days=1)
            
            is_recent = False
            if taken_at:
                if dt_taken.date() in (today_date, yesterday_date):
                    is_recent = True
            else:
                if dt.date() in (today_date, yesterday_date):
                    is_recent = True

            # Thumbnail URL cikar
            thumbnail_url = None
            image_versions = media.get("image_versions2", {}).get("candidates", [])
            if image_versions:
                thumbnail_url = image_versions[-1].get("url") or image_versions[0].get("url")
            elif media.get("carousel_media"):
                first_c = media.get("carousel_media")[0]
                c_versions = first_c.get("image_versions2", {}).get("candidates", [])
                if c_versions:
                    thumbnail_url = c_versions[-1].get("url") or c_versions[0].get("url")

            user_profile_pic_url = media.get("user", {}).get("profile_pic_url") or item.get("user", {}).get("profile_pic_url") or ""

            posts.append({
                "id": media.get("id"),
                "code": code,
                "url": f"https://www.instagram.com/p/{code}/",
                "shared_at": datetime.datetime.utcfromtimestamp(timestamp_sec).isoformat() + "Z",
                "date": date,
                "username": sender_username,
                "like_count": like_count,
                "comment_count": comment_count,
                "comments_disabled": comments_disabled,
                "taken_at": taken_at,
                "is_recent": is_recent,
                "thumbnail_url": thumbnail_url,
                "user_profile_pic_url": user_profile_pic_url,
            })
        
        # Parse links from text messages in the thread (to catch plain text link shares)
        if t_data:
            text_posts = []
            try:
                items = t_data.get("thread", {}).get("items", [])
                for item in items:
                    timestamp = item.get("timestamp", 0)
                    if timestamp < min_ts or timestamp > max_ts:
                        continue
                    
                    sender_pk = str(item.get("user_id", ""))
                    sender_username = thread_users_map.get(sender_pk, "unknown")
                    
                    text = item.get("text", "") or ""
                    if item.get("link"):
                        text += " " + str(item.get("link", {}).get("text", ""))
                        
                    import re
                    matches = re.findall(r"instagram\.com/(?:share/)?(?:p|reels?|tv)/([a-zA-Z0-9\-_]+)", text)
                    for code in matches:
                        text_posts.append({
                            "code": code,
                            "sender_username": sender_username,
                            "timestamp": timestamp
                        })
            except Exception as e:
                logger.warning("Thread items parsing error: %s", e)
                
            seen_codes = {p["code"] for p in posts}
            for tp in text_posts:
                code = tp["code"]
                if code not in seen_codes:
                    seen_codes.add(code)
                    
                    from donustur import donustur
                    dummy_link = f"https://www.instagram.com/p/{code}"
                    media_id = str(donustur(dummy_link) or "")
                    
                    timestamp = tp["timestamp"]
                    timestamp_sec = int(timestamp / 1000000)
                    dt_utc = datetime.datetime.utcfromtimestamp(timestamp_sec)
                    dt_utc = utc.localize(dt_utc)
                    dt = dt_utc.astimezone(gmt3)
                    
                    posts.append({
                        "id": media_id,
                        "code": code,
                        "url": f"https://www.instagram.com/p/{code}/",
                "shared_at": datetime.datetime.utcfromtimestamp(timestamp_sec).isoformat() + "Z",
                        "date": f"({dt.day} {turkish_months[dt.month]} Yüklendi) {dt.day} {turkish_months[dt.month]} {dt.strftime('%H:%M')}",
                        "username": tp["sender_username"],
                        "like_count": -1,
                        "comment_count": -1,
                        "comments_disabled": False,
                        "taken_at": timestamp_sec,
                        "is_recent": True,
                        "media_type": "image",
                    })
        
        return {"ok": True, "posts": posts}
    except Exception as e:
        logger.error("Grup paylasimlari cekme hatasi: %s", e)
        return {"ok": False, "error": str(e)}


def fetch_own_thread_items(token_record, thread_id, limit=20):
    """Thread'deki son mesajları çeker, yalnızca bot'un attıklarını döndürür."""
    token = current_token(username, token_record.get("token", ""))
    user_agent = token_record.get("user_agent", "")
    android_id = token_record.get("android_id_yeni", "")
    device_id = token_record.get("device_id", "")

    my_user_id = extract_user_id_from_token(token)
    if not my_user_id:
        return {"ok": False, "error": "Token'dan user_id alinamadi"}

    headers = {
        "authorization": token,
        "user-agent": user_agent,
        "x-ig-app-id": IG_APP_ID,
        "x-ig-android-id": f"android-{android_id}",
        "x-ig-device-id": device_id,
        "x-ig-capabilities": "3brTv10=",
        "x-ig-connection-type": "WIFI",
        "accept-language": "tr-TR, en-US",
    }

    try:
        username = _get_username(token_record)
        resp = _get_http_session(username).get(
            f"https://i.instagram.com/api/v1/direct_v2/threads/{thread_id}/",
            headers=headers,
            params={"limit": limit},
            timeout=15,
        )
        if resp.status_code != 200:
            return {"ok": False, "error": f"HTTP {resp.status_code}"}

        data = resp.json()
        items = data.get("thread", {}).get("items", [])

        own_items = []
        for item in items:
            sender_id = str(item.get("user_id", ""))
            if sender_id == str(my_user_id):
                item_id = item.get("item_id")
                item_type = item.get("item_type", "")
                text = ""
                if item_type == "text":
                    text = item.get("text", "")
                own_items.append({
                    "item_id": item_id,
                    "item_type": item_type,
                    "text": text,
                })

        return {"ok": True, "items": own_items, "my_user_id": my_user_id}
    except Exception as e:
        logger.error("Thread item cekme hatasi: %s", e)
        return {"ok": False, "error": str(e)}


def delete_thread_item(token_record, thread_id, item_id):
    """Bir DM mesajını geri alır (siler)."""
    token = current_token(username, token_record.get("token", ""))
    user_agent = token_record.get("user_agent", "")
    android_id = token_record.get("android_id_yeni", "")
    device_id = token_record.get("device_id", "")

    headers = {
        "authorization": token,
        "user-agent": user_agent,
        "x-ig-app-id": IG_APP_ID,
        "x-ig-android-id": f"android-{android_id}",
        "x-ig-device-id": device_id,
        "x-ig-capabilities": "3brTv10=",
        "content-type": "application/x-www-form-urlencoded",
    }

    try:
        username = _get_username(token_record)
        resp = _get_http_session(username).post(
            f"https://i.instagram.com/api/v1/direct_v2/threads/{thread_id}/items/{item_id}/delete/",
            headers=headers,
            timeout=10,
        )
        ok = resp.status_code == 200
        if not ok:
            logger.warning("Mesaj silinemedi item=%s status=%s", item_id, resp.status_code)
        return {"ok": ok, "status": resp.status_code}
    except Exception as e:
        logger.error("Mesaj silme hatasi: %s", e)
        return {"ok": False, "error": str(e)}


def get_media_taken_at(media_id, token_record):
    """
    Returns (taken_at_timestamp, sender_username) or (None, None).
    taken_at_timestamp is in seconds (Unix timestamp).
    """
    username = _get_username(token_record)
    token = current_token(username, token_record.get("token", ""))
    user_agent = token_record.get("user_agent", "")
    android_id = token_record.get("android_id_yeni", "")
    device_id = token_record.get("device_id", "")
    
    headers = build_auth_headers(token, user_agent, android_id, device_id, username=username)
    
    try:
        response = _get_http_session(username).get(
            f"https://i.instagram.com/api/v1/media/{media_id}/info/",
            headers=headers,
            timeout=10,
        )
        _update_session_from_response(username, response)
        if response.status_code == 200:
            data = response.json()
            items = data.get("items", [])
            if items:
                taken_at = items[0].get("taken_at", 0)
                user = items[0].get("user", {})
                sender = user.get("username", "")
                return taken_at, sender
    except Exception as e:
        logger.warning("get_media_taken_at hatasi: %s", e)
    
    return None, None


# =====================================================================
# ⚡ AIOHTTP YENİ NESİL ASENKRON PARALEL SORGULAMA MOTORU (ULTRA-FAST)
# =====================================================================
import aiohttp
import asyncio
import os

def get_outbound_proxy():
    """PythonAnywhere veya diğer sunucularda proxy adresini bulur."""
    proxy = (
        os.environ.get("https_proxy") or 
        os.environ.get("HTTPS_PROXY") or 
        os.environ.get("http_proxy") or 
        os.environ.get("HTTP_PROXY")
    )
    if not proxy:
        if os.path.exists("/etc/pythonanywhere") or os.environ.get("PYTHONANYWHERE_SITE") or os.environ.get("PYTHONANYWHERE_DOMAIN") or os.path.exists("/var/www"):
            proxy = "http://proxy.server:3128"
    return proxy

async def get_post_details_async(media_id, token_record, session: aiohttp.ClientSession):
    """aiohttp ile asenkron gönderi detayları, sahibi, beğeni ve yorum sayısı."""
    username = _get_username(token_record)
    token = current_token(username, token_record.get("token", ""))
    user_agent = token_record.get("user_agent", "")
    android_id = token_record.get("android_id_yeni", "")
    device_id = token_record.get("device_id", "")
    
    res = {
        "sender": None,
        "owner_fullname": None,
        "like_count": 0,
        "like_count_verified": False,
        "comment_count": 0,
        "caption": "",
        "taken_at": 0,
        "profile_pic_url": "",
        "thumbnail_url": "",
        "is_video": False,
        "video_url": ""
    }
    
    if not all([token, user_agent, android_id, device_id]):
        return res
        
    headers = build_auth_headers(token, user_agent, android_id, device_id, username=username)
    headers.update({
        "x-ig-app-locale": "tr_TR",
        "x-ig-device-locale": "tr_TR",
        "x-ig-mapped-locale": "tr_TR",
        "x-ig-capabilities": "3brTv10=",
        "x-ig-connection-type": "WIFI",
        "x-fb-connection-type": "WIFI",
        "accept-language": "tr-TR, en-US",
        "accept-encoding": "gzip, deflate",
        "Accept-Encoding": "gzip, deflate",
    })
    headers = {str(k): str(v) for k, v in headers.items() if v is not None}
    proxy_url = get_outbound_proxy()
    
    try:
        async with session.get(
            f"https://i.instagram.com/api/v1/media/{media_id}/info/",
            headers=headers,
            proxy=proxy_url,
            timeout=aiohttp.ClientTimeout(total=8)
        ) as response:
            from app_core.session_state import update_session
            update_session(username, response.headers, expected_token=headers.get("authorization"))
            headers.update(build_auth_headers(token, user_agent, android_id, device_id, username=username))
            if response.status == 200:
                data = await response.json()
                items = data.get("items", [])
                if items:
                    item = items[0]
                    user = item.get("user", {})
                    res["sender"] = user.get("username")
                    res["owner_fullname"] = user.get("full_name")
                    res["profile_pic_url"] = user.get("profile_pic_url", "")
                    res["like_count"] = item.get("like_count", 0)
                    res["like_count_verified"] = isinstance(item.get("like_count"), int)
                    res["comment_count"] = item.get("comment_count", 0)
                    res["taken_at"] = item.get("taken_at", 0)
                    caption = item.get("caption") or {}
                    res["caption"] = caption.get("text", "")
                    
                    # Thumbnail
                    image_versions = item.get("image_versions2", {}).get("candidates", [])
                    if image_versions:
                        res["thumbnail_url"] = image_versions[0].get("url") or image_versions[-1].get("url") or ""
                    elif item.get("carousel_media"):
                        first_c = item.get("carousel_media")[0]
                        c_versions = first_c.get("image_versions2", {}).get("candidates", [])
                        if c_versions:
                            res["thumbnail_url"] = c_versions[0].get("url") or c_versions[-1].get("url") or ""
                            
                    # Video / Reels
                    is_video = bool(item.get("is_video") or item.get("media_type") == 2 or item.get("video_versions"))
                    video_url = ""
                    video_versions = item.get("video_versions", [])
                    if video_versions:
                        video_url = video_versions[0].get("url", "")
                    elif item.get("carousel_media"):
                        for cm in item.get("carousel_media"):
                            if cm.get("video_versions"):
                                video_url = cm.get("video_versions")[0].get("url", "")
                                is_video = True
                                break
                    res["is_video"] = is_video
                    res["video_url"] = video_url
                    return res
    except Exception as e:
        logger.warning("get_post_details_async info hatası: %s (sync fallback deneniyor)", e)
        try:
            return get_post_details(media_id, token_record)
        except Exception:
            return res
        
    return res


async def fetch_comment_usernames_async(media_id, token_record, session: aiohttp.ClientSession, min_id=None):
    """aiohttp ile asenkron hızlı yorum akışı çekme."""
    username = _get_username(token_record)
    token = current_token(username, token_record.get("token", ""))
    user_agent = token_record.get("user_agent", "")
    android_id = token_record.get("android_id_yeni", "")
    device_id = token_record.get("device_id", "")

    headers = build_auth_headers(token, user_agent, android_id, device_id, username=username)
    headers.update({
        "x-ig-app-locale": "tr_TR",
        "x-ig-device-locale": "tr_TR",
        "x-ig-mapped-locale": "tr_TR",
        "x-ig-capabilities": "3brTv10=",
        "x-ig-connection-type": "WIFI",
        "x-fb-connection-type": "WIFI",
        "accept-language": "tr-TR, en-US",
        "x-fb-http-engine": "Liger",
        "accept-encoding": "gzip, deflate",
        "Accept-Encoding": "gzip, deflate",
    })
    headers = {str(k): str(v) for k, v in headers.items() if v is not None}

    params = {
        "sort_order": "popular",
        "analytics_module": "comments_v2_feed_contextual_profile",
        "can_support_threading": "true",
        "is_carousel_bumped_post": "false",
        "feed_position": "0",
    }
    if min_id:
        params["min_id"] = str(min_id)

    usernames = set()
    incomplete = False
    page_count = 0
    proxy_url = get_outbound_proxy()

    while page_count < MAX_COMMENT_PAGES:
        page_count += 1
        try:
            async with session.get(
                f"https://i.instagram.com/api/v1/media/{media_id}/stream_comments/",
                params=params,
                headers=headers,
                proxy=proxy_url,
                timeout=aiohttp.ClientTimeout(total=8)
            ) as response:
                from app_core.session_state import update_session
                update_session(username, response.headers, expected_token=headers.get("authorization"))
                headers.update(build_auth_headers(token, user_agent, android_id, device_id, username=username))
                if response.status in [401, 403]:
                    return {"ok": False, "status": response.status, "comments": list(usernames)}
                if response.status == 429:
                    return {"ok": False, "status": 429, "rate_limited": True, "comments": list(usernames)}
                if response.status != 200:
                    return {"ok": False, "status": response.status, "comments": list(usernames)}

                text_body = await response.text()
                json_data, page_comments, page_incomplete = parse_comment_page(text_body)
                usernames.update(page_comments)
                incomplete = incomplete or page_incomplete

                if not json_data or json_data.get("status") == "fail":
                    return {"ok": False, "status": 502, "comments": list(usernames)}
                next_min_id = json_data.get("next_min_id")
                if not next_min_id:
                    break
                params["min_id"] = str(next_min_id)
        except Exception as err:
            logger.error("Yorum API aiohttp hatasi (sayfa %d): %s (sync fallback deneniyor)", page_count, err)
            if page_count == 1:
                try:
                    from app_core.token_service import fetch_comments_with_failover
                    sync_res = fetch_comments_with_failover(media_id, token_record=token_record)
                    if isinstance(sync_res, dict) and not sync_res.get("ok"):
                        return sync_res
                    sync_comments = sync_res if isinstance(sync_res, list) else sync_res.get("comments", [])
                    return {"ok": True, "status": 200, "comments": sync_comments}
                except Exception as sync_err:
                    logger.error("Sync fallback hatasi: %s", sync_err)
            return {"ok": False, "status": 502, "comments": list(usernames)}

    if page_count >= MAX_COMMENT_PAGES and json_data.get("next_min_id"):
        return {"ok": False, "status": 502, "comments": list(usernames)}
    return {"ok": not incomplete, "status": 200, "incomplete": incomplete, "comments": list(usernames)}


async def fetch_liker_usernames_async(media_id, token_record, session: aiohttp.ClientSession):
    """aiohttp ile asenkron beğenen kullanıcıları çekme."""
    username = _get_username(token_record)
    token = current_token(username, token_record.get("token", ""))
    user_agent = token_record.get("user_agent", "")
    android_id = token_record.get("android_id_yeni", "")
    device_id = token_record.get("device_id", "")

    headers = build_auth_headers(token, user_agent, android_id, device_id, username=username)
    headers.update({
        "x-ig-app-locale": "tr_TR",
        "x-ig-device-locale": "tr_TR",
        "x-ig-mapped-locale": "tr_TR",
        "x-ig-capabilities": "3brTv10=",
        "x-ig-connection-type": "WIFI",
        "x-fb-connection-type": "WIFI",
        "accept-language": "tr-TR, en-US",
        "accept-encoding": "gzip, deflate",
        "Accept-Encoding": "gzip, deflate",
    })
    headers = {str(k): str(v) for k, v in headers.items() if v is not None}
    proxy_url = get_outbound_proxy()

    try:
        async with session.get(
            f"https://i.instagram.com/api/v1/media/{media_id}/likers/",
            headers=headers,
            proxy=proxy_url,
            timeout=aiohttp.ClientTimeout(total=8)
        ) as response:
            from app_core.session_state import update_session
            update_session(username, response.headers, expected_token=headers.get("authorization"))
            headers.update(build_auth_headers(token, user_agent, android_id, device_id, username=username))
            if response.status == 200:
                data = await response.json()
                if data.get("status") == "fail" or not isinstance(data.get("users"), list):
                    return {"ok": False, "status": 502, "usernames": set()}
                users = data.get("users", [])
                usernames = {u.get("username") for u in users if u.get("username")}
                return {"ok": True, "status": 200, "usernames": usernames}
            return {"ok": False, "status": response.status, "usernames": set()}
    except Exception as e:
        logger.error("Begeni aiohttp hatasi: %s (sync fallback)", e)
        try:
            from app_core.token_service import fetch_likers_with_failover
            sync_res = fetch_likers_with_failover(media_id, token_record=token_record)
            if isinstance(sync_res, dict) and not sync_res.get("ok"):
                return sync_res
            sync_likers = sync_res if isinstance(sync_res, set) else set(sync_res.get("usernames", set()))
            return {"ok": True, "status": 200, "usernames": sync_likers}
        except Exception:
            return {"ok": False, "status": 500, "usernames": set()}

