import unittest
from unittest.mock import patch
import test_jobs
from app_core import create_app, jobs

class ControlTypeTests(unittest.TestCase):
    setUp=test_jobs.JobTests.setUp

    def test_explicit_choice_and_optional_limit_reach_job(self):
        with patch('app_core.init_storage'): client=create_app().test_client()
        for mode, limit in [('comments',False),('likes',False),('likes',True)]:
            with patch('app_core.followup.rules_for',return_value={'mode':'likes' if mode=='comments' else 'comments'}), patch('app_core.routes.main.get_working_active_token',return_value={'token':'test'}):
                response=client.post('/',data={'post_link':'https://www.instagram.com/p/ABC/', 'grup_uye':'alice bob','thread_id':'g','control_mode':mode,'low_likes':'on' if limit else ''},headers={'X-Requested-With':'XMLHttpRequest'})
            self.assertEqual(response.status_code,302,response.data)
            payload=jobs.get_job(response.location.rsplit('/',1)[-1])['payload']
            self.assertEqual(payload['check_likes'],mode=='likes')
            self.assertEqual(payload['low_likes'],limit)



