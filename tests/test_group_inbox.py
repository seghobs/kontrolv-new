import unittest
from unittest.mock import Mock, patch
from app_core import instagram_api as api


class GroupInboxTests(unittest.TestCase):
    def fetch(self, data):
        response = Mock(status_code=200)
        response.json.return_value = data
        client = Mock()
        client.get.return_value = response
        with patch.object(api, '_get_http_session', return_value=client), \
                patch.object(api, 'build_auth_headers', return_value={}), \
                patch.object(api, 'current_token', return_value='synthetic'), \
                patch.object(api, '_update_session_from_response'), \
                patch('app_core.storage.cache_group_names'), \
                patch('socket.socket.connect', side_effect=AssertionError('No real network')):
            return api.fetch_group_threads(dict(username='synthetic', token='synthetic',
                user_agent='test', android_id_yeni='test', device_id='test'))

    def test_null_images_do_not_hide_any_groups(self):
        groups = [dict(thread_id=str(i), thread_title='Group '+str(i),
            users=[{'username':'a','profile_pic_url':'https://example.test/a'}, {'username':'b'}],
            thread_image=None, image_versions2=None, inviter=None) for i in range(3)]
        groups[1]['thread_image'] = {'image_versions2':{'candidates':[None, {'url':'https://example.test/group'}]}}
        groups[2]['image_versions2'] = {'candidates':None}
        result = self.fetch({'inbox':{'threads':groups}})
        self.assertTrue(result['ok'])
        self.assertEqual(len(result['groups']),3)
        self.assertEqual(result['groups'][0]['group_pic_url'],'https://example.test/a')
        self.assertEqual(result['groups'][1]['group_pic_url'],'https://example.test/group')

    def test_absent_inbox_is_not_reported_as_successful_empty_list(self):
        self.assertFalse(self.fetch({'inbox':None})['ok'])
        self.assertFalse(self.fetch({'inbox':{'threads':None}})['ok'])

    def test_null_threads_and_members_are_tolerated(self):
        result=self.fetch({'inbox':{'threads':[None, {'thread_title':'No members','users':None},
            {'thread_id':'1','users':[None,{'username':'a'},{'username':'b'}], 'thread_image':None}]}})
        self.assertTrue(result['ok']);self.assertEqual(len(result['groups']),1)

    def test_missing_members_cannot_be_reported_as_an_empty_success(self):
        for thread in (None, {'users':None}, {'users':[None]}):
            with patch.object(api,'_get_http_session') as http, \
                    patch.object(api,'build_auth_headers',return_value={}), \
                    patch.object(api,'current_token',return_value='fake'), \
                    patch.object(api,'_update_session_from_response'):
                response=Mock(status_code=200);response.json.return_value={'thread':thread}
                http.return_value.get.return_value=response
                result=api.fetch_group_members(dict(username='fake',token='fake',
                    user_agent='fake',android_id_yeni='fake',device_id='fake'),'1')
            self.assertFalse(result['ok']);self.assertNotIn('NoneType',result['error'])
