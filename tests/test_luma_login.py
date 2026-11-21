"""Resumable login tests with synthetic SDK clients; all sockets are blocked."""
import base64
import copy
import json
import socket
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch
import uuid
import types

import requests
import test_jobs
from app_core import luma_login as login, storage, session_state
from app_core.login_client import apply_profile


class FakeClient:
    def __init__(self):
        self.settings={'uuids':{'uuid':str(uuid.uuid4()),'phone_id':str(uuid.uuid4()),
            'android_device_id':'android-'+uuid.uuid4().hex[:16]},
            'device_settings':{'model':'Pixel 8 Pro','app_version':'449.0.0.52.84'},
            'authorization_data':{},'cookies':{},'user_agent':'Instagram 449.0.0.52.84 Android (fake)'}
        self.private=requests.Session();self.public=requests.Session();self.graphql=requests.Session()
        self.username='';self.password='';self.caa_aac='context-secret'
        self.ig_u_rur='region';self.ig_www_claim='claim';self.locale='tr_TR';self.country='TR';self.timezone_offset=10800;self.mid='mid'
        self.bloks_versioning_id='a'*64
        self.bloks_caa_login=Mock(side_effect=self.sign)
        self.account_info=Mock(side_effect=lambda:SimpleNamespace(pk=self.user_id,username=self.username,full_name='Fake User'))
        self.bloks_two_step_verification_entrypoint=Mock(return_value={'step':login.APPROVAL,'context':'server-context'})
        self.bloks_two_step_verification_method_picker=Mock(return_value={'methods':['whatsapp','totp','sms','backup']})
        self.bloks_two_step_verification_select_method=Mock(return_value={'step':login.WHATSAPP})
        self.bloks_app=Mock(return_value={'step':login.VERIFY})
        self.bloks_async_action=Mock(return_value={'logged_in':True})
        self.bloks_two_step_verification_verify_code=Mock(return_value={'logged_in':True})
        self.bloks_two_step_verification_enter_totp_code=Mock(return_value={})
        self.bloks_two_step_verification_enter_backup_code=Mock(return_value={})
        self.bloks_ap_two_step_verification_submit_code=Mock(return_value={'logged_in':True})
        self.private_request=Mock(return_value={'step':login.APPROVAL,'context':'updated-context'})

    @property
    def uuid(self):return self.settings['uuids']['uuid']
    @property
    def phone_id(self):return self.settings['uuids']['phone_id']
    @property
    def android_device_id(self):return self.settings['uuids']['android_device_id']
    @property
    def user_agent(self):return self.settings['user_agent']
    @property
    def user_id(self):return self.settings['authorization_data'].get('ds_user_id')
    @property
    def authorization(self):
        return 'Bearer IGT:2:'+base64.b64encode(json.dumps(self.settings['authorization_data']).encode()).decode() if self.user_id else ''
    @property
    def authorization_data(self):return self.settings['authorization_data']
    @authorization_data.setter
    def authorization_data(self,value):self.settings['authorization_data']=value
    def parse_authorization(self,token):return json.loads(base64.b64decode(token.removeprefix('Bearer IGT:2:')))
    def get_settings(self):return copy.deepcopy(self.settings)
    def set_settings(self,settings):
        self.settings=copy.deepcopy(settings)
        self.private.cookies=requests.utils.cookiejar_from_dict(settings.get('cookies',{}))
    def set_uuids(self,ids):self.settings['uuids']=copy.deepcopy(ids)
    def set_device(self,device,**kwargs):self.settings['device_settings'].update(device)
    def set_user_agent(self,value):self.settings['user_agent']=value
    def sign(self,**kwargs):
        self.settings['authorization_data']={'ds_user_id':'123','sessionid':'fake-session'}
        self.private.cookies.set('sessionid','fake-session',domain='i.instagram.com',path='/')
        return {'logged_in':True}
    def bloks_apply_login_response(self,result):
        if result.get('logged_in'):self.sign();return True
        return False
    def bloks_extract_login_response(self,result):
        return {'logged_in':True,'login_response':{'logged_in_user':{'pk':'123','username':self.username}}} if result.get('logged_in') else {}
    def _bloks_all_text(self,result):return json.dumps(result)
    def bloks_extract_two_step_verification_context(self,result):return result.get('context')
    def _bloks_extract_context_value(self,result,action,key):return None
    def _bloks_payload(self,value):return value


