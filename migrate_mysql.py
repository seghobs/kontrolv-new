"""Run inside PythonAnywhere. Copies a stopped SQLite app into empty MySQL tables.

Default action only checks connectivity. --source enables migration. The source
is backed up, never modified. Nonempty targets are refused, never overwritten.
"""
import argparse
from collections import Counter
from datetime import datetime
import json
from pathlib import Path
import re
import sqlite3
from app_core.mysql_backend import connect, init_schema


def quote(name):
    if not re.fullmatch(r'[a-z_][a-z_0-9]*', name):
        raise ValueError('Unexpected SQL identifier')
    return '`' + name + '`'


def migrate(source_path):
    path = Path(source_path).resolve(strict=True)
    backup = path.with_name(path.stem + '.before-mysql-' + datetime.now().strftime('%Y%m%d-%H%M%S-%f') + '.db')
    source = sqlite3.connect(path.as_uri() + '?mode=ro', uri=True)
    snapshot = sqlite3.connect(backup)
    try:
        source.backup(snapshot)
    finally:
        source.close()
    destination = None
    try:
        tables = [r[0] for r in snapshot.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")]
        if 'jobs' in tables and snapshot.execute("SELECT 1 FROM jobs WHERE state IN ('running','cancelling') LIMIT 1").fetchone():
            raise RuntimeError('Active jobs exist. Stop web/worker and resolve active jobs before migration.')
        destination = connect()
        init_schema(destination)
        with destination.raw.cursor() as cursor:
            cursor.execute('SHOW TABLES')
            available = {next(iter(row.values())) for row in cursor.fetchall()}
        if set(tables) - available:
            raise RuntimeError('Source contains unsupported tables; migration stopped without changing data.')
        destination.execute('BEGIN IMMEDIATE')
        for table in available - {'_app_write_lock'}:
            if destination.execute('SELECT COUNT(*) FROM ' + quote(table)).fetchone()[0]:
                raise RuntimeError('Target database is not empty; existing records will not be overwritten.')
        counts = {}
        for table in tables:
            rows = snapshot.execute('SELECT * FROM ' + quote(table))
            columns = [column[0] for column in rows.description]
            values = rows.fetchall()
            projection = ','.join(quote(column) for column in columns)
            query = 'INSERT INTO ' + quote(table) + '(' + projection + ') VALUES (' + ','.join('?' for _ in columns) + ')'
            for offset in range(0, len(values), 100):
                destination.executemany(query, values[offset:offset+100])
            copied = destination.execute('SELECT ' + projection + ' FROM ' + quote(table)).fetchall()
            expected = Counter(json.dumps(list(row), ensure_ascii=False) for row in values)
            actual = Counter(json.dumps([row[col] for col in columns], ensure_ascii=False) for row in copied)
            if expected != actual:
                raise RuntimeError('Data verification failed for ' + table + '; transaction rolled back.')
            counts[table] = len(values)
        destination.commit()
        print('Migration verified and committed. Rows per table:', counts)
        print('SQLite backup:', backup)
    except BaseException:
        if destination:
            destination.rollback()
        raise
    finally:
        snapshot.close()
        if destination:
            destination.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', help='SQLite database to copy into an EMPTY MySQL database')
    args = parser.parse_args()
    if args.source:
        migrate(args.source)
    else:
        conn = connect()
        try:
            row = conn.execute('SELECT DATABASE() AS db, VERSION() AS version').fetchone()
            print('MySQL connection OK:', row['db'], row['version'])
        finally:
            conn.close()

if __name__ == '__main__':
    main()
