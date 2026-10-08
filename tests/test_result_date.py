import unittest
from unittest.mock import patch
import test_jobs
from app_core import create_app,jobs
from app_core.followup import read,write
class PostDateTests(unittest.TestCase):
 setUp=test_jobs.JobTests.setUp
 def test_form_date_is_resolved_and_preserved(self):
  with patch('app_core.init_storage'):c=create_app().test_client()
  r=c.post('/',data={'post_link':'https://www.instagram.com/p/ABC/','grup_uye':'member','thread_id':'g','control_mode':'comments','selected_date':'2026-10-07'},headers={'Accept':'application/json'})
  self.assertEqual(r.status_code,200);self.assertEqual(jobs.get_job(r.json['job_id'])['payload']['selected_date'],'2026-10-07');self.assertEqual(read('selected-post-date:g'),'2026-10-07')
  self.assertEqual(c.post('/',data={'post_link':'https://www.instagram.com/p/ABC/','selected_date':'wrong'},headers={'Accept':'application/json'}).status_code,400)
 def test_result_prefers_last_group_selected_date(self):
  from app_core.routes.main import result_page_new
  job=jobs.enqueue('manual',{});jobs.claim_request(job,'test');jobs.complete(job,'test',{'thread_id':'g','links':[],'group':[],'all_commented':[],'selected_date':'2026-10-06'})
  write('selected-post-date:g','2026-10-07')
  with patch('app_core.init_storage'):app=create_app()
  with app.test_request_context(),patch('app_core.routes.main.render_template',return_value='OK') as render:
   result_page_new(job);self.assertEqual(render.call_args.kwargs['selected_date'],'2026-10-07')
 def test_group_date_is_stored_when_day_requested(self):
  with patch('app_core.init_storage'):c=create_app().test_client()
  with patch('app_core.routes.main.fetch_group_media_with_failover',return_value={'ok':True,'posts':[]}):c.get('/api/get_group_posts/g?date=2026-10-06')
  self.assertEqual(read('selected-post-date:g'),'2026-10-06')

 def test_group_preferences_exposes_last_selected_date(self):
  write('selected-post-date:g','2026-10-07')
  with patch('app_core.init_storage'):client=create_app().test_client()
  self.assertEqual(client.get('/api/group_control_preferences/g').json['selected_date'],'2026-10-07')
