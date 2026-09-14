import os,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
import tempfile
fixture_dir=tempfile.TemporaryDirectory()
os.environ['APP_DB_FILE']=str(Path(fixture_dir.name)/'fixture.sqlite')
os.environ['SECRET_KEY']='isolated-preview-only'
from app_core import storage,create_app,jobs
for key in ('TOKENS_FILE','TOKEN_FILE','EXEMPTIONS_FILE'):setattr(storage,key,str(Path(__file__).with_name('no-fixture.json')))
app=create_app()
app.jinja_env.auto_reload=True
from app_core import followup
identifier='a'*32
if not jobs.get_job(identifier):
 jobs.enqueue('manual',dict(link='https://www.instagram.com/p/ABC',grup_uye='alice bob',thread_id='g',post_senders_raw=[],check_likes=False),job_id=identifier)
 jobs.claim_request(identifier,'fixture')
 jobs.complete(identifier,'fixture',dict(group=['alice','bob'],thread_id='g',links=[dict(post_link='https://www.instagram.com/p/ABC',eksikler=['bob'],commenters=['alice'],sender='ornekhesap',checked_at=1700000000,source='live',caption='Örnek paylaşım açıklaması'),dict(post_link='https://www.instagram.com/p/DEF',eksikler=[],commenters=[],error='Yorum listesi tam alınamadı.',checked_at=1700000000,source='live')],user_missing_posts={'bob':['https://www.instagram.com/p/ABC']}))
storage.save_automations({'g':dict(is_active=False,group_name='Örnek grup')})
member_id='b'*32
member_payload=dict(username='alice',thread_id='g',date='2026-09-14',check_likes=False,dual_check=True)
jobs.enqueue('member',member_payload,job_id=member_id,parent_id=identifier)
jobs.claim_request(member_id,'fixture')
known=dict(url='https://www.instagram.com/p/ABC/',sender='ornek',state='present',comments=['Gerçekten güzel bir paylaşım 🌸'],reason='Doğrulandı.',checked_at=123)
unknown=dict(url='https://www.instagram.com/p/DEF/',sender='diger',state='unknown',comments=[],reason='Yorum listesi toplam yorum sayısıyla doğrulanamadı; üye eksik sayılmadı.')
comments=dict(**member_payload,rows=[known,unknown],total=2,counts=dict(present=1,missing=0,unknown=1,excluded=0))
likes={**comments,'check_likes':True,'rows':[{**known,'comments':[]},unknown]}
jobs.complete(member_id,'fixture',{**member_payload,'analysis_version':2,'comment_report':comments,'like_report':likes})
@app.get('/_preview/login')
def login():
 from flask import session,redirect
 session['admin_logged_in']=True
 return redirect('/group-rules')
app.run(host='127.0.0.1',port=5087,debug=False)
