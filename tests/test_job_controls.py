import time
import unittest
from unittest.mock import Mock, patch
import test_jobs
from app_core import create_app, jobs
import worker


class JobControlTests(unittest.TestCase):
    setUp = test_jobs.JobTests.setUp

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
        self.assertIsNone(jobs.claim('worker'))
        jobs.recover_stale(time.time()+100)
        self.assertEqual(jobs.get_job(job_id)['state'], 'cancelled')

    def test_running_cancel_fences_writes_and_waits_for_stop(self):
        job_id = jobs.enqueue('automation', {})
        jobs.claim('worker')
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
        jobs.claim('worker'); jobs.complete(job_id,'worker',{'saved':True})
        self.assertEqual(jobs.cancel(job_id),'conflict')
        self.assertEqual(jobs.get_job(job_id)['result'],{'saved':True})
        self.assertEqual(jobs.cancel('missing'),'not_found')

    def test_cancel_survives_supervisor_crash(self):
        job_id = jobs.enqueue('manual', {})
        jobs.claim('worker'); jobs.cancel(job_id)
        jobs.recover_stale(time.time()+60)
        self.assertEqual(jobs.get_job(job_id)['state'],'cancelled')
        self.assertIsNone(jobs.claim('other'))

    def test_worker_presence_includes_idle_stale_and_stopped(self):
        self.assertFalse(jobs.worker_status()['online'])
        jobs.worker_presence('a')
        self.assertTrue(jobs.worker_status()['online'])
        jobs.enqueue('manual',{})
        self.assertEqual(jobs.worker_status()['queued'],1)
        jobs.claim('a')
        self.assertEqual(jobs.worker_status()['running'],1)
        with patch('app_core.jobs.time.time', return_value=time.time()+31):
            self.assertFalse(jobs.worker_status()['online'])
        jobs.worker_presence('b')
        jobs.worker_presence('a', stopped=True)
        self.assertTrue(jobs.worker_status()['online'])
        jobs.worker_presence('b', stopped=True)
        self.assertFalse(jobs.worker_status()['online'])

    def test_supervisor_terminates_cancelled_child(self):
        job_id = jobs.enqueue('manual', {})
        process=Mock()
        process.is_alive.side_effect=[True, False]
        context=Mock()
        context.Process.return_value=process
        with patch('app_core.storage.init_storage'), patch.object(jobs,'import_legacy'), patch.object(worker,'schedule_due'), patch.object(worker.multiprocessing,'get_context',return_value=context), patch.object(worker.time,'sleep',side_effect=lambda _: jobs.cancel(job_id)):
            worker.run(once=True)
        process.terminate.assert_called_once()
        self.assertEqual(jobs.get_job(job_id)['state'],'cancelled')
        self.assertFalse(jobs.worker_status()['online'])

    def test_authenticated_routes_and_cancel_ui(self):
        with patch('app_core.init_storage'): app=create_app()
        app.config.update(TESTING=True,SESSION_COOKIE_SECURE=False)
        client=app.test_client()
        job_id=jobs.enqueue('manual',{})
        self.assertEqual(client.get('/api/worker_status').status_code,401)
        self.assertEqual(client.post('/history/'+job_id+'/cancel').status_code,302)
        self.assertEqual(jobs.get_job(job_id)['state'],'queued')
        with client.session_transaction() as session: session['admin_logged_in']=True
        self.assertEqual(client.get('/api/worker_status').json['queued'],1)
        self.assertIn('Denetimi İptal Et',client.get('/result/'+job_id).get_data(as_text=True))
        response=client.post('/history/'+job_id+'/cancel',follow_redirects=True)
        self.assertEqual(response.status_code,200)
        text=response.get_data(as_text=True)
        self.assertIn('Denetim iptal edildi',text)
        self.assertNotIn('Denetimi İptal Et',text)
        self.assertIn('İptal edildi',client.get('/history').get_data(as_text=True))
