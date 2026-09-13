import json
import logging
import sqlite3
import os
from datetime import datetime
import pytz

GMT3 = pytz.timezone('Europe/Istanbul')

from app_core.config import DB_FILE, EXEMPTIONS_FILE, TOKEN_FILE, TOKENS_FILE
from app_core.validators import normalize_username

logger = logging.getLogger(__name__)


def _connect():
    conn = sqlite3.connect(DB_FILE, timeout=30.0)
    conn.row_factory = sqlite3.Row
    # The database may reside on a shared filesystem.
    mode = os.getenv("SQLITE_JOURNAL_MODE", "DELETE").upper()
    if mode not in {"DELETE", "WAL"}:
        conn.close()
        raise ValueError("SQLITE_JOURNAL_MODE must be DELETE or WAL")
    conn.execute(f"PRAGMA journal_mode = {mode};")
    conn.execute("PRAGMA synchronous = NORMAL;")
    conn.execute("PRAGMA cache_size = -64000;")
    conn.execute("PRAGMA temp_store = MEMORY;")
    conn.execute("PRAGMA mmap_size = 268435456;")
    conn.execute("PRAGMA busy_timeout = 30000;")
    return conn


def _json_read(path, default):
    try:
        with open(path, "r", encoding="utf-8") as file:
            return json.load(file)
    except Exception:
        return default

def _init_db(conn):
    from app_core.sqlite_schema import init_schema
    init_schema(conn)


def _migrate_from_json(conn):
    existing_count = conn.execute("SELECT COUNT(*) AS c FROM tokens").fetchone()["c"]
    if existing_count > 0:
        return

    tokens_payload = _json_read(TOKENS_FILE, [])
    if isinstance(tokens_payload, list):
        for token in tokens_payload:
            upsert_token(token, conn=conn)

    exemptions_payload = _json_read(EXEMPTIONS_FILE, {})
    if isinstance(exemptions_payload, dict):
        for link, usernames in exemptions_payload.items():
            if isinstance(usernames, list):
                for username in usernames:
                    conn.execute("INSERT OR IGNORE INTO exemptions (post_link, username) VALUES (?, ?)",
                                 (link, normalize_username(username)))

    token_payload = _json_read(TOKEN_FILE, {})
    if isinstance(token_payload, dict) and token_payload:
        conn.execute(
            "INSERT OR IGNORE INTO key_value (key, value) VALUES ('legacy_token_data', ?)",
            (json.dumps(token_payload, ensure_ascii=False),),
        )

    conn.commit()
    logger.info("JSON verisi SQLite'a migrate edildi.")


def init_storage():
    conn = _connect()
    try:
        _init_db(conn)
        _migrate_from_json(conn)
    finally:
        conn.close()


def _row_to_token(row):
    item = dict(row)
    item["is_active"] = bool(item.get("is_active", 0))
    if not item.get("logout_reason"):
        item.pop("logout_reason", None)
    if not item.get("logout_time"):
        item.pop("logout_time", None)
    if not item.get("deleted_at"):
        item.pop("deleted_at", None)
    return item


def load_tokens(include_deleted=False, search=None, page=None, page_size=None):
    conn = _connect()
    try:
        query = "SELECT * FROM tokens WHERE 1=1"
        params = []

        if not include_deleted:
            query += " AND (deleted_at IS NULL OR deleted_at = '')"

        if search:
            query += " AND (username LIKE ? OR full_name LIKE ?)"
            like = f"%{search.strip()}%"
            params.extend([like, like])

        query += " ORDER BY rowid DESC"

        if page and page_size:
            offset = (max(int(page), 1) - 1) * max(int(page_size), 1)
            query += " LIMIT ? OFFSET ?"
            params.extend([int(page_size), int(offset)])

        rows = conn.execute(query, tuple(params)).fetchall()
        return [_row_to_token(row) for row in rows]
    finally:
        conn.close()


