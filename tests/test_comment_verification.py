import asyncio,json,unittest
from unittest.mock import patch
from app_core.comment_verification import fetch_complete_comments

def comment(cid, **kw):
 return dict(pk=cid,user={'username':'alice'},text='same',**kw)
class Response:
 status=200;headers={};cookies={}
 def __init__(self,data):self.data=data
 async def __aenter__(self):return self
 async def __aexit__(self,*args):pass
 async def text(self):return json.dumps(self.data)
class Session:
 def __init__(self,pages):self.pages=iter(pages);self.urls=[];self.params=[]
 def get(self,url,**kw):self.urls.append(url);self.params.append(kw.get('params',{}).copy());return Response(next(self.pages))
class CompleteCommentTests(unittest.TestCase):
 def fetch(self,pages):
  session=Session(pages)
  with patch('app_core.instagram_api.current_token',return_value='test'), patch('app_core.instagram_api.prepare_async_headers',side_effect=lambda u,url,h:(h,0)), patch('app_core.instagram_api.build_auth_headers',return_value={}), patch('app_core.session_state.update_session'), patch('app_core.instagram_api.get_outbound_proxy',return_value=None):
   result=asyncio.run(fetch_complete_comments('1',{'username':'test'},session))
  return result,session
 def test_distinct_ids_same_text_and_duplicate_page(self):
  r,_=self.fetch([{'comments':[comment('1'),comment('2')],'next_min_id':'a'},{'comments':[comment('2'),comment('3')]}])
  self.assertTrue(r['ok']);self.assertEqual(len(r['comments']),3)
 def test_children_and_preview_deduplicated(self):
  r,s=self.fetch([{'comments':[comment('1',child_comment_count=2,preview_child_comments=[comment('2')])]}, {'child_comments':[comment('2')],'next_min_child_cursor':'a'},{'child_comments':[comment('3')]}])
  self.assertTrue(r['ok']);self.assertEqual(len(r['comments']),3);self.assertIn('inline_child_comments',s.urls[1])
 def test_missing_children_remain_incomplete(self):
  r,_=self.fetch([{'comments':[comment('1',child_comment_count=2)]},{'child_comments':[]}])
  self.assertFalse(r['ok'])
 def test_cursor_loop_and_null_author_are_not_absence(self):
  r,_=self.fetch([{'comments':[comment('1')],'next_min_id':'a'},{'comments':[comment('1')],'next_min_id':'a'}]);self.assertFalse(r['ok'])
  r,_=self.fetch([{'comments':[{'pk':'1','user':None}]}]);self.assertFalse(r['ok'])
 def test_network_failure_preserves_found_comments(self):
  r,_=self.fetch([{'comments':[comment('1')],'next_min_id':'a'}]);self.assertFalse(r['ok']);self.assertEqual(len(r['comments']),1)

 def test_recent_order_is_preserved_during_pagination(self):
  r,s=self.fetch([{'comments':[comment('1')],'next_min_id':'a'},{'comments':[comment('2')]}])
  self.assertTrue(r['ok']);self.assertEqual([p['sort_order'] for p in s.params],['recent','recent'])
