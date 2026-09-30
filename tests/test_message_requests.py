import unittest,json,time
from unittest.mock import patch,Mock
import test_jobs
from app_core import create_app,jobs
from app_core.followup import write,read
from app_core.message_requests import associate,classify
class MessageRequestTests(unittest.TestCase):
 setUp=test_jobs.JobTests.setUp
 def fixture(self):
  identifier=jobs.enqueue('manual',{'thread_id':'123'});jobs.claim_request(identifier,'test')
  jobs.complete(identifier,'test',{'thread_id':'123','links':[{'post_link':'https://www.instagram.com/p/ABC/','eksikler':['bob'],'commenters':[]}],'group':['bob'],'user_missing_posts':{'bob':['https://www.instagram.com/p/ABC/']},'check_likes':False})
  with patch('app_core.init_storage'):client=create_app().test_client()
  return identifier,client
 def test_sender_attribution_ambiguous_posts_and_reply(self):
  rows=[{'item_id':'s1','user_id':1,'timestamp':10e6,'item_type':'xma_clip','url':'https://www.instagram.com/p/ABC/'},{'item_id':'s2','user_id':1,'timestamp':11e6,'item_type':'media_share','url':'https://www.instagram.com/p/DEF/'},{'item_id':'m','user_id':1,'timestamp':12e6,'item_type':'text','text':'Sadece beğeni'},{'item_id':'reply','user_id':1,'timestamp':13e6,'item_type':'text','text':'Yorum yok','replied_to_message':{'item_id':'s1'}},{'item_id':'other','user_id':2,'timestamp':13e6,'item_type':'text','text':'Yorum yok','replied_to_message':{'item_id':'s1'}}]
  r=associate(rows,{'1':'alice','2':'bob'},['https://www.instagram.com/p/ABC/','https://www.instagram.com/p/DEF/'],0,20)
  self.assertEqual(len(r),2);self.assertEqual(len(r[0]['urls']),2);self.assertEqual(r[1]['association'],'reply');self.assertEqual(r[1]['urls'],['https://www.instagram.com/p/ABC/'])
 def test_background_start_does_not_wait_and_deduplicates(self):
  identifier,c=self.fixture()
  with patch('app_core.message_requests.threading.Thread') as thread,patch('app_core.message_requests._slots') as slots:
   slots.acquire.return_value=True
   self.assertEqual(c.post('/api/message-requests/'+identifier).status_code,202)
   self.assertEqual(c.post('/api/message-requests/'+identifier).json['state'],'running');self.assertEqual(thread.call_count,1)
  self.assertEqual(jobs.get_job(identifier)['result']['user_missing_posts'],{'bob':['https://www.instagram.com/p/ABC/']})
 def test_approval_requires_valid_candidate_and_only_changes_selected_report(self):
  identifier,c=self.fixture();url='https://www.instagram.com/p/ABC/'
  write('message-requests:'+identifier,{'state':'complete','requests':[{'id':'m','kind':'likes_only','urls':[url]}]})
  self.assertEqual(c.post('/api/message-requests/'+identifier+'/approve',json={'id':'fake','url':url}).status_code,400)
  self.assertEqual(c.post('/api/message-requests/'+identifier+'/approve',json={'id':'m','url':url}).status_code,200)
  result=jobs.get_job(identifier)['result'];self.assertEqual(result['user_missing_posts'],{});self.assertEqual(result['links'][0]['eksikler'],[]);self.assertEqual(result['links'][0]['commenters'],[])
 def test_failure_keeps_primary_report_and_provides_retry(self):
  from app_core.message_requests import worker
  identifier,c=self.fixture();before=jobs.get_job(identifier)['result']
  write('message-requests:'+identifier,{'state':'running','revision':'r'})
  with patch('app_core.message_requests.collect',side_effect=ValueError('Test failure')),patch('app_core.message_requests._slots') as slots:
   worker(identifier,'r');slots.release.assert_called_once()
  self.assertEqual(read('message-requests:'+identifier)['state'],'failed');self.assertEqual(jobs.get_job(identifier)['result'],before)
 def test_topic_cannot_be_used_to_exempt_and_likes_report_unchanged(self):
  identifier,c=self.fixture();url='https://www.instagram.com/p/ABC/'
  write('message-requests:'+identifier,{'state':'complete','requests':[{'id':'m','kind':'comment_topic','urls':[url]}]})
  self.assertEqual(c.post('/api/message-requests/'+identifier+'/approve',json={'id':'m','url':url}).status_code,400)
  with jobs.transaction() as conn:
   result=jobs.get_job(identifier)['result'];result['check_likes']=True
   conn.execute('UPDATE jobs SET result=? WHERE id=?',(json.dumps(result),identifier))
  write('message-requests:'+identifier,{'state':'complete','requests':[{'id':'m','kind':'likes_only','urls':[url]}]})
  self.assertEqual(c.post('/api/message-requests/'+identifier+'/approve',json={'id':'m','url':url}).status_code,400)
  self.assertEqual(jobs.get_job(identifier)['result']['links'][0]['eksikler'],['bob'])
 def test_model_cannot_invent_message_ids(self):
  response=Mock(ok=True);response.json.return_value={'candidates':[{'finishReason':'STOP','content':{'parts':[{'text':json.dumps({'requests':[{'id':'fake','kind':'likes_only','summary':'fake'}]})}]}}]}
  with patch('app_core.save_control.api_key',return_value='test'),patch('app_core.message_requests.requests.post',return_value=response):
   with self.assertRaises(ValueError):classify([{'id':'real','text':'hello'}])
 def test_no_candidates_no_model_request(self):
  with patch('app_core.message_requests.requests.post') as req:self.assertEqual(classify([]),[]);req.assert_not_called()