def upsert_token(token, conn=None):
    own_conn = conn is None
    if own_conn:
        conn = _connect()

    try:
        conn.execute(
            """
            INSERT INTO tokens (
                username, full_name, password, token, android_id_yeni, user_agent,
                device_id, is_active, added_at, logout_reason, logout_time, deleted_at, relogin_attempts,
                last_relogin_failed_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(username) DO UPDATE SET
                full_name=excluded.full_name,
                password=excluded.password,
                token=excluded.token,
                android_id_yeni=excluded.android_id_yeni,
                user_agent=excluded.user_agent,
                device_id=excluded.device_id,
                is_active=excluded.is_active,
                added_at=excluded.added_at,
                logout_reason=excluded.logout_reason,
                logout_time=excluded.logout_time,
                deleted_at=excluded.deleted_at,
                relogin_attempts=excluded.relogin_attempts,
                last_relogin_failed_at=excluded.last_relogin_failed_at
            """,
            (
                token.get("username", ""),
                token.get("full_name", ""),
                token.get("password", ""),
                token.get("token", ""),
                token.get("android_id_yeni", ""),
                token.get("user_agent", ""),
                token.get("device_id", ""),
                1 if token.get("is_active", False) else 0,
                token.get("added_at", ""),
                token.get("logout_reason", ""),
                token.get("logout_time", ""),
                token.get("deleted_at", ""),
                token.get("relogin_attempts", 0),
                token.get("last_relogin_failed_at", ""),
            ),
        )

        if own_conn:
            conn.commit()
        return True
    except Exception as error:
        logger.error("Token upsert hatasi: %s", error)
        return False
    finally:
        if own_conn:
            conn.close()


def save_tokens(tokens):
    conn = _connect()
    try:
        for token in tokens:
            upsert_token(token, conn=conn)
        conn.commit()
        return True
    except Exception as error:
        logger.error("Token DB yazma hatasi: %s", error)
        return False
    finally:
        conn.close()


def hard_delete_token(username):
    conn = _connect()
    try:
        conn.execute("DELETE FROM tokens WHERE username = ?", (username,))
        conn.commit()
        return True
    except Exception as error:
        logger.error("Hard delete hatasi: %s", error)
        return False
    finally:
        conn.close()


def restore_token(username):
    conn = _connect()
    try:
        conn.execute(
            "UPDATE tokens SET deleted_at = '', is_active = 1 WHERE username = ?",
            (username,),
        )
        conn.commit()
        return True
    except Exception as error:
        logger.error("Restore hatasi: %s", error)
        return False
    finally:
        conn.close()


def count_tokens(include_deleted=False, search=None):
    conn = _connect()
    try:
        query = "SELECT COUNT(*) AS c FROM tokens WHERE 1=1"
        params = []
        if not include_deleted:
            query += " AND (deleted_at IS NULL OR deleted_at = '')"
        if search:
            like = f"%{search.strip()}%"
            query += " AND (username LIKE ? OR full_name LIKE ?)"
            params.extend([like, like])
        row = conn.execute(query, tuple(params)).fetchone()
        return row["c"] if row else 0
    finally:
        conn.close()


def load_exemptions(search=None, page=None, page_size=None):
    conn = _connect()
    try:
        query = "SELECT post_link, username FROM exemptions WHERE 1=1"
        params = []
        if search:
            like = f"%{search.strip()}%"
            query += " AND (post_link LIKE ? OR username LIKE ?)"
            params.extend([like, like])
        query += " ORDER BY post_link ASC, username ASC"

        if page and page_size:
            offset = (max(int(page), 1) - 1) * max(int(page_size), 1)
            query += " LIMIT ? OFFSET ?"
            params.extend([int(page_size), int(offset)])

        rows = conn.execute(query, tuple(params)).fetchall()
        result = {}
        for row in rows:
            result.setdefault(row["post_link"], []).append(row["username"])
        return result
    finally:
        conn.close()


def load_exemptions_grouped(search=None, page=None, page_size=None):
    """Returns (list of {post_link, usernames, count}, total_groups, total_users)."""
    full = load_exemptions(search=search)
    grouped = []
    for post_link, usernames in full.items():
        clean = sorted({str(u).strip() for u in usernames if str(u).strip()})
        if not clean:
            continue
        grouped.append({"post_link": post_link, "usernames": clean, "count": len(clean)})
    grouped.sort(key=lambda x: x["post_link"])
    total_groups = len(grouped)
    total_users = sum(g["count"] for g in grouped)
    if page and page_size:
        page = max(1, int(page))
        page_size = max(1, int(page_size))
        start = (page - 1) * page_size
        grouped = grouped[start : start + page_size]
    return grouped, total_groups, total_users


