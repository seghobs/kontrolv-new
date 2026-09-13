import unittest
from unittest.mock import MagicMock
from app_core.mysql_backend import translate, Connection, Result, Row


class MySQLAdapterTests(unittest.TestCase):
    def test_values_are_bound_and_literals_unchanged(self):
        sql = translate("SELECT key FROM key_value WHERE key=? AND value LIKE '100%?'", True)
        self.assertEqual(sql, "SELECT `key` FROM key_value WHERE `key`=%s AND value LIKE '100%%?'")

    def test_upserts_and_replace(self):
        self.assertEqual(translate('INSERT OR REPLACE INTO key_value(key,value) VALUES (?,?)', True),
                         'REPLACE INTO key_value(`key`,value) VALUES (%s,%s)')
        sql = translate('INSERT INTO tokens(username,token) VALUES (?,?) ON CONFLICT(username) DO UPDATE SET token=excluded.token', True)
        self.assertIn('ON DUPLICATE KEY UPDATE token=VALUES(token)', sql)
        self.assertIn('INSERT IGNORE', translate('INSERT OR IGNORE INTO exemptions VALUES (?,?)'))

    def test_glob_escapes_underscores(self):
        sql = translate("SELECT key FROM key_value WHERE key GLOB 'group_name_*'")
        self.assertIn("LIKE 'group!_name!_%' ESCAPE '!'", sql)

    def test_json_scalar_and_row_order(self):
        self.assertIn("JSON_UNQUOTE(JSON_EXTRACT(payload,'$.thread_id'))", translate("SELECT json_extract(payload,'$.thread_id') FROM jobs"))
        self.assertIn('added_at DESC, username DESC', translate('SELECT * FROM tokens ORDER BY rowid DESC'))
        row = Row(name='alice', count=2)
        self.assertEqual(row[0], row['name'])
        self.assertEqual(dict(row), {'name':'alice', 'count':2})
        self.assertEqual(dict([Row(state='queued', count=3)]), {'queued':3})

    def test_queue_lease_counts_matched_rows(self):
        # Unchanged heartbeat values still count as a successful matched UPDATE.
        from pymysql.constants import CLIENT
        from unittest.mock import patch
        from app_core.mysql_backend import connect
        with patch('app_core.mysql_backend.settings', return_value={}), patch('pymysql.connect') as factory:
            connect()
            self.assertEqual(factory.call_args.kwargs['client_flag'], CLIENT.FOUND_ROWS)

    def test_transaction_locks_before_read_and_commit_releases(self):
        raw = MagicMock()
        cursor = raw.cursor.return_value.__enter__.return_value
        cursor.fetchone.return_value = {'id':1}
        cursor.description = None
        conn = Connection(raw)
        conn.execute('BEGIN IMMEDIATE')
        raw.begin.assert_called_once()
        self.assertIn('FOR UPDATE', cursor.execute.call_args.args[0])
        conn.execute('UPDATE jobs SET progress=? WHERE id=?', (50,'id'))
        self.assertEqual(cursor.execute.call_args.args, ('UPDATE jobs SET progress=%s WHERE id=%s', (50,'id')))
        self.assertEqual(sum('FOR UPDATE' in call.args[0] for call in cursor.execute.call_args_list), 1)
        conn.commit()
        self.assertFalse(conn.write_locked)
        conn.execute('DELETE FROM jobs WHERE id=?', ('id',))
        self.assertEqual(sum('FOR UPDATE' in call.args[0] for call in cursor.execute.call_args_list), 2)
        conn.rollback()
        self.assertFalse(conn.write_locked)

    def test_transaction_fails_if_lock_schema_missing(self):
        raw=MagicMock()
        raw.cursor.return_value.__enter__.return_value.fetchone.return_value=None
        with self.assertRaises(RuntimeError):
            Connection(raw).execute('BEGIN IMMEDIATE')

    def test_boolean_json_values(self):
        cursor=MagicMock(description=True, rowcount=2, lastrowid=None)
        cursor.fetchall.return_value=[{'check_likes':'false'},{'check_likes':'true'}]
        result=Result(cursor)
        self.assertEqual(result.fetchone()['check_likes'],0)
        self.assertEqual(result.fetchone()['check_likes'],1)
        self.assertIsNone(result.fetchone())
