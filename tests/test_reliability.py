import asyncio
import json
import time
import unittest
from unittest.mock import Mock, AsyncMock, patch
import requests
import test_jobs
from test_token_lifecycle import bearer
from app_core import storage, jobs, create_app, instagram_api as api, session_state as state
from app_core import token_service, automation, member_analysis
from app_core.delivery import classify_dm, DeliveryResult


class ReliabilityTests(unittest.TestCase):
    setUp = test_jobs.JobTests.setUp

    def account(self):
        record = dict(username='fixture', token=bearer('old'), user_agent='agent',
                      android_id_yeni='device', device_id='device', is_active=True)
        storage.upsert_token(record)
        self.addCleanup(api.clear_http_session, 'fixture')
        return record

    def response(self, code=200, body=None):
        response = requests.Response()
        response.status_code = code
        response._content = json.dumps(body).encode()
        response.url = 'https://i.instagram.com/api/v1/test/'
        return response

    def test_dm_error_matrix_never_reports_success(self):
        for code, body, expected in [
            (200, {'status':'fail','message':'login_required'}, 'login_required'),
            (403, {'message':'Please verify','error_type':'challenge_required'}, 'challenge_required'),
            (403, {'message':'feedback_required'}, 'restricted'),
            (429, {}, 'restricted'), (500, {}, 'rejected'),
            (200, None, 'invalid_response'), (200, {'status':'ok'}, 'unconfirmed'),
            (200, {'status':'ok','payload':None}, 'unconfirmed'),
            (200, {'status':'ok','payload':{'item_id':True}}, 'unconfirmed'),
        ]:
            with self.subTest(code=code, body=body):
                result = classify_dm(self.response(code, body))
                self.assertFalse(result); self.assertEqual(result.code, expected)

    def test_dm_acceptance_requires_id_and_no_errors(self):
        body = {'status':'ok','payload':{'item_id':'123'}}
        self.assertTrue(classify_dm(self.response(body=body)))
        body['errors'] = ['failure']
        self.assertFalse(classify_dm(self.response(body=body)))

    def test_both_dm_paths_report_unknown_after_timeout_without_retry(self):
        http = Mock(); http.post.side_effect = requests.Timeout()
        with patch.object(api, 'build_auth_headers', return_value={}), patch.object(api, '_get_http_session', return_value=http):
            for function in (automation._send_dm, automation._send_dm_to_user):
                http.reset_mock()
                result = function('123','test', {})
                self.assertFalse(result); self.assertEqual(result.state, 'unknown')
                self.assertEqual(http.post.call_count, 1)

    def test_notification_stops_after_first_unconfirmed_send(self):
        with patch('app_core.init_storage'): app = create_app()
        client = app.test_client()
        with client.session_transaction() as session: session['admin_logged_in'] = True
        with patch('app_core.routes.admin.get_working_active_token', return_value={'token':'test'}), \
             patch.object(automation, '_get_user_id_by_username', return_value='123'), \
             patch.object(automation, '_send_dm_to_user', return_value=DeliveryResult('unknown','uncertain','unconfirmed')) as send:
            response = client.post('/admin/test_admin_notification', json={'notify_username':'fixture'})
        self.assertFalse(response.json['success']); self.assertEqual(send.call_count, 1)

    def test_delayed_response_cannot_roll_back_auxiliary_state(self):
        account = self.account()
        state.update_session('fixture', {'ig-set-authorization':bearer('new'),'x-ig-set-www-claim':'new'}, account['token'])
        state.update_session('fixture', {'x-ig-set-www-claim':'old'}, account['token'])
        self.assertEqual(state.get_session('fixture')['www_claim'], 'new')

    def test_revision_blocks_old_state_even_without_token_rotation(self):
        account = self.account()
        state.update_session('fixture', {'x-ig-set-www-claim':'new'}, account['token'], expected_revision=0)
        state.update_session('fixture', {'x-ig-set-www-claim':'old'}, account['token'], expected_revision=0)
        self.assertEqual(state.get_session('fixture')['www_claim'], 'new')

    def test_irrelevant_response_does_not_consume_revision(self):
        account = self.account()
        state.update_session('fixture', {'content-type':'application/json'}, account['token'], expected_revision=0)
        self.assertEqual(state.get_session('fixture').get('revision',0), 0)

    def test_cookies_survive_restart_and_explicit_auth_does_not_hide_them(self):
        account = self.account()
        response = self.response(body={})
        response.cookies.set('mid','fixture-mid',domain='i.instagram.com',path='/')
        response.cookies.set('scoped','only-other-path',domain='i.instagram.com',path='/other/')
        response.request = requests.Request('GET',response.url, headers={'authorization':account['token']}).prepare()
        api._update_session_from_response('fixture',response)
        api.clear_http_session('fixture')
        client = api._get_http_session('fixture')
        prepared = client.prepare_request(requests.Request('GET',response.url,headers={'cookie':'sessionid=synthetic'}))
        self.assertIn('mid=fixture-mid', prepared.headers['Cookie'])
        self.assertIn('sessionid=synthetic', prepared.headers['Cookie'])
        self.assertNotIn('scoped=', prepared.headers['Cookie'])
        async_headers, _ = api.prepare_async_headers('fixture', response.url, {'cookie':'sessionid=synthetic'})
        self.assertIn('mid=fixture-mid', async_headers['Cookie'])

    def test_deleted_cookie_is_not_restored(self):
        self.account()
        cookie = dict(name='mid',value='old',domain='i.instagram.com',path='/',secure=True,expires=None,rest={})
        state.update_session('fixture', {}, cookies=[cookie])
        state.update_session('fixture', {}, cookies=[{**cookie,'value':'','expires':time.time()-1}])
        self.assertEqual(state.get_session('fixture')['http_cookies'], [])

    def test_different_account_does_not_receive_cookies(self):
        self.account()
        cookie = dict(name='mid',value='old',domain='i.instagram.com',path='/',secure=True,expires=None,rest={})
        state.update_session('fixture', {}, cookies=[cookie])
        headers, _ = api.prepare_async_headers('unrelated', 'https://i.instagram.com/', {})
        self.assertNotIn('Cookie', headers)

    def test_header_rotation_and_body_claim_are_saved_together(self):
        account = self.account()
        response = self.response(body={'headers':{'x-ig-set-www-claim':'hmac.new'}})
        response.headers['ig-set-authorization'] = bearer('new')
        response.request = requests.Request('GET',response.url,headers={'authorization':account['token']}).prepare()
        api._update_session_from_response('fixture', response)
        self.assertEqual(state.get_session('fixture')['www_claim'], 'hmac.new')
        self.assertEqual(storage.load_tokens()[0]['token'], bearer('new'))

    def test_validation_timeout_is_unknown_and_account_remains_active(self):
        record = self.account()
        http = Mock(); http.post.side_effect = requests.Timeout(); http.get.side_effect = requests.Timeout()
        with patch.object(api, '_get_http_session', return_value=http):
            self.assertIsNone(api.validate_token(record))
        with patch.object(api, 'validate_token', return_value=None):
            token_service._last_validation_times.clear()
            self.assertEqual(token_service.get_working_active_token()['_validation_status'], 'unknown')
            self.assertNotIn('fixture', token_service._last_validation_times)
        self.assertTrue(storage.load_tokens()[0]['is_active'])

    def test_validation_requires_readable_data(self):
        record = self.account()
        for body, expected in [({},None),({'status':'ok'},None),({'inbox':{}},True),({'message':'login_required'},False)]:
            response = self.response(body=body)
            http = Mock(post=Mock(return_value=response), get=Mock(return_value=response))
            with patch.object(api, '_get_http_session', return_value=http), patch.object(api, '_update_session_from_response'):
                self.assertIs(api.validate_token(record), expected)

    def test_preview_reply_is_retained_and_unseen_replies_are_incomplete(self):
        parent = {'user':{'username':'bob'},'text':'parent','child_comment_count':2,
                  'preview_child_comments':[{'user':{'username':'alice'},'text':'reply'}]}
        _, records, incomplete = api.parse_comment_page(json.dumps({'comments':[parent]}))
        self.assertIn(('alice','reply'), records); self.assertTrue(incomplete)

    def scan(self, response, details):
        with patch.object(token_service,'get_working_active_token',return_value={'token':'test'}), \
             patch.object(token_service,'fetch_group_media_with_failover',return_value={'ok':True,'posts':[{'url':'https://www.instagram.com/p/ABC/'}]}), \
             patch.object(api,'fetch_comment_usernames_async',new=AsyncMock(return_value=response)), \
             patch.object(api,'get_post_details_async',new=AsyncMock(return_value=details)):
            return member_analysis.run({'username':'alice','thread_id':'g','date':'2026-09-14','check_likes':False},lambda *a:None)['rows'][0]

    def test_member_absence_requires_complete_verified_count(self):
        for details in ({}, None, {'comment_count':3,'comment_count_verified':True}):
            row = self.scan({'ok':True,'comments':[('bob','x')]},details)
            self.assertEqual(row['state'], 'unknown')
        self.assertEqual(self.scan({'ok':True,'comments':[('bob','x')]},{'comment_count':1,'comment_count_verified':True})['state'],'missing')

    def test_member_known_author_survives_bad_records_and_missing_text(self):
        row = self.scan({'ok':False,'comments':[None,('ALICE',None)]},None)
        self.assertEqual(row['state'],'present'); self.assertEqual(row['comments'],[''])

    def test_manual_control_does_not_mark_missing_when_total_exceeds_returned_comments(self):
        from app_core.routes import main
        with patch.object(main,'get_working_active_token',return_value={'token':'test'}), \
             patch.object(api,'get_post_details_async',new=AsyncMock(return_value={'comment_count':14,'comment_count_verified':True})), \
             patch.object(api,'fetch_comment_usernames_async',new=AsyncMock(return_value={'ok':True,'comments':[(f'user{i}','text') for i in range(11)]})), \
             patch('asyncio.sleep',new=AsyncMock()):
            result=main.run_manual_control('https://www.instagram.com/p/ABC/','alice bob','',[],False)
        self.assertEqual(result['links'][0]['eksikler'],[])
        self.assertTrue(result['links'][0]['error'])

    def test_automation_does_not_prepare_missing_dms_from_partial_comments(self):
        with patch.object(api,'get_post_details',return_value={'sender':'bob','comment_count':14,'comment_count_verified':True}), \
             patch.object(api,'fetch_comment_usernames',return_value={'ok':True,'comments':[('alice','one')]}):
            with self.assertRaisesRegex(RuntimeError,'eksik bildirimi gönderilmedi'):
                automation._fetch_comment_details('1',{})

    def test_fresh_analysis_of_legacy_report_does_not_reuse_old_classification(self):
        payload={'username':'alice','thread_id':'g','date':'2026-09-14','check_likes':False}
        source=jobs.enqueue('member',payload);jobs.claim_request(source,'test')
        jobs.complete(source,'test',{**payload,'rows':[],'total':0,'counts':{'unknown':0}})
        with patch('app_core.init_storage'):app=create_app()
        client=app.test_client()
        self.assertEqual(client.post('/api/member_analysis/'+source+'/retry-unknown').status_code,400)
        response=client.post('/api/member_analysis/'+source+'/refresh')
        self.assertTrue(response.json['success'])
        self.assertNotIn('retry_source',jobs.get_job(response.json['job_id'])['payload'])
        self.assertEqual(jobs.get_job(source)['state'],'completed')

    def test_admin_validation_unknown_does_not_disable_or_enable_account(self):
        self.account()
        with patch('app_core.init_storage'):app=create_app()
        client=app.test_client()
        with client.session_transaction() as session:session['admin_logged_in']=True
        with patch('app_core.routes.admin.validate_token',return_value=None):
            response=client.post('/admin/validate_token',json={'username':'fixture'})
        self.assertFalse(response.json['success'])
        self.assertTrue(storage.load_tokens()[0]['is_active'])

    def test_retry_unknown_preserves_other_modes_and_duplicate_clicks(self):
        payload = {'username':'alice','thread_id':'g','date':'2026-09-14','check_likes':False,'dual_check':True}
        source = jobs.enqueue('member', payload); jobs.claim_request(source,'test')
        row = {'url':'https://www.instagram.com/p/ABC/','sender':'bob','state':'present','comments':['saved text'],'checked_at':123}
        comment = {**payload,'check_likes':False,'rows':[row],'counts':{'present':1,'unknown':0}}
        like = {**payload,'check_likes':True,'rows':[{**row,'state':'unknown','comments':[]}],'counts':{'present':0,'unknown':1}}
        jobs.complete(source,'test',{**payload,'analysis_version':2,'comment_report':comment,'like_report':like})
        with patch('app_core.init_storage'): app=create_app()
        client=app.test_client(); path='/api/member_analysis/'+source+'/retry-unknown'
        first=client.post(path); second=client.post(path)
        self.assertEqual(first.json['job_id'],second.json['job_id'])
        retry=jobs.get_job(first.json['job_id'])
        with patch.object(token_service,'get_working_active_token',return_value={'token':'test'}), \
             patch.object(token_service,'fetch_group_media_with_failover') as media, \
             patch.object(api,'fetch_comment_usernames_async',new=AsyncMock()) as comments, \
             patch.object(api,'fetch_liker_usernames_async',new=AsyncMock(return_value={'ok':True,'usernames':['alice']})) as likes:
            result=member_analysis.run(retry['payload'], lambda *a:None)
        comments.assert_not_called(); media.assert_not_called(); self.assertEqual(likes.await_count,1)
        self.assertEqual(result['comment_report']['rows'][0]['comments'],['saved text'])
        self.assertEqual(result['comment_report']['rows'][0]['checked_at'],123)
        self.assertEqual(result['like_report']['counts']['present'],1)
        self.assertEqual(jobs.get_job(source)['result']['like_report']['rows'][0]['state'],'unknown')
