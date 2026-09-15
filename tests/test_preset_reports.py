import copy
import unittest
from unittest.mock import patch
from datetime import datetime
import pytz
import test_jobs
from app_core import create_app, storage, jobs, features
from app_core.preset_reports import execute, matrix, missing_text, combine, enqueue_active

URL='https://www.instagram.com/p/AAA/'
NEW='https://www.instagram.com/p/BBB/'

def report(likes=False, url=URL):
 return dict(thread_id='g',check_likes=likes,group=['alice','bob'],links=[dict(post_link=url,sender='owner',checked_at=123,
  commenters=['bob' if likes else 'alice'],eksikler=['alice' if likes else 'bob'],comments_list=[] if likes else [{'username':'alice','text':'Çok güzel 🌸'}])],
  user_missing_posts={('alice' if likes else 'bob'):[url]},user_comments={} if likes else {'alice':['Çok güzel 🌸']},all_commented=['bob' if likes else 'alice'])

class PresetReportTests(unittest.TestCase):
 setUp=test_jobs.JobTests.setUp
 def client(self):
  with patch('app_core.init_storage'):app=create_app()
  return app.test_client()
 def source(self, data=None):
  identifier=jobs.enqueue('preset',dict(thread_id='g',date='2026-09-14'))
  jobs.claim_request(identifier,'fixture');jobs.complete(identifier,'fixture',data or combine({'comments':report(),'likes':report(True)},dict(date='2026-09-14',thread_id='g')))
  return identifier
 def mock_run(self,*args,**kwargs): return report(args[4],args[0].splitlines()[0])
 def test_dual_execution_and_separate_copy(self):
  payload=dict(thread_id='g',date='2026-09-14',dual_check=True)
  with patch('app_core.token_service.fetch_group_members_with_failover',return_value={'ok':True,'members':[{'username':'alice'},{'username':'bob'}]}),patch('app_core.token_service.fetch_group_media_with_failover',return_value={'ok':True,'posts':[{'url':URL,'username':'owner'}]}),patch('app_core.routes.main.run_manual_control',side_effect=self.mock_run) as run:
   data=execute(payload,lambda *args:None)
  self.assertEqual([c.args[4] for c in run.call_args_list],[False,True]);self.assertTrue(data['dual_check'])
  self.assertIn('@bob',missing_text(data['comment_report']));self.assertNotIn('@alice',missing_text(data['comment_report']))
  self.assertIn('@alice',missing_text(data['like_report']))
 def test_extend_only_new_canonical_posts_preserves_old(self):
  identifier=self.source();old=copy.deepcopy(jobs.get_job(identifier)['result'])
  with patch('app_core.token_service.fetch_group_members_with_failover',side_effect=AssertionError('Membership must remain fixed')),patch('app_core.token_service.fetch_group_media_with_failover',return_value={'ok':True,'posts':[{'url':'https://www.instagram.com/reel/AAA/?x=1'},{'url':NEW,'username':'owner'},{'url':NEW}]}),patch('app_core.routes.main.run_manual_control',side_effect=self.mock_run) as run:
   data=execute(dict(thread_id='g',date='2026-09-14',_operation='extend',_source_id=identifier),lambda *a:None)
  self.assertEqual(run.call_count,2);self.assertTrue(all(c.args[0]==NEW for c in run.call_args_list))
  self.assertEqual(data['added_posts'],1);self.assertEqual(data['comment_report']['links'][0],old['comment_report']['links'][0]);self.assertEqual(jobs.get_job(identifier)['result'],old)
  self.assertEqual(len(data['like_report']['links']),2)
 def test_no_new_posts_does_not_scan(self):
  identifier=self.source()
  with patch('app_core.token_service.fetch_group_media_with_failover',return_value={'ok':True,'posts':[{'url':URL}]}),patch('app_core.routes.main.run_manual_control') as run:
   data=execute(dict(thread_id='g',date='2026-09-14',_operation='extend',_source_id=identifier),lambda *a:None)
  run.assert_not_called();self.assertEqual(data['added_posts'],0)
 def test_failed_discovery_preserves_report(self):
  identifier=self.source();before=jobs.get_job(identifier)['result']
  with patch('app_core.token_service.fetch_group_media_with_failover',return_value={'ok':False}),self.assertRaises(ValueError):
   execute(dict(thread_id='g',date='2026-09-14',_operation='extend',_source_id=identifier),lambda *a:None)
  self.assertEqual(jobs.get_job(identifier)['result'],before)
 def test_refresh_both_modes_uses_separate_previous_data(self):
  identifier=self.source()
  with patch('app_core.routes.main.run_manual_control',side_effect=self.mock_run) as run,patch('app_core.token_service.fetch_group_media_with_failover',side_effect=AssertionError('Refresh must retain post scope')):
   execute(dict(thread_id='g',_operation='refresh',_source_id=identifier,only_missing=True),lambda *a:None)
  self.assertFalse(run.call_args_list[0].kwargs['prev_result']['check_likes']);self.assertTrue(run.call_args_list[1].kwargs['prev_result']['check_likes'])
  self.assertTrue(all(c.kwargs['only_missing'] for c in run.call_args_list))
 def test_matrix_unknown_excluded_unchecked_are_distinct(self):
  data=report();data['group']+=['charlie','dave'];post=data['links'][0]
  post.update(error='Partial',unknown_members=['charlie'],excluded_members={'charlie':'Tarih doğrulanamadı','dave':'İzinli'})
  _,rows=matrix(data);rows={r['username']:r['cells'][0] for r in rows}
  self.assertEqual(rows['alice']['comments'],'present');self.assertEqual(rows['bob']['comments'],'unknown')
  self.assertEqual(rows['charlie']['comments'],'unknown');self.assertEqual(rows['dave']['comments'],'excluded');self.assertEqual(rows['alice']['likes'],'unchecked')
  self.assertEqual(missing_text(data),'Doğrulanmış eksik bulunmuyor.')
 def test_edit_preserves_id_and_historical_payload(self):
  c=self.client();storage.cache_group_names([{'id':'g','name':'Group'}]);c.post('/tools/presets',data=dict(name='First',thread_id='g',kind='comments'))
  preset=features.overview()['presets'][0];source=self.source();before=jobs.get_job(source)
  self.assertEqual(c.get('/tools/presets/'+preset['id']+'/edit').status_code,200)
  r=c.post('/tools/presets/'+preset['id']+'/edit',data=dict(name='Both',thread_id='g',kind='both',only_sharers='on'))
  self.assertEqual(r.status_code,302);saved=features.overview()['presets'][0]
  self.assertEqual(saved['id'],preset['id']);self.assertTrue(saved['dual_check']);self.assertEqual(jobs.get_job(source),before)
 def test_dates_modes_validation_and_active_deduplication(self):
  c=self.client();storage.cache_group_names([{'id':'g','name':'Group'}]);c.post('/tools/presets',data=dict(name='Both',thread_id='g',kind='both'))
  preset=features.overview()['presets'][0];url='/tools/presets/'+preset['id']+'/start'
  first=c.post(url,data={'date':'2026-09-13'});second=c.post(url,data={'date':'2026-09-13'});other=c.post(url,data={'date':'2026-09-14'})
  self.assertEqual(first.location,second.location);self.assertNotEqual(first.location,other.location)
  self.assertEqual(jobs.get_job(first.location.rsplit('/',1)[-1])['payload']['date'],'2026-09-13')
  for date in ('invalid','9999-01-01','2026-02-30'):self.assertEqual(c.post(url,data={'date':date}).status_code,400)
  self.assertEqual(c.post('/tools/presets',data=dict(name='Bad',thread_id='g',kind='invalid')).status_code,400)
 def test_extension_can_run_again_after_completion(self):
  identifier=self.source();c=self.client();url='/api/reports/'+identifier+'/extend'
  first=c.post(url,json={'date':'2026-09-14'}).json['result_url'];second=c.post(url,json={'date':'2026-09-14'}).json['result_url'];self.assertEqual(first,second)
  new_id=first.rsplit('/',1)[-1];jobs.claim_request(new_id,'test');jobs.complete(new_id,'test',report())
  third=c.post(url,json={'date':'2026-09-14'}).json['result_url'];self.assertNotEqual(first,third)
 def test_render_views_and_dual_recheck(self):
  identifier=self.source();c=self.client()
  comments=c.get('/result/'+identifier);likes=c.get('/result/'+identifier+'?mode=likes');table=c.get('/reports/'+identifier+'/matrix')
  self.assertEqual([comments.status_code,likes.status_code,table.status_code],[200,200,200])
  self.assertIn('Beğeni Durumu Özeti',likes.text);self.assertIn('Yorum Durumu Özeti',comments.text)
  r=c.post('/api/recheck/'+identifier,json={'only_missing':True});self.assertEqual(r.status_code,200)
  job=jobs.get_job(r.json['result_url'].split('/')[-1]);self.assertEqual(job['kind'],'preset');self.assertTrue(job['payload']['only_missing'])
 def test_real_request_execution_pipeline(self):
  identifier=jobs.enqueue('preset',dict(thread_id='g',date='2026-09-14',dual_check=True))
  with patch('app_core.token_service.fetch_group_members_with_failover',return_value={'ok':True,'members':[{'username':'alice'},{'username':'bob'}]}),patch('app_core.token_service.fetch_group_media_with_failover',return_value={'ok':True,'posts':[{'url':URL}]}),patch('app_core.routes.main.run_manual_control',side_effect=self.mock_run):
   r=self.client().post('/api/task_run/'+identifier)
  self.assertEqual(r.status_code,200);self.assertEqual(r.json['status'],'completed');self.assertTrue(jobs.get_job(identifier)['result']['dual_check'])

if __name__=='__main__':unittest.main()
