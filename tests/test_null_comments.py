import asyncio
import json
import unittest
from contextlib import ExitStack
from unittest.mock import AsyncMock, Mock, patch
from app_core import instagram_api as api
from app_core.routes import main
import test_jobs


class NullCommentTests(unittest.TestCase):
    setUp = test_jobs.JobTests.setUp

    def test_malformed_and_anonymous_records_keep_known_authors(self):
        cases=[None,{},{'user':None},{'user':{'username':None}},{'user':{'username':[]}},'bad']
        for bad in cases:
            _,comments,incomplete=api.parse_comment_page(json.dumps({'comments':[bad,{'user':{'username':'alice'},'text':None}]}))
            self.assertTrue(incomplete)
            self.assertEqual(comments,{('alice','')})

    def test_empty_list_is_complete_but_null_or_missing_list_is_not(self):
        for value in (None,{}, {'comments':None}, {'comments':'bad'}, {'comments':[None]}):
            self.assertTrue(api.parse_comment_page(json.dumps(value))[2])
        self.assertFalse(api.parse_comment_page('{"comments":[]}')[2])
        self.assertFalse(api.parse_comment_page('{"comments":[{"user":{"username":"alice"},"text":null}]}')[2])

    def test_both_network_engines_preserve_incomplete_flag_without_fallback(self):
        body=json.dumps({'comments':[None,{'user':{'username':'alice'},'text':None}]})
        response=Mock(status_code=200,status=200,headers={},text=body)
        context=AsyncMock();context.__aenter__.return_value=Mock(status=200,headers={},text=AsyncMock(return_value=body))
        with ExitStack() as stack:
            stack.enter_context(patch.object(api,'build_auth_headers',return_value={}))
            stack.enter_context(patch.object(api,'_update_session_from_response'))
            stack.enter_context(patch('app_core.session_state.update_session'))
            stack.enter_context(patch.object(api,'get_outbound_proxy',return_value=None))
            stack.enter_context(patch.object(api,'_get_http_session',return_value=Mock(get=Mock(return_value=response))))
            fallback=stack.enter_context(patch('app_core.token_service.fetch_comments_with_failover'))
            for result in (api.fetch_comment_usernames('1',{}),asyncio.run(api.fetch_comment_usernames_async('1',{},Mock(get=Mock(return_value=context))))):
                self.assertTrue(result['incomplete'])
                self.assertFalse(result['ok'])
                self.assertIn(('alice',''),result['comments'])
            fallback.assert_not_called()

    def test_partial_post_does_not_stop_other_posts_or_create_false_missing(self):
        async def comments(mid,*args):
            if mid==main.donustur('https://www.instagram.com/p/ABC'):
                return {'ok':False,'incomplete':True,'comments':[('alice','')]}
            return {'ok':True,'comments':[('alice','hello')]}
        with patch.object(main,'get_working_active_token',return_value={'token':'test'}), \
             patch.object(api,'get_post_details_async',new=AsyncMock(return_value={})), \
             patch.object(api,'fetch_comment_usernames_async',side_effect=comments), \
             patch('asyncio.sleep',new=AsyncMock()):
            result=main.run_manual_control('https://www.instagram.com/p/ABC\nhttps://www.instagram.com/p/DEF','alice bob','',[],False)
        self.assertTrue(result['links'][0]['error'])
        self.assertEqual(result['links'][0]['eksikler'],[])
        self.assertEqual(result['links'][1]['eksikler'],['bob'])
        self.assertEqual(result['user_missing_posts']['bob'],['https://www.instagram.com/p/DEF'])
        self.assertEqual(result['all_commented'],[])

    def test_null_text_establishes_presence_without_false_format_violation(self):
        with patch.object(main,'get_working_active_token',return_value={'token':'test'}), \
             patch.object(api,'get_post_details_async',new=AsyncMock(return_value={})), \
             patch.object(api,'fetch_comment_usernames_async',new=AsyncMock(return_value={'ok':True,'comments':[('alice','')]})), \
             patch('asyncio.sleep',new=AsyncMock()):
            result=main.run_manual_control('https://www.instagram.com/p/ABC','alice bob','',[],False)
        self.assertIn('alice',result['all_commented'])
        self.assertNotIn('alice',result['invalid_comment_users'])

    def test_member_partial_result_preserves_positive_and_unknown(self):
        from app_core.member_analysis import run
        payload={'username':'alice','date':'2026-09-11','thread_id':'g','check_likes':False}
        for comments,state in [([('alice','')],'present'),([('bob','hello')],'unknown')]:
            with patch('app_core.token_service.get_working_active_token',return_value={'token':'test'}), \
                 patch('app_core.token_service.fetch_group_media_with_failover',return_value={'ok':True,'posts':[{'url':'https://www.instagram.com/p/ABC'}]}), \
                 patch.object(api,'fetch_comment_usernames_async',new=AsyncMock(return_value={'ok':False,'incomplete':True,'comments':comments})):
                result=run(payload,lambda *args:None)
            self.assertEqual(result['rows'][0]['state'],state)
            self.assertEqual(result['counts']['missing'],0)
