"""Data-preserving classic/free PythonAnywhere installer; standard library only."""
import argparse
import ast
from contextlib import closing
from datetime import datetime
import getpass
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

REPOSITORY = 'https://github.com/seghobs/kontrolv-new.git'
STATE_FILE = '.pythonanywhere-setup.json'


class SetupError(RuntimeError):
    pass


class PythonAnywhere:
    def __init__(self, host, username, token):
        self.base = f'https://{host}/api/v0/user/{username}/'
        self.token = token

    def call(self, method, path, data=None):
        request = Request(self.base + path, data=urlencode(data).encode() if data is not None else None,
                          method=method, headers={'Authorization':'Token ' + self.token})
        try:
            with urlopen(request, timeout=60) as response:
                body = response.read()
                return json.loads(body) if body else None
        except HTTPError as error:
            raise SetupError(f'PythonAnywhere API: {path} (HTTP {error.code}). Tokeni ve hesap sınırlarını kontrol edin.') from None
        except (URLError, TimeoutError):
            raise SetupError(f'PythonAnywhere bağlantısı tamamlanamadı: {path}. Yeniden çalıştırabilirsiniz.') from None


def atomic_text(path, text):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=path.parent, delete=False) as handle:
        temporary = Path(handle.name)
        handle.write(text)
    try:
        temporary.chmod(0o600)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def wsgi_environment(text):
    """Never execute the previous WSGI file to inspect configuration."""
    values = {}
    allowed = {'APP_DB_FILE','ADMIN_PASSWORD','SECRET_KEY'}
    try:
        tree = ast.parse(text)
    except SyntaxError:
        raise SetupError('Mevcut WSGI dosyası okunamadı; dosya değiştirilmedi.') from None
    for node in ast.walk(tree):
        pairs = []
        if isinstance(node, ast.Assign):
            pairs = [(t.slice, node.value) for t in node.targets if isinstance(t, ast.Subscript) and ast.unparse(t.value) == 'os.environ']
        elif isinstance(node, ast.Call) and ast.unparse(node.func) == 'os.environ.setdefault' and len(node.args) >= 2:
            pairs = [node.args[:2]]
        elif isinstance(node, ast.Call) and ast.unparse(node.func) == 'os.environ.update' and node.args and isinstance(node.args[0], ast.Dict):
            pairs = zip(node.args[0].keys, node.args[0].values)
        for key, value in pairs:
            if isinstance(key, ast.Constant) and key.value in allowed:
                if not isinstance(value, ast.Constant) or not isinstance(value.value, str):
                    raise SetupError(f'WSGI içindeki {key.value} dinamik tanımlı; otomatik değişiklik yapılmadı.')
                values[key.value] = value.value
    return values


def select_database(project, explicit=None, previous=None):
    candidates = sorted(path for path in project.glob('*')
                        if path.is_file() and path.suffix.lower() in {'.db', '.db3', '.sqlite', '.sqlite3'})
    configured = explicit or (previous or {}).get('APP_DB_FILE')
    if not configured and (project / STATE_FILE).exists():
        try:
            configured = json.loads((project / STATE_FILE).read_text(encoding='utf-8'))['database']
            if not isinstance(configured, str) or not configured:
                raise ValueError('missing database')
        except (ValueError, KeyError, TypeError):
            raise SetupError('Kayıtlı kurulum ayarı okunamadı. --database ile aktif dosyayı belirtin.') from None
    if configured:
        path = Path(configured).expanduser()
        path = (project / path).resolve() if not path.is_absolute() else path.resolve()
        if not path.exists() and not explicit:
            raise SetupError(f'Kayıtlı veritabanı bulunamadı: {path}. Boş veritabanı oluşturulmadı.')
        if not path.exists() and candidates:
            raise SetupError('Belirtilen veritabanı yok fakat mevcut veriler var. Dosya yolunu kontrol edin; boş veritabanına geçilmedi.')
        return path
    if len(candidates) > 1:
        raise SetupError('Birden çok veritabanı var. Aktif dosyayı --database /tam/yol ile belirtin; hiçbir dosya silinmedi.')
    return candidates[0] if candidates else project / 'app.db'


