"""Shared, atomic rate limiting, keyed by the direct client's IP."""
import hashlib
import hmac
import math
import time
from app_core.jobs import transaction


def client_key(ip, secret):
    return hmac.new(str(secret).encode(), str(ip).encode(), hashlib.sha256).hexdigest()


def reserve_attempt(key, limit=5, window=900):
    now = time.time()
    with transaction() as conn:
        conn.execute('DELETE FROM login_attempts WHERE expires<=?', (now,))
        row = conn.execute('SELECT * FROM login_attempts WHERE client=?', (key,)).fetchone()
        if row and row['failures'] >= limit:
            return max(1, math.ceil(row['expires']-now))
        conn.execute('''INSERT INTO login_attempts(client,failures,expires) VALUES (?,1,?)
            ON CONFLICT(client) DO UPDATE SET failures=failures+1''', (key,now+window))
    return 0


def clear_attempts(key):
    with transaction() as conn:
        conn.execute('DELETE FROM login_attempts WHERE client=?', (key,))
