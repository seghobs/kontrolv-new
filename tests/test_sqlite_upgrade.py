import sqlite3
import tempfile
import unittest
from pathlib import Path
from app_core.sqlite_schema import init_schema


class UpgradeTests(unittest.TestCase):
    def test_legacy_records_survive_repeated_in_place_upgrade(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / 'existing.db'
            conn = sqlite3.connect(path)
            try:
                conn.executescript("""
                    CREATE TABLE tokens(username TEXT PRIMARY KEY, token TEXT, password TEXT);
                    INSERT INTO tokens VALUES ('member', 'saved-token', 'saved-password');
                    CREATE TABLE jobs(id TEXT PRIMARY KEY, result TEXT);
                    INSERT INTO jobs VALUES ('audit', '{"comments": ["hello"]}');
                    CREATE TABLE custom_records(value BLOB);
                    INSERT INTO custom_records VALUES (X'0001');
                """)
                inode = path.stat().st_ino
                before = {t: conn.execute('SELECT * FROM ' + t).fetchall() for t in ('tokens','jobs','custom_records')}
                for _ in range(2):
                    init_schema(conn)
                    self.assertEqual(conn.execute('SELECT username,token,password FROM tokens').fetchall(), before['tokens'])
                    self.assertEqual(conn.execute('SELECT id,result FROM jobs').fetchall(), before['jobs'])
                    self.assertEqual(conn.execute('SELECT * FROM custom_records').fetchall(), before['custom_records'])
                    self.assertEqual(conn.execute('PRAGMA integrity_check').fetchone()[0], 'ok')
                    self.assertEqual(path.stat().st_ino, inode)
                self.assertIn('deleted_at', {r[1] for r in conn.execute('PRAGMA table_info(tokens)')})
            finally:
                conn.close()

    def test_incompatible_key_rolls_back_all_schema_changes(self):
        conn = sqlite3.connect(':memory:')
        try:
            conn.execute('CREATE TABLE tokens(token TEXT)')
            conn.execute("INSERT INTO tokens VALUES ('keep')")
            conn.commit()
            before = conn.execute('SELECT sql FROM sqlite_master').fetchall()
            with self.assertRaises(ValueError): init_schema(conn)
            self.assertEqual(conn.execute('SELECT sql FROM sqlite_master').fetchall(), before)
            self.assertEqual(conn.execute('SELECT * FROM tokens').fetchall(), [('keep',)])
        finally:
            conn.close()

    def test_duplicate_legacy_unique_values_fail_without_deleting_rows(self):
        conn = sqlite3.connect(':memory:')
        try:
            conn.executescript("CREATE TABLE global_exemptions(id INTEGER PRIMARY KEY, username TEXT); INSERT INTO global_exemptions VALUES(1,'same'),(2,'same');")
            with self.assertRaises(sqlite3.IntegrityError): init_schema(conn)
            self.assertEqual(conn.execute('SELECT * FROM global_exemptions').fetchall(), [(1,'same'),(2,'same')])
            self.assertEqual(len(conn.execute('PRAGMA table_info(global_exemptions)').fetchall()), 2)
        finally:
            conn.close()