def backup_database(source, target):
    if not source.exists():
        return
    with closing(sqlite3.connect(source.as_uri() + '?mode=ro', uri=True, timeout=30)) as old:
        tables = {row[0] for row in old.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if 'jobs' in tables:
            columns = {row[1] for row in old.execute('PRAGMA table_info(jobs)')}
            if {'state','lease_until'} <= columns and old.execute("SELECT 1 FROM jobs WHERE state IN ('running','cancelling') AND lease_until>? LIMIT 1",(time.time(),)).fetchone():
                raise SetupError('Aktif denetim var. Tamamlandıktan sonra kurulumu tekrar çalıştırın; denetim durdurulmadı.')
        if old.execute('PRAGMA quick_check').fetchone()[0] != 'ok':
            raise SetupError('Veritabanı bütünlük kontrolü başarısız; kurulum durduruldu.')
        with closing(sqlite3.connect(target)) as backup:
            old.backup(backup)
            if backup.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
                raise SetupError('Veritabanı yedeği doğrulanamadı.')
    target.chmod(0o600)


def command(args, **kwargs):
    subprocess.run([str(arg) for arg in args], check=True, **kwargs)


def managed_code(name):
    path = Path(name)
    if path.is_absolute() or '..' in path.parts or not path.parts:
        return False
    if any(part.startswith('.') or part in ('uploads', 'data', 'backups', 'scratch', '__pycache__') for part in path.parts):
        return False
    return path.suffix.lower() in {'.py', '.html', '.css', '.js', '.mjs', '.cjs', '.sh', '.md', '.sql'} or name == 'requirements.txt'


def restore_code(project, backup):
    plan = json.loads((backup / 'code-plan.json').read_text(encoding='utf-8'))
    for name in plan['changed']:
        destination = project / name
        saved = backup / 'code' / name
        if saved.is_file():
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(saved, destination)
        else:
            destination.unlink(missing_ok=True)


def ensure_project(project, backup=None):
    existing = (project / 'flask_app.py').is_file() and (project / 'requirements.txt').is_file()
    if project.exists() and any(project.iterdir()) and not existing:
        raise SetupError('Hedef klasör boş değil ve uygulama bulunamadı. Başka klasörü --path ile belirtin.')
    if backup is None:
        raise SetupError('Kod güncellemesi için doğrulanmış yedek klasörü gerekli.')
    project.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='kontrol-download-', dir=project.parent) as temporary:
        checkout = Path(temporary) / 'source'
        command(['git','clone','--depth','1','--branch','main',REPOSITORY,checkout])
        tracked = subprocess.check_output(['git','-C',str(checkout),'ls-files','-z']).decode().split('\0')
        incoming = {name for name in tracked if managed_code(name)}
        if not {'flask_app.py','requirements.txt','app_core/sqlite_schema.py'} <= incoming:
            raise SetupError('İndirilen sürüm eksik; mevcut kod değiştirilmedi.')
        old = set()
        state = project / STATE_FILE
        if state.exists():
            old.update(json.loads(state.read_text(encoding='utf-8')).get('managed_files', []))
        if (project / '.git').exists():
            old.update(subprocess.check_output(['git','-C',str(project),'ls-files','-z']).decode().split('\0'))
        old = {name for name in old if managed_code(name)}
        changed = sorted(incoming | old)
        # Validate all paths before copying or removing anything. Never traverse symlinks.
        for name in changed:
            destination = project / name
            if destination.resolve() != project.resolve() / name or destination.is_symlink():
                raise SetupError('Kod yolunda sembolik bağlantı var; güncelleme durduruldu.')
            if destination.exists() and not destination.is_file():
                raise SetupError('Kod dosyası yerine klasör var; güncelleme durduruldu.')
        for name in incoming:
            if (checkout / name).is_symlink():
                raise SetupError('İndirilen kodda sembolik bağlantı var.')
        for name in changed:
            source = project / name
            if source.is_file():
                target = backup / 'code' / name
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, target)
        atomic_text(backup / 'code-plan.json', json.dumps({'changed': changed}))
        project.mkdir(parents=True, exist_ok=True)
        try:
            for name in incoming:
                destination = project / name
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(checkout / name, destination)
            for name in old - incoming:
                (project / name).unlink(missing_ok=True)
        except BaseException:
            restore_code(project, backup)
            raise
        return sorted(incoming)


