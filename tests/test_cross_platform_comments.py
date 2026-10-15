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
