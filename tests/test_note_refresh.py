import unittest
from unittest.mock import patch
from app_core import create_app
from app_core.followup import write,read,link_key
import test_jobs
class NoteRefreshTests(unittest.TestCase):
 setUp=test_jobs.JobTests.setUp
 def test_refresh_uses_report_group_date_and_keeps_audit(self):
  url='https://www.instagram.com/p/POST/';job={'state':'completed','payload':{'shared_dates':{link_key(url):'2026-10-07T20:00:00Z'}},'result':{'thread_id':'group','links':[{'post_link':url,'eksikler':['missing']}],'all_commented':['present']}}
  with patch('app_core.init_storage'):client=create_app().test_client()
  def fetch(tid,date,complete):
   self.assertEqual(tid,'group');self.assertEqual(date.strftime('%Y-%m-%d'),'2026-10-07');self.assertTrue(complete)
   write('nearby-notes:group',{'POST':{'2026-10-07':[{'id':'n','timestamp':1,'text':'<img src=x> Sadece beğeni','username':'member','time':'07.10.2026 23:00'}]}})
   return {'ok':True,'posts':[{'code':'POST'}]}
  with patch('app_core.jobs.get_job',return_value=job),patch('app_core.routes.main.fetch_group_media_with_failover',side_effect=fetch) as api:
   r=client.post('/api/reports/report/notes/refresh',json={'link':url});self.assertEqual(r.status_code,200);self.assertEqual(r.json['count'],1);self.assertIn('&lt;img',r.json['html']);self.assertEqual(job['result']['links'][0]['eksikler'],['missing'])
   self.assertEqual(client.post('/api/reports/report/notes/refresh',json={'link':'https://www.instagram.com/p/OTHER/'}).status_code,400);self.assertEqual(api.call_count,1)
 def test_failure_retains_cached_notes(self):
  url='https://www.instagram.com/p/POST/';write('nearby-notes:group',{'POST':{'2026-10-07':[{'id':'old'}]}})
  job={'state':'completed','result':{'thread_id':'group','links':[{'post_link':url}]}}
  with patch('app_core.init_storage'):client=create_app().test_client()
  with patch('app_core.jobs.get_job',return_value=job),patch('app_core.routes.main.fetch_group_media_with_failover',return_value={'ok':False}):
   self.assertEqual(client.post('/api/reports/report/notes/refresh',json={'link':url}).status_code,502)
  self.assertEqual(read('nearby-notes:group')['POST']['2026-10-07'],[{'id':'old'}])
