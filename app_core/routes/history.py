from datetime import datetime
import pytz
from flask import Blueprint, render_template, request, redirect, url_for, session, abort, jsonify
from app_core import jobs

history_bp = Blueprint('history', __name__)
LABELS = {'queued':'Sırada', 'running':'Çalışıyor', 'completed':'Tamamlandı',
          'cancelled':'İptal edildi', 'cancelling':'Durduruluyor',
          'failed':'Başarısız', 'needs_attention':'Gönderim kontrolü gerekli'}


def compare_results(before, after):
    if (str(before.get('thread_id','')) != str(after.get('thread_id','')) or
            bool(before.get('check_likes')) != bool(after.get('check_likes'))):
        raise ValueError('Aynı gruptaki aynı kontrol türünü seçin.')
    old = {item['post_link']: item for item in before.get('links', [])}
    new = {item['post_link']: item for item in after.get('links', [])}
    rows = []
    for link in sorted(old.keys() | new.keys()):
        first, second = old.get(link), new.get(link)
        comparable = first is not None and second is not None and not first.get('error') and not second.get('error')
        previous = set(first.get('eksikler',[])) if first else set()
        current = set(second.get('eksikler',[])) if second else set()
        rows.append({'link':link, 'comparable':comparable, 'before':sorted(previous), 'after':sorted(current),
                     'resolved':sorted(previous-current) if comparable else [],
                     'new_missing':sorted(current-previous) if comparable else []})
    return rows


@history_bp.route('/history')
def index():
    page = max(1, request.args.get('page', 1, type=int) or 1)
    rows = jobs.history(page)
    from app_core.storage import load_group_names
    group_names = load_group_names()
    for row in rows:
        row['group_name'] = group_names.get(str(row.get('thread_id')), 'Grup adı henüz alınmadı') if row.get('thread_id') else 'Manuel'
        row['date'] = datetime.fromtimestamp(row['created'], pytz.timezone('Europe/Istanbul')).strftime('%d.%m.%Y %H:%M:%S')
    before_id, after_id = request.args.get('before'), request.args.get('after')
    comparisons, error, members_changed = None, None, False
    if before_id and after_id:
        before, after = jobs.get_job(before_id), jobs.get_job(after_id)
        if not before or not after or before['state'] != 'completed' or after['state'] != 'completed' or before['kind']=='member' or after['kind']=='member':
            error = 'Karşılaştırma için tamamlanmış iki denetim seçin.'
        else:
            try:
                comparisons = compare_results(before['result'] or {}, after['result'] or {})
                members_changed = set((before['result'] or {}).get('group',[])) != set((after['result'] or {}).get('group',[]))
            except ValueError as exc:
                error = str(exc)
    return render_template('history.html', rows=rows, labels=LABELS, page=page,
                           comparisons=comparisons, error=error, members_changed=members_changed)


@history_bp.route('/history/<job_id>/retry', methods=['POST'])
def retry(job_id):
    source = jobs.get_job(job_id)
    if not source:
        abort(404)
    if source['state'] not in ('failed', 'needs_attention'):
        abort(409)
    if source['effects_started'] and request.form.get('confirm_resend') != 'yes':
        abort(400, 'Gönderilen mesajları kontrol edip yeniden gönderimi onaylayın.')
    new_id = jobs.enqueue(source['kind'], source['payload'], parent_id=job_id, dedupe_key='retry:'+job_id)
    return redirect(url_for('main.result_page_new', post_code=new_id))


@history_bp.route('/history/<job_id>/cancel', methods=['POST'])
def cancel(job_id):
    state = jobs.cancel(job_id)
    if state == 'not_found':
        abort(404)
    if state == 'conflict':
        abort(409, 'Bu denetim artık iptal edilemez.')
    from app_core.storage import add_audit_log
    add_audit_log('denetim', job_id, 'Denetim iptali istendi', 'Yönetici oturumu')
    return redirect(url_for('main.result_page_new', post_code=job_id))


@history_bp.route('/tools')
def tools_page():
    from app_core.features import overview, group_summary
    from app_core.storage import load_group_names,get_audit_logs
    return render_template('tools.html', **overview(), groups=load_group_names(), summaries=group_summary(), logs=get_audit_logs(100))


@history_bp.route('/api/management_overview')
def management_overview():
    from app_core.features import overview
    data=overview()
    return jsonify(expiring=data['expiring'], undo=data['undo'])


@history_bp.route('/tools/presets',methods=['POST'])
def save_preset():
    import json,uuid
    from app_core.storage import load_group_names,add_audit_log
    name=request.form.get('name','').strip()
    tid=request.form.get('thread_id','').strip()
    if not name or len(name)>80 or tid not in load_group_names():abort(400)
    value=dict(name=name,thread_id=tid,check_likes=request.form.get('kind')=='likes',
               low_likes=request.form.get('low_likes')=='on',only_sharers=request.form.get('only_sharers')=='on')
    with jobs.transaction() as conn:
        conn.execute('INSERT INTO key_value(key,value) VALUES (?,?)',('preset_'+uuid.uuid4().hex,json.dumps(value)))
    add_audit_log('şablon',name,'Denetim şablonu kaydedildi','Yönetici oturumu')
    return redirect(url_for('history.tools_page'))


@history_bp.route('/tools/presets/<identifier>/start',methods=['POST'])
def start_preset(identifier):
    import json
    with jobs.transaction() as conn:
        row=conn.execute('SELECT value FROM key_value WHERE key=?',('preset_'+identifier,)).fetchone()
    if not row:abort(404)
    payload=json.loads(row['value'])
    payload['date']=datetime.now(pytz.timezone('Europe/Istanbul')).strftime('%Y-%m-%d')
    # Repeated clicks reuse the in-progress run; completed checks can be run again.
    with jobs.transaction() as conn:
        active=conn.execute("SELECT id FROM jobs WHERE kind='preset' AND state IN ('queued','running','cancelling') AND json_extract(payload,'$.preset_id')=?",(identifier,)).fetchone()
        if active:return redirect(url_for('main.result_page_new',post_code=active['id']))
        import time,uuid
        job_id=uuid.uuid4().hex;now=time.time();payload['preset_id']=identifier
        conn.execute("INSERT INTO jobs(id,kind,payload,created,updated,available,message) VALUES (?,?,?,?,?,?,?)",
                     (job_id,'preset',json.dumps(payload),now,now,now,'Şablon denetimi sırada.'))
    from app_core.storage import add_audit_log
    add_audit_log('şablon',payload['name'],'Şablon denetimi başlatıldı',job_id)
    return redirect(url_for('main.result_page_new',post_code=job_id))


@history_bp.route('/tools/undo/<identifier>',methods=['POST'])
def undo(identifier):
    from app_core.features import undo_change
    if not undo_change(identifier):abort(409,'Süre doldu veya kayıt sonradan değiştirildi; işlem geri alınamadı.')
    return redirect(url_for('history.tools_page'))


@history_bp.route('/tools/presets/<identifier>/delete',methods=['POST'])
def delete_preset(identifier):
    with jobs.transaction() as conn:
        conn.execute('DELETE FROM key_value WHERE key=?',('preset_'+identifier,))
    from app_core.storage import add_audit_log
    add_audit_log('şablon',identifier,'Denetim şablonu silindi','Yönetici oturumu')
    return redirect(url_for('history.tools_page'))
