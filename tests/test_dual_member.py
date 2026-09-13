import unittest
from unittest.mock import patch,AsyncMock
from bs4 import BeautifulSoup
from app_core import create_app
from app_core.member_analysis import run

class DualMemberTests(unittest.TestCase):
    def test_one_day_fetch_both_modes_with_independent_errors(self):
        payload={'username':'alice','date':'2026-09-11','thread_id':'g','check_likes':True,'dual_check':True}
        with patch('app_core.token_service.get_working_active_token',return_value={'token':'x'}),patch('app_core.token_service.fetch_group_media_with_failover',return_value={'ok':True,'posts':[{'url':'https://www.instagram.com/p/ABC/'}]}) as media,patch('app_core.instagram_api.fetch_comment_usernames_async',new=AsyncMock(side_effect=ValueError('network'))) as comments,patch('app_core.instagram_api.fetch_liker_usernames_async',new=AsyncMock(return_value={'ok':True,'usernames':['alice']})) as likes:
            result=run(payload,lambda *args:None)
        media.assert_called_once();comments.assert_called_once();likes.assert_called_once()
        self.assertEqual(result['comment_report']['counts']['unknown'],1)
        self.assertEqual(result['like_report']['counts']['present'],1)
        self.assertEqual(result['comment_report']['counts']['missing'],0)
    def test_two_copy_lists_do_not_mix_modes(self):
        payload={'username':'alice','date':'2026-09-11','thread_id':'g','check_likes':False,'dual_check':True}
        def report(likes,url):
            return {**payload,'check_likes':likes,'total':1,'counts':{'present':0,'missing':1,'unknown':0},'rows':[{'url':url,'sender':'owner','state':'missing','comments':[]}]}
        result={**payload,'comment_report':report(False,'https://www.instagram.com/p/COMMENT/'),'like_report':report(True,'https://www.instagram.com/reel/LIKE/')}
        job={'id':'dual','kind':'member','parent_id':'original','payload':payload,'state':'completed','progress':100,'message':'done','error':None,'attempts':1,'result':result}
        with patch('app_core.init_storage'):app=create_app()
        with patch('app_core.member_analysis.jobs.get_job',return_value=job):response=app.test_client().get('/member-analysis/dual')
        self.assertEqual(response.status_code,200)
        soup=BeautifulSoup(response.get_data(as_text=True),'html.parser')
        for mode,match,other in [('comments','COMMENT','LIKE'),('likes','LIKE','COMMENT')]:
            text=soup.select_one('#member-missing-text-'+mode).text
            self.assertIn('/'+match+'/',text);self.assertNotIn('/'+other+'/',text)
            self.assertIsNotNone(soup.select_one('#copy-member-missing-'+mode))
        ids=[e['id'] for e in soup.select('[id]')];self.assertEqual(len(ids),len(set(ids)))
