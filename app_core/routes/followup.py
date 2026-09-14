"""Themed follow-up screens. Sensitive settings and backups require admin login."""
import io
import json
import time
import uuid
import zipfile
from pathlib import Path
from xml.etree.ElementTree import Element, SubElement, tostring
from flask import Blueprint, render_template, request, session, abort, redirect, jsonify, send_file
from app_core import jobs, storage
from app_core import followup as service

bp = Blueprint('followup', __name__)


def admin():
    if not session.get('admin_logged_in'): abort(403)


def completed(identifier):
    job = jobs.get_job(identifier)
    if not job or job['state'] != 'completed': abort(404)
    return job


@bp.get('/followup/<identifier>')
def report(identifier):
    job = completed(identifier)
    result = job['result'] or {}
    previous = jobs.get_job(job['parent_id']) if job['parent_id'] else None
    delta = service.changes(previous['result'] or {}, result) if previous else []
    resolved = {u for row in delta for u in row['resolved']}
    notes = service.read('notes:' + identifier, {})
    return render_template('followup.html', job=job, result=result, delta=delta, resolved=len(resolved), notes=notes)


@bp.post('/followup/<identifier>/note')
def note(identifier):
    completed(identifier)
    text = request.form.get('note','').strip()
    url = request.form.get('url','')
    if len(text)>2000: abort(400)
    job = completed(identifier)
    if url not in {p['post_link'] for p in job['result'].get('links',[])}: abort(400)
    # Merge under one lock so two edits to different posts cannot discard each other.
    with jobs.transaction() as conn:
        key='notes:'+identifier
        row=conn.execute('SELECT value FROM key_value WHERE key=?',(key,)).fetchone()
        notes=json.loads(row['value']) if row else {}
        notes[url]=dict(text=text, time=time.time())
        conn.execute('INSERT INTO key_value(key,value) VALUES (?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value',(key,json.dumps(notes)))
    return redirect('/followup/'+identifier)


@bp.get('/members/<username>')
def member(username):
    days = request.args.get('days',7,type=int)
    if days not in (1,7,30):abort(400)
    return render_template('member_tracking.html', username=username, days=days, records=service.member_history(username,days))


@bp.route('/group-rules', methods=['GET','POST'])
def group_rules():
    admin()
    groups=storage.load_group_names()
    tid=request.values.get('thread_id') or next(iter(groups),'')
    if request.method=='POST':
        if tid not in groups:abort(400)
        try:
            joined={}
            for line in request.form.get('joined','').splitlines():
                if line.strip():
                    user,date=line.split();joined[user]=date
            leave=[]
            for line in request.form.get('leave','').splitlines():
                if line.strip():
                    user,start,end=line.split();leave.append(dict(username=user,start=start,end=end))
            rules=service.validate_rules(dict(skip_owner='skip_owner' in request.form, require_emoji='require_emoji' in request.form,
                min_words=request.form.get('min_words',2), grace_hours=request.form.get('grace_hours',0),mode=request.form.get('mode','selected'),
                exempt=request.form.get('exempt','').split(),excluded=request.form.get('excluded','').splitlines(), joined=joined,leave=leave))
        except (ValueError,KeyError,TypeError):return 'Ayar biçimi geçersiz; hiçbir değişiklik kaydedilmedi.',400
        service.write('rules:'+tid,rules)
        return redirect('/group-rules?thread_id='+tid)
    return render_template('group_rules.html',groups=groups,tid=tid,rules=service.rules_for(tid),diff=service.read('member-diff:'+tid,{}))


@bp.post('/group-rules/<tid>/delete')
def delete_rules(tid):
    admin()
    move_to_trash('rules:'+tid, 'Grup kuralları '+tid)
    return redirect('/group-rules')


def move_to_trash(key, label):
    with jobs.transaction() as conn:
        row=conn.execute('SELECT value FROM key_value WHERE key=?',(key,)).fetchone()
        if row:
            value=dict(key=key,label=label,value=row['value'],expires=time.time()+30*86400)
            conn.execute('INSERT INTO key_value(key,value) VALUES (?,?)',('trash:'+uuid.uuid4().hex,json.dumps(value)))
            conn.execute('DELETE FROM key_value WHERE key=?',(key,))


