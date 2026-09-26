import unittest
from unittest.mock import patch
import test_jobs
from app_core import create_app,storage
class GroupPreferenceTests(unittest.TestCase):
 setUp=test_jobs.JobTests.setUp
 def client(self):
  with patch('app_core.init_storage'):app=create_app()
  return app.test_client()
 def test_defaults_and_group_isolation(self):
  c=self.client();off=dict(only_sharers=False,low_likes=False)
  self.assertEqual(c.get('/api/group_control_preferences/a').json['preferences'],off)
  self.assertTrue(c.post('/api/group_control_preferences/a',json=dict(only_sharers=True,low_likes=True)).json['ok'])
  self.assertEqual(c.get('/api/group_control_preferences/b').json['preferences'],off)
  self.assertEqual(self.client().get('/api/group_control_preferences/a').json['preferences'],dict(only_sharers=True,low_likes=True))
 def test_six_group_modes_and_last_override(self):
  names=[('INFLUENCER VİBES (27)','comments'),('İNFLUENCER VİBES LİKE (9)','likes'),('🎀 ZİRVE YORUM BEĞENİ 2 🎀 (99)','comments'),('🩷 ZİRVE BEĞENİ GRUBU 2 🩷 (75)','likes'),('🧿 ZİRVE BEĞENİ GRUBU 1 🧿 (80)','likes'),('💜ZİRVE YORUM BEĞENİ 1💜 (75)','comments')]
  ids=['340282366841710301281152316007215030727','340282366841710301281152285221828141838','340282366841710301281176651461280340717','340282366841710301281160514595477770576','340282366841710301281159538622628703126','340282366841710301281156982018321100464']
  storage.cache_group_names([{'id':ids[i],'name':name} for i,(name,_) in enumerate(names)])
  c=self.client()
  for i,(_,mode) in enumerate(names):
   url='/api/group_control_preferences/'+ids[i]
   self.assertEqual(c.get(url).json['control_mode'],mode)
   storage.cache_group_names([{'id':ids[i],'name':'Tamamen farklı yeni isim'}])
   self.assertEqual(c.get(url).json['control_mode'],mode)
   changed='likes' if mode=='comments' else 'comments'
   c.post(url,json=dict(only_sharers=False,low_likes=False,control_mode=changed))
   self.assertEqual(self.client().get(url).json['control_mode'],changed)
   storage.cache_group_names([{'id':ids[i],'name':'Bir kez daha değişti'}])
   self.assertEqual(c.get(url).json['control_mode'],changed)
   c.post(url,json=dict(only_sharers=True,low_likes=False))
   self.assertEqual(c.get(url).json['control_mode'],changed)
   self.assertEqual(c.post(url,json=dict(only_sharers=False,low_likes=False,control_mode='invalid')).status_code,400)
   self.assertEqual(c.get(url).json['control_mode'],changed)
  storage.cache_group_names([{'id':'unrelated','name':'İNFLUENCER VİBES LİKE'}])
  self.assertEqual(c.get('/api/group_control_preferences/unrelated').json['control_mode'],'comments')
 def test_uncheck_is_persisted_and_independent_flags(self):
  c=self.client();u='/api/group_control_preferences/a'
  for value in [dict(only_sharers=True,low_likes=False),dict(only_sharers=False,low_likes=True),dict(only_sharers=False,low_likes=False)]:
   self.assertEqual(c.post(u,json=value).status_code,200)
   self.assertEqual(c.get(u).json['preferences'],value)
 def test_invalid_payload_does_not_overwrite(self):
  c=self.client();u='/api/group_control_preferences/a';initial=dict(only_sharers=True,low_likes=False);c.post(u,json=initial)
  for bad in [None,[],{},dict(only_sharers='false',low_likes=False),dict(only_sharers=1,low_likes=True),dict(only_sharers=False,low_likes=False,extra=True)]:
   self.assertEqual(c.post(u,json=bad).status_code,400)
  self.assertEqual(c.get(u).json['preferences'],initial)
 def test_database_failure_is_visible(self):
  c=self.client()
  with patch('app_core.routes.main._connect') as connect:
   connect.return_value.execute.side_effect=RuntimeError('test DB error')
   self.assertEqual(c.get('/api/group_control_preferences/a').status_code,503)
   self.assertEqual(c.post('/api/group_control_preferences/a',json=dict(only_sharers=True,low_likes=False)).status_code,503)
 def test_existing_records_preserved(self):
  c=self.client();conn=storage._connect();conn.execute("INSERT INTO key_value(key,value) VALUES ('keep_me','original')");conn.commit();conn.close()
  c.post('/api/group_control_preferences/a',json=dict(only_sharers=True,low_likes=False))
  conn=storage._connect();self.assertEqual(conn.execute("SELECT value FROM key_value WHERE key='keep_me'").fetchone()['value'],'original');conn.close()
