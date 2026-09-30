import unittest
from app_core.share_counts import count_member_shares
class ShareCountTests(unittest.TestCase):
 def test_sender_repeats_stories_and_day_boundaries(self):
  def msg(mid,kind,**kw):return dict(item_id=mid,item_type=kind,user_id='1',timestamp=150,**kw)
  post=msg('1','media_share',media_share={'code':'ABC','user':{'username':'other'}})
  rows=[post,post,msg('2','media_share',media_share={'code':'ABC'}),msg('3','xma_clip'),msg('4','story_share'),msg('5','text',text='hello'),{**msg('6','xma_clip'),'timestamp':250}]
  r=count_member_shares(rows,{'1':'alice'},100,200)['alice']
  self.assertEqual((r['post'],r['reels'],r['story'],r['total']),(2,1,1,4))
 def test_text_links_and_reply_not_share(self):
  rows=[dict(item_id='1',user_id='1',timestamp=150,item_type='text',text='https://www.instagram.com/p/ABC/ https://www.instagram.com/p/ABC/ https://www.instagram.com/reel/DEF/'),dict(item_id='2',user_id='1',timestamp=150,item_type='story_reply')]
  r=count_member_shares(rows,{'1':'alice'},100,200)['alice'];self.assertEqual(r['total'],2);self.assertEqual(r['story'],0)
