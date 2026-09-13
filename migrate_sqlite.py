"""Export MySQL databases to verified SQLite files without modifying MySQL."""
from collections import Counter
from datetime import date, datetime
from decimal import Decimal
import base64
import hashlib
import json
from pathlib import Path
import re
import sqlite3


def quote(name):
    if not re.fullmatch(r'[A-Za-z0-9_$]+', name):
        raise ValueError('Unexpected identifier')
    return '`' + name + '`'


def canonical(value):
    if isinstance(value, bytes): return {'bytes':base64.b64encode(value).decode('ascii')}
    if isinstance(value, (date,datetime)): return value.isoformat()
    if isinstance(value,Decimal): return str(value)
    return value


def rows_digest(rows):
    lines=sorted(json.dumps([canonical(v) for v in row],ensure_ascii=False,separators=(',',':')) for row in rows)
    return hashlib.sha256('\n'.join(lines).encode()).hexdigest()


def export_database(raw, database, destination, application=False):
    path=Path(destination)
    if path.exists(): raise RuntimeError('Destination exists; refusing to overwrite')
    path.parent.mkdir(parents=True,exist_ok=True)
    target=sqlite3.connect(path)
    target.row_factory=sqlite3.Row
    if application:
        from app_core.storage import _init_db
        _init_db(target)
    report={}; archive={}
    try:
        with raw.cursor() as cur:
            cur.execute('USE '+quote(database))
            cur.execute('SHOW FULL TABLES')
            tables=[]
            for item in cur.fetchall():
                values=list(item.values())
                if values[1]!='BASE TABLE': raise RuntimeError('Non-table object requires manual migration')
                tables.append(values[0])
            target.execute('BEGIN IMMEDIATE')
            for table in tables:
                cur.execute('SHOW CREATE TABLE '+quote(table)); ddl=list(cur.fetchone().values())[1]
                cur.execute('SHOW COLUMNS FROM '+quote(table)); definitions=cur.fetchall()
                cur.execute('SELECT * FROM '+quote(table)); source=cur.fetchall()
                columns=[item['Field'] for item in definitions]
                values=[tuple(canonical(row[col]) if isinstance(row[col],(Decimal,date,datetime)) else row[col] for col in columns) for row in source]
                existing=[r[1] for r in target.execute('PRAGMA table_info('+quote(table)+')')]
                if not existing:
                    types=[]
                    for field in definitions:
                        kind=field['Type'].lower()
                        sqlite_type='INTEGER' if 'int' in kind else 'REAL' if any(t in kind for t in ('double','float','real')) else 'BLOB' if any(t in kind for t in ('blob','binary')) else 'TEXT'
                        types.append(quote(field['Field'])+' '+sqlite_type)
                    primary=[quote(f['Field']) for f in definitions if f['Key']=='PRI']
                    if primary: types.append('PRIMARY KEY ('+','.join(primary)+')')
                    target.execute('CREATE TABLE '+quote(table)+' ('+','.join(types)+')')
                    existing=columns
                if set(existing)!=set(columns): raise RuntimeError('Column mismatch: '+table)
                projection=','.join(quote(c) for c in columns)
                target.executemany('INSERT INTO '+quote(table)+' ('+projection+') VALUES ('+','.join('?' for _ in columns)+')',values)
                copied=[tuple(r) for r in target.execute('SELECT '+projection+' FROM '+quote(table))]
                if rows_digest(values)!=rows_digest(copied): raise RuntimeError('Verification failed: '+table)
                report[table]={'rows':len(values),'sha256':rows_digest(values)}
                archive[table]={'mysql_ddl':ddl,'columns':columns,'rows':[[canonical(v) for v in row] for row in values]}
            target.commit()
            if target.execute('PRAGMA integrity_check').fetchone()[0]!='ok': raise RuntimeError('SQLite integrity failure')
            if target.execute('PRAGMA foreign_key_check').fetchall(): raise RuntimeError('SQLite foreign key failure')
        path.with_suffix('.mysql-backup.json').write_text(json.dumps(archive,ensure_ascii=False),encoding='utf-8')
        path.with_suffix('.verification.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
        path.chmod(0o600)
        return report
    except BaseException:
        target.rollback()
        raise
    finally:
        target.close()
