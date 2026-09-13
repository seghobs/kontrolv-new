import unittest
from unittest.mock import patch
from flask import render_template
from app_core import create_app
from bs4 import BeautifulSoup

class MemberCompatibilityTests(unittest.TestCase):
    def test_completed_reports_render_without_extra_view_context(self):
        payload={'username':'alice','date':'2026-09-11','check_likes':False}
        report={**payload,'rows':[],'total':0,'counts':{'present':0,'missing':0,'unknown':0}}
        with patch('app_core.init_storage'):app=create_app()
        with app.test_request_context():
            for dual in (False,True):
                result={'dual_check':True,'comment_report':report,'like_report':{**report,'check_likes':True}} if dual else report
                html=render_template('member_analysis.html',job={'id':'test','parent_id':'original','payload':{**payload,'dual_check':dual},'result':result},status={'status':'completed'})
                soup=BeautifulSoup(html,'html.parser')
                self.assertEqual(len(soup.select('.member-mode-block')),2 if dual else 1)
            html=render_template('member_analysis.html',job={'id':'test','parent_id':'original','payload':payload,'result':None},status={'status':'completed'})
            self.assertIn('Sonuç görüntülenemedi',html)
            self.assertIsNotNone(BeautifulSoup(html,'html.parser').select_one('[role=alert]'))