@bp.get('/trash')
def trash():
    admin()
    conn=storage._connect()
    try:
        items=[]
        for r in conn.execute("SELECT key,value FROM key_value WHERE key LIKE 'trash:%'"):
            value=json.loads(r['value'])
            if value['expires']>=time.time():items.append(dict(id=r['key'][6:],**value))
    finally:conn.close()
    return render_template('trash.html',items=items)


@bp.post('/trash/<identifier>/restore')
def restore(identifier):
    admin()
    with jobs.transaction() as conn:
        row=conn.execute('SELECT value FROM key_value WHERE key=?',('trash:'+identifier,)).fetchone()
        if not row:abort(404)
        item=json.loads(row['value'])
        if item['expires']<time.time():abort(409)
        if item['key'].startswith('automation:'):
            value=json.loads(item['value'])
            if conn.execute('SELECT 1 FROM automations WHERE thread_id=?',(value['thread_id'],)).fetchone():abort(409)
            conn.execute('INSERT INTO automations(thread_id,is_active,group_name,notify_username,control_method,updated_at) VALUES (?,?,?,?,?,?)',
                         tuple(value[k] for k in ('thread_id','is_active','group_name','notify_username','control_method','updated_at')))
        else:
            if conn.execute('SELECT 1 FROM key_value WHERE key=?',(item['key'],)).fetchone():abort(409)
            conn.execute('INSERT INTO key_value(key,value) VALUES (?,?)',(item['key'],item['value']))
        conn.execute('DELETE FROM key_value WHERE key=?',('trash:'+identifier,))
    return redirect('/trash')


BACKUP_ROOT = Path.home()/'.kontrol-backups'


def backups():
    root=BACKUP_ROOT.resolve()
    return [p for p in sorted(root.glob('*/database.sqlite'),reverse=True) if not p.is_symlink() and p.resolve().is_relative_to(root)]


@bp.get('/backups')
def backup_page():
    admin()
    return render_template('backups.html',items=[dict(name=p.parent.name,size=p.stat().st_size) for p in backups()])


@bp.get('/backups/<name>/download')
def download_backup(name):
    admin()
    path=next((p for p in backups() if p.parent.name==name),None)
    if path is None:abort(404)
    return send_file(path,as_attachment=True,download_name=name+'.sqlite')


@bp.get('/followup/<identifier>/export.xlsx')
def export(identifier):
    job=completed(identifier);result=job['result'] or {}
    posts=result.get('links',[])
    rows=[['Üye']+[p['post_link'] for p in posts]]
    for user in sorted(result.get('group',[])):
        rows.append([user]+['Doğrulanamadı' if p.get('error') or user in p.get('unknown_members',[]) else ('Muaf' if user in p.get('excluded_members',{}) else ('Eksik' if user in p.get('eksikler',[]) else ('Tamamlandı' if user in p.get('commenters',[]) else 'Değerlendirilmedi'))) for p in posts])
    return send_file(xlsx(rows,'Beğeni' if result.get('check_likes') else 'Yorum'),as_attachment=True,download_name='denetim.xlsx',mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')


def xlsx(rows, name):
    # Inline string cells keep user content literal (including leading =, +, @).
    ns='http://schemas.openxmlformats.org/spreadsheetml/2006/main'
    sheet=Element('worksheet',xmlns=ns); data=SubElement(sheet,'sheetData')
    for values in rows:
        row=SubElement(data,'row')
        for value in values:
            cell=SubElement(row,'c',t='inlineStr');SubElement(SubElement(cell,'is'),'t').text=str(value)
    stream=io.BytesIO()
    with zipfile.ZipFile(stream,'w',zipfile.ZIP_DEFLATED) as archive:
        archive.writestr('[Content_Types].xml','<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/><Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/></Types>')
        archive.writestr('_rels/.rels','<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>')
        archive.writestr('xl/workbook.xml',f'<workbook xmlns="{ns}" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="{name}" sheetId="1" r:id="rId1"/></sheets></workbook>')
        archive.writestr('xl/_rels/workbook.xml.rels','<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/></Relationships>')
        archive.writestr('xl/worksheets/sheet1.xml',tostring(sheet,encoding='utf-8'))
    stream.seek(0);return stream
