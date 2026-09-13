"""MySQL adapter for the application's existing parameterized repository queries.

All writers take the same InnoDB row lock, preserving SQLite's single-writer
semantics for queue claims, deduplication and read/modify/write operations.
No SQL values are interpolated by this module.
"""
import json
import os
import re
from pathlib import Path


def settings():
    path = Path(os.getenv('MYSQL_CONFIG_FILE', Path(__file__).resolve().parent.parent / '.mysql.json'))
    saved = json.loads(path.read_text(encoding='utf-8')) if path.exists() else {}
    def value(name, default=None):
        return os.getenv('MYSQL_' + name.upper(), saved.get(name, default))
    config = dict(host=value('host', 'kontrolyeni.mysql.pythonanywhere-services.com'),
                  user=value('user', 'kontrolyeni'), password=value('password'),
                  database=value('database', 'kontrolyeni$kontrolyeni'), port=int(value('port', 3306)))
    if not config['password']:
        raise RuntimeError('MySQL password is missing: set MYSQL_PASSWORD or .mysql.json')
    return config


def translate(sql, parameters=False):
    # The repository only uses literal prefix GLOB patterns. Escape SQL LIKE's
    # underscore wildcard to preserve SQLite GLOB semantics.
    def glob(match):
        pattern = match[1].replace('!', '!!').replace('%', '!%').replace('_', '!_').replace('*', '%').replace('?', '_')
        return "LIKE '" + pattern + "' ESCAPE '!'"
    sql = re.sub(r"GLOB '([^']*)'", glob, sql, flags=re.I)
    sql = re.sub(r"json_extract\((\w+),\s*('(?:[^']|'')*')\)", r'JSON_UNQUOTE(JSON_EXTRACT(\1,\2))', sql, flags=re.I)
    # Transform only SQL code, never quoted string literals.
    pieces = re.split(r"('(?:''|[^'])*')", sql)
    for index in range(0, len(pieces), 2):
        part = pieces[index]
        part = re.sub(r'\bINSERT OR REPLACE\b', 'REPLACE', part, flags=re.I)
        part = re.sub(r'\bINSERT OR IGNORE\b', 'INSERT IGNORE', part, flags=re.I)
        part = re.sub(r'ON CONFLICT\(\w+\) DO UPDATE SET', 'ON DUPLICATE KEY UPDATE', part, flags=re.I)
        part = re.sub(r'\bexcluded\.(\w+)', r'VALUES(\1)', part, flags=re.I)
        part = re.sub(r'\browid\s+DESC', 'added_at DESC, username DESC', part, flags=re.I)
        part = re.sub(r'(?<!`)\bkey\b(?!`)', '`key`', part, flags=re.I)
        # The KEY keyword in ON DUPLICATE KEY UPDATE is not a column.
        part = part.replace('DUPLICATE `key` UPDATE', 'DUPLICATE KEY UPDATE')
        pieces[index] = part
    if parameters:
        pieces = [part.replace('%', '%%') for part in pieces]
        for index in range(0, len(pieces), 2):
            pieces[index] = pieces[index].replace('?', '%s')
    return ''.join(pieces)


class Row(dict):
    def __iter__(self):
        # sqlite3.Row iterates values; dict(row) still uses this mapping's keys.
        return iter(self.values())

    def __getitem__(self, key):
        return list(self.values())[key] if isinstance(key, int) else super().__getitem__(key)


class Result:
    def __init__(self, cursor):
        self.rowcount = cursor.rowcount
        self.lastrowid = cursor.lastrowid
        self.rows = [Row(row) for row in cursor.fetchall()] if cursor.description else []
        # SQLite json_extract returns booleans as integers.
        for row in self.rows:
            if row.get('check_likes') in ('true', 'false'):
                row['check_likes'] = int(row['check_likes'] == 'true')
        self.position = 0

    def fetchone(self):
        if self.position >= len(self.rows):
            return None
        row = self.rows[self.position]
        self.position += 1
        return row

    def fetchall(self):
        rows = self.rows[self.position:]
        self.position = len(self.rows)
        return rows

    def __iter__(self):
        return iter(self.fetchall())


class Connection:
    dialect = 'mysql'

    def __init__(self, raw):
        self.raw = raw
        self.write_locked = False

    def _lock_writer(self):
        if not self.write_locked:
            with self.raw.cursor() as cursor:
                cursor.execute('SELECT id FROM _app_write_lock WHERE id=1 FOR UPDATE')
                if cursor.fetchone() is None:
                    raise RuntimeError('MySQL schema is not initialized')
            self.write_locked = True

    def execute(self, sql, parameters=None):
        if sql.strip().upper() == 'BEGIN IMMEDIATE':
            self.raw.begin()
            self._lock_writer()
            return None
        if re.match(r'\s*(INSERT|UPDATE|DELETE|REPLACE)\b', sql, re.I):
            self._lock_writer()
        with self.raw.cursor() as cursor:
            cursor.execute(translate(sql, parameters is not None), parameters)
            return Result(cursor)

    def executemany(self, sql, parameters):
        self._lock_writer()
        with self.raw.cursor() as cursor:
            cursor.executemany(translate(sql, True), parameters)
            return Result(cursor)

    def commit(self):
        self.raw.commit()
        self.write_locked = False

    def rollback(self):
        self.raw.rollback()
        self.write_locked = False

    def close(self):
        self.raw.close()  # Rolls back uncommitted work, releasing the row lock.


def connect():
    import pymysql
    from pymysql.constants import CLIENT
    raw = pymysql.connect(**settings(), charset='utf8mb4', autocommit=False,
                          cursorclass=pymysql.cursors.DictCursor, client_flag=CLIENT.FOUND_ROWS,
                          connect_timeout=10, read_timeout=30, write_timeout=30)
    with raw.cursor() as cursor:
        cursor.execute('SET SESSION TRANSACTION ISOLATION LEVEL READ COMMITTED')
        cursor.execute("SET SESSION sql_mode = 'STRICT_TRANS_TABLES,NO_ENGINE_SUBSTITUTION'")
    return Connection(raw)


def init_schema(conn):
    # DDL commits implicitly in MySQL; keep it outside all data transactions.
    schema = Path(__file__).with_name('mysql_schema.sql').read_text(encoding='utf-8')
    with conn.raw.cursor() as cursor:
        for statement in schema.split(';'):
            if statement.strip():
                cursor.execute(statement)
        cursor.execute('CREATE TABLE IF NOT EXISTS _app_write_lock (id INTEGER PRIMARY KEY) ENGINE=InnoDB')
        cursor.execute('INSERT IGNORE INTO _app_write_lock(id) VALUES (1)')
    conn.commit()
