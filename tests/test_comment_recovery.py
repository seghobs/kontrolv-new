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
