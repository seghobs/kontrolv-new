import unittest
from unittest.mock import Mock,patch
from datetime import datetime,timezone,timedelta
import test_jobs
from app_core import create_app
from app_core.instagram_api import fetch_group_media
class GroupDayTests(unittest.TestCase):
 setUp=test_jobs.JobTests.setUp
 def fetch(self,messages,media=None,older=None,details=None):
  self.stamp=int(datetime(2026,9,18,12,tzinfo=timezone(timedelta(hours=3))).timestamp()*1000000)
  def response(d):r=Mock(status_code=200);r.json.return_value=d;return r
  for m in messages:m.setdefault('timestamp',self.stamp)
  responses=[response({'thread':{'items':messages,'users':[],'has_older':bool(older),'oldest_cursor':'next'}}),response({'items':media or []})]
  if older:
   for m in older:m.setdefault('timestamp',self.stamp-100)
   responses.append(response({'thread':{'items':older,'has_older':False}}))
  responses.extend(response(d) for d in (details or []))
  http=Mock();http.get.side_effect=responses
  with patch('app_core.instagram_api.current_token',return_value='token'),patch('app_core.instagram_api.extract_user_id_from_token',return_value='1'),patch('app_core.instagram_api.build_auth_headers',return_value={}),patch('app_core.instagram_api._get_http_session',return_value=http),patch('app_core.instagram_api._update_session_from_response'):
   result=fetch_group_media({'username':'test','token':'token','user_agent':'ua','android_id_yeni':'a','device_id':'d'},'g',datetime(2026,9,18),complete=True)
  return result,http
 def test_reels_posts_text_and_older_messages(self):
  result,http=self.fetch([{'item_type':'media_share','media_share':{'code':'POST','user':None}},{'item_type':'clip','clip':{'clip':{'media':{'code':'REEL','product_type':'clips'}}}},{'item_type':'reel_share','reel_share':{'code':'STORY'}}],older=[{'item_type':'text','text':'https://www.instagram.com/p/TEXT/'},{'item_type':'media_share','media_share':{'code':'POST'}}])
  self.assertTrue(result['ok'],result);self.assertEqual({p['code'] for p in result['posts']},{'POST','REEL','TEXT'});self.assertEqual(result['story_count'],1);self.assertEqual(http.get.call_count,3)
  self.assertEqual(next(p for p in result['posts'] if p['code']=='REEL')['media_type'],'video')
 def test_text_only_day_and_date_boundary(self):
  result,_=self.fetch([{'item_type':'text','text':'https://www.instagram.com/reel/ABC/ https://www.instagram.com/p/ABC/'},{'timestamp':1,'item_type':'media_share','media_share':{'code':'OLD'}}])
  self.assertTrue(result['ok'],result);self.assertEqual([p['code'] for p in result['posts']],['ABC'])
 def test_form_requests_full_day(self):
  with patch('app_core.init_storage'):client=create_app().test_client()
  with patch('app_core.routes.main.fetch_group_media_with_failover',return_value={'ok':True,'posts':[]}) as fetch:
   self.assertEqual(client.get('/api/get_group_posts/g?date=2026-09-18').status_code,200)
  self.assertEqual(fetch.call_args.kwargs,{'complete':True});self.assertEqual(fetch.call_args.args[1].strftime('%Y-%m-%d'),'2026-09-18')
 def test_xma_real_format_metadata_dedup_and_story_exclusion(self):
  messages=[{'item_type':'xma_media_share','xma_media_share':[{'target_url':'https://www.instagram.com/p/NEW/?is_sponsored=false','preview_media_fbid':123}]},
   {'item_type':'xma_media_share','xma_media_share':[{'target_url':'https://www.instagram.com/p/OLD/'}]},
   {'item_type':'xma_story_share','xma_story_share':[{'target_url':'https://www.instagram.com/stories/member/123'}]},
   {'item_type':'text','replied_to_message':{'item_type':'xma_media_share','xma_media_share':[{'target_url':'https://www.instagram.com/p/QUOTED/'}]}}]
  result,http=self.fetch(messages,media=[{'timestamp':int(datetime(2026,9,18,12,tzinfo=timezone(timedelta(hours=3))).timestamp()*1000000),'media':{'code':'OLD'}}],details=[{'items':[{'code':'NEW','user':{'username':'owner'},'like_count':81,'media_type':2}]}])
  self.assertTrue(result['ok'],result);self.assertEqual({p['code'] for p in result['posts']},{'NEW','OLD'});self.assertEqual(result['story_count'],1)
  post=next(p for p in result['posts'] if p['code']=='NEW')
  self.assertEqual((post['username'],post['like_count'],post['media_type']),('owner',81,'video'));self.assertEqual(http.get.call_count,3)
 def test_xma_missing_metadata_still_lists_link_and_nulls_do_not_crash(self):
  result,_=self.fetch([{'item_type':'xma_media_share','xma_media_share':[None,{'target_url':None},{'target_url':'https://evil.test/p/FAKE/'},{'target_url':'https://www.instagram.com/reel/NEW/'}]}, {'item_type':'xma_media_share','xma_media_share':None}],details=[{'items':None}])
  self.assertTrue(result['ok'],result);self.assertEqual([p['code'] for p in result['posts']],['NEW']);self.assertEqual(result['posts'][0]['like_count'],-1);self.assertEqual(result['posts'][0]['media_type'],'video')
