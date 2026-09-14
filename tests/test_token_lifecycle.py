import base64
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
import requests
from app_core import storage, session_state as state, instagram_api as api, token_service as service


def bearer(session, user='123'):
    return 'Bearer IGT:2:' + base64.b64encode(json.dumps({'ds_user_id':user,'sessionid':session}).encode()).decode()


class TokenLifecycleTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        db = patch.object(storage, 'DB_FILE', str(Path(temp.name)/'test.db'))
        db.start(); self.addCleanup(db.stop)
        conn = storage._connect(); storage._init_db(conn); conn.close()
        self.old, self.new = bearer('old'), bearer('new')
        self.record = {'username':'tester','token':self.old,'is_active':True,'password':'keep',
                       'android_id_yeni':'device','device_id':'device','user_agent':'agent'}
        storage.upsert_token(self.record)

    def test_rotation_preserves_fields_and_resolves_old_input(self):
        state.update_session('tester', {'IG-Set-Authorization':self.new}, expected_token=self.old)
        row = storage.load_tokens()[0]
        self.assertEqual(row['token'],self.new)
        self.assertEqual(row['password'],'keep')
        self.assertTrue(row['is_active'])
        self.assertEqual(api.build_auth_headers(self.old,'agent','device','device','tester')['authorization'],self.new)
        self.assertEqual(state.get_current_token('tester',bearer('manual-new')),bearer('manual-new'))

    def test_delayed_response_cannot_overwrite_new_token(self):
        state.rotate_token('tester',self.new,self.old)
        state.rotate_token('tester',bearer('delayed'),self.old)
        self.assertEqual(storage.load_tokens()[0]['token'],self.new)

    def test_invalid_and_other_account_tokens_ignored(self):
        for candidate in ['Bearer IGT:garbage', bearer('other','999'), '']:
            state.rotate_token('tester',candidate,self.old)
        self.assertEqual(storage.load_tokens()[0]['token'],self.old)

    def test_body_rotation(self):
        state.update_session_from_body('tester',{'headers':{'ig-set-authorization':self.new}},expected_token=self.old)
        self.assertEqual(storage.load_tokens()[0]['token'],self.new)

    def test_403_requires_explicit_rejection(self):
        for body, expected in [({'message':'feedback_required'},False),({'message':'challenge_required'},False),
                               ({'message':'Forbidden'},False),({'message':'login_required'},True)]:
            response=Mock(status_code=403, json=Mock(return_value=body))
            self.assertEqual(api.response_has_invalid_session(response),expected)

    def test_validation_does_not_reject_plain_403(self):
        response=Mock(status_code=403, json=Mock(return_value={'message':'Forbidden'}))
        with patch.object(api,'_get_http_session',return_value=Mock(post=Mock(return_value=response),get=Mock(return_value=response))), patch.object(api,'_update_session_from_response'):
            self.assertIsNone(api.validate_token(self.record))
            response.json.return_value={'message':'login_required'}
            self.assertFalse(api.validate_token(self.record))

    def test_failover_does_not_deactivate_plain_403(self):
        with patch.object(api,'fetch_group_threads',return_value={'ok':False,'error':'HTTP 403'}), patch.object(service,'handle_invalid_token') as invalid:
            self.assertFalse(service.fetch_group_threads_with_failover(self.record)['ok'])
            invalid.assert_not_called()
        with patch.object(service,'fetch_comment_usernames',return_value={'ok':False,'status':403}), patch.object(service,'deactivate_token') as invalid:
            self.assertFalse(service.fetch_comments_with_failover('1',token_record=self.record)['ok'])
            invalid.assert_not_called()

    def test_explicit_rejection_deactivates(self):
        with patch.object(service,'fetch_comment_usernames',return_value={'ok':False,'status':403,'invalid_session':True}):
            service.fetch_comments_with_failover('1',token_record=self.record)
        self.assertFalse(storage.load_tokens()[0]['is_active'])

    def test_error_response_still_updates_headers(self):
        response=requests.Response();response.status_code=403;response._content=b'{}'
        response.headers['ig-set-authorization']=self.new
        response.request=requests.Request('GET','https://example.invalid',headers={'authorization':self.old}).prepare()
        api._update_session_from_response('tester',response)
        self.assertEqual(storage.load_tokens()[0]['token'],self.new)

if __name__=='__main__':unittest.main()
