"""Persistent job queue. Only the standalone worker executes jobs."""
import json
import time
import uuid
from contextlib import contextmanager


def init_schema(conn):
    conn.executescript('''
        CREATE TABLE IF NOT EXISTS jobs (
            id TEXT PRIMARY KEY, kind TEXT NOT NULL, payload TEXT NOT NULL,
            state TEXT NOT NULL DEFAULT 'queued', created REAL NOT NULL,
            updated REAL NOT NULL, available REAL NOT NULL, attempts INTEGER NOT NULL DEFAULT 0,
            owner TEXT, lease_until REAL, progress INTEGER NOT NULL DEFAULT 0,
            message TEXT NOT NULL DEFAULT '', error TEXT, result TEXT,
            dedupe_key TEXT UNIQUE, parent_id TEXT, effects_started INTEGER NOT NULL DEFAULT 0
        );
        CREATE INDEX IF NOT EXISTS jobs_pending ON jobs(state, available);
        CREATE INDEX IF NOT EXISTS jobs_created ON jobs(created);
        CREATE TABLE IF NOT EXISTS login_attempts (
            client TEXT PRIMARY KEY, failures INTEGER NOT NULL, expires REAL NOT NULL
        );
        CREATE TABLE IF NOT EXISTS workers (
            owner TEXT PRIMARY KEY, last_seen REAL NOT NULL, job_id TEXT,
            stopped INTEGER NOT NULL DEFAULT 0
        );
    ''')


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
             dedupe_key, parent_id, 'İşçi bekleniyor; denetim sırada.'))
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


def recover_stale(now=None):
    now = time.time() if now is None else now
    with transaction() as conn:
        rows = conn.execute("SELECT * FROM jobs WHERE state='running' AND lease_until<?", (now,)).fetchall()
        for row in rows:
            _fail(conn, row, 'İşçi kesildi veya süre aşımı oluştu.', now)
        conn.execute("""UPDATE jobs SET state='cancelled',owner=NULL,lease_until=NULL,
            message='Denetim iptal edildi; işçi sahipliği sona erdi.',updated=?
            WHERE state='cancelling' AND lease_until<?""", (now,now))
    return len(rows)


def claim(owner, lease_seconds=30):
    now = time.time()
    with transaction() as conn:
        row = conn.execute("SELECT * FROM jobs WHERE state='queued' AND available<=? ORDER BY created LIMIT 1", (now,)).fetchone()
        if not row:
            return None
        conn.execute('''UPDATE jobs SET state='running', attempts=attempts+1, owner=?,
            lease_until=?,updated=?,message='Denetim başladı.',error=NULL WHERE id=?''',
            (owner, now + lease_seconds, now, row['id']))
        return _decode(conn.execute('SELECT * FROM jobs WHERE id=?', (row['id'],)).fetchone())


def heartbeat(job_id, owner):
    with transaction() as conn:
        return conn.execute("UPDATE jobs SET lease_until=?,updated=? WHERE id=? AND owner=? AND state='running'",
                            (time.time()+30, time.time(), job_id, owner)).rowcount == 1


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
            raise RuntimeError('İşçi sahipliği sona erdi; mesaj gönderimi durduruldu.')


def public_status(job):
    state = job['state']
    return {'status': 'running' if state in ('queued','running','cancelling') else
                     'failed' if state == 'needs_attention' else state,
            'queue_state': state, 'progress': job['progress'], 'message': job['message'],
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
        message = 'Denetim iptal edildi.' if state == 'cancelled' else 'İptal istendi; işçinin durması bekleniyor.'
        conn.execute('UPDATE jobs SET state=?,message=?,error=NULL,updated=? WHERE id=?',
                     (state,message,time.time(),job_id))
        return state


def finish_cancel(job_id, owner):
    """Called by supervisor only after its child process has stopped."""
    with transaction() as conn:
        return conn.execute("""UPDATE jobs SET state='cancelled',owner=NULL,lease_until=NULL,
            message='Denetim iptal edildi.',updated=? WHERE id=? AND owner=? AND state='cancelling'""",
            (time.time(),job_id,owner)).rowcount == 1


def worker_presence(owner, job_id=None, stopped=False):
    with transaction() as conn:
        conn.execute('''INSERT INTO workers(owner,last_seen,job_id,stopped) VALUES (?,?,?,?)
            ON CONFLICT(owner) DO UPDATE SET last_seen=excluded.last_seen,
            job_id=excluded.job_id,stopped=excluded.stopped''', (owner,time.time(),job_id,int(stopped)))
        conn.execute('DELETE FROM workers WHERE last_seen<?', (time.time()-7*86400,))


def worker_status():
    from app_core.storage import _connect
    conn = _connect()
    try:
        now = time.time()
        live = conn.execute('SELECT COUNT(*) FROM workers WHERE stopped=0 AND last_seen>=?', (now-30,)).fetchone()[0]
        last = conn.execute('SELECT MAX(last_seen) FROM workers').fetchone()[0]
        counts = dict(conn.execute('SELECT state,COUNT(*) FROM jobs GROUP BY state').fetchall())
        return {'online': bool(live), 'online_workers': live, 'last_seen': last,
                'queued': counts.get('queued',0), 'running': counts.get('running',0),
                'cancelling': counts.get('cancelling',0)}
    finally:
        conn.close()