def schema_preview(project, database):
    schema_file=project/'app_core'/'sqlite_schema.py'
    if not schema_file.exists():return ['Şema önizlemesi güncel kod indirildiğinde hazırlanacak.']
    tree=ast.parse(schema_file.read_text(encoding='utf-8-sig'))
    definition=next(node.value for node in tree.body if isinstance(node,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='STATEMENTS' for t in node.targets))
    statements=ast.literal_eval(definition)
    with closing(sqlite3.connect(':memory:')) as expected:
        for sql in statements:expected.execute(sql)
        actual=sqlite3.connect(database.as_uri()+'?mode=ro',uri=True) if database.exists() else sqlite3.connect(':memory:')
        with closing(actual):
            additions=[]
            for (table,) in expected.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"):
                old={row[1] for row in actual.execute(f'PRAGMA table_info("{table}")')}
                if not old:additions.append('Yeni tablo: '+table)
                else:
                    additions.extend('Yeni sütun: '+table+'.'+row[1] for row in expected.execute(f'PRAGMA table_info("{table}")') if row[1] not in old)
            return additions or ['Tablo ve sütunlar güncel.']


def make_wsgi(project, database, previous):
    env = {'APP_ENV':'prod','APP_DB_BACKEND':'sqlite','APP_DB_FILE':str(database),'SQLITE_JOURNAL_MODE':'DELETE'}
    env.update({k:v for k,v in previous.items() if k in ('ADMIN_PASSWORD','SECRET_KEY')})
    return ('# Generated by kontrolv-new setup.\nimport os\nimport sys\n'
            f'sys.path.insert(0, {str(project)!r})\nos.chdir({str(project)!r})\n'
            f'os.environ.update({env!r})\nfrom flask_app import app as application\n')


def prepare_runtime(project, executable, version, database, previous):
    environment = project / '.venv'
    python = environment / 'bin' / 'python'
    if python.exists():
        actual = subprocess.check_output([str(python),'-c','import sys;print("%s.%s"%sys.version_info[:2])'], text=True).strip()
        if actual != version:
            raise SetupError(f'.venv Python {actual} kullanıyor, web uygulaması {version}. Ortam değiştirilmedi.')
    elif environment.exists():
        raise SetupError('.venv var fakat tamamlanmamış; dosyalar korunarak kurulum durduruldu.')
    else:
        command([executable,'-m','venv',environment])
    command([python,'-m','pip','install','--disable-pip-version-check','-r',project / 'requirements.txt'])
    command([python,'-m','pip','check'])
    database.parent.mkdir(parents=True, exist_ok=True)
    for name in ('secret.key','admin_password.txt'):
        path = project / name
        if not path.exists():
            atomic_text(path, secrets.token_urlsafe(32) + '\n')
        path.chmod(0o600)
    env = {**os.environ, **previous, 'APP_DB_FILE':str(database),'APP_DB_BACKEND':'sqlite',
           'APP_ENV':'prod','SQLITE_JOURNAL_MODE':'DELETE'}
    command([python,'-c','from flask_app import app; from app_core.healthcheck import verify; print(verify(app))'], cwd=project, env=env)
    database.chmod(0o600)
    return environment


