import tempfile
import unittest
from unittest.mock import patch
from app_core import jobs, storage
from app_core.web_jobs import execute_job

class WebJobsTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.db=patch.object(storage,'DB_FILE',self.temp.name+'/test.db'); self.db.start()
        connection=storage._connect(); storage._init_db(connection); connection.close()
    def tearDown(self):
        self.db.stop(); self.temp.cleanup()
    def test_completes_manual_job_without_worker(self):
        identifier=jobs.enqueue('manual',{'link':'example','grup_uye':'alice'})
        with patch('app_core.routes.main.run_manual_control',return_value={'links':[]}) as run:
            status,code=execute_job(identifier)
        self.assertEqual(code,200); self.assertEqual(status['status'],'completed')
        self.assertEqual(jobs.get_job(identifier)['result'],{'links':[]})
        run.assert_called_once()
    def test_second_request_does_not_repeat_check(self):
        identifier=jobs.enqueue('manual',{})
        def run(**kwargs):
            status,code=execute_job(identifier)
            self.assertEqual(status['status'],'running')
            return {'links':[]}
        with patch('app_core.routes.main.run_manual_control',side_effect=run) as call:
            execute_job(identifier); execute_job(identifier)
        call.assert_called_once()
    def test_automation_cannot_be_triggered_by_browser(self):
        identifier=jobs.enqueue('automation',{})
        self.assertEqual(execute_job(identifier)[1],403)
        self.assertEqual(jobs.get_job(identifier)['state'],'queued')
    def test_failure_keeps_job_and_allows_bounded_retry(self):
        identifier=jobs.enqueue('manual',{})
        with patch('app_core.routes.main.run_manual_control',side_effect=ValueError('failed')):
            execute_job(identifier)
        job=jobs.get_job(identifier)
        self.assertEqual(job['state'],'queued'); self.assertEqual(job['attempts'],1)
        self.assertIn('failed',job['error'])

    def test_preset_executes_without_service(self):
        identifier=jobs.enqueue('preset',{'thread_id':'g'})
        with patch('app_core.features.run_preset',return_value={'links':[]}) as run:
            status,code=execute_job(identifier)
        self.assertEqual(status['status'],'completed')
        run.assert_called_once()

    def test_admin_execution_requires_login_and_keeps_schedule_settings(self):
        from app_core import create_app
        with patch('app_core.init_storage'): app=create_app()
        app.config.update(TESTING=True,SESSION_COOKIE_SECURE=False)
        client=app.test_client()
        identifier=jobs.enqueue('automation',{'thread_id':'g'})
        self.assertEqual(client.post('/api/task_run/'+identifier).status_code,403)
        with client.session_transaction() as session: session['admin_logged_in']=True
        with patch('app_core.automation.run_automation_for_thread',return_value={}) as run:
            response=client.post('/api/task_run/'+identifier)
        self.assertEqual(response.json['status'],'completed')
        run.assert_called_once()
        storage.set_global_automation_status(True)
        response=client.post('/admin/toggle_global_automation')
        self.assertFalse(response.json['success'])
        self.assertTrue(storage.get_global_automation_status())
        self.assertFalse(client.get('/admin/get_global_automation_status').json['is_active'])
