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