def configure(api, project, domain, version, environment, wsgi_path, backup, existing, previous):
    endpoint = f'webapps/{domain}/'
    old_wsgi = wsgi_path.read_text(encoding='utf-8') if wsgi_path.exists() else None
    mappings = api.call('GET',endpoint + 'static_files/') if existing else []
    if sum(item['url'] == '/static/' for item in mappings) > 1:
        raise SetupError('Birden çok /static/ eşlemesi var; otomatik değişiklik yapılmadı.')
    target = next((item for item in mappings if item['url'] == '/static/'),None)
    atomic_text(backup / 'web-config.json',json.dumps(existing or {},indent=2))
    atomic_text(backup / 'static-mappings.json',json.dumps(mappings,indent=2))
    if old_wsgi is not None:
        atomic_text(backup / 'previous_wsgi.py',old_wsgi)
    created_mapping = None
    try:
        if not existing:
            api.call('POST','webapps/',{'domain_name':domain,'python_version':'python'+version.replace('.','')})
        atomic_text(wsgi_path,make_wsgi(project,previous['APP_DB_FILE'],previous))
        api.call('PATCH',endpoint,{'source_directory':str(project),'virtualenv_path':str(environment),'force_https':'true'})
        if target:
            api.call('PATCH',endpoint+f'static_files/{target["id"]}/',{'url':'/static/','path':str(project/'static')})
        else:
            created_mapping = api.call('POST',endpoint+'static_files/',{'url':'/static/','path':str(project/'static')})
        api.call('POST',endpoint+'reload/')
    except Exception:
        # Never restore the database over concurrent user writes.
        if existing:
            try:
                if old_wsgi is not None:
                    atomic_text(wsgi_path,old_wsgi)
                api.call('PATCH',endpoint,{k:existing[k] for k in ('source_directory','virtualenv_path','force_https') if k in existing})
                if target:
                    api.call('PATCH',endpoint+f'static_files/{target["id"]}/',{'url':target['url'],'path':target['path']})
                elif created_mapping:
                    api.call('DELETE',endpoint+f'static_files/{created_mapping["id"]}/')
                api.call('POST',endpoint+'reload/')
            except Exception:
                print(f'Önceki yapılandırma geri yüklenemedi. Yedek: {backup}',file=sys.stderr)
        raise


def verify_site(domain):
    for _ in range(12):
        try:
            with urlopen(f'https://{domain}/',timeout=15) as response:
                if response.status == 200 and 'id="checkForm"' in response.read().decode('utf-8'):
                    return True
        except (URLError,TimeoutError):
            pass
        time.sleep(5)
    return False


