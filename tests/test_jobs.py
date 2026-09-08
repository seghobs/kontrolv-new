import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

from app_core import jobs, create_app
import app_core.storage as storage
from app_core.login_limits import reserve_attempt, clear_attempts
from app_core.routes.history import compare_results
import worker


class JobTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.db = str(Path(self.tmp.name)/'test.db')
        database = patch.object(storage, 'DB_FILE', self.db)
        database.start()
        self.addCleanup(database.stop)
        conn = storage._connect()
        storage._init_db(conn)
        conn.close()

    def due(self, job_id):
        with jobs.transaction() as conn:
            conn.execute('UPDATE jobs SET available=0 WHERE id=?',(job_id,))

    def test_atomic_claim_and_deduplication(self):
        first = jobs.enqueue('manual', {}, dedupe_key='one')
        self.assertEqual(jobs.enqueue('manual', {}, dedupe_key='one'), first)
        with ThreadPoolExecutor(2) as pool:
            claimed = list(pool.map(jobs.claim, ['a','b']))
        self.assertEqual(sum(job is not None for job in claimed), 1)

    def test_retry_after_crash_and_fencing(self):
        job_id = jobs.enqueue('manual', {})
        old = jobs.claim('old')
        self.assertEqual(jobs.recover_stale(now=time.time()+60),1)
        self.assertEqual(jobs.get_job(job_id)['state'],'queued')
        self.assertFalse(jobs.complete(job_id,'old',{'bad':True}))
        self.due(job_id)
        current = jobs.claim('new')
        self.assertEqual(current['attempts'],2)
        self.assertTrue(jobs.complete(job_id,'new',{'valid':True}))
        self.assertEqual(jobs.get_job(job_id)['result'],{'valid':True})

    def test_retry_budget_is_bounded(self):
        job_id=jobs.enqueue('manual', {})
        for _ in range(3):
            self.due(job_id)
            jobs.claim('worker')
            jobs.fail(job_id,'worker','network')
        self.assertEqual(jobs.get_job(job_id)['state'],'failed')
        self.assertIsNone(jobs.claim('worker'))

    def test_uncertain_message_is_not_resent_automatically(self):
        job_id=jobs.enqueue('automation', {})
        jobs.claim('worker')
        jobs.mark_effects_started(job_id,'worker')
        jobs.recover_stale(time.time()+60)
        self.assertEqual(jobs.get_job(job_id)['state'],'needs_attention')
        self.due(job_id)
        self.assertIsNone(jobs.claim('other'))

    def test_expired_owner_cannot_send(self):
        job_id=jobs.enqueue('automation', {})
        jobs.claim('worker')
        with jobs.transaction() as conn:
            conn.execute('UPDATE jobs SET lease_until=0 WHERE id=?',(job_id,))
        with self.assertRaises(RuntimeError):
            jobs.mark_effects_started(job_id,'worker')

    def test_history_retains_previous_result(self):
        first=jobs.enqueue('manual', {'thread_id':'group'})
        jobs.claim('a'); jobs.complete(first,'a',{'links':[]})
        second=jobs.enqueue('manual', {'thread_id':'group'},parent_id=first)
        jobs.claim('b'); jobs.complete(second,'b',{'links':[{'post_link':'new'}]})
        self.assertEqual(len(jobs.history()),2)
        self.assertEqual(jobs.get_job(first)['result'],{'links':[]})

    def test_legacy_running_job_is_imported_once(self):
        with jobs.transaction() as conn:
            for key,value in [('task_status_old',{'status':'running'}),('manual_run_inputs_old',{'link':'url'})]:
                conn.execute('INSERT INTO key_value VALUES (?,?)',(key,json.dumps(value)))
        jobs.import_legacy(); jobs.import_legacy()
        self.assertEqual(jobs.get_job('old')['state'],'queued')
        self.assertEqual(len(jobs.history()),1)

    def test_limiter_expires_and_success_resets(self):
        for _ in range(5): self.assertEqual(reserve_attempt('ip'),0)
        self.assertGreater(reserve_attempt('ip'),0)
        self.assertEqual(reserve_attempt('other'),0)
        clear_attempts('ip')
        self.assertEqual(reserve_attempt('ip'),0)
        with patch('app_core.login_limits.time.time',return_value=time.time()+1000):
            self.assertEqual(reserve_attempt('ip'),0)

    def test_scheduler_keeps_one_job_per_slot(self):
        import datetime, pytz
        now=pytz.timezone('Europe/Istanbul').localize(datetime.datetime(2026,9,9,10,0))
        with patch.object(storage,'get_global_automation_status',return_value=True), patch.object(storage,'get_global_automation_settings',return_value={'times':'09:00,11:00'}), patch('app_core.automation.load_automations',return_value={'group':{'is_active':True}}):
            worker.schedule_due(now); worker.schedule_due(now)
        self.assertEqual(len(jobs.history()),1)
        job=jobs.claim('a')
        jobs.fail(job['id'],'a','temporary')
        self.due(job['id'])
        self.assertEqual(jobs.claim('b')['id'],job['id'])

    def test_manual_execution_persists_result(self):
        job_id=jobs.enqueue('manual', {'link':'url','grup_uye':'alice','thread_id':'group','post_senders_raw':[],'check_likes':False})
        job=jobs.claim('a')
        with patch('app_core.routes.main.run_manual_control',return_value={'links':[]}):
            worker.execute(job)
        self.assertEqual(jobs.get_job(job_id)['state'],'completed')

    def test_standalone_worker_process_failure_is_recoverable(self):
        job_id=jobs.enqueue('invalid-test-kind',{})
        result=subprocess.run([sys.executable,'-B','worker.py','--once'],cwd=Path(__file__).resolve().parents[1],
            env={**os.environ,'APP_DB_FILE':self.db},capture_output=True,text=True,timeout=30)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(jobs.get_job(job_id)['state'],'queued')
        self.assertEqual(jobs.get_job(job_id)['attempts'],1)

    def test_web_queues_without_calling_instagram(self):
        with patch('app_core.init_storage'):
            app=create_app()
        app.config.update(TESTING=True, SESSION_COOKIE_SECURE=False)
        client=app.test_client()
        with client.session_transaction() as session: session['admin_logged_in']=True
        with patch('app_core.routes.main.get_working_active_token',side_effect=AssertionError('Web must not call Instagram')):
            first=client.post('/',data={'post_link':'https://www.instagram.com/p/ABC123/','grup_uye':'alice'})
            second=client.post('/',data={'post_link':'https://www.instagram.com/p/ABC123/','grup_uye':'bob'})
        self.assertEqual(first.status_code,302)
        self.assertNotEqual(first.location,second.location)
        self.assertEqual(len(jobs.history()),2)
        self.assertEqual(client.get('/history').status_code,200)
        self.assertEqual(client.get(first.location).status_code,200)

    def test_login_throttle_response(self):
        with patch('app_core.init_storage'): app=create_app()
        app.config.update(TESTING=True, SESSION_COOKIE_SECURE=False)
        client=app.test_client()
        with patch('app_core.routes.admin.ADMIN_PASSWORD','correct'):
            for _ in range(5): self.assertEqual(client.post('/admin/login',data={'password':'bad'}).status_code,200)
            response=client.post('/admin/login',data={'password':'bad'})
        self.assertEqual(response.status_code,429)
        self.assertGreater(int(response.headers['Retry-After']),0)

    def test_comparison_tracks_missing_members_per_post(self):
        before={'thread_id':'group','links':[{'post_link':'url','eksikler':['alice','bob']}]}
        after={'thread_id':'group','links':[{'post_link':'url','eksikler':['bob','charlie']}]}
        diff=compare_results(before,after)[0]
        self.assertEqual(diff['resolved'],['alice'])
        self.assertEqual(diff['new_missing'],['charlie'])
        with self.assertRaises(ValueError):compare_results(before,{**after,'check_likes':True})

    def test_closed_comments_are_not_selected(self):
        from app_core.automation import _fetch_comment_details
        with patch('app_core.instagram_api.get_post_details', return_value={'sender':'alice','comments_disabled':True}), patch('app_core.instagram_api.fetch_comment_usernames') as fetch:
            self.assertEqual(_fetch_comment_details('id',{}),(set(),0,False,[]))
            fetch.assert_not_called()

    def test_automation_preflight_failure_is_retried(self):
        job_id=jobs.enqueue('automation', {'thread_id':'group'})
        job=jobs.claim('a')
        with patch('app_core.token_service.get_working_active_token', return_value=None):
            worker.execute(job)
        self.assertEqual(jobs.get_job(job_id)['state'],'queued')
        self.assertFalse(jobs.get_job(job_id)['effects_started'])

    def test_recheck_creates_new_record_and_preserves_old(self):
        source=jobs.enqueue('manual',{'link':'url','grup_uye':'alice','thread_id':'g','post_senders_raw':[],'check_likes':False})
        jobs.claim('a');jobs.complete(source,'a',{'links':[]})
        with patch('app_core.init_storage'):app=create_app()
        app.config.update(TESTING=True,SESSION_COOKIE_SECURE=False)
        client=app.test_client()
        with client.session_transaction() as session:session['admin_logged_in']=True
        response=client.post('/api/recheck/'+source,json={'only_missing':True})
        self.assertTrue(response.json['success'])
        new_id=response.json['result_url'].rsplit('/',1)[-1]
        self.assertNotEqual(new_id,source)
        self.assertEqual(jobs.get_job(new_id)['parent_id'],source)
        self.assertEqual(jobs.get_job(source)['state'],'completed')

    def test_uncertain_retry_requires_explicit_acknowledgment(self):
        source=jobs.enqueue('automation',{'thread_id':'group'})
        jobs.claim('a');jobs.mark_effects_started(source,'a');jobs.fail(source,'a','unknown')
        with patch('app_core.init_storage'):app=create_app()
        app.config.update(TESTING=True,SESSION_COOKIE_SECURE=False)
        client=app.test_client()
        with client.session_transaction() as session:session['admin_logged_in']=True
        self.assertEqual(client.post('/history/'+source+'/retry').status_code,400)
        first=client.post('/history/'+source+'/retry',data={'confirm_resend':'yes'})
        second=client.post('/history/'+source+'/retry',data={'confirm_resend':'yes'})
        self.assertEqual(first.status_code,302)
        self.assertEqual(first.location,second.location)
        self.assertEqual(len(jobs.history()),2)
