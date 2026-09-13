import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch
from scripts import pythonanywhere_setup as setup


class FakeAPI:
    def __init__(self):
        self.calls=[]
        self.mappings=[]
        self.fail_patch=False

    def call(self,method,path,data=None):
        self.calls.append((method,path,data))
        if method=='GET' and path.endswith('static_files/'):
            return [dict(item) for item in self.mappings]
        if method=='PATCH' and self.fail_patch:
            self.fail_patch=False
            raise setup.SetupError('Simulated connection error')
        if method=='POST' and path.endswith('static_files/'):
            item={'id':7,**data};self.mappings.append(item);return item
        if method=='PATCH' and '/static_files/' in path:
            self.mappings[0].update(data)


class SetupTests(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup)
        self.root=Path(temporary.name).resolve()

    def test_sqlite_backup_preserves_unicode_null_and_existing_file(self):
        source=self.root/'app.db';target=self.root/'backup.db'
        with sqlite3.connect(source) as conn:
            conn.execute('CREATE TABLE records(id INTEGER PRIMARY KEY, text TEXT)')
            conn.executemany('INSERT INTO records VALUES (?,?)',[(1,'yorum ❤️'),(2,None)])
        conn.close()
        before=source.read_bytes()
        setup.backup_database(source,target)
        self.assertEqual(source.read_bytes(),before)
        with sqlite3.connect(target) as conn:
            self.assertEqual(conn.execute('SELECT * FROM records').fetchall(),[(1,'yorum ❤️'),(2,None)])
        conn.close()

    def test_database_selection_preserves_wsgi_and_rejects_ambiguity(self):
        for name in ('app.db','app-sqlite.db'):(self.root/name).touch()
        with self.assertRaises(setup.SetupError):setup.select_database(self.root)
        self.assertEqual(setup.select_database(self.root,previous={'APP_DB_FILE':str(self.root/'app-sqlite.db')}),self.root/'app-sqlite.db')
        with self.assertRaises(setup.SetupError):setup.select_database(self.root,previous={'APP_DB_FILE':str(self.root/'missing.db')})

    def test_wsgi_round_trip_preserves_secrets_and_database(self):
        previous=setup.wsgi_environment("import os\nos.environ['APP_DB_FILE']='/home/test/app.db'\nos.environ.setdefault('ADMIN_PASSWORD','test-only')")
        text=setup.make_wsgi(self.root,previous['APP_DB_FILE'],previous)
        compile(text,'wsgi','exec')
        self.assertEqual(setup.wsgi_environment(text),previous)
        self.assertIn(repr(str(self.root)),text)

    def test_dynamic_wsgi_settings_are_not_executed_or_overwritten(self):
        with self.assertRaises(setup.SetupError):
            setup.wsgi_environment("import os\nos.environ['APP_DB_FILE']=get_database()")

    def test_existing_non_application_directory_is_never_replaced(self):
        data=self.root/'important.txt';data.write_text('keep')
        with self.assertRaises(setup.SetupError):setup.ensure_project(self.root)
        self.assertEqual(data.read_text(),'keep')

    def test_web_configuration_can_be_repeated_without_duplicate_mapping(self):
        api=FakeAPI();wsgi=self.root/'wsgi.py';backup=self.root/'backup'
        previous={'APP_DB_FILE':str(self.root/'app.db')}
        args=(api,self.root,'test.pythonanywhere.com','3.13',self.root/'.venv',wsgi,backup)
        setup.configure(*args,None,previous)
        existing={'source_directory':str(self.root),'virtualenv_path':str(self.root/'.venv'),'force_https':True}
        setup.configure(*args,existing,previous)
        self.assertEqual(sum(m=='POST' and p=='webapps/' for m,p,d in api.calls),1)
        self.assertEqual(len(api.mappings),1)
        self.assertEqual(setup.wsgi_environment(wsgi.read_text())['APP_DB_FILE'],previous['APP_DB_FILE'])
        self.assertFalse(any('always_on' in p or 'schedule' in p or 'databases/mysql' in p for m,p,d in api.calls))

    def test_config_failure_restores_old_wsgi_without_touching_database(self):
        api=FakeAPI();api.fail_patch=True
        wsgi=self.root/'wsgi.py';wsgi.write_text('# old WSGI\n')
        db=self.root/'app.db';db.write_bytes(b'untouched')
        existing={'source_directory':'/old','virtualenv_path':'/old/env','force_https':False}
        with self.assertRaises(setup.SetupError):
            setup.configure(api,self.root,'test.pythonanywhere.com','3.13',self.root/'.venv',wsgi,self.root/'backup',existing,{'APP_DB_FILE':str(db)})
        self.assertEqual(wsgi.read_text(),'# old WSGI\n')
        self.assertEqual(db.read_bytes(),b'untouched')

    def test_runtime_preserves_existing_keys_and_uses_selected_database(self):
        (self.root/'.venv/bin').mkdir(parents=True)
        (self.root/'.venv/bin/python').touch()
        for name in ('secret.key','admin_password.txt'):(self.root/name).write_text('preserve-test-value')
        db=self.root/'app.db';db.touch()
        with patch.object(setup.subprocess,'check_output',return_value='3.13\n'),patch.object(setup,'command') as command:
            setup.prepare_runtime(self.root,'python3.13','3.13',db,{})
        self.assertEqual((self.root/'secret.key').read_text(),'preserve-test-value')
        self.assertEqual((self.root/'admin_password.txt').read_text(),'preserve-test-value')
        self.assertEqual(command.call_args.kwargs['env']['APP_DB_FILE'],str(db))
        self.assertEqual(command.call_count,3)

    def test_runtime_version_mismatch_stops_before_install(self):
        (self.root/'.venv/bin').mkdir(parents=True);(self.root/'.venv/bin/python').touch()
        with patch.object(setup.subprocess,'check_output',return_value='3.10\n'),patch.object(setup,'command') as command:
            with self.assertRaises(setup.SetupError):
                setup.prepare_runtime(self.root,'python3.13','3.13',self.root/'app.db',{})
        command.assert_not_called()

    def test_state_file_is_used_without_guessing(self):
        database=self.root/'custom.sqlite';database.touch()
        (self.root/setup.STATE_FILE).write_text(json.dumps({'database':str(database)}))
        self.assertEqual(setup.select_database(self.root),database)

    def test_active_job_prevents_installation_backup_and_reload(self):
        import time
        database=self.root/'active.db'
        with sqlite3.connect(database) as conn:
            conn.execute('CREATE TABLE jobs(state TEXT, lease_until REAL)')
            conn.execute('INSERT INTO jobs VALUES (?,?)',('running',time.time()+120))
        conn.close()
        with self.assertRaises(setup.SetupError):setup.backup_database(database,self.root/'backup.db')
        self.assertFalse((self.root/'backup.db').exists())

    def test_bad_state_and_missing_explicit_file_do_not_hide_existing_data(self):
        (self.root/setup.STATE_FILE).write_text('{"database":null}')
        with self.assertRaises(setup.SetupError):setup.select_database(self.root)
        (self.root/'app.db').touch()
        with self.assertRaises(setup.SetupError):setup.select_database(self.root,str(self.root/'typo.db'))

