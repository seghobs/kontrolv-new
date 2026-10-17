import unittest
from app_core.instagram_api import comment_totals, comments_cover_total
class CrossPlatformCommentTests(unittest.TestCase):
 def test_facebook_comment_is_not_required_in_instagram_list(self):
  details=comment_totals({'comment_count':71,'fb_comment_count':1})
  self.assertEqual(details['comment_count'],70)
  self.assertEqual(details['reported_comment_count'],71)
  self.assertTrue(comments_cover_total(details,[('member','comment')]*70))
 def test_missing_instagram_comment_is_still_incomplete(self):
  details=comment_totals({'comment_count':71,'fb_comment_count':1})
  self.assertFalse(comments_cover_total(details,[('member','comment')]*69))
 def test_without_explicit_facebook_count_total_is_not_reduced(self):
  self.assertEqual(comment_totals({'comment_count':71})['comment_count'],71)
 def test_invalid_facebook_counts_never_reduce_required_total(self):
  for value in (None,True,-1,72,'1'):
   self.assertEqual(comment_totals({'comment_count':71,'fb_comment_count':value})['comment_count'],71)
 def test_invalid_total_does_not_establish_completeness(self):
  for value in (None,True,-1,'71'):
   self.assertFalse(comments_cover_total(comment_totals({'comment_count':value,'fb_comment_count':1}),[]))
 def test_zero_total_and_facebook_count_are_valid(self):
  self.assertTrue(comments_cover_total(comment_totals({'comment_count':0,'fb_comment_count':0}),[]))

 def confirmed_listing(self):
  return {'ok':True,'status':200,'incomplete':False,'scanned_orders':['recent','popular'],'list_count_verified':True,'list_comment_count':1,'comment_ids':['comment1'],'comments':[('alice','hello')]}
 def test_listing_count_can_resolve_stale_media_aggregate(self):
  from app_core.instagram_api import reconcile_comment_total
  details=reconcile_comment_total({'comment_count':2,'comment_count_verified':True},self.confirmed_listing())
  self.assertEqual(details['comment_count'],1);self.assertEqual(details['media_comment_count'],2)
  self.assertTrue(comments_cover_total(details,[('alice','hello')]))
 def test_incomplete_unconfirmed_or_single_order_cannot_lower_total(self):
  from app_core.instagram_api import reconcile_comment_total
  original={'comment_count':2,'comment_count_verified':True}
  for override in ({'ok':False},{'incomplete':True},{'list_count_verified':False},{'scanned_orders':['recent']},{'list_comment_count':2},{'comment_ids':['comment1','comment1']}):
   response={**self.confirmed_listing(),**override}
   self.assertEqual(reconcile_comment_total(original,response),original)
 def test_facebook_count_is_not_subtracted_again_from_listing(self):
  from app_core.instagram_api import reconcile_comment_total
  original={'comment_count':2,'comment_count_verified':True,'facebook_comment_count':1}
  self.assertEqual(reconcile_comment_total(original,self.confirmed_listing()),original)

 def test_visible_scope_is_explicit_when_aggregate_stays_higher(self):
  from app_core.instagram_api import reconcile_comment_total
  response={**self.confirmed_listing(),'list_count_verified':False,'list_comment_count':None,'visible_count_verified':True,'visible_comment_count':1,'reported_list_comment_count':2}
  details=reconcile_comment_total({'comment_count':2,'comment_count_verified':True},response)
  self.assertEqual(details['comment_count'],1);self.assertEqual(details['media_comment_count'],2)
  self.assertIn('erişilebilir',details['comment_count_notice']);self.assertIn('2',details['comment_count_notice'])
 def test_unverified_visible_scope_cannot_override_counter(self):
  from app_core.instagram_api import reconcile_comment_total
  response={**self.confirmed_listing(),'list_count_verified':False,'list_comment_count':None,'visible_count_verified':False,'visible_comment_count':1}
  original={'comment_count':2,'comment_count_verified':True}
  self.assertEqual(reconcile_comment_total(original,response),original)
