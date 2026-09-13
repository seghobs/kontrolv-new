"""Additive SQLite upgrades: no record updates, table rebuilds or implicit commits."""
import sqlite3

STATEMENTS = [
    """CREATE TABLE IF NOT EXISTS jobs (
            id TEXT PRIMARY KEY, kind TEXT NOT NULL, payload TEXT NOT NULL,
            state TEXT NOT NULL DEFAULT 'queued', created REAL NOT NULL,
            updated REAL NOT NULL, available REAL NOT NULL, attempts INTEGER NOT NULL DEFAULT 0,
            owner TEXT, lease_until REAL, progress INTEGER NOT NULL DEFAULT 0,
            message TEXT NOT NULL DEFAULT '', error TEXT, result TEXT,
            dedupe_key TEXT UNIQUE, parent_id TEXT, effects_started INTEGER NOT NULL DEFAULT 0
        )""",
    """CREATE INDEX IF NOT EXISTS jobs_pending ON jobs(state, available)""",
    """CREATE INDEX IF NOT EXISTS jobs_created ON jobs(created)""",
    """CREATE TABLE IF NOT EXISTS login_attempts (
            client TEXT PRIMARY KEY, failures INTEGER NOT NULL, expires REAL NOT NULL
        )""",
    """CREATE TABLE IF NOT EXISTS tokens (
            username TEXT PRIMARY KEY,
            full_name TEXT DEFAULT '',
            password TEXT DEFAULT '',
            token TEXT DEFAULT '',
            android_id_yeni TEXT DEFAULT '',
            user_agent TEXT DEFAULT '',
            device_id TEXT DEFAULT '',
            is_active INTEGER DEFAULT 1,
            added_at TEXT DEFAULT '',
            logout_reason TEXT DEFAULT '',
            logout_time TEXT DEFAULT '',
            deleted_at TEXT DEFAULT '',
            relogin_attempts INTEGER DEFAULT 0,
            last_relogin_failed_at TEXT DEFAULT ''
        )""",
    """CREATE TABLE IF NOT EXISTS exemptions (
            post_link TEXT NOT NULL,
            username TEXT NOT NULL,
            PRIMARY KEY (post_link, username)
        )""",
    """CREATE TABLE IF NOT EXISTS global_exemptions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            created_at TEXT NOT NULL,
            expires_at TEXT DEFAULT NULL,
            duration_days INTEGER DEFAULT 0
        )""",
    """CREATE TABLE IF NOT EXISTS key_value (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )""",
    """CREATE TABLE IF NOT EXISTS audit_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            entity_type TEXT NOT NULL,
            entity_id TEXT NOT NULL,
            action TEXT NOT NULL,
            details TEXT DEFAULT '',
            created_at TEXT NOT NULL
        )""",
    """CREATE TABLE IF NOT EXISTS comment_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            thread_id TEXT,
            username TEXT,
            post_code TEXT,
            comment_text TEXT,
            spam_score REAL,
            is_format_valid INTEGER,
            created_at TEXT NOT NULL,
            UNIQUE(thread_id, username, post_code)
        )""",
    """CREATE TABLE IF NOT EXISTS automations (
            thread_id TEXT PRIMARY KEY,
            is_active INTEGER DEFAULT 0,
            group_name TEXT DEFAULT '',
            notify_username TEXT DEFAULT '',
            control_method TEXT DEFAULT 'all_members',
            updated_at TEXT DEFAULT ''
        )""",
    """CREATE INDEX IF NOT EXISTS idx_comment_history_thread_user ON comment_history(thread_id, username)""",
    """CREATE INDEX IF NOT EXISTS idx_comment_history_user_created ON comment_history(username, created_at)""",
    """CREATE INDEX IF NOT EXISTS idx_audit_logs_action_created ON audit_logs(action, created_at)""",
    """CREATE INDEX IF NOT EXISTS idx_exemptions_username ON exemptions(username)""",
    """CREATE INDEX IF NOT EXISTS idx_tokens_active_deleted ON tokens(is_active, deleted_at)""",
]


def init_schema(conn):
    reference = sqlite3.connect(':memory:')
    try:
        for sql in STATEMENTS:
            reference.execute(sql)
        conn.execute('SAVEPOINT schema_upgrade')
        try:
            for (table,) in reference.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"):
                expected = reference.execute(f'PRAGMA table_info("{table}")').fetchall()
                actual = {row[1]: row for row in conn.execute(f'PRAGMA table_info("{table}")')}
                if not actual:
                    sql = reference.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchone()[0]
                    conn.execute(sql)
                    continue
                for _, name, kind, required, default, primary in expected:
                    if name in actual:
                        if primary and not actual[name][5]:
                            raise ValueError(f'{table}.{name}: primary key incompatible; data unchanged')
                        continue
                    if primary:
                        raise ValueError(f'{table}.{name}: primary key missing; data unchanged')
                    # Existing records retain every original value; only new fields get defaults.
                    if required and default is None:
                        default = "''" if kind == 'TEXT' else '0'
                    definition = kind + (' NOT NULL' if required else '')
                    if default is not None:
                        definition += ' DEFAULT ' + default
                    conn.execute(f'ALTER TABLE "{table}" ADD COLUMN "{name}" {definition}')
                # Unique constraints are required by the application's upserts.
                for index in reference.execute(f'PRAGMA index_list("{table}")').fetchall():
                    if not index[2] or index[3] == 'pk':
                        continue
                    columns = [row[2] for row in reference.execute(f'PRAGMA index_info("{index[1]}")')]
                    quoted = ', '.join('"' + column + '"' for column in columns)
                    conn.execute(f'CREATE UNIQUE INDEX IF NOT EXISTS "upgrade_{table}_{"_".join(columns)}" ON "{table}" ({quoted})')
            for sql in STATEMENTS:
                if sql.startswith('CREATE INDEX'):
                    conn.execute(sql)
            conn.execute('RELEASE SAVEPOINT schema_upgrade')
        except BaseException:
            conn.execute('ROLLBACK TO SAVEPOINT schema_upgrade')
            conn.execute('RELEASE SAVEPOINT schema_upgrade')
            raise
    finally:
        reference.close()
