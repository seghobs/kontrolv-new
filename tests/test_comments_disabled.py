import asyncio
import unittest
from unittest.mock import Mock, AsyncMock, patch
from contextlib import ExitStack
import test_jobs
from app_core import instagram_api as api


class ClosedCommentTests(unittest.TestCase):
    setUp = test_jobs.JobTests.setUp

    def test_manual_preview_exposes_closed_open_and_unknown(self):
        from app_core import create_app
        with patch('app_core.init_storage'): client=create_app().test_client()
        for state in (True, False, None):
            with patch('app_core.token_service.get_working_active_token',return_value={'token':'test'}), patch.object(api,'get_post_details',return_value={'comments_disabled':state}):
                response=client.get('/api/get_post_thumbnail?link=https://www.instagram.com/p/DWy2bcUCNG0/')
            self.assertEqual(response.status_code,200)
            self.assertIs(response.json['comments_disabled'],state)

    def test_global_flag_is_distinct_from_zero_comments_and_viewer_restriction(self):
        for source in ({}, None, {'comment_count':0}, {'commenting_disabled_for_viewer':True}, {'comments_disabled':'true'}, {'comments_disabled':1}):
            self.assertIsNone(api.comment_availability(source)['comments_disabled'])
        self.assertIs(api.comment_availability({'comments_disabled':False})['comments_disabled'],False)
        self.assertIs(api.comment_availability({'comments_disabled':True})['comments_disabled'],True)

    def test_real_response_flags_survive_both_detail_parsers(self):
        # Whitelisted fields observed on DWy2bcUCNG0, 2026-09-26, HTTP 200.
        item={'code':'DWy2bcUCNG0','comments_disabled':True,
              'commenting_disabled_for_viewer':True,'comment_count':0,'user':{}}
        response=Mock(status_code=200,status=200,headers={})
        response.json=Mock(return_value={'items':[item]})
        async_response=Mock(status=200,headers={})
        async_response.json=AsyncMock(return_value={'items':[item]})
        context=AsyncMock();context.__aenter__.return_value=async_response
        token={'username':'fixture','token':'test','user_agent':'ua','android_id_yeni':'a','device_id':'d'}
        with ExitStack() as stack:
            stack.enter_context(patch.object(api,'current_token',return_value='test'))
            stack.enter_context(patch.object(api,'build_auth_headers',return_value={}))
            stack.enter_context(patch.object(api,'prepare_async_headers',return_value=({},0)))
            stack.enter_context(patch.object(api,'_update_session_from_response'))
            stack.enter_context(patch('app_core.session_state.update_session'))
            stack.enter_context(patch('app_core.session_state.response_cookies',return_value=[]))
            stack.enter_context(patch.object(api,'_get_http_session',return_value=Mock(get=Mock(return_value=response))))
            results=[api.get_post_details('1',token),asyncio.run(api.get_post_details_async('1',token,Mock(get=Mock(return_value=context))))]
        for result in results:
            self.assertIs(result['comments_disabled'],True)
            self.assertIs(result['commenting_disabled_for_viewer'],True)
            self.assertEqual(result['comment_count'],0)
