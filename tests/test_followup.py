import io
import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch, AsyncMock
import test_jobs
from app_core import create_app, jobs, storage, followup
from app_core.routes import followup as routes
from app_core.member_analysis import run


class FollowupTests(unittest.TestCase):
    setUp=test_jobs.JobTests.setUp

    def client(self, admin=False):
        with patch('app_core.init_storage'): app=create_app()
        client=app.test_client()
        if admin:
            with client.session_transaction() as session:session['admin_logged_in']=True
        return client

    def source(self):
        identifier=jobs.enqueue('manual',dict(link='https://www.instagram.com/p/ABC',grup_uye='alice bob',thread_id='g',post_senders_raw=[],check_likes=False))
        jobs.claim_request(identifier,'test')
        jobs.complete(identifier,'test',dict(group=['alice','bob'],thread_id='g',links=[dict(post_link='https://www.instagram.com/p/ABC',eksikler=['bob'],commenters=['alice'],checked_at=1,source='live')],user_missing_posts={'bob':['https://www.instagram.com/p/ABC']}))
        return identifier

    def test_extraction_deduplicates_media_types_and_ignores_unrelated_links(self):
        self.assertEqual(followup.extract_links('Hello https://www.instagram.com/reel/ABC/?x=2 and https://instagram.com/p/ABC/ https://evil.com/p/Z'),['https://www.instagram.com/p/ABC/'])

    def test_rules_dates_owner_exclusion_and_missing_date(self):
        rules=followup.validate_rules(dict(joined={'alice':'2026-09-10'},leave=[dict(username='bob',start='2026-09-01',end='2026-09-09')],grace_hours=2))
        self.assertIn('katılmadan',followup.eligibility('alice','u','other','2026-09-09',rules,now=2e9))
        self.assertIn('İzinli',followup.eligibility('bob','u','other','2026-09-09',rules,now=2e9))
        self.assertIn('Tarih doğrulanamadı',followup.eligibility('bob','u','other',None,rules))
        self.assertEqual(followup.eligibility('alice','u','alice',None,rules),'Kendi paylaşımı')
        with self.assertRaises(ValueError):followup.validate_rules({'grace_hours':-1})
        with self.assertRaises(ValueError):followup.validate_rules({'joined':{'alice':'bad-date'}})

    def test_report_rules_remove_only_excluded_members(self):
        followup.write('rules:g',followup.validate_rules({'exempt':['bob']}))
        result=followup.apply_rules(dict(group=['alice','bob'],links=[dict(post_link='u',eksikler=['alice','bob'])]),'g')
        self.assertEqual(result['user_missing_posts'],{'alice':['u']})
        self.assertEqual(result['links'][0]['excluded_members']['bob'],'Grup muafiyeti')

    def test_changes_do_not_claim_removed_comments_on_failed_or_cached_data(self):
        post=dict(post_link='u',eksikler=['bob'],comments_list=[dict(username='alice',text='old')])
        new=dict(post_link='u',eksikler=[],commenters=['bob'],comments_list=[dict(username='alice',text='new')])
        delta=followup.changes({'links':[post]},{'links':[new]})[0]
        self.assertEqual(delta['resolved'],['bob']);self.assertEqual(delta['changed'],['alice'])
        for flags in ({'error':'unavailable'},{'source':'previous'}):self.assertEqual(followup.changes({'links':[post]},{'links':[{**new,**flags}]}),[])

    def test_member_identity_requires_matching_id(self):
        followup.track_members('g',[{'id':1,'username':'old'}])
        change=followup.track_members('g',[{'id':1,'username':'new'},{'id':2,'username':'other'}])
        self.assertEqual(change['renamed'],[dict(before='old',after='new')]);self.assertEqual(change['added'],['other'])
        followup.track_members('h',[{'username':'old'}])
        self.assertEqual(followup.track_members('h',[{'username':'new'}])['renamed'],[])

    def test_report_notes_export_and_member_card(self):
        source=self.source();client=self.client()
        for path in ('/followup/'+source,'/members/alice'):
            self.assertEqual(client.get(path).status_code,200)
        self.assertEqual(client.post('/followup/'+source+'/note',data={'url':'bad','note':'x'}).status_code,400)
        response=client.post('/followup/'+source+'/note',data={'url':'https://www.instagram.com/p/ABC','note':'<script>alert(1)</script>'})
        self.assertEqual(response.status_code,302)
        rendered=client.get('/followup/'+source).get_data(as_text=True)
        self.assertIn('&lt;script&gt;',rendered);self.assertNotIn('<script>alert',rendered)
        response=client.get('/followup/'+source+'/export.xlsx')
        self.assertEqual(response.status_code,200)
        with zipfile.ZipFile(io.BytesIO(response.data)) as archive:
            self.assertIn(b'bob',archive.read('xl/worksheets/sheet1.xml'))
            self.assertIn(b'inlineStr',archive.read('xl/worksheets/sheet1.xml'))

    def test_admin_guards_and_backup_path_validation(self):
        for path in ('/backups','/group-rules','/trash','/backups/test/download'):
            self.assertEqual(self.client().get(path).status_code,403)
        with tempfile.TemporaryDirectory() as root,patch.object(routes,'BACKUP_ROOT',Path(root)):
            folder=Path(root)/'backup-date';folder.mkdir();(folder/'database.sqlite').write_bytes(b'test-db')
            client=self.client(True)
            self.assertEqual(client.get('/backups').status_code,200)
            response=client.get('/backups/backup-date/download');self.assertEqual(response.data,b'test-db');response.close()
            self.assertEqual(client.get('/backups/unknown/download').status_code,404)

    def test_trash_preserves_value_and_refuses_overwrite(self):
        followup.write('rules:g',{'exempt':['alice']});routes.move_to_trash('rules:g','Group')
        conn=storage._connect()
        try:key=conn.execute("SELECT key FROM key_value WHERE key LIKE 'trash:%'").fetchone()[0]
        finally:conn.close()
        followup.write('rules:g',{'exempt':['bob']})
        self.assertEqual(self.client(True).post('/trash/'+key[6:]+'/restore').status_code,409)
        self.assertEqual(followup.read('rules:g'),{'exempt':['bob']})
        with jobs.transaction() as conn:conn.execute('DELETE FROM key_value WHERE key=?',('rules:g',))
        self.assertEqual(self.client(True).post('/trash/'+key[6:]+'/restore').status_code,302)
        self.assertEqual(followup.read('rules:g'),{'exempt':['alice']})

    def test_range_validation_and_unknown_retry(self):
        source=self.source();client=self.client()
        self.assertEqual(client.post('/api/member_analysis/'+source,json=dict(username='alice',date='2026-09-01',end_date='2026-10-10')).status_code,400)
        response=client.post('/api/member_analysis/'+source,json=dict(username='alice',date='2026-09-01',end_date='2026-09-03',skip_owner=True))
        self.assertEqual(jobs.get_job(response.json['job_id'])['payload']['end_date'],'2026-09-03')
        response=client.post('/api/recheck/'+source,json={'unknown_only':True})
        self.assertTrue(jobs.get_job(response.json['result_url'].split('/')[-1])['payload']['unknown_only'])

    def test_range_scan_deduplicates_and_keeps_unknown_separate(self):
        with patch('app_core.token_service.get_working_active_token',return_value={'token':'test'}),patch('app_core.token_service.fetch_group_media_with_failover',return_value={'ok':True,'posts':[{'url':'https://www.instagram.com/p/ABC/','username':'bob'}]}) as media,patch('app_core.instagram_api.fetch_comment_usernames_async',new=AsyncMock(return_value={'ok':True,'incomplete':True,'comments':[]})),patch('app_core.instagram_api.fetch_liker_usernames_async',new=AsyncMock(return_value=None)):
            result=run(dict(username='alice',thread_id='g',date='2026-09-01',end_date='2026-09-03',check_likes=False,dual_check=True),lambda *args:None)
        self.assertEqual(media.call_count,3)
        self.assertEqual(result['total'],1)
        self.assertEqual(result['comment_report']['counts']['unknown'],1)
        self.assertEqual(result['like_report']['counts']['unknown'],1)

    def test_healthcheck_does_not_insert_audit_or_token_rows(self):
        self.source()
        from app_core.healthcheck import verify
        with patch('app_core.init_storage'):app=create_app()
        conn=storage._connect()
        try:before=conn.execute('SELECT COUNT(*) FROM jobs').fetchone()[0]
        finally:conn.close()
        self.assertEqual(verify(app)['rapor'],'başarılı')
        conn=storage._connect()
        try:self.assertEqual(conn.execute('SELECT COUNT(*) FROM jobs').fetchone()[0],before)
        finally:conn.close()

    def test_checkpoint_reuses_completed_post_without_instagram_fetch(self):
        from app_core.routes import main
        row=dict(post_link='https://www.instagram.com/p/ABC',eksikler=['bob'],commenters=['alice'],comments_list=[['alice','nice photo']],commenters_normalized=['alice'],checked_at=123)
        with patch.object(main,'get_working_active_token',return_value={'token':'test'}),patch('app_core.instagram_api.get_post_details_async',new=AsyncMock()) as remote,patch.object(main,'add_audit_log'):
            result=main.run_manual_control(row['post_link'],'alice bob','',[],False,checkpoints={row['post_link']:row})
        remote.assert_not_called()
        self.assertEqual(result['links'][0]['checked_at'],123)
        self.assertEqual(result['links'][0]['source'],'checkpoint')
        self.assertEqual(result['user_missing_posts'],{'bob':[row['post_link']]})

    def test_unknown_only_preserves_good_post_without_rescan(self):
        from app_core.routes import main
        url='https://www.instagram.com/p/ABC'
        previous={'links':[dict(post_link=url,eksikler=['bob'],commenters=['alice'],comments_list=[{'username':'alice','text':'nice'}],checked_at=100)]}
        with patch.object(main,'get_working_active_token',return_value={'token':'test'}),patch('app_core.instagram_api.get_post_details_async',new=AsyncMock()) as remote,patch.object(main,'add_audit_log'):
            result=main.run_manual_control(url,'alice bob','',[],False,unknown_only=True,prev_result=previous)
        remote.assert_not_called();self.assertEqual(result['links'][0]['source'],'previous');self.assertEqual(result['links'][0]['checked_at'],100)

    def test_own_post_member_analysis_is_excluded_not_missing(self):
        with patch('app_core.token_service.get_working_active_token',return_value={'token':'test'}),patch('app_core.token_service.fetch_group_media_with_failover',return_value={'ok':True,'posts':[{'url':'https://www.instagram.com/p/ABC/','username':'alice'}]}),patch('app_core.instagram_api.fetch_comment_usernames_async',new=AsyncMock()) as remote:
            result=run(dict(username='alice',thread_id='g',date='2026-09-01',check_likes=False,dual_check=True,skip_owner=True),lambda *args:None)
        remote.assert_not_called();self.assertEqual(result['comment_report']['counts']['excluded'],1)

    def test_group_settings_form_and_schema_preview(self):
        storage.save_automations({'g':dict(is_active=False,group_name='Example')})
        response=self.client(True).post('/group-rules',data=dict(thread_id='g',min_words='4',grace_hours='2',mode='comments',skip_owner='on',joined='alice 2026-09-01',leave='bob 2026-09-01 2026-09-03'))
        self.assertEqual(response.status_code,302)
        self.assertEqual(followup.rules_for('g')['min_words'],4)
        self.assertEqual(self.client(True).get('/group-rules?thread_id=g').status_code,200)
        from scripts.pythonanywhere_setup import schema_preview
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'new.sqlite'
            result=schema_preview(Path(__file__).resolve().parent.parent,path.resolve())
            self.assertTrue(any('tokens' in line for line in result))
            self.assertFalse(path.exists())

    def test_group_removal_moves_settings_to_trash(self):
        storage.save_automations({'g':dict(is_active=False,group_name='Example')})
        storage.save_automations({})
        conn=storage._connect()
        try:
            row=conn.execute("SELECT key,value FROM key_value WHERE key LIKE 'trash:%'").fetchone()
        finally:conn.close()
        self.assertEqual(json.loads(row['value'])['key'],'automation:g')
        self.assertEqual(self.client(True).post('/trash/'+row['key'][6:]+'/restore').status_code,302)
        self.assertIn('g',storage.load_automations())

    def test_cancellation_does_not_trigger_sync_fallback(self):
        from app_core.routes import main
        with patch.object(main,'get_working_active_token',return_value={'token':'test'}),patch('app_core.instagram_api.get_post_details_async',new=AsyncMock(side_effect=jobs.ControlStopped('stop'))),patch.object(main,'get_post_details') as fallback:
            with self.assertRaises(jobs.ControlStopped):main.run_manual_control('https://www.instagram.com/p/ABC','alice','',[],False)
        fallback.assert_not_called()

    def test_timezone_and_exemptions_do_not_create_false_completion(self):
        rules=followup.validate_rules({'joined':{'alice':'2026-09-02'}})
        self.assertIsNone(followup.eligibility('alice','u','bob','2026-09-01T22:30:00Z',rules,now=2e9))
        old={'links':[dict(post_link='u',eksikler=['alice'])]}
        new={'links':[dict(post_link='u',eksikler=[],commenters=[],excluded_members={'alice':'Muaf'})]}
        self.assertEqual(followup.changes(old,new)[0]['resolved'],[])

    def test_group_comment_format_rules_are_applied_to_new_checks(self):
        from test_audit_regressions import AuditRegressions
        followup.write('rules:',followup.validate_rules({'min_words':1,'require_emoji':False}))
        result,_,_=AuditRegressions.control(self)
        self.assertNotIn('alice',result['invalid_comment_users'])
        followup.write('rules:',followup.validate_rules({'min_words':3,'require_emoji':False}))
        result,_,_=AuditRegressions.control(self)
        self.assertIn('alice',result['invalid_comment_users'])

    def test_excluded_posts_do_not_call_instagram_or_claim_completion(self):
        from app_core.routes import main
        url='https://www.instagram.com/p/ABC'
        followup.write('rules:',followup.validate_rules({'excluded':[url]}))
        with patch.object(main,'get_working_active_token',return_value={'token':'test'}),patch('app_core.instagram_api.get_post_details_async',new=AsyncMock()) as remote,patch.object(main,'add_audit_log'):
            result=main.run_manual_control(url,'alice','',[],False)
        remote.assert_not_called();self.assertEqual(result['all_commented'],[]);self.assertEqual(result['user_missing_posts'],{})

    def test_member_card_follows_verified_account_rename(self):
        self.source()
        followup.track_members('g',[dict(id=7,username='alice')])
        followup.track_members('g',[dict(id=7,username='renamed')])
        records=followup.member_history('renamed')
        self.assertEqual(records[0]['state'],'Tamamlandı')