def save_exemptions(exemptions, conn=None):
    own_conn = conn is None
    if own_conn:
        conn = _connect()
    try:
        with conn:
            if own_conn: conn.execute("BEGIN IMMEDIATE")
            before = [list(r) for r in conn.execute("SELECT post_link,username FROM exemptions ORDER BY post_link,username")]
            conn.execute("DELETE FROM exemptions")
            for post_link, usernames in exemptions.items():
                for username in usernames:
                    clean_u = normalize_username(username)
                    if clean_u:
                        conn.execute(
                            "INSERT OR IGNORE INTO exemptions (post_link, username) VALUES (?, ?)",
                            (post_link, clean_u),
                        )
            after = [list(r) for r in conn.execute("SELECT post_link,username FROM exemptions ORDER BY post_link,username")]
            if before != after:
                from app_core.features import record_change
                removed = [r for r in before if r not in after]
                added = [r for r in after if r not in before]
                label = "; ".join(["Kaldırıldı: @"+r[1]+" ("+r[0]+")" for r in removed]+["Eklendi: @"+r[1]+" ("+r[0]+")" for r in added])
                record_change(conn,"gönderi muafiyeti","Gönderi muafiyetleri",before,after,label)
        return True
    except Exception as error:
        logger.error("Exemptions DB yazma hatasi: %s", error)
        return False
    finally:
        if own_conn:
            conn.close()


def load_global_exemptions():
    conn = _connect()
    try:
        from datetime import datetime
        now_iso = datetime.now().isoformat()
        # Automatically clean expired temporary exemptions
        try:
            conn.execute(
                "DELETE FROM global_exemptions WHERE expires_at IS NOT NULL AND expires_at != '' AND expires_at < ?",
                (now_iso,)
            )
            conn.commit()
        except Exception:
            pass

        cursor = conn.execute(
            "SELECT username, created_at, expires_at, duration_days FROM global_exemptions ORDER BY created_at DESC"
        )
        result = []
        for row in cursor.fetchall():
            result.append({
                "username": row[0],
                "created_at": row[1],
                "expires_at": row[2] if len(row) > 2 else None,
                "duration_days": int(row[3]) if len(row) > 3 and row[3] else 0,
            })
        return result
    except Exception as error:
        logger.error("Global exemptions okuma hatasi: %s", error)
        return []
    finally:
        conn.close()


def add_global_exemption(username, days=0):
    username = normalize_username(username)
    if not username:
        return False
    conn = _connect()
    try:
        conn.execute("BEGIN IMMEDIATE")
        old_row = conn.execute("SELECT * FROM global_exemptions WHERE username=?", (username,)).fetchone()
        before = dict(old_row) if old_row else None
        from datetime import datetime, timedelta
        now = datetime.now()
        now_iso = now.isoformat()
        
        days_val = 0
        expires_at = None
        if days:
            try:
                days_val = int(days)
                if days_val > 0:
                    expires_at = (now + timedelta(days=days_val)).isoformat()
            except (ValueError, TypeError):
                days_val = 0
                expires_at = None

        conn.execute(
            """
            INSERT INTO global_exemptions (username, created_at, expires_at, duration_days) 
            VALUES (?, ?, ?, ?)
            ON CONFLICT(username) DO UPDATE SET 
                created_at = excluded.created_at,
                expires_at = excluded.expires_at,
                duration_days = excluded.duration_days
            """,
            (username, now_iso, expires_at, days_val),
        )
        new_row = conn.execute("SELECT * FROM global_exemptions WHERE username=?", (username,)).fetchone()
        after = dict(new_row) if new_row else None
        if before != after:
            from app_core.features import record_change
            record_change(conn, "muafiyet", username, before, after, "Muafiyet eklendi / güncellendi")
        conn.commit()
        return True
    except Exception as error:
        logger.error("Global exemption ekleme hatasi: %s", error)
        return False
    finally:
        conn.close()


def remove_global_exemption(username):
    username = normalize_username(username)
    conn = _connect()
    try:
        conn.execute("BEGIN IMMEDIATE")
        old_row = conn.execute("SELECT * FROM global_exemptions WHERE username=?", (username,)).fetchone()
        before = dict(old_row) if old_row else None
        conn.execute("DELETE FROM global_exemptions WHERE username = ?", (username,))
        new_row = conn.execute("SELECT * FROM global_exemptions WHERE username=?", (username,)).fetchone()
        after = dict(new_row) if new_row else None
        if before != after:
            from app_core.features import record_change
            record_change(conn, "muafiyet", username, before, after, "Muafiyet kaldırıldı")
        conn.commit()
        return True
    except Exception as error:
        logger.error("Global exemption silme hatasi: %s", error)
        return False
    finally:
        conn.close()