class CodeUpdateTests(unittest.TestCase):
    def test_update_preserves_data_and_restores_code(self):
        with tempfile.TemporaryDirectory() as root:
            project = Path(root).resolve() / 'project'; project.mkdir()
            backup = Path(root) / 'backup'; backup.mkdir()
            original = {'flask_app.py': 'old', 'requirements.txt': '', 'obsolete.py': 'old module',
                        'app.db': 'database', 'tokens.json': 'credentials', 'secret.key': 'secret',
                        'custom.txt': 'custom', 'untracked.py': 'local extension'}
            for name, value in original.items(): (project / name).write_text(value)
            (project / setup.STATE_FILE).write_text(json.dumps({'managed_files': ['obsolete.py', 'app.db', '../outside.py']}))
            def clone(args, **kwargs):
                target = Path(args[-1]); (target / 'app_core').mkdir(parents=True)
                for name in ('flask_app.py', 'requirements.txt', 'app_core/sqlite_schema.py'):
                    (target / name).write_text('new')
            with patch.object(setup, 'command', side_effect=clone), patch.object(setup.subprocess, 'check_output', return_value=b'flask_app.py\0requirements.txt\0app_core/sqlite_schema.py\0'):
                files = setup.ensure_project(project, backup)
            self.assertEqual((project / 'flask_app.py').read_text(), 'new')
            self.assertFalse((project / 'obsolete.py').exists())
            for name in ('app.db','tokens.json','secret.key','custom.txt','untracked.py'):
                self.assertEqual((project / name).read_text(), original[name])
            self.assertIn('app_core/sqlite_schema.py', files)
            setup.restore_code(project, backup)
            for name, value in original.items(): self.assertEqual((project / name).read_text(), value)
            self.assertFalse((project / 'app_core/sqlite_schema.py').exists())

    def test_failed_download_keeps_code(self):
        with tempfile.TemporaryDirectory() as root:
            project = Path(root).resolve(); backup = project / 'backup'; backup.mkdir()
            (project / 'flask_app.py').write_text('old')
            (project / 'requirements.txt').write_text('old')
            with patch.object(setup, 'command', side_effect=OSError('network unavailable')):
                with self.assertRaises(OSError): setup.ensure_project(project, backup)
            self.assertEqual((project / 'flask_app.py').read_text(), 'old')
