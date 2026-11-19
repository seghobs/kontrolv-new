import unittest
from unittest.mock import AsyncMock,patch
from app_core.comment_verification import recover_comment_list
class CommentRecoveryTests(unittest.IsolatedAsyncioTestCase):
 async def test_partial_stream_recovers_all_comments(self):
  details={'comment_count':58,'comment_count_verified':True};partial={'ok':True,'comments':[('member','text')]*52};full={'ok':True,'incomplete':False,'comments':[('member','text')]*58}
  with patch('app_core.comment_verification.fetch_complete_comments',AsyncMock(return_value=full)) as fetch,patch('app_core.instagram_api.get_post_details_async',AsyncMock(return_value=details)):
   result,response=await recover_comment_list('id',{},None,details,partial)
  self.assertEqual(len(response['comments']),58);fetch.assert_awaited_once()
 async def test_complete_stream_avoids_extra_requests(self):
  details={'comment_count':1,'comment_count_verified':True};response={'ok':True,'comments':[('member','text')]}
  with patch('app_core.comment_verification.fetch_complete_comments',AsyncMock()) as fetch:
   self.assertEqual(await recover_comment_list('id',{},None,details,response),(details,response))
  fetch.assert_not_awaited()
 async def test_failed_recovery_preserves_partial_status(self):
  details={'comment_count':58,'comment_count_verified':True};response={'ok':False,'incomplete':True,'comments':[]}
  with patch('app_core.comment_verification.fetch_complete_comments',AsyncMock(return_value={'ok':False,'incomplete':True,'comments':[]})):
   self.assertEqual(await recover_comment_list('id',{},None,details,response),(details,response))
 async def test_rate_limit_does_not_trigger_another_request(self):
  response={'ok':False,'status':429,'comments':[]}
  with patch('app_core.comment_verification.fetch_complete_comments',AsyncMock()) as fetch:
   await recover_comment_list('id',{},None,{},response)
  fetch.assert_not_awaited()

 async def test_second_stream_confirms_missing_tail(self):
  details={'comment_count':3,'comment_count_verified':True};partial={'ok':True,'comments':[('member','one')]};full={'ok':True,'comments':[('member','one'),('member','two')]};retry={'ok':True,'comments':[('member','one'),('member','two'),('member','three')]}
  with patch('app_core.comment_verification.fetch_complete_comments',AsyncMock(return_value=full)),patch('app_core.instagram_api.get_post_details_async',AsyncMock(return_value=details)),patch('app_core.instagram_api.fetch_comment_usernames_async',AsyncMock(return_value=retry)):
   _,response=await recover_comment_list('id',{},None,details,partial)
  self.assertEqual(len(response['comments']),3)

 async def test_recovery_does_not_replace_larger_partial_list(self):
  details={'comment_count':3,'comment_count_verified':True};original={'ok':True,'comments':[('alice','one'),('bob','two')]};shorter={'ok':True,'comments':[('alice','one')]}
  with patch('app_core.comment_verification.fetch_complete_comments',AsyncMock(return_value=shorter)),patch('app_core.instagram_api.get_post_details_async',AsyncMock(return_value=details)),patch('app_core.instagram_api.fetch_comment_usernames_async',AsyncMock(return_value=original)):
   _,response=await recover_comment_list('id',{},None,details,original)
  self.assertEqual(response['comments'],original['comments'])
 async def test_known_authors_survive_incomplete_list_without_false_missing(self):
  from app_core.routes.main import incomplete_comment_post
  row=incomplete_comment_post('url',{'comment_count':3},'owner',[('alice','text'),('outsider','text')],{'alice','bob'})
  self.assertEqual(row['commenters'],['alice']);self.assertEqual(row['eksikler'],[])
  self.assertTrue(row['verification_pending']);self.assertEqual(row['obtained_comment_count'],2)

 async def test_smaller_refreshed_counter_does_not_erase_gap(self):
  details={'comment_count':3,'comment_count_verified':True}
  response={'ok':True,'comments':[('alice','one'),('bob','two')], 'scanned_orders':['recent','popular']}
  with patch('app_core.instagram_api.get_post_details_async',AsyncMock(return_value={'comment_count':2,'comment_count_verified':True})),patch('app_core.instagram_api.fetch_comment_usernames_async',AsyncMock(return_value=response)),patch('app_core.comment_verification.recover_other_account',AsyncMock(side_effect=lambda m,t,s,d,r:(d,r))):
   result,_=await recover_comment_list('id',{},None,details,response)
  self.assertEqual(result['comment_count'],3)

 async def test_other_active_account_recovers_real_identity(self):
  from app_core.comment_verification import recover_other_account
  details={'comment_count':2,'comment_count_verified':True}
  original={'ok':True,'comment_ids':['1'],'comments':[('alice','same')]}
  other=dict(username='second',is_active=True,token='test',user_agent='test',android_id_yeni='test',device_id='test')
  recovered={'ok':True,'status':200,'comment_ids':['1','2'],'comments':[('alice','same'),('bob','same')],'reported_max_comment_count':2}
  with patch('app_core.storage.load_tokens',return_value=[other]),patch('app_core.session_state.load_from_db'),patch('app_core.comment_verification.fetch_complete_comments',AsyncMock(return_value=recovered)):
   result,response=await recover_other_account('id',{'username':'first'},None,details,original)
  self.assertEqual(response['comment_ids'],['1','2'])
  self.assertEqual(len(response['comments']),2)
  self.assertEqual(response['additional_accounts_checked'],1)

 async def test_inactive_accounts_never_used_for_recovery(self):
  from app_core.comment_verification import recover_other_account
  response={'ok':True,'comment_ids':['1'],'comments':[('alice','text')]}
  with patch('app_core.storage.load_tokens',return_value=[{'username':'inactive','is_active':False}]),patch('app_core.comment_verification.fetch_complete_comments',AsyncMock()) as fetch:
   await recover_other_account('id',{'username':'first'},None,{'comment_count':2},response)
  fetch.assert_not_awaited()
