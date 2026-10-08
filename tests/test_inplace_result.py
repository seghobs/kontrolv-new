import unittest
from unittest.mock import patch
import test_jobs
from app_core import create_app,jobs
class InplaceResultTests(unittest.TestCase):
 setUp=test_jobs.JobTests.setUp
 def test_completed_report_json_contains_full_report_and_state(self):
  identifier=jobs.enqueue('manual',{'low_likes':True});jobs.claim_request(identifier,'owner')
  jobs.complete(identifier,'owner',{'thread_id':'group','links':[{'post_link':'https://www.instagram.com/p/ABC/','sender':'member','eksikler':['missing']}],'group':['missing','present'],'all_commented':['present'],'user_comments':{'present':['Hello']}})
  with patch('app_core.init_storage'):client=create_app().test_client()
  r=client.get('/result/'+identifier+'?fragment=1');self.assertEqual(r.status_code,200)
  self.assertIn('name="low_likes" value="on"',r.json['html']);self.assertIn('result-header-title',r.json['html']);self.assertEqual(r.json['state']['postCode'],identifier)
  self.assertEqual(r.json['state']['userComments'],{'present':['Hello']});self.assertEqual(r.json['state']['postDetailsData']['1']['link'],'https://www.instagram.com/p/ABC/')
 def test_ajax_submission_returns_job_instead_of_redirect(self):
  with patch('app_core.init_storage'):client=create_app().test_client()
  r=client.post('/',headers={'Accept':'application/json'},data={'post_link':'https://www.instagram.com/p/ABC/','thread_id':'g','grup_uye':'member','selected_date':'2026-10-07','control_mode':'likes'})
  self.assertEqual(r.status_code,200);self.assertNotIn('Location',r.headers)
  job=jobs.get_job(r.json['job_id']);self.assertEqual(job['payload']['selected_date'],'2026-10-07');self.assertTrue(job['payload']['check_likes'])
