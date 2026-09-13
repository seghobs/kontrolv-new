import unittest,tempfile,sqlite3
from contextlib import closing
from pathlib import Path
from migrate_sqlite import export_database

class Cursor:
    def __enter__(self): return self
    def __exit__(self,*a): pass
    def execute(self,sql):
        if sql.startswith('SHOW FULL TABLES'): self.rows=[{'name':'sample','type':'BASE TABLE'}]
        elif sql.startswith('SHOW CREATE'): self.rows=[{'name':'sample','ddl':'CREATE TABLE sample (id INT PRIMARY KEY, text TEXT)'}]
        elif sql.startswith('SHOW COLUMNS'): self.rows=[{'Field':'id','Type':'int','Key':'PRI'},{'Field':'text','Type':'text','Key':''}]
        elif sql.startswith('SELECT'): self.rows=[{'id':41,'text':'Türkçe 🎉'},{'id':50,'text':None}]
        else: self.rows=[]
    def fetchall(self): return self.rows
    def fetchone(self): return self.rows[0]
class Source:
    def cursor(self): return Cursor()
class MigrationTests(unittest.TestCase):
    def test_preserves_ids_unicode_nulls_and_verifies(self):
        with tempfile.TemporaryDirectory() as directory:
            target=Path(directory)/'new.db'
            report=export_database(Source(),'example',target)
            self.assertEqual(report['sample']['rows'],2)
            with closing(sqlite3.connect(target)) as db:
                self.assertEqual(db.execute('SELECT * FROM sample ORDER BY id').fetchall(),[(41,'Türkçe 🎉'),(50,None)])
            self.assertTrue(target.with_suffix('.mysql-backup.json').exists())
            with self.assertRaises(RuntimeError): export_database(Source(),'example',target)
