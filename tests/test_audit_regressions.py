import unittest
from contextlib import ExitStack
from unittest.mock import AsyncMock, patch
from app_core.routes import main
from app_core import instagram_api as instagram
import test_jobs


class AuditRegressions(unittest.TestCase):
    setUp = test_jobs.JobTests.setUp

    def control(self, *, likes=False, details=None, likers=None, previous=None, sync=False, link=None):
        with ExitStack() as stack:
            stack.enter_context(patch.object(main, 'get_working_active_token', return_value={'token':'test'}))
            stack.enter_context(patch.object(main, 'get_global_exempted_users', return_value=set()))
            stack.enter_context(patch.object(main, 'add_audit_log'))
            stack.enter_context(patch('asyncio.sleep', new=AsyncMock()))
            stack.enter_context(patch.object(instagram, 'get_post_details_async', new=AsyncMock(
                side_effect=RuntimeError('transport failure') if sync else None, return_value=details or {})))
            comments=stack.enter_context(patch.object(instagram, 'fetch_comment_usernames_async',new=AsyncMock(return_value={'ok':True,'comments':[('alice','hello')]})))
            stack.enter_context(patch.object(instagram, 'fetch_liker_usernames_async',new=AsyncMock(return_value={'ok':True,'usernames':likers or set()})))
            stack.enter_context(patch.object(main, 'get_post_details',return_value=details or {}))
            fallback=stack.enter_context(patch.object(main,'fetch_likers_with_failover',return_value={'ok':True,'usernames':likers or set()}))
            result=main.run_manual_control(link or 'https://www.instagram.com/p/ABC','alice bob','',[],likes,
                only_missing=previous is not None,prev_result=previous)
            return result, comments.call_count, fallback.call_count

    def test_partial_likers_cannot_mark_absent_members_missing(self):
        for sync in (False,True):
            for details in ({'like_count':10,'like_count_verified':True},{'like_count':0}):
                with self.subTest(sync=sync,details=details):
                    result,_,_=self.control(likes=True,details=details,likers={'alice'},sync=sync)
                    self.assertTrue(result['links'][0]['error'])
                    self.assertEqual(result['links'][0]['eksikler'],[])
                    self.assertEqual(result['all_commented'],[])

    def test_partial_positive_likers_are_valid_when_everyone_is_found(self):
        result,_,_=self.control(likes=True,details={'like_count':10,'like_count_verified':True},likers={'alice','bob'})
        self.assertEqual(result['links'][0]['eksikler'],[])

    def test_quick_update_retries_failed_posts(self):
        previous={'links':[{'post_link':'https://www.instagram.com/p/ABC','error':'API error','eksikler':[]}]}
        result,calls,_=self.control(previous=previous,details={'comment_count':1,'comment_count_verified':True})
        self.assertEqual(calls,1)
        self.assertEqual(result['links'][0]['eksikler'],['bob'])

    def test_skipped_posts_do_not_claim_everyone_completed_in_either_engine(self):
        for sync in (False,True):
            result,_,fallback=self.control(likes=True,details={'like_count':91,'like_count_verified':True},sync=sync)
            self.assertTrue(result['links'][0]['error'])
            self.assertEqual(result['all_commented'],[])
            self.assertEqual(fallback,0)

    def test_invalid_bulk_link_does_not_generate_false_missing(self):
        with self.assertRaises(main.ControlUnavailable):
            self.control(link='https://www.instagram.com/p/ABC\ninvalid')

    def test_invalid_bulk_submission_does_not_queue_work(self):
        from app_core import create_app
        with patch('app_core.init_storage'):app=create_app()
        with patch('app_core.jobs.enqueue') as enqueue:
            response=app.test_client().post('/',data={'post_link':'https://www.instagram.com/p/ABC\ninvalid'},headers={'Accept':'application/json'})
        self.assertEqual(response.status_code,400)
        self.assertFalse(response.json['success'])
        enqueue.assert_not_called()
