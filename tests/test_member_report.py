import unittest
from unittest.mock import patch
from bs4 import BeautifulSoup
from app_core import create_app

class MemberReportTests(unittest.TestCase):
    def render(self, likes=False, running=False):
        rows=[{'url':'https://www.instagram.com/p/MISSING/','sender':'alice','state':'missing','comments':[]}, {'url':'https://www.instagram.com/reel/DONE/','sender':'bob','state':'present','comments':['hello <script>bad</script>']},{'url':'https://www.instagram.com/p/UNKNOWN/','sender':'c','state':'unknown','comments':[]}]
        payload={'username':'target','date':'2026-09-11','check_likes':likes}
        job={'id':'test','kind':'member','parent_id':'original','payload':payload,'state':'running' if running else 'completed','progress':0,'message':'Checking','error':None,'attempts':1,'result':{**payload,'rows':rows,'total':3,'counts':{'present':1,'missing':1,'unknown':1}}}
        with patch('app_core.init_storage'):app=create_app()
        with patch('app_core.member_analysis.jobs.get_job',return_value=job):
            response=app.test_client().get('/member-analysis/test')
        self.assertEqual(response.status_code,200)
        return BeautifulSoup(response.get_data(as_text=True),'html.parser')
    def test_only_confirmed_missing_links_in_missing_list_and_copy_text(self):
        for likes in (True,False):
            page=self.render(likes)
            missing=page.select_one('#member-missing')
            self.assertEqual(len(missing.select('.member-row')),1)
            self.assertIn('/p/MISSING/',missing.get_text())
            text=page.select_one('#member-missing-text').get_text()
            self.assertIn('/p/MISSING/',text)
            self.assertNotIn('/reel/DONE/',text);self.assertNotIn('/p/UNKNOWN/',text)
            self.assertEqual(len(page.select('#member-unknown .member-row')),1)
            self.assertEqual(len(page.select('#member-present .member-row')),1)
            self.assertIsNone(page.select_one('blockquote script'))
            self.assertIn('Beğeni' if likes else 'Yorum',missing.get_text())
    def test_running_state_does_not_claim_missing_results(self):
        page=self.render(running=True)
        self.assertIsNotNone(page.select_one('.member-processing #loading-message'))
        self.assertIsNone(page.select_one('#member-missing'))
        self.assertIsNone(page.select_one('.member-summary'))