class LumaLoginTests(unittest.TestCase):
    def setUp(self):
        test_jobs.JobTests.setUp(self)
        guard=patch('socket.socket.connect',side_effect=AssertionError('Live login forbidden'))
        guard.start();self.addCleanup(guard.stop)
        self.clients=[]
        def factory():
            client=FakeClient();self.clients.append(client);return client
        self.factory=patch.object(login,'make_client',side_effect=factory)
        self.factory.start();self.addCleanup(self.factory.stop)

    def read_profile(self,name='alice'):
        with login.transaction() as conn:return login._get(conn,'luma-account:'+name)

    def pending(self):
        client=FakeClient();client.bloks_caa_login=Mock(return_value={
            'logged_in':False,'two_step_verification_context':'server-context','result':{'step':login.APPROVAL}})
        with patch.object(login,'make_client',return_value=client):
            flow=login.start('alice','SECRETPASSWORD',owner='browser')
        return flow,client

    def test_verified_login_saves_token_and_profile_without_password(self):
        flow=login.start('alice','SECRETPASSWORD',owner='browser')
        self.assertEqual(flow['stage'],'done');self.assertEqual(len(storage.load_tokens()),1)
        self.assertEqual(storage.load_tokens()[0]['password'],'')
        with login.transaction() as conn:
            values=' '.join(r['value'] for r in conn.execute('SELECT value FROM key_value'))
        self.assertNotIn('SECRETPASSWORD',values)
        self.assertNotIn('settings',flow);self.assertNotIn('context',flow)
        self.assertEqual(self.clients[-1].password,'')

    def test_new_login_is_used_by_dm_even_when_job_holds_previous_device(self):
        from app_core.direct_sender import send_text
        from urllib.parse import parse_qs
        login.start('alice','pw',owner='browser')
        previous=storage.load_tokens()[0]
        login.start('alice','pw',owner='browser',new_device=True)
        current=storage.load_tokens()[0]
        self.assertNotEqual(previous['device_id'],current['device_id'])
        captured=[]
        def transport(session,request,**kwargs):
            captured.append(request)
            body=parse_qs(request.body)
            response=requests.Response();response.status_code=200;response.request=request
            response._content=json.dumps({'status':'ok','payload':{'item_id':'99','thread_id':'456',
                'client_context':body['client_context'][0]}}).encode()
            return response
        with patch('requests.sessions.Session.send',new=transport):
            result=send_text('456','Synthetic integration test',previous,request_id='new-login')
        self.assertTrue(result);self.assertEqual(len(captured),1)
        request=captured[0];body=parse_qs(request.body)
        self.assertEqual(request.headers['authorization'],current['token'])
        self.assertEqual(request.headers['user-agent'],current['user_agent'])
        self.assertEqual(request.headers['x-ig-device-id'],current['device_id'])
        self.assertEqual(body['_uuid'][0],current['device_id'])
        self.assertEqual(request.headers['x-ig-android-id'],'android-'+current['android_id_yeni'])
        self.assertEqual(body['device_id'][0],request.headers['x-ig-android-id'])
        self.assertEqual(request.headers['x-bloks-version-id'],'a'*64)
        self.assertIn('sessionid=fake-session',request.headers['Cookie'])
        self.assertEqual(request.headers['x-ig-family-device-id'],self.clients[-1].phone_id)
        self.assertEqual(request.headers['ig-intended-user-id'],'123')

    def test_new_login_reads_groups_members_and_posts_with_its_saved_session(self):
        from app_core import instagram_api as api
        from datetime import datetime, timezone, timedelta
        login.start('alice','pw',owner='browser')
        record=storage.load_tokens()[0]
        now=datetime.now(timezone(timedelta(hours=3)))
        stamp=int(now.timestamp()*1000000)
        users=[{'pk':'123','username':'alice'},{'pk':'456','username':'bob'}]
        messages=[{'timestamp':stamp,'item_id':'msg1','user_id':'456','item_type':'xma_media_share',
                   'xma_media_share':[{'target_url':None}]}]
        thread={'thread_id':'789','thread_title':'Synthetic group','users':users,'items':messages,
                'thread_image':None,'admin_user_ids':None,'has_older':False}
        captured=[]
        def transport(session,request,**kwargs):
            captured.append(request)
            self.assertEqual(request.method,'GET')
            self.assertEqual(request.headers['authorization'],record['token'])
            self.assertIn('sessionid=fake-session',request.headers['Cookie'])
            self.assertEqual(request.headers['x-ig-device-id'],record['device_id'])
            if '/inbox/' in request.url:data={'inbox':{'threads':[thread]}}
            elif '/media/' in request.url:data={'items':[{'timestamp':stamp,'media':{'code':'TEST',
                'user':None,'image_versions2':None,'carousel_media':[None,{'image_versions2':None}]},
                'media_share':{'user':None},'user':None}]}
            else:data={'thread':thread}
            response=requests.Response();response.status_code=200;response.request=request
            response._content=json.dumps(data).encode();return response
        with patch('requests.sessions.Session.send',new=transport):
            groups=api.fetch_group_threads(record)
            members=api.fetch_group_members(record,'789')
            posts=api.fetch_group_media(record,'789',now,complete=True)
        self.assertTrue(groups['ok'],groups);self.assertEqual(len(groups['groups']),1)
        self.assertTrue(members['ok'],members);self.assertEqual(members['usernames'],['alice','bob'])
        self.assertTrue(posts['ok'],posts);self.assertEqual(posts['posts'][0]['code'],'TEST')
        self.assertIsNone(posts['posts'][0]['thumbnail_url']);self.assertEqual(len(captured),4)

    def test_media_read_uses_session_rotated_by_preceding_thread_response(self):
        from app_core import instagram_api as api
        login.start('alice','pw',owner='browser')
        record=storage.load_tokens()[0]
        new_auth='Bearer IGT:2:'+base64.b64encode(json.dumps({'ds_user_id':'123','sessionid':'rotated'}).encode()).decode()
        calls=[]
        def transport(session,request,**kwargs):
            calls.append(request)
            response=requests.Response();response.status_code=200;response.request=request
            if len(calls)==1:
                response.headers['ig-set-authorization']=new_auth
                data={'thread':{'items':[],'users':None,'inviter':None,'has_older':False}}
            else:
                self.assertEqual(request.headers['authorization'],new_auth)
                self.assertIn('sessionid=rotated',request.headers['Cookie'])
                data={'items':[]}
            response._content=json.dumps(data).encode();return response
        with patch('requests.sessions.Session.send',new=transport):
            result=api.fetch_group_media(record,'789',complete=True)
        self.assertTrue(result['ok'],result);self.assertEqual(len(calls),2)

    def test_all_25_presets_generate_separate_ids_even_for_same_model(self):
        from app_core.device_profiles import DEVICE_PROFILES
        self.assertEqual(len(DEVICE_PROFILES),25)
        seen=set()
        for index,key in enumerate(DEVICE_PROFILES):
            for duplicate_model in range(2):
                name='device'+str(index)+'_'+str(duplicate_model)
                flow=login.start(name,'pw',owner='browser',profile_name=key)
                self.assertEqual(flow['stage'],'done',flow)
                ids=self.read_profile(name)['settings']['uuids']
                values=set(ids.values())
                self.assertEqual(len(values),7);self.assertFalse(values & seen)
                seen.update(values)
        self.assertEqual(len(seen),350)

    def test_custom_profile_cannot_duplicate_another_saved_device(self):
        login.start('alice','pw',owner='browser')
        ids=self.read_profile()['settings']['uuids']
        with self.assertRaises(login.LoginFailure):
            login.start('bob','pw',owner='browser',profile_name='custom',
                custom_profile={'uuids':{'uuid':ids['uuid']}})
        self.assertIsNone(self.read_profile('bob'))

    def test_saved_option_preserves_device_and_ids(self):
        login.start('alice','pw',owner='browser',profile_name='s24')
        before=self.read_profile()['settings']['uuids']
        flow=login.start('alice',owner='browser',profile_name='saved')
        self.assertEqual(flow['device'],'SM-S921B')
        after=self.read_profile()['settings']['uuids']
        for key in ('uuid','android_device_id','phone_id','advertising_id','tray_session_id'):
            self.assertEqual(before[key],after[key])

    def test_selecting_different_model_applies_it_without_extra_checkbox(self):
        login.start('alice','pw',owner='browser')
        before=self.read_profile()['settings']['uuids']
        flow=login.start('alice','pw',owner='browser',profile_name='s24ultra')
        self.assertEqual(flow['stage'],'done');self.assertEqual(flow['device'],'SM-S928B')
        after=self.read_profile()['settings']['uuids']
        for key in before:self.assertNotEqual(before[key],after[key])
        flow=login.start('alice',owner='browser',profile_name='s24ultra')
        self.assertEqual(flow['stage'],'done');self.assertEqual(self.read_profile()['settings']['uuids']['uuid'],after['uuid'])

    def test_different_model_without_password_preserves_existing_profile(self):
        login.start('alice','pw',owner='browser')
        before=self.read_profile()
        with self.assertRaises(login.LoginFailure):
            login.start('alice',owner='browser',profile_name='s24ultra')
        self.assertEqual(self.read_profile(),before)

    def test_recreating_saved_device_preserves_model_with_new_ids(self):
        login.start('alice','pw',owner='browser',profile_name='s24ultra')
        before=self.read_profile()['settings']['uuids']['uuid']
        flow=login.start('alice','pw',owner='browser',new_device=True)
        self.assertEqual(flow['device'],'SM-S928B')
        self.assertNotEqual(before,self.read_profile()['settings']['uuids']['uuid'])

    def test_each_account_has_distinct_persistent_device(self):
        login.start('alice','pw',owner='browser');login.start('bob','pw',owner='browser')
        a=self.read_profile('alice')['settings']['uuids'];b=self.read_profile('bob')['settings']['uuids']
        self.assertNotEqual(a['uuid'],b['uuid']);self.assertNotEqual(a['android_device_id'],b['android_device_id'])

    def test_saved_session_is_verified_without_new_password_login(self):
        login.start('alice','pw',owner='browser');first=self.read_profile()['settings']['uuids']
        flow=login.start('alice',owner='browser')
        self.assertEqual(flow['stage'],'done');self.clients[-1].bloks_caa_login.assert_not_called()
        second=self.read_profile()['settings']['uuids']
        self.assertEqual(first['uuid'],second['uuid']);self.assertNotEqual(first['request_id'],second['request_id'])

    def test_password_alone_reauthenticates_instead_of_reusing_expired_auth(self):
        login.start('alice','pw',owner='browser')
        ids=self.read_profile()['settings']['uuids']
        observed=[]
        client=FakeClient()
        def sign(**kwargs):
            observed.append((client.user_id,client.private.cookies.get('sessionid')))
            return client.sign(**kwargs)
        client.bloks_caa_login=Mock(side_effect=sign)
        with patch.object(login,'make_client',return_value=client):
            flow=login.start('alice','new-password',owner='browser')
        self.assertEqual(flow['stage'],'done');self.assertEqual(observed,[(None,None)])
        self.assertEqual(client.uuid,ids['uuid'])
        self.assertEqual(client.android_device_id,ids['android_device_id'])
        self.assertEqual(client.phone_id,ids['phone_id'])
        self.assertNotIn('new-password',json.dumps(self.read_profile()))

    def test_explicit_fresh_login_preserves_device(self):
        login.start('alice','pw',owner='browser');before=self.read_profile()['settings']['uuids']['uuid']
        flow=login.start('alice','new-secret',owner='browser',fresh=True)
        self.assertEqual(flow['stage'],'done');self.assertEqual(before,self.read_profile()['settings']['uuids']['uuid'])
        self.clients[-1].bloks_caa_login.assert_called_once()

    def test_explicit_new_device_changes_identity_and_supports_another_model(self):
        login.start('alice','pw',owner='browser');before=self.read_profile()['settings']['uuids']['uuid']
        flow=login.start('alice','pw',owner='browser',new_device=True,profile_name='s23')
        self.assertEqual(flow['device'],'SM-S911B');self.assertNotEqual(before,self.read_profile()['settings']['uuids']['uuid'])

    def test_profile_rejects_captured_headers_tokens_and_version_mismatch(self):
        for profile in ({'token':'captured'},{'authorization':'captured'}, {'uuids':{'client_session_id':'captured'}},
                        {'device_settings':{'app_version':'1'},'user_agent':'Instagram 2 Android fake'}):
            with self.assertRaises(ValueError):apply_profile(FakeClient(),profile)

    def test_approval_polls_only_the_issued_context_without_credentials(self):
        flow,initial=self.pending();self.assertEqual(flow['stage'],'approval')
        resumed=FakeClient();resumed.private_request=Mock(return_value={'logged_in':True})
        with patch.object(login,'make_client',return_value=resumed):
            done=login.advance(flow['id'],'browser','poll')
        self.assertEqual(done['stage'],'done');resumed.bloks_caa_login.assert_not_called()
        params=resumed.private_request.call_args.kwargs['data']
        self.assertEqual(params['server_params']['two_step_verification_context'],'server-context')
        self.assertNotIn('password',json.dumps(params));self.assertEqual(initial.password,'')

    def test_direct_approval_screen_context_is_recovered_and_completed(self):
        initial=FakeClient()
        initial.bloks_caa_login=Mock(return_value={'logged_in':False,
            'result':{'step':login.APPROVAL},'two_step_verification_context':''})
        initial._bloks_extract_context_value=Mock(side_effect=lambda result,action,key:
            'direct-screen-context' if action==login.APPROVAL and key=='two_step_verification_context' else None)
        with patch.object(login,'make_client',return_value=initial):
            flow=login.start('alice','pw',owner='browser')
        self.assertEqual(flow['stage'],'approval')
        initial.bloks_two_step_verification_entrypoint.assert_not_called()
        resumed=FakeClient();resumed.private_request=Mock(return_value={'logged_in':True})
        with patch.object(login,'make_client',return_value=resumed):
            done=login.advance(flow['id'],'browser','poll')
        self.assertEqual(done['stage'],'done')
        self.assertEqual(resumed.private_request.call_args.kwargs['data']['server_params']['two_step_verification_context'],'direct-screen-context')
        resumed.bloks_caa_login.assert_not_called()

    def test_missing_context_or_preflight_is_not_misreported_as_waiting_for_phone(self):
        for index,reason in enumerate(('', 'CAA preflight did not return account access and attestation data')):
            client=FakeClient();client.bloks_caa_login=Mock(return_value={'logged_in':False,'reason':reason})
            with patch.object(login,'make_client',return_value=client):
                flow=login.start('missing'+str(index),'pw',owner='browser')
            self.assertEqual(flow['stage'],'failed')
            with login.transaction() as conn:
                stored=login._get(conn,'luma-flow:'+flow['id'])
            self.assertFalse(stored['login_diagnostics']['has_approval_context'])
            self.assertEqual(stored['login_diagnostics']['preflight_failed'],bool(reason))
            self.assertNotIn('login_diagnostics',flow)

    def test_response_diagnostics_keep_structure_without_response_secrets(self):
        from app_core.login_client import login_response_summary
        client=FakeClient()
        outcome={'result':{'status':'ok','layout':{'action':
            'com.bloks.www.caa.login.approval "challenge_context" "SECRET-CONTEXT"'},
            'headers':{'Authorization':'SECRET-TOKEN'},'cookies':{'sessionid':'SECRET-COOKIE'},
            'message':'PRIVATE-EMAIL'}}
        summary=login_response_summary(client,outcome)
        encoded=json.dumps(summary)
        for secret in ('SECRET-CONTEXT','SECRET-TOKEN','SECRET-COOKIE','PRIVATE-EMAIL'):
            self.assertNotIn(secret,encoded)
        self.assertTrue(summary['markers']['challenge_context'])
        self.assertEqual(summary['apps'],['com.bloks.www.caa.login.approval'])

    def test_poll_rejects_wrong_user_before_applying_session(self):
        flow,_=self.pending();client=FakeClient()
        client.private_request=Mock(return_value={'logged_in':True})
        client.bloks_extract_login_response=Mock(return_value={'login_response':{'logged_in_user':{'pk':'999','username':'another'}}})
        client.bloks_apply_login_response=Mock()
        with patch.object(login,'make_client',return_value=client):
            result=login.advance(flow['id'],'browser','poll')
        self.assertEqual(result['stage'],'failed');client.bloks_apply_login_response.assert_not_called()

    def test_other_browser_cannot_inspect_or_continue_flow(self):
        flow,_=self.pending()
        for operation in (lambda:login.status(flow['id'],'other'),lambda:login.advance(flow['id'],'other','poll')):
            with self.assertRaises(login.LoginFailure) as raised:operation()
            self.assertEqual(raised.exception.status,404)

    def test_existing_pending_flow_is_not_replaced_with_another_password_attempt(self):
        flow,_=self.pending()
        with self.assertRaises(login.LoginFailure) as raised:login.start('alice','another',owner='browser')
        self.assertEqual(raised.exception.status,409)
        self.assertEqual(self.read_profile()['flow_id'],flow['id'])

    def test_whatsapp_selection_and_code_resume_without_password_replay(self):
        flow,_=self.pending();methods=login.advance(flow['id'],'browser','methods')
        self.assertIn('whatsapp',methods['methods'])
        code=login.advance(flow['id'],'browser','select',method='whatsapp');self.assertEqual(code['stage'],'code')
        result=login.advance(flow['id'],'browser','code',code='987654')
        self.assertEqual(result['stage'],'done');self.clients[-1].bloks_caa_login.assert_not_called()
        self.assertEqual(self.clients[-1].bloks_async_action.call_args.args[0],login.VERIFY)
        with login.transaction() as conn:
            raw=json.dumps(login._get(conn,'luma-flow:'+flow['id']))
        self.assertNotIn('987654',raw)

    def test_server_unoffered_method_is_rejected_without_request(self):
        flow,_=self.pending()
        with self.assertRaises(login.LoginFailure):login.advance(flow['id'],'browser','select',method='whatsapp')

    def test_cancel_is_persistent_and_does_not_activate_a_token(self):
        flow,_=self.pending();cancelled=login.advance(flow['id'],'browser','cancel')
        self.assertEqual(cancelled['stage'],'cancelled');self.assertEqual(storage.load_tokens(),[])
        self.assertEqual(login.advance(flow['id'],'browser','poll')['stage'],'cancelled')

    def test_wrong_authenticated_account_never_replaces_existing_token(self):
        client=FakeClient();client.account_info=Mock(return_value=SimpleNamespace(pk='999',username='mallory'))
        with patch.object(login,'make_client',return_value=client):flow=login.start('alice','pw',owner='browser')
        self.assertEqual(flow['stage'],'failed');self.assertEqual(storage.load_tokens(),[])

    def test_unverified_new_session_survives_account_query_failure(self):
        client=FakeClient();client.account_info=Mock(side_effect=requests.Timeout())
        with patch.object(login,'make_client',return_value=client):flow=login.start('alice','pw',owner='browser')
        self.assertEqual(flow['stage'],'failed');self.assertEqual(storage.load_tokens(),[])
        self.assertEqual(self.read_profile()['settings']['authorization_data']['ds_user_id'],'123')

    def test_failed_login_keeps_profile_and_enforces_cooldown(self):
        client=FakeClient();client.bloks_caa_login=Mock(side_effect=requests.Timeout())
        with patch.object(login,'make_client',return_value=client):flow=login.start('alice','pw',owner='browser')
        self.assertEqual(flow['stage'],'failed')
        self.assertEqual(self.read_profile()['settings']['uuids']['uuid'],client.uuid)
        with self.assertRaises(login.LoginFailure):login.start('alice','pw',owner='browser')

    def test_expired_flow_cannot_submit_code(self):
        flow,_=self.pending()
        with patch.object(login.time,'time',return_value=flow['expires']+1):
            with self.assertRaises(login.LoginFailure) as raised:login.advance(flow['id'],'browser','poll')
        self.assertEqual(raised.exception.status,410)

    def test_saved_profile_headers_are_available_to_existing_control_requests(self):
        login.start('alice','pw',owner='browser')
        headers=session_state.get_auth_headers('alice','token','agent','android','uuid')
        self.assertEqual(headers['x-bloks-version-id'],'a'*64)
        self.assertEqual(headers['x-ig-app-locale'],'tr_TR')
        self.assertEqual(headers['x-ig-family-device-id'],self.read_profile()['settings']['uuids']['phone_id'])

    def test_approval_poll_does_not_reopen_entrypoint_or_replay_login(self):
        flow,_=self.pending();client=FakeClient();client.private_request=Mock(return_value={'status':'ok'})
        with patch.object(login,'make_client',return_value=client):result=login.advance(flow['id'],'browser','poll')
        self.assertEqual(result['stage'],'approval')
        client.bloks_caa_login.assert_not_called();client.bloks_two_step_verification_entrypoint.assert_not_called()

    def test_totp_opens_the_server_code_screen_before_verifying(self):
        flow,_=self.pending();login.advance(flow['id'],'browser','methods')
        result=login.advance(flow['id'],'browser','select',method='totp')
        self.assertEqual(result['stage'],'code')
        self.clients[-1].bloks_two_step_verification_enter_totp_code.assert_called_once()
        result=login.advance(flow['id'],'browser','code',code='123456')
        self.assertEqual(result['stage'],'done')
        self.assertEqual(self.clients[-1].bloks_two_step_verification_verify_code.call_args.kwargs['challenge'],'totp')

    def test_profile_email_code_resumes_issued_submit_context_after_restart(self):
        module=types.ModuleType('instagrapi.mixins.bloks')
        module.AP_2SV_ENTRYPOINT='entry';module.AP_2SV_CODE_ENTRY='screen';module.AP_2SV_CODE_ENTRY_ASYNC='submit'
        client=FakeClient()
        client.bloks_extract_context_data=lambda result,key:result.get(key)
        client.bloks_ap_two_step_verification_entrypoint=Mock(return_value={'screen':'issued-screen'})
        client.bloks_ap_two_step_verification_code_entry=Mock(return_value={'submit':'issued-submit'})
        client.bloks_caa_login=Mock(side_effect=lambda **kw:{'logged_in':False,'two_step':client.bloks_caa_resolve_two_step_verification({'entry':'issued-entry'})})
        with patch.dict('sys.modules',{'instagrapi.mixins.bloks':module}),patch.object(login,'make_client',return_value=client):
            flow=login.start('alice','secret',owner='browser')
        self.assertEqual(flow['stage'],'code')
        result=login.advance(flow['id'],'browser','code',code='654321')
        self.assertEqual(result['stage'],'done')
        self.clients[-1].bloks_ap_two_step_verification_submit_code.assert_called_once_with('issued-submit','654321',domain='i.instagram.com')
        self.clients[-1].bloks_caa_login.assert_not_called()
        self.assertEqual(self.clients[-1].caa_aac,'context-secret')

    def test_token_publish_failure_rolls_back_and_preserves_old_account(self):
        storage.upsert_token({'username':'alice','token':'old-token','is_active':True})
        with patch('app_core.storage.upsert_token',return_value=False):
            flow=login.start('alice','pw',owner='browser')
        self.assertEqual(flow['stage'],'failed')
        self.assertEqual(storage.load_tokens()[0]['token'],'old-token')

    def test_cancel_cannot_retroactively_cancel_verified_account(self):
        flow=login.start('alice','pw',owner='browser')
        result=login.advance(flow['id'],'browser','cancel')
        self.assertEqual(result['stage'],'done');self.assertTrue(storage.load_tokens()[0]['is_active'])

    def test_unverified_issued_session_is_not_replaced_by_older_pool_token(self):
        from test_token_lifecycle import bearer
        storage.upsert_token({'username':'alice','token':bearer('OLD'),'is_active':True})
        client=FakeClient();client.account_info=Mock(side_effect=requests.Timeout())
        with patch.object(login,'make_client',return_value=client):login.start('alice','pw',owner='browser')
        with patch.object(login.time,'time',return_value=__import__('time').time()+181):
            result=login.start('alice',owner='browser')
        self.assertEqual(result['stage'],'done')
        self.clients[-1].bloks_caa_login.assert_not_called()
        self.assertEqual(self.clients[-1].authorization_data['sessionid'],'fake-session')

    def test_control_token_rotation_is_reused_by_saved_sdk_session(self):
        from test_token_lifecycle import bearer
        login.start('alice','pw',owner='browser')
        with login.transaction() as conn:conn.execute('UPDATE tokens SET token=? WHERE username=?',(bearer('ROTATED'),'alice'))
        result=login.start('alice',owner='browser')
        self.assertEqual(result['stage'],'done')
        self.assertEqual(self.clients[-1].authorization_data['sessionid'],'ROTATED')

    def test_permanent_delete_forgets_sdk_session_and_pending_context(self):
        flow,_=self.pending()
        self.assertTrue(storage.hard_delete_token('alice'))
        self.assertIsNone(self.read_profile())
        with self.assertRaises(login.LoginFailure):login.status(flow['id'],'browser')

    def test_permanent_delete_cannot_be_undone_by_delayed_login_response(self):
        client=FakeClient()
        def delayed_account():
            storage.hard_delete_token('alice')
            return SimpleNamespace(pk='123',username='alice')
        client.account_info=Mock(side_effect=delayed_account)
        with patch.object(login,'make_client',return_value=client):
            with self.assertRaises(login.LoginFailure):login.start('alice','pw',owner='browser')
        self.assertEqual(storage.load_tokens(),[]);self.assertIsNone(self.read_profile())
