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
   result=asyncio.run(fetch_complete_comments('1',{'username':'test'},session,orders=('recent',)))
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

 def test_all_supported_orders_merge_ids_without_double_counting(self):
  session=Session([{'comments':[comment('1'),comment('2')],'next_min_id':'a'}, {'comments':[comment('3')]}, {'comments':[comment('2'),comment('4')]}])
  with patch('app_core.instagram_api.current_token',return_value='test'),patch('app_core.instagram_api.prepare_async_headers',side_effect=lambda u,url,h:(h,0)),patch('app_core.instagram_api.build_auth_headers',return_value={}),patch('app_core.session_state.update_session'),patch('app_core.instagram_api.get_outbound_proxy',return_value=None):
   result=asyncio.run(fetch_complete_comments('1',{'username':'test'},session))
  self.assertTrue(result['ok']);self.assertEqual(set(result['comment_ids']),{'1','2','3','4'})
  self.assertEqual([p['sort_order'] for p in session.params],['recent','recent','popular'])

 def test_failed_order_preserves_authors_from_other_order(self):
  session=Session([{'status':'fail'},{'comments':[comment('1')]}])
  with patch('app_core.instagram_api.current_token',return_value='test'),patch('app_core.instagram_api.prepare_async_headers',side_effect=lambda u,url,h:(h,0)),patch('app_core.instagram_api.build_auth_headers',return_value={}),patch('app_core.session_state.update_session'),patch('app_core.instagram_api.get_outbound_proxy',return_value=None):
   result=asyncio.run(fetch_complete_comments('1',{'username':'test'},session))
  self.assertFalse(result['ok']);self.assertEqual(result['comment_ids'],['1'])
  self.assertEqual([p['sort_order'] for p in session.params],['recent','popular'])
 def test_children_seen_in_different_orders_are_not_requested_again(self):
  session=Session([{'comments':[comment('1',child_comment_count=2,preview_child_comments=[comment('2')])]}, {'comments':[comment('1',child_comment_count=2,preview_child_comments=[comment('3')])]}])
  with patch('app_core.instagram_api.current_token',return_value='test'),patch('app_core.instagram_api.prepare_async_headers',side_effect=lambda u,url,h:(h,0)),patch('app_core.instagram_api.build_auth_headers',return_value={}),patch('app_core.session_state.update_session'),patch('app_core.instagram_api.get_outbound_proxy',return_value=None):
   result=asyncio.run(fetch_complete_comments('1',{'username':'test'},session))
  self.assertTrue(result['ok']);self.assertEqual(len(result['comment_ids']),3);self.assertEqual(len(session.urls),2)

 def test_matching_exhausted_order_counts_are_explicitly_verified(self):
  session=Session([{'sort_order':'recent','comment_count':1,'comments':[comment('1')]},{'sort_order':'popular','comment_count':1,'comments':[comment('1')]}])
  with patch('app_core.instagram_api.current_token',return_value='test'),patch('app_core.instagram_api.prepare_async_headers',side_effect=lambda u,url,h:(h,0)),patch('app_core.instagram_api.build_auth_headers',return_value={}),patch('app_core.session_state.update_session'),patch('app_core.instagram_api.get_outbound_proxy',return_value=None):
   result=asyncio.run(fetch_complete_comments('1',{'username':'test'},session))
  self.assertTrue(result['list_count_verified']);self.assertEqual(result['list_comment_count'],1)
 def test_disagreeing_order_totals_do_not_verify_listing_count(self):
  session=Session([{'sort_order':'recent','comment_count':2,'comments':[comment('1')]},{'sort_order':'popular','comment_count':1,'comments':[comment('1')]}])
  with patch('app_core.instagram_api.current_token',return_value='test'),patch('app_core.instagram_api.prepare_async_headers',side_effect=lambda u,url,h:(h,0)),patch('app_core.instagram_api.build_auth_headers',return_value={}),patch('app_core.session_state.update_session'),patch('app_core.instagram_api.get_outbound_proxy',return_value=None):
   result=asyncio.run(fetch_complete_comments('1',{'username':'test'},session))
  self.assertFalse(result['list_count_verified'])

 def test_hidden_or_filtered_list_does_not_override_media_count(self):
  for flags in ({'geoblocked_comment_notices':['restricted']},{'comment_filter_param':'filtered'}):
   pages=[{'sort_order':order,'comment_count':1,'comments':[comment('1')],**flags} for order in ('recent','popular')]
   session=Session(pages)
   with patch('app_core.instagram_api.current_token',return_value='test'),patch('app_core.instagram_api.prepare_async_headers',side_effect=lambda u,url,h:(h,0)),patch('app_core.instagram_api.build_auth_headers',return_value={}),patch('app_core.session_state.update_session'),patch('app_core.instagram_api.get_outbound_proxy',return_value=None):
    result=asyncio.run(fetch_complete_comments('1',{'username':'test'},session))
   self.assertFalse(result['list_count_verified'])

 def exhaustive(self, pages):
  session=Session(pages)
  with patch('app_core.instagram_api.current_token',return_value='test'),patch('app_core.instagram_api.prepare_async_headers',side_effect=lambda u,url,h:(h,0)),patch('app_core.instagram_api.build_auth_headers',return_value={}),patch('app_core.session_state.update_session'),patch('app_core.instagram_api.get_outbound_proxy',return_value=None):
   return asyncio.run(fetch_complete_comments('1',{'username':'test'},session))
 def test_exhausted_identical_visible_ids_do_not_require_counter_equality(self):
  pages=[{'sort_order':order,'comment_count':2,'comments':[comment('1')],'has_more_comments':False,'has_more_headload_comments':False} for order in ('recent','popular')]
  result=self.exhaustive(pages)
  self.assertTrue(result['visible_count_verified']);self.assertEqual(result['visible_comment_count'],1)
  self.assertFalse(result['list_count_verified']);self.assertEqual(result['reported_list_comment_count'],2)
 def test_unfinished_empty_or_different_lists_are_not_visible_completeness(self):
  for override in ({'has_more_headload_comments':True},{'comments':[]},{'has_more_comments':None}):
   pages=[{'sort_order':order,'comment_count':2,'comments':[comment('1')],'has_more_comments':False,'has_more_headload_comments':False,**override} for order in ('recent','popular')]
   self.assertFalse(self.exhaustive(pages)['visible_count_verified'])
  pages=[{'sort_order':order,'comment_count':2,'comments':[comment(str(i))],'has_more_comments':False,'has_more_headload_comments':False} for i,order in enumerate(('recent','popular'))]
  self.assertFalse(self.exhaustive(pages)['visible_count_verified'])
