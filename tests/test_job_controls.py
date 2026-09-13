import time
import unittest
from unittest.mock import Mock, patch
import test_jobs
from app_core import create_app, jobs
from app_core.web_jobs import execute_claimed


class JobControlTests(unittest.TestCase):
    setUp = test_jobs.JobTests.setUp
    claim = test_jobs.JobTests.claim
    expire = test_jobs.JobTests.expire

    def test_history_shows_cached_name_and_full_id_for_existing_jobs(self):
        from app_core.storage import cache_group_names, load_group_names
        thread_id = '340282366841710301281152316007215'
        jobs.enqueue('manual', {'thread_id': thread_id})
        cache_group_names([{'id': thread_id, 'name': 'Sanat & Yorum Grubu'}])
        cache_group_names([])
        self.assertEqual(load_group_names()[thread_id], 'Sanat & Yorum Grubu')
        with patch('app_core.init_storage'):
            app = create_app()
        client = app.test_client()
        with client.session_transaction() as session:
            session['admin_logged_in'] = True
        response = client.get('/history')
        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        self.assertIn('Sanat &amp; Yorum Grubu', html)
        self.assertIn('>' + thread_id + '</small>', html)

    def test_queued_cancel_is_immediate_and_idempotent(self):
        job_id = jobs.enqueue('manual', {})
        self.assertEqual(jobs.cancel(job_id), 'cancelled')
        self.assertEqual(jobs.cancel(job_id), 'cancelled')
        self.assertIsNone(self.claim('worker'))
        self.expire(job_id)
        self.assertEqual(jobs.get_job(job_id)['state'], 'cancelled')

    def test_running_cancel_fences_writes_and_waits_for_stop(self):
        job_id = jobs.enqueue('automation', {})
        self.claim('worker')
        self.assertEqual(jobs.cancel(job_id), 'cancelling')
        self.assertFalse(jobs.complete(job_id, 'worker', {}))
        with self.assertRaises(RuntimeError): jobs.mark_effects_started(job_id,'worker')
        jobs.fail(job_id,'worker','cancelled during processing')
        self.assertEqual(jobs.get_job(job_id)['state'],'cancelling')
        self.assertFalse(jobs.finish_cancel(job_id,'other'))
        self.assertTrue(jobs.finish_cancel(job_id,'worker'))
        self.assertEqual(jobs.public_status(jobs.get_job(job_id))['status'],'cancelled')

    def test_completed_result_cannot_be_cancelled(self):
        job_id = jobs.enqueue('manual', {})
        self.claim('worker'); jobs.complete(job_id,'worker',{'saved':True})
        self.assertEqual(jobs.cancel(job_id),'conflict')
        self.assertEqual(jobs.get_job(job_id)['result'],{'saved':True})
        self.assertEqual(jobs.cancel('missing'),'not_found')

    def test_cancel_survives_supervisor_crash(self):
        job_id = jobs.enqueue('manual', {})
        self.claim('worker'); jobs.cancel(job_id)
        self.expire(job_id)
        self.assertEqual(jobs.get_job(job_id)['state'],'cancelled')
        self.assertIsNone(self.claim('other'))

    def test_public_routes_and_cancel_ui(self):
        with patch('app_core.init_storage'): app=create_app()
        app.config.update(TESTING=True,SESSION_COOKIE_SECURE=False)
        client=app.test_client()
        job_id=jobs.enqueue('manual',{})
        self.assertEqual(client.get('/api/worker_status').status_code,404)
        self.assertEqual(client.get('/result/'+job_id).location, '/?task='+job_id)
        response=client.post('/history/'+job_id+'/cancel',follow_redirects=True)
        self.assertEqual(response.status_code,200)
        text=response.get_data(as_text=True)
        self.assertIn('Denetim iptal edildi',text)
        self.assertNotIn('Denetimi iptal et',text)
        self.assertIn('İptal edildi',client.get('/history').get_data(as_text=True))
