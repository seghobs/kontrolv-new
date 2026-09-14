"""Read-only installation smoke checks; never creates fake users or audit records."""

def verify(app):
    from app_core import storage
    conn=storage._connect()
    try:
        assert conn.execute('PRAGMA quick_check').fetchone()[0]=='ok', 'Veritabanı bütünlüğü'
        recent=conn.execute("SELECT id FROM jobs WHERE state='completed' AND kind='manual' ORDER BY created DESC LIMIT 1").fetchone()
    finally:conn.close()
    client=app.test_client()
    checks={}
    for path in ('/','/admin/login','/history','/tools'):
        assert client.get(path).status_code==200,path
        checks[path]='başarılı'
    assert client.get('/backups').status_code==403
    assert client.get('/admin').status_code in (302,303)
    with client.session_transaction() as session:session['admin_logged_in']=True
    for path in ('/admin','/backups','/group-rules','/trash'):
        assert client.get(path).status_code==200,path
        checks[path]='başarılı'
    if recent:
        for path in ('/result/'+recent['id'],'/followup/'+recent['id']):
            assert client.get(path).status_code==200,path
        checks['rapor']='başarılı'
    else:
        # Template rendering covers the empty-install report without writing a record.
        with app.test_request_context('/'):
            app.jinja_env.get_template('result.html').render(links=[],group=[],all_commented=[],user_missing_posts={},user_comments={},post_code='health-check',is_loading=False)
        checks['rapor']='boş kurulum şablonu başarılı; kayıtlı rapor yok'
    return checks