def is_global_exempted(username):
    username = normalize_username(username)
    conn = _connect()
    try:
        from datetime import datetime
        now_iso = datetime.now().isoformat()
        cursor = conn.execute(
            """
            SELECT 1 FROM global_exemptions 
            WHERE username = ? AND (expires_at IS NULL OR expires_at = '' OR expires_at >= ?)
            """,
            (username, now_iso),
        )
        return cursor.fetchone() is not None
    finally:
        conn.close()


def load_token_data():
    conn = _connect()
    try:
        row = conn.execute("SELECT value FROM key_value WHERE key='legacy_token_data'").fetchone()
        if not row:
            return {}
        try:
            return json.loads(row["value"])
        except Exception:
            return {}
    finally:
        conn.close()


def save_token_data(data):
    conn = _connect()
    try:
        conn.execute(
            "INSERT OR IGNORE INTO key_value (key, value) VALUES ('legacy_token_data', ?)",
            (json.dumps(data, ensure_ascii=False),),
        )
        conn.commit()
        return True
    except Exception as error:
        logger.error("Legacy token DB yazma hatasi: %s", error)
        return False
    finally:
        conn.close()


def add_audit_log(entity_type, entity_id, action, details=""):
    conn = _connect()
    try:
        conn.execute(
            "INSERT INTO audit_logs (entity_type, entity_id, action, details, created_at) VALUES (?, ?, ?, ?, ?)",
            (entity_type, entity_id, action, details, datetime.now().isoformat()),
        )
        conn.commit()
        return True
    except Exception as error:
        logger.error("Audit log hatasi: %s", error)
        return False
    finally:
        conn.close()