def main(argv=None):
    parser = argparse.ArgumentParser(description='PythonAnywhere ücretsiz hesap için verileri koruyan otomatik kurulum.')
    local = Path(__file__).resolve().parent.parent
    parser.add_argument('--path',type=Path,default=local if (local/'flask_app.py').exists() else Path.home()/'mysite')
    parser.add_argument('--database',help='Kullanılacak SQLite dosyasının tam yolu.')
    parser.add_argument('--api-host',choices=['www.pythonanywhere.com','eu.pythonanywhere.com'],
                        default=os.getenv('PYTHONANYWHERE_SITE','www.pythonanywhere.com').removeprefix('https://').rstrip('/'))
    parser.add_argument('--check',action='store_true',help='Yalnız ön kontrol; dosya veya web ayarı değiştirmez.')
    args = parser.parse_args(argv)
    if sys.platform != 'linux' or not Path('/var/www').exists():
        raise SetupError('Bu betiği PythonAnywhere Bash konsolunda çalıştırın.')
    username = getpass.getuser()
    if not re.fullmatch(r'[A-Za-z0-9_-]+',username):
        raise SetupError('PythonAnywhere kullanıcı adı belirlenemedi.')
    token = os.getenv('API_TOKEN','').strip() or os.getenv('PYTHONANYWHERE_API_TOKEN','').strip()
    if not token and sys.stdin.isatty():
        token = getpass.getpass('PythonAnywhere API tokenı (gizli): ').strip()
    if not token:
        raise SetupError('API_TOKEN bulunamadı. Hesap > API token bölümünden token oluşturup yeni Bash konsolu açın.')
    if args.api_host not in ('www.pythonanywhere.com','eu.pythonanywhere.com'):
        raise SetupError('--api-host ile doğru API sunucusunu belirtin.')
    api = PythonAnywhere(args.api_host,username,token)
    domain = username + ('.eu.pythonanywhere.com' if args.api_host.startswith('eu.') else '.pythonanywhere.com')
    webapps = api.call('GET','webapps/')
    existing = next((app for app in webapps if app['domain_name'] == domain),None)
    if webapps and not existing:
        raise SetupError('Hesapta başka web uygulaması var; ücretsiz hesap sınırı nedeniyle değiştirilmedi.')
    project = args.path.expanduser().resolve()
    if existing and existing.get('source_directory') and Path(existing['source_directory']).resolve() != project:
        raise SetupError('Web uygulamasının klasörü farklı. Aynı klasörü --path ile belirtin.')
    if existing and existing.get('password_protection_enabled'):
        raise SetupError('Web uygulamasında site genelinde parola koruması var. Kurulum bu ayarı değiştirmedi; önce Web sekmesinde kapatın.')
    wsgi_path = Path('/var/www') / (domain.replace('.','_') + '_wsgi.py')
    previous = wsgi_environment(wsgi_path.read_text(encoding='utf-8')) if wsgi_path.exists() else {}
    for key in ('ADMIN_PASSWORD','SECRET_KEY'):
        if os.getenv(key):
            previous.setdefault(key,os.environ[key])
    database = select_database(project,args.database,previous)
    version = existing['python_version'] if existing else api.call('GET','default_python3_version/')['default_python3_version']
    if not re.fullmatch(r'3\.\d+',version) or tuple(map(int,version.split('.'))) < (3,10):
        raise SetupError('Python 3.10 veya üstü gerekli; web uygulamasının Python sürümünü güncelleyin.')
    executable = shutil.which('python'+version)
    if not executable:
        raise SetupError(f'Python {version} bu sistemde bulunamadı.')
    print(f'Hesap: {username} | Python: {version}\nProje: {project}\nSQLite: {database}',flush=True)
    print('Güncellenecek sürüm: GitHub main. Eksik SQLite sütunları ve tabloları yerinde eklenecek. Yedekler: ~/.kontrol-backups/',flush=True)
    if args.check:
        print('\n'.join(schema_preview(project,database)))
        print('Ön kontrol başarılı. Hiçbir dosya veya web ayarı değiştirilmedi.')
        return
    import fcntl
    with (Path.home()/'.kontrol-setup.lock').open('w') as lock:
        try:
            fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:
            raise SetupError('Başka bir kurulum çalışıyor; tamamlanmasını bekleyin.') from None
        backup = Path.home()/'.kontrol-backups'/(datetime.now().strftime('%Y%m%d-%H%M%S')+'-'+secrets.token_hex(3))
        backup.mkdir(parents=True,mode=0o700)
        backup.parent.chmod(0o700)
        backup_database(database,backup/'database.sqlite')
        for name in ('secret.key','admin_password.txt',STATE_FILE):
            if (project/name).exists():
                shutil.copy2(project/name,backup/name)
                (backup/name).chmod(0o600)
        print(f'Yedek hazır: {backup}',flush=True)
        managed_files = ensure_project(project, backup)
        try:
            print('\n'.join(schema_preview(project,database)),flush=True)
            environment = prepare_runtime(project,executable,version,database,previous)
            configure(api,project,domain,version,environment,wsgi_path,backup,existing,{**previous,'APP_DB_FILE':str(database)})
        except BaseException:
            restore_code(project, backup)
            if existing:
                try:
                    api.call('POST', f'webapps/{domain}/reload/')
                except Exception:
                    pass
            raise
        atomic_text(project/STATE_FILE,json.dumps({'domain':domain,'database':str(database),'backup':str(backup),'managed_files':managed_files},indent=2))
        if not verify_site(domain):
            raise SetupError('Canlı sayfa doğrulanamadı. PythonAnywhere hata günlüğünü kontrol edin; kurulum başarılı olarak işaretlenmedi.')
        print(f'Kurulum tamamlandı: https://{domain}\nYönetici şifresi dosyası: {project/"admin_password.txt"} (var olan WSGI şifre ayarı korunur).\nVeritabanı korundu; worker veya zamanlanmış görev kurulmadı.')


if __name__ == '__main__':
    try:
        main()
    except (SetupError,OSError,ValueError,subprocess.CalledProcessError) as error:
        print(f'Kurulum tamamlanamadı: {error}',file=sys.stderr)
        sys.exit(1)
