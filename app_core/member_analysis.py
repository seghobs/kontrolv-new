"""A separate, read-only Instagram analysis for one member and one group day."""
import asyncio
from datetime import datetime, timedelta
import re
import aiohttp
from flask import Blueprint, request, jsonify, render_template, abort
from app_core import jobs
from app_core.validators import normalize_username

member_bp=Blueprint('member_analysis',__name__)

@member_bp.post('/api/member_analysis/<source_id>')
def start(source_id):
    source=jobs.get_job(source_id)
    if not source or source['state']!='completed': abort(404)
    data=request.get_json(silent=True) or {}
    username=normalize_username(str(data.get('username','')))
    date=str(data.get('date',''))
    try:
        if not re.fullmatch(r'\d{4}-\d{2}-\d{2}',date): raise ValueError()
        datetime.strptime(date,'%Y-%m-%d')
    except ValueError: return jsonify(error='Geçerli bir tarih seçin.'),400
    end_date = str(data.get('end_date') or date)
    try:
        end = datetime.strptime(end_date, '%Y-%m-%d')
        if not 0 <= (end - datetime.strptime(date, '%Y-%m-%d')).days <= 30: raise ValueError()
    except ValueError: return jsonify(error='Tarih aralığı en fazla 31 gün olabilir.'),400
    result=source['result'] or {}
    members={normalize_username(u) for u in result.get('group',[])}
    members.update(normalize_username(u) for u in result.get('user_missing_posts',{}))
    tid=result.get('thread_id') or source['payload'].get('thread_id')
    if not tid or username not in members: return jsonify(error='Bu sonuç için geçerli bir üye ve grup gerekli.'),400
    payload={'dual_check':True,'username':username,'date':date,'thread_id':str(tid),'check_likes':bool(result.get('check_likes',source['payload'].get('check_likes',False)))}
    payload.update(end_date=end_date, skip_owner=bool(data.get('skip_owner', True)))
    # Every explicit analysis is fresh; duplicate clicks reuse only an unfinished record.
    import json,time,uuid
    with jobs.transaction() as conn:
        key='member-dual:'+source_id+':'+username+':'+date+':'+end_date+':'+str(payload['skip_owner'])
        row=conn.execute("SELECT id FROM jobs WHERE dedupe_key=? AND state IN ('queued','running','cancelling')",(key,)).fetchone()
        if row: identifier=row['id']
        else:
            conn.execute('UPDATE jobs SET dedupe_key=NULL WHERE dedupe_key=?',(key,))
            identifier=uuid.uuid4().hex;now=time.time()
            conn.execute('INSERT INTO jobs(id,kind,payload,created,updated,available,parent_id,dedupe_key,message) VALUES (?,?,?,?,?,?,?,?,?)',
                (identifier,'member',json.dumps(payload),now,now,now,source_id,key,'Üye analizi hazırlanıyor.'))
    return jsonify(success=True,job_id=identifier,result_url='/member-analysis/'+identifier)

@member_bp.get('/member-analysis/<identifier>')
def page(identifier):
    job=jobs.get_job(identifier)
    if not job or job['kind']!='member':abort(404)
    return render_template('member_analysis.html',job=job,status=jobs.public_status(job))


def run(payload, progress):
    from app_core.token_service import get_working_active_token,fetch_group_media_with_failover
    from app_core.instagram_api import fetch_comment_usernames_async,fetch_liker_usernames_async,get_post_details_async
    from donustur import donustur
    progress(0,1,'Seçilen günün tüm paylaşımları alınıyor…')
    token=get_working_active_token()
    if not token:raise ValueError('Geçerli bir Instagram oturumu bulunamadı.')
    posts=[];seen=set()
    start = datetime.strptime(payload['date'],'%Y-%m-%d')
    end = datetime.strptime(payload.get('end_date') or payload['date'],'%Y-%m-%d')
    if not 0 <= (end-start).days <= 30: raise ValueError('Geçersiz tarih aralığı.')
    for offset in range((end-start).days+1):
        date = start + timedelta(days=offset)
        media=fetch_group_media_with_failover(payload['thread_id'],date,token_record=token,complete=True)
        if not media.get('ok'):raise ValueError('Günün tüm paylaşımları alınamadı; analiz tamamlanmadı.')
        for post in media.get('posts',[]):
            code=donustur(post.get('url',''))
            key=str(code) if code else post.get('url','')
            if key in seen:continue
            seen.add(key);posts.append({**post,'shared_at':date.isoformat()})
    username=payload['username'];likes=payload['check_likes'];done=0
    from app_core.followup import read, write
    checkpoint_key='member-checkpoint:'+str(payload.get('_job_id',''))
    saved=read(checkpoint_key,{}) if payload.get('_job_id') else {}
    async def scan():
        sem=asyncio.Semaphore(4)
        async with aiohttp.ClientSession() as session:
            async def check(post, likes):
                row={'url':post['url'],'sender':post.get('username',''),'state':'unknown','comments':[], 'checked_at':__import__('time').time(), 'reason':'Veriler tam doğrulanamadı.'}
                if payload.get('skip_owner') and normalize_username(post.get('username','')) == username:
                    row.update(state='excluded', reason='Kendi paylaşımı')
                    return row
                try:
                    mid=donustur(post['url'])
                    if not mid: raise ValueError('Geçersiz paylaşım bağlantısı.')
                    if likes:
                        response=await fetch_liker_usernames_async(mid,token,session) or {}
                        users={normalize_username(u) for u in response.get('usernames',[]) if u}
                        if username in users:row['state']='present'
                        elif response.get('ok'):
                            details=await get_post_details_async(mid,token,session)
                            count=(details or {}).get('like_count')
                            if details.get('like_count_verified') and isinstance(count,int) and count>=0 and len(users)>=count: row['state']='missing'
                    else:
                        response=await fetch_comment_usernames_async(mid,token,session) or {}
                        row['comments']=[text for user,text in response.get('comments',[]) if normalize_username(user)==username]
                        if row['comments']:row['state']='present'
                        elif response.get('ok') and not response.get('incomplete'):row['state']='missing'
                except Exception:
                    row['state']='unknown'
                if row['state'] != 'unknown': row['reason'] = 'Güncel Instagram verisiyle kontrol edildi.'
                return row
            async def one(post):
                nonlocal done
                async with sem:
                    if post['url'] in saved:
                        done+=1;progress(done,max(1,len(posts)),'Önceki tamamlanan paylaşım korundu.')
                        return saved[post['url']]
                    if payload.get('dual_check'):
                        # Independent outcomes; a failure in one mode never hides the other.
                        result = (await check(post, False), await check(post, True))
                    else:
                        result = await check(post, likes)
                    saved[post['url']]=result
                    if payload.get('_job_id'):write(checkpoint_key,saved)
                    done+=1;progress(done,max(1,len(posts)),f'{done}/{len(posts)} paylaşım kontrol edildi.')
                    return result
            return await asyncio.gather(*(one(post) for post in posts))
    rows=asyncio.run(scan())
    def report(items, mode):
        return {**payload,'check_likes':mode,'rows':items,'total':len(items),'counts':{s:sum(r['state']==s for r in items) for s in ('present','missing','unknown','excluded')}}
    if payload.get('dual_check'):
        return {**payload,'total':len(rows),'comment_report':report([r[0] for r in rows],False),'like_report':report([r[1] for r in rows],True)}
    return report(rows,likes)
