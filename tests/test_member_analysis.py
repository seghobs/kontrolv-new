import unittest
from unittest.mock import patch,AsyncMock
import test_jobs
from app_core import create_app,jobs
from app_core.member_analysis import run
from app_core.web_jobs import execute_job

class MemberAnalysisTests(unittest.TestCase):
    setUp=test_jobs.JobTests.setUp
    def source(self,likes=False):
        identifier=jobs.enqueue('manual',{'thread_id':'g','check_likes':likes})
        jobs.claim_request(identifier,'t');jobs.complete(identifier,'t',{'thread_id':'g','group':['alice','bob'],'check_likes':likes,'links':[]})
        return identifier
    def test_creates_independent_record_inherits_mode_deduplicates_clicks(self):
        source=self.source(True)
        with patch('app_core.init_storage'):app=create_app()
        client=app.test_client()
        params={'username':'alice','date':'2026-09-11','check_likes':False}
        first=client.post('/api/member_analysis/'+source,json=params)
        second=client.post('/api/member_analysis/'+source,json=params)
        self.assertEqual(first.json['job_id'],second.json['job_id'])
        child=jobs.get_job(first.json['job_id'])
        self.assertTrue(child['payload']['check_likes'])
        self.assertTrue(child['payload']['dual_check'])
        self.assertEqual(child['parent_id'],source)
        self.assertEqual(jobs.get_job(source)['state'],'completed')
        with patch('app_core.member_analysis.run',return_value={**child['payload'],'dual_check':False,'rows':[],'counts':{'present':0,'missing':0,'unknown':0},'total':0}):
            status,_=execute_job(child['id'])
        self.assertEqual(status['status'],'completed')
        self.assertEqual(client.get('/result/'+child['id']).location,'/member-analysis/'+child['id'])
        self.assertEqual(client.get('/member-analysis/'+child['id']).status_code,200)
        third=client.post('/api/member_analysis/'+source,json=params)
        self.assertNotEqual(first.json['job_id'],third.json['job_id'])
    def test_rejects_unknown_members_and_invalid_dates(self):
        source=self.source()
        with patch('app_core.init_storage'):app=create_app()
        client=app.test_client()
        for user,date in [('stranger','2026-09-11'),('alice','2026-02-31')]:
            self.assertEqual(client.post('/api/member_analysis/'+source,json={'username':user,'date':date}).status_code,400)
    def scan(self,likes,response,details=None):
        with patch('app_core.token_service.get_working_active_token',return_value={'token':'test'}),patch('app_core.token_service.fetch_group_media_with_failover',return_value={'ok':True,'posts':[{'url':'https://www.instagram.com/reel/ABC/'},{'url':'https://www.instagram.com/p/ABC/'}]}) as media,patch('app_core.instagram_api.fetch_comment_usernames_async',new=AsyncMock(return_value=response)),patch('app_core.instagram_api.fetch_liker_usernames_async',new=AsyncMock(return_value=response)),patch('app_core.instagram_api.get_post_details_async',new=AsyncMock(return_value=details or {})):
            result=run({'username':'alice','thread_id':'g','date':'2026-09-11','check_likes':likes},lambda *args:None)
        self.assertTrue(media.call_args.kwargs['complete'])
        self.assertEqual(result['total'],1)
        return result['rows'][0]
    def test_target_comments_and_failure_are_distinct(self):
        row=self.scan(False,{'ok':True,'comments':[('bob','other'),('alice','my comment')]})
        self.assertEqual(row['state'],'present');self.assertEqual(row['comments'],['my comment'])
        self.assertEqual(self.scan(False,{'ok':True,'comments':[]},{'comment_count':0,'comment_count_verified':True})['state'],'missing')
        self.assertEqual(self.scan(False,{'ok':False,'comments':[]})['state'],'unknown')
    def test_high_like_count_is_checked_and_partial_lists_are_unknown(self):
        self.assertEqual(self.scan(True,{'ok':True,'usernames':['alice']},{'like_count':200})['state'],'present')
        self.assertEqual(self.scan(True,{'ok':True,'usernames':['bob']},{'like_count':200,'like_count_verified':True})['state'],'unknown')
        self.assertEqual(self.scan(True,{'ok':True,'usernames':['bob']},{'like_count':1,'like_count_verified':True})['state'],'missing')
        self.assertEqual(self.scan(True,{'ok':True,'usernames':[]})['state'],'unknown')
    def test_incomplete_day_fails_instead_of_returning_empty_success(self):
        with patch('app_core.token_service.get_working_active_token',return_value={'token':'x'}),patch('app_core.token_service.fetch_group_media_with_failover',return_value={'ok':False}):
            with self.assertRaises(ValueError):run({'username':'alice','thread_id':'g','date':'2026-09-11','check_likes':False},lambda *args:None)

class DayPaginationTests(unittest.TestCase):
    def test_complete_mode_continues_after_fifty_media(self):
        from datetime import datetime,timezone,timedelta
        from unittest.mock import Mock
        from app_core.instagram_api import fetch_group_media
        stamp=int(datetime(2026,9,11,12,tzinfo=timezone(timedelta(hours=3))).timestamp()*1000000)
        items=[{'timestamp':stamp-i,'media':{'code':'ABC','id':'1','user':{'username':'owner'}}} for i in range(50)]
        def response(data):
            result=Mock(status_code=200);result.json.return_value=data;return result
        http=Mock();http.get.side_effect=[response({'thread':{'items':[],'has_older':False}}),response({'items':items}),response({'items':[{'timestamp':stamp-100,'media':{'code':'DEF','id':'2','user':{'username':'owner'}}}]})]
        with patch('app_core.instagram_api.current_token',return_value='token'),patch('app_core.instagram_api.extract_user_id_from_token',return_value='1'),patch('app_core.instagram_api.build_auth_headers',return_value={}),patch('app_core.instagram_api._get_http_session',return_value=http),patch('app_core.instagram_api._update_session_from_response'):
            result=fetch_group_media({'username':'test','token':'token','user_agent':'ua','android_id_yeni':'a','device_id':'d'},'group',datetime(2026,9,11),complete=True)
        self.assertTrue(result['ok'],result)
        self.assertEqual(len(result['posts']),51)
        self.assertEqual(http.get.call_count,3)
        self.assertEqual(http.get.call_args.kwargs['params']['max_timestamp'],stamp-50)