def get_audit_logs(limit=100):
    conn = _connect()
    try:
        rows = conn.execute(
            "SELECT id, entity_type, entity_id, action, details, created_at FROM audit_logs ORDER BY id DESC LIMIT ?",
            (int(limit),),
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def get_audit_relogin_count(days=7):
    conn = _connect()
    try:
        from datetime import timedelta
        since = (datetime.now() - timedelta(days=int(days))).isoformat()
        row = conn.execute(
            "SELECT COUNT(*) AS c FROM audit_logs WHERE action = 'relogin_basarili' AND created_at >= ?",
            (since,),
        ).fetchone()
        return row["c"] if row else 0
    finally:
        conn.close()


def get_global_automation_status():
    conn = _connect()
    try:
        row = conn.execute("SELECT value FROM key_value WHERE key='global_automation_status'").fetchone()
        if not row:
            return False
        return row["value"] == "1"
    finally:
        conn.close()


def set_global_automation_status(status):
    conn = _connect()
    try:
        val = "1" if status else "0"
        conn.execute(
            "INSERT OR REPLACE INTO key_value (key, value) VALUES ('global_automation_status', ?)",
            (val,),
        )
        conn.commit()
        return True
    except Exception as error:
        logger.error("Global automation status yazma hatasi: %s", error)
        return False
    finally:
        conn.close()


def get_global_automation_settings():
    conn = _connect()
    try:
        row = conn.execute("SELECT value FROM key_value WHERE key='global_automation_settings'").fetchone()
        if row:
            import json
            return json.loads(row["value"])
        return {
            "times": "23:59",
            "send_to_group": True,
            "template": "@everyone merhaba arkadaşlar eksik listesindeki tüm arkadaşlarımıza dm yazdık dönüş yapmayanları aramızdan çıkarmak durumunda kalacağız.",
            "send_dm_to_missing": True,
            "dm_template": "Merhaba, {grup_ismi} grubumuzda eksiğiniz bulunmaktadır. Lütfen dönüş yapalım..",
            "admin_notify_template": "✅ Otomasyon tamamlandı!\n\n📌 Grup: {grup_ismi}\n🔗 Post: {post_url}\n📅 Paylaşım Tarihi: {post_tarihi}\n\n👥 Toplam üye: {toplam_uye}\n❌ Eksik: {eksik_sayisi}\n⏰ Saat: {saat}"
        }
    finally:
        conn.close()


def set_global_automation_settings(data):
    conn = _connect()
    try:
        conn.execute("BEGIN IMMEDIATE")
        old_row = conn.execute("SELECT value FROM key_value WHERE key='global_automation_settings'").fetchone()
        before = old_row["value"] if old_row else None
        import json
        val = json.dumps(data)
        conn.execute(
            "INSERT OR REPLACE INTO key_value (key, value) VALUES ('global_automation_settings', ?)",
            (val,),
        )
        if before != val:
            from app_core.features import record_change
            record_change(conn, "ayar", "global_automation_settings", before, val, "Otomasyon ayarları değiştirildi")
        conn.commit()
        return True
    except Exception as error:
        logger.error("Global automation settings yazma hatasi: %s", error)
        return False
    finally:
        conn.close()





def get_selected_post_for_group(thread_id, date_str):
    conn = _connect()
    try:
        key = f"sel_post_{thread_id}_{date_str}"
        row = conn.execute("SELECT value FROM key_value WHERE key=?", (key,)).fetchone()
        return row["value"] if row else None
    except Exception as error:
        logger.error("get_selected_post_for_group hatasi: %s", error)
        return None
    finally:
        conn.close()


def set_selected_post_for_group(thread_id, date_str, post_url):
    conn = _connect()
    try:
        key = f"sel_post_{thread_id}_{date_str}"
        conn.execute(
            "INSERT OR REPLACE INTO key_value (key, value) VALUES (?, ?)",
            (key, post_url),
        )
        conn.commit()
        return True
    except Exception as error:
        logger.error("set_selected_post_for_group hatasi: %s", error)
        return False
    finally:
        conn.close()


def get_cached_run_result(thread_id, date_str):
    conn = _connect()
    try:
        key = f"auto_run_result_{thread_id}_{date_str}"
        row = conn.execute("SELECT value FROM key_value WHERE key=?", (key,)).fetchone()
        if row:
            import json
            return json.loads(row["value"])
        return None
    except Exception as error:
        logger.error("get_cached_run_result hatasi: %s", error)
        return None
    finally:
        conn.close()


def set_cached_run_result(thread_id, date_str, result_data):
    conn = _connect()
    try:
        key = f"auto_run_result_{thread_id}_{date_str}"
        import json
        val = json.dumps(result_data, ensure_ascii=False)
        conn.execute(
            "INSERT OR REPLACE INTO key_value (key, value) VALUES (?, ?)",
            (key, val),
        )
        conn.commit()
        return True
    except Exception as error:
        logger.error("set_cached_run_result hatasi: %s", error)
        return False
    finally:
        conn.close()


def save_comment_log(thread_id, username, post_code, comment_text, spam_score, is_format_valid, conn=None):
    own_conn = conn is None
    if own_conn:
        conn = _connect()
    try:
        now_str = datetime.now(GMT3).strftime("%Y-%m-%d %H:%M:%S")
        conn.execute(
            """
            INSERT OR REPLACE INTO comment_history 
            (thread_id, username, post_code, comment_text, spam_score, is_format_valid, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (thread_id, username, post_code, comment_text, spam_score, is_format_valid, now_str)
        )
        conn.commit()
        return True
    except Exception as error:
        logger.error("save_comment_log hatasi: %s", error)
        return False
    finally:
        if own_conn:
            conn.close()


def get_group_spam_report(thread_id):
    conn = _connect()
    try:
        cursor = conn.execute(
            """
            SELECT 
                username,
                COUNT(id) AS total_comments,
                AVG(spam_score) AS average_spam_score,
                SUM(CASE WHEN is_format_valid = 0 THEN 1 ELSE 0 END) AS format_errors
            FROM comment_history
            WHERE thread_id = ?
            GROUP BY username
            ORDER BY average_spam_score DESC
            """,
            (thread_id,)
        )
        return [dict(row) for row in cursor.fetchall()]
    except Exception as error:
        logger.error("get_group_spam_report hatasi: %s", error)
        return []
    finally:
        conn.close()


def get_user_comment_details(thread_id, username):
    conn = _connect()
    try:
        cursor = conn.execute(
            """
            SELECT post_code, comment_text, spam_score, is_format_valid, created_at
            FROM comment_history
            WHERE thread_id = ? AND username = ?
            ORDER BY created_at DESC
            """,
            (thread_id, username)
        )
        return [dict(row) for row in cursor.fetchall()]
    except Exception as error:
        logger.error("get_user_comment_details hatasi: %s", error)
        return []
    finally:
        conn.close()


def get_user_recent_comments(username, limit=5, conn=None):
    own_conn = conn is None
    if own_conn:
        conn = _connect()
    try:
        cursor = conn.execute(
            """
            SELECT comment_text
            FROM comment_history
            WHERE username = ?
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (username, limit)
        )
        return [row["comment_text"] for row in cursor.fetchall()]
    except Exception as error:
        logger.error("get_user_recent_comments hatasi: %s", error)
        return []
    finally:
        if own_conn:
            conn.close()


def load_automations():
    """Tüm grup otomasyon yapılandırmalarını SQLite'dan okur."""
    conn = _connect()
    try:
        cursor = conn.execute("SELECT thread_id, is_active, group_name, notify_username, control_method FROM automations")
        rows = cursor.fetchall()
        result = {}
        for row in rows:
            result[str(row["thread_id"])] = {
                "is_active": bool(row["is_active"]),
                "group_name": row["group_name"] or "",
                "notify_username": row["notify_username"] or "",
                "control_method": row["control_method"] or "all_members",
            }
        return result
    except Exception as error:
        logger.error("Automations DB okuma hatasi: %s", error)
        return {}
    finally:
        conn.close()


def save_automations(data):
    """Tüm grup otomasyon yapılandırmalarını SQLite'a atomik olarak kaydeder."""
    if not isinstance(data, dict):
        return False
    conn = _connect()
    try:
        now_str = datetime.now(GMT3).strftime("%Y-%m-%d %H:%M:%S")
        with conn:
            conn.execute("BEGIN IMMEDIATE")
            before=[dict(r) for r in conn.execute("SELECT * FROM automations ORDER BY thread_id")]
            conn.execute("DELETE FROM automations")
            for thread_id, config in data.items():
                if not thread_id:
                    continue
                is_active = 1 if config.get("is_active") else 0
                group_name = str(config.get("group_name", "") or "")
                notify_username = str(config.get("notify_username", "") or "")
                control_method = str(config.get("control_method", "all_members") or "all_members")
                conn.execute(
                    """
                    INSERT OR REPLACE INTO automations 
                    (thread_id, is_active, group_name, notify_username, control_method, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (str(thread_id), is_active, group_name, notify_username, control_method, now_str)
                )
            after=[dict(r) for r in conn.execute("SELECT * FROM automations ORDER BY thread_id")]
            if before != after:
                from app_core.features import record_change
                record_change(conn,"grup ayarı","Grup otomasyon ayarları",before,after,"Grup otomasyon ayarları değiştirildi")
        return True
    except Exception as error:
        logger.error("Automations DB yazma hatasi: %s", error)
        return False
    finally:
        conn.close()




def cache_group_names(groups):
    """Keep group labels locally so history never needs an Instagram request."""
    conn = _connect()
    try:
        for group in groups:
            if group.get('id') and group.get('name'):
                conn.execute('INSERT OR REPLACE INTO key_value(key,value) VALUES (?,?)',
                             ('group_name_' + str(group['id']), json.dumps(str(group['name']), ensure_ascii=False)))
        conn.commit()
    finally:
        conn.close()


def load_group_names():
    conn = _connect()
    try:
        names = {str(row['thread_id']): row['group_name'] for row in
                 conn.execute("SELECT thread_id,group_name FROM automations WHERE group_name != ''")}
        for row in conn.execute("SELECT key,value FROM key_value WHERE key GLOB 'group_name_*'"):
            names[row['key'][len('group_name_'):]] = json.loads(row['value'])
        return names
    finally:
        conn.close()


def score_and_save_comment_logs(records):
    """Reuse one connection while preserving sequential history-based scores."""
    from app_core.nlp_scorer import calculate_comment_spam_score
    conn = _connect()
    try:
        for thread_id, username, post_code, text, is_valid in records:
            recent = get_user_recent_comments(username, limit=5, conn=conn)
            score = calculate_comment_spam_score(username, text, recent_comments=recent)
            if not save_comment_log(thread_id, username, post_code, text, score, is_valid, conn=conn):
                conn.rollback()
    finally:
        conn.close()
