"""Persistent request execution records, results and retry protection."""
import json
import time
import uuid
from contextlib import contextmanager


def init_schema(conn):
    from app_core.sqlite_schema import init_schema as upgrade
    upgrade(conn)


@contextmanager
def transaction():
    from app_core.storage import _connect
    conn = _connect()
    try:
        conn.execute('BEGIN IMMEDIATE')
        yield conn
        conn.commit()
    except BaseException:
        conn.rollback()
        raise
    finally:
        conn.close()


def _decode(row):
    if row is None:
        return None
    job = dict(row)
    job['payload'] = json.loads(job['payload'])
    job['result'] = json.loads(job['result']) if job['result'] else None
    return job


def get_job(job_id):
    from app_core.storage import _connect
    conn = _connect()
    try:
        return _decode(conn.execute('SELECT * FROM jobs WHERE id=?', (job_id,)).fetchone())
    finally:
        conn.close()


def get_job_state(job_id):
    """Read status without transferring stored inputs or comment results."""
    from app_core.storage import _connect
    conn = _connect()
    try:
        row = conn.execute('SELECT id,kind,state,owner,lease_until,progress,message,error,attempts FROM jobs WHERE id=?', (job_id,)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def enqueue(kind, payload, *, dedupe_key=None, parent_id=None, job_id=None):
    now = time.time()
    job_id = job_id or uuid.uuid4().hex
    with transaction() as conn:
        if dedupe_key:
            row = conn.execute('SELECT id FROM jobs WHERE dedupe_key=?', (dedupe_key,)).fetchone()
            if row:
                return row['id']
        conn.execute('''INSERT INTO jobs
            (id,kind,payload,created,updated,available,dedupe_key,parent_id,message)
            VALUES (?,?,?,?,?,?,?,?,?)''',
            (job_id, kind, json.dumps(payload, ensure_ascii=False), now, now, now,
             dedupe_key, parent_id, 'Denetim başlatılmaya hazır.'))
    return job_id


def _fail(conn, row, error, now):
    # A crash during a remote write has an unknown outcome. Never resend automatically.
    state = ('needs_attention' if row['effects_started'] else
             'queued' if row['attempts'] < 3 else 'failed')
    delay = min(300, 30 * max(1, row['attempts']))
    conn.execute('''UPDATE jobs SET state=?, error=?, message=?, updated=?, available=?,
                    owner=NULL, lease_until=NULL, progress=0 WHERE id=?''',
                 (state, error, 'Yeniden deneme bekleniyor.' if state == 'queued' else error,
                  now, now + delay, row['id']))


def claim_request(job_id, owner, lease_seconds=170):
    now = time.time()
    with transaction() as conn:
        row = conn.execute('SELECT * FROM jobs WHERE id=?', (job_id,)).fetchone()
        if not row:
            return None
        if row['state'] == 'cancelling' and (row['lease_until'] or 0) < now:
            conn.execute("UPDATE jobs SET state='cancelled',owner=NULL,lease_until=NULL,message='Denetim iptal edildi.',updated=? WHERE id=?", (now,job_id))
            return None
        if row['state'] == 'running' and (row['lease_until'] or 0) < now:
            _fail(conn, row, 'Denetim isteği kesildi veya süresi doldu.', now)
            row = conn.execute('SELECT * FROM jobs WHERE id=?', (job_id,)).fetchone()
        if row['state'] != 'queued' or row['available'] > now:
            return None
        conn.execute("UPDATE jobs SET state='running',owner=?,lease_until=?,updated=?,attempts=attempts+1,message='Denetim başladı.' WHERE id=?",
                     (owner,now+lease_seconds,now,job_id))
        return _decode(conn.execute('SELECT * FROM jobs WHERE id=?', (job_id,)).fetchone())


def progress(job_id, owner, current, total, message):
    with transaction() as conn:
        conn.execute("UPDATE jobs SET progress=?,message=?,updated=? WHERE id=? AND owner=? AND state='running' AND lease_until>?",
                     (min(95, int(current/max(1,total)*90)), message, time.time(), job_id, owner, time.time()))


def complete(job_id, owner, result):
    with transaction() as conn:
        return conn.execute('''UPDATE jobs SET state='completed', result=?, progress=100,
            message='Denetim tamamlandı.', error=NULL, updated=?, owner=NULL, lease_until=NULL
            WHERE id=? AND owner=? AND state='running' AND lease_until>?''',
            (json.dumps(result, ensure_ascii=False), time.time(), job_id, owner, time.time())).rowcount == 1


def fail(job_id, owner, error):
    with transaction() as conn:
        row = conn.execute("SELECT * FROM jobs WHERE id=? AND owner=? AND state='running'", (job_id, owner)).fetchone()
        if row:
            _fail(conn, row, str(error), time.time())


def mark_effects_started(job_id, owner):
    with transaction() as conn:
        changed = conn.execute('''UPDATE jobs SET effects_started=1 WHERE id=? AND owner=?
            AND state='running' AND lease_until>?''', (job_id, owner, time.time())).rowcount
        if not changed:
            raise RuntimeError('Denetim isteğinin süresi doldu; mesaj gönderimi durduruldu.')


def public_status(job):
    state = job['state']
    return {'status': 'running' if state in ('queued','running','cancelling') else
                     'failed' if state == 'needs_attention' else state,
            'queue_state': state, 'progress': job['progress'], 'message': ('Denetim başlatılmaya hazır.' if state == 'queued' and 'İşçi' in (job['message'] or '') else job['message']),
            'error': job['error'], 'attempts': job['attempts']}


def history(page=1, page_size=30):
    from app_core.storage import _connect
    conn = _connect()
    try:
        # Do not transfer full comment payloads for the overview.
        rows = conn.execute('''SELECT id,kind,state,created,updated,attempts,message,error,parent_id,
            json_extract(payload,'$.thread_id') AS thread_id,
            json_extract(payload,'$.check_likes') AS check_likes
            FROM jobs ORDER BY created DESC LIMIT ? OFFSET ?''', (page_size,(page-1)*page_size)).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def import_legacy():
    """One-time import; old post-code result links remain usable."""
    with transaction() as conn:
        if conn.execute("SELECT 1 FROM key_value WHERE key='jobs_migrated_v1'").fetchone():
            return
        rows = conn.execute("SELECT key,value FROM key_value WHERE key LIKE 'task_status_%'").fetchall()
        for row in rows:
            try:
                job_id = row['key'][len('task_status_'):]
                status = json.loads(row['value'])
                inputs = conn.execute('SELECT value FROM key_value WHERE key=?', ('manual_run_inputs_'+job_id,)).fetchone()
                result = conn.execute('SELECT value FROM key_value WHERE key=?', ('manual_run_result_'+job_id,)).fetchone()
                if not inputs:
                    continue
                json.loads(inputs['value'])
                state = 'queued' if status.get('status') == 'running' else status.get('status', 'failed')
                now = time.time()
                conn.execute('''INSERT OR IGNORE INTO jobs
                    (id,kind,payload,state,created,updated,available,result,message,error)
                    VALUES (?,'manual',?,?,?,?,?,?,?,?)''',
                    (job_id,inputs['value'],state,now,now,now,
                     result['value'] if result and state=='completed' else None,
                     'Eski kayıt içe aktarıldı; tarih içe aktarma zamanıdır.',status.get('error')))
            except (ValueError, TypeError):
                continue
        conn.execute("INSERT INTO key_value(key,value) VALUES ('jobs_migrated_v1','1')")


def snapshot(job_id, owner, result):
    with transaction() as conn:
        changed = conn.execute("UPDATE jobs SET result=? WHERE id=? AND owner=? AND state='running' AND lease_until>?",
            (json.dumps(result, ensure_ascii=False), job_id, owner, time.time())).rowcount
        if not changed:
            raise RuntimeError('Denetim sahipliği sona erdi.')


def cancel(job_id):
    with transaction() as conn:
        row = conn.execute('SELECT state FROM jobs WHERE id=?', (job_id,)).fetchone()
        if not row:
            return 'not_found'
        if row['state'] in ('cancelled', 'cancelling'):
            return row['state']
        if row['state'] not in ('queued', 'running'):
            return 'conflict'
        state = 'cancelled' if row['state'] == 'queued' else 'cancelling'
        message = 'Denetim iptal edildi.' if state == 'cancelled' else 'İptal istendi; devam eden isteğin bitmesi bekleniyor.'
        conn.execute('UPDATE jobs SET state=?,message=?,error=NULL,updated=? WHERE id=?',
                     (state,message,time.time(),job_id))
        return state


def finish_cancel(job_id, owner):
    """Finalize cancellation after the request has stopped executing."""
    with transaction() as conn:
        return conn.execute("""UPDATE jobs SET state='cancelled',owner=NULL,lease_until=NULL,
            message='Denetim iptal edildi.',updated=? WHERE id=? AND owner=? AND state='cancelling'""",
            (time.time(),job_id,owner)).rowcount == 1


