"""Saved checks and local management summaries; no remote calls on page loads."""
import json
import time
import uuid
from datetime import datetime, timedelta
from collections import Counter
from app_core import storage, jobs


def record_change(conn, kind, target, before, after, action):
    if kind == 'grup ayarı':
        remaining = {row['thread_id'] for row in (after or [])}
        for row in (before or []):
            if row['thread_id'] not in remaining:
                trash = dict(key='automation:'+row['thread_id'],label='Grup ayarı '+(row.get('group_name') or row['thread_id']),value=json.dumps(row),expires=time.time()+30*86400)
                conn.execute('INSERT INTO key_value(key,value) VALUES (?,?)',('trash:'+uuid.uuid4().hex,json.dumps(trash)))
    identifier = uuid.uuid4().hex
    entry = dict(kind=kind, target=target, before=before, after=after, expires=time.time()+60)
    conn.execute("INSERT INTO key_value(key,value) VALUES (?,?)", ('undo_'+identifier,json.dumps(entry)))
    conn.execute("INSERT INTO audit_logs(entity_type,entity_id,action,details,created_at) VALUES (?,?,?,?,?)",
                 (kind,target,action,'Yönetici oturumu',datetime.now().isoformat()))
    conn.execute("DELETE FROM key_value WHERE key GLOB 'undo_*' AND json_extract(value,'$.expires') < ?", (time.time(),))


def undo_change(identifier):
    with jobs.transaction() as conn:
        row = conn.execute('SELECT value FROM key_value WHERE key=?',('undo_'+identifier,)).fetchone()
        if not row: return False
        entry=json.loads(row['value'])
        if entry['expires'] < time.time(): return False
        if entry['kind']=='muafiyet':
            row=conn.execute('SELECT * FROM global_exemptions WHERE username=?',(entry['target'],)).fetchone()
            current=dict(row) if row else None
            if current != entry['after']: return False
            old=entry['before']
            if old:
                conn.execute('INSERT OR REPLACE INTO global_exemptions(username,created_at,expires_at,duration_days) VALUES (?,?,?,?)',
                             tuple(old[k] for k in ('username','created_at','expires_at','duration_days')))
            else: conn.execute('DELETE FROM global_exemptions WHERE username=?',(entry['target'],))
        elif entry['kind']=='gönderi muafiyeti':
            current=[list(r) for r in conn.execute('SELECT post_link,username FROM exemptions ORDER BY post_link,username')]
            if current != entry['after']:return False
            conn.execute('DELETE FROM exemptions')
            conn.executemany('INSERT INTO exemptions(post_link,username) VALUES (?,?)',entry['before'])
        elif entry['kind']=='grup ayarı':
            current=[dict(r) for r in conn.execute('SELECT * FROM automations ORDER BY thread_id')]
            if current != entry['after']:return False
            conn.execute('DELETE FROM automations')
            for old in entry['before']:
                conn.execute('INSERT INTO automations(thread_id,is_active,group_name,notify_username,control_method,updated_at) VALUES (?,?,?,?,?,?)',
                             tuple(old[k] for k in ('thread_id','is_active','group_name','notify_username','control_method','updated_at')))
        elif entry['kind']=='ayar':
            row=conn.execute('SELECT value FROM key_value WHERE key=?',(entry['target'],)).fetchone()
            if (row['value'] if row else None) != entry['after']: return False
            if entry['before'] is None: conn.execute('DELETE FROM key_value WHERE key=?',(entry['target'],))
            else: conn.execute('UPDATE key_value SET value=? WHERE key=?',(entry['before'],entry['target']))
        else: return False
        conn.execute('DELETE FROM key_value WHERE key=?',('undo_'+identifier,))
        conn.execute('INSERT INTO audit_logs(entity_type,entity_id,action,details,created_at) VALUES (?,?,?,?,?)',
                     (entry['kind'],entry['target'],'İşlem geri alındı','Yönetici oturumu',datetime.now().isoformat()))
        return True


