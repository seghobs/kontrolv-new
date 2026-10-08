import unittest
from app_core.member_notes import nearby_notes, attach_notes, cache_notes
import test_jobs

class MemberNoteTests(unittest.TestCase):
    setUp = test_jobs.JobTests.setUp
    def share(self,id='s',stamp=10000000000,uid='1',code='POST'):
        return dict(item_id=id,user_id=uid,timestamp=stamp,item_type='media_share',media_share={'code':code,'user':{'username':'different_owner'}})
    def note(self,id='n',stamp=10000300000,uid='1',text='Sadece begeni'):
        return dict(item_id=id,user_id=uid,timestamp=stamp,item_type='text',text=text)
    def test_sender_identity_not_owner_and_time_window(self):
        rows=[self.share(),self.note(),self.note('other',uid='2'),self.note('far',stamp=14000000000),self.note('before',stamp=9999000000)]
        out=nearby_notes(rows,{'1':'sender','2':'other'},0,20000000000)
        self.assertEqual([n['id'] for n in out['POST']],['before','n'])
        self.assertEqual(out['POST'][0]['username'],'sender')
    def test_nearest_share_and_dedup(self):
        n=self.note(stamp=10100000000)
        out=nearby_notes([self.share(),self.share('s2',10100100000,code='SECOND'),n,n],{'1':'sender'},0,20000000000)
        self.assertNotIn('POST',out);self.assertEqual(len(out['SECOND']),1)
    def test_reply_targets_share_not_nearest(self):
        n=self.note(stamp=10100000000);n['replied_to_message']={'item_id':'s'}
        out=nearby_notes([self.share(),self.share('s2',10100100000,code='SECOND'),n],{'1':'sender'},0,20000000000)
        self.assertEqual(set(out),{'POST'})
    def test_stories_and_other_group_excluded_cache_clears(self):
        s=self.share();s['item_type']='story_share'
        self.assertEqual(nearby_notes([s,self.note()],{'1':'sender'},0,20000000000),{})
        notes=nearby_notes([self.share(),self.note()],{'1':'sender'},0,20000000000)
        cache_notes('g',[{'code':'POST'}],notes,'2026-10-08')
        posts=[{'post_link':'https://www.instagram.com/p/POST/'}]
        attach_notes('other',posts);self.assertEqual(posts[0]['nearby_notes'],[])
        attach_notes('g',posts);self.assertEqual(posts[0]['nearby_notes'][0]['text'],'Sadece begeni')
        cache_notes('g',[{'code':'POST'}],{},'2026-10-08');attach_notes('g',posts);self.assertEqual(posts[0]['nearby_notes'],[])
    def test_text_escaped_and_visible_with_report_error(self):
        from app_core import create_app
        from flask import render_template
        from unittest.mock import patch
        with patch('app_core.init_storage'):app=create_app()
        with app.test_request_context():
            html=render_template('result.html',links=[{'post_link':'https://www.instagram.com/p/POST/','error':'incomplete','nearby_notes':[{'text':'<script>alert(1)</script>','username':'member','time':'08.10.2026 12:00'}]}],group=[],all_commented=[],post_code='a'*32,thread_id='g')
        self.assertIn('Üyenin notu',html);self.assertIn('&lt;script&gt;',html);self.assertNotIn('<script>alert(1)</script>',html)