def overview():
    conn=storage._connect()
    try:
        now=datetime.now()
        expiring=[dict(r) for r in conn.execute('SELECT username,expires_at FROM global_exemptions WHERE expires_at>=? AND expires_at<=? ORDER BY expires_at',
                                               (now.isoformat(),(now+timedelta(hours=24)).isoformat()))]
        undo=[]
        for row in conn.execute("SELECT key,value FROM key_value WHERE key GLOB 'undo_*' AND json_extract(value,'$.expires') >= ?",(time.time(),)):
            item=json.loads(row['value']);undo.append(dict(id=row['key'][5:],target=item['target'],seconds=max(0,int(item['expires']-time.time()))))
        presets=[dict(id=r['key'][7:],**json.loads(r['value'])) for r in conn.execute("SELECT key,value FROM key_value WHERE key GLOB 'preset_*'")]
        return dict(expiring=expiring,undo=undo,presets=presets)
    finally:conn.close()


def group_summary():
    conn=storage._connect()
    try:
        # Latest 100 complete checks; errors and exempt/skipped posts excluded.
        rows=conn.execute("SELECT created,result FROM jobs WHERE state='completed' AND kind!='member' AND result IS NOT NULL ORDER BY created DESC LIMIT 100").fetchall()
        groups={}
        for row in reversed(rows):
            data=json.loads(row['result']);tid=str(data.get('thread_id') or '')
            if not tid:continue
            kind='Beğeni' if data.get('check_likes') else 'Yorum'
            key=(tid,kind); group=groups.setdefault(key,dict(thread_id=tid,kind=kind,runs=[],missing=Counter()))
            eligible=done=0;missing=set()
            for post in data.get('links',[]):
                if post.get('error'):continue
                absent=set(post.get('eksikler') or []);present=set(post.get('commenters') or [])
                eligible+=len(absent|present);done+=len(present-absent);missing.update(absent)
            if not eligible:continue
            group['runs'].append(round(done/eligible*100,1));group['missing'].update(missing)
        names=storage.load_group_names();result=[]
        for group in groups.values():
            if not group['runs']:continue
            group['name']=names.get(group['thread_id'],'Grup adı henüz alınmadı')
            group['latest']=group['runs'][-1]
            group['previous']=group['runs'][-2] if len(group['runs'])>1 else None
            group['frequent']=group['missing'].most_common(5)
            result.append(group)
        return result
    finally:conn.close()


def run_preset(payload, progress_callback):
    from app_core.token_service import fetch_group_members_with_failover,fetch_group_media_with_failover
    from app_core.routes.main import run_manual_control
    tid=payload['thread_id']
    progress_callback(0,1,'Şablon için güncel grup bilgileri alınıyor…')
    members=fetch_group_members_with_failover(tid)
    if not members.get('ok'):raise RuntimeError('Grup üyeleri alınamadı; şablon başlatılamadı.')
    media=fetch_group_media_with_failover(tid,datetime.strptime(payload['date'],'%Y-%m-%d'))
    if not media.get('ok'):raise RuntimeError('Paylaşımlar alınamadı; şablon başlatılamadı.')
    posts=media.get('posts') or []
    if payload.get('low_likes'):posts=[p for p in posts if isinstance(p.get('like_count'),(int,float)) and 0<=p['like_count']<=90]
    if not posts:raise RuntimeError('Bu gün ve filtreler için paylaşım bulunamadı.')
    users={m['username'] for m in members.get('members',[]) if m.get('username')}
    if payload.get('only_sharers'):users &= {p.get('username') for p in posts}
    if not users:raise RuntimeError('Kontrol edilecek üye bulunamadı.')
    return run_manual_control('\n'.join(p['url'] for p in posts),' '.join(users),tid,
                              [p['url']+'|'+p['username'] for p in posts if p.get('username')],
                              payload['check_likes'],progress_callback=progress_callback,shared_dates={p['url']:p['shared_at'] for p in posts if p.get('shared_at')})
