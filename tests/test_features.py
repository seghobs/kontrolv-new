import json
import unittest
from unittest.mock import patch
from datetime import datetime,timedelta
import test_jobs
from app_core import create_app,jobs,storage,features

class FeatureTests(unittest.TestCase):
    setUp=test_jobs.JobTests.setUp

    def client(self):
        with patch('app_core.init_storage'):app=create_app()
        client=app.test_client()
        with client.session_transaction() as s:s['admin_logged_in']=True
        return client

    def test_expiry_and_undo_keep_original_expiration(self):
        storage.add_global_exemption('alice',1)
        self.assertEqual(len(features.overview()['expiring']),1)
        original=storage.load_global_exemptions()[0]['expires_at']
        storage.remove_global_exemption('alice')
        candidate=next(x for x in features.overview()['undo'] if x['target']=='alice' and features.undo_change(x['id']))
        self.assertEqual(storage.load_global_exemptions()[0]['expires_at'],original)
        self.assertFalse(features.undo_change(candidate['id']))

    def test_undo_cannot_overwrite_later_edit_or_expired_action(self):
        storage.add_global_exemption('alice',1)
        identifier=features.overview()['undo'][0]['id']
        storage.add_global_exemption('alice',2)
        self.assertFalse(features.undo_change(identifier))
        with patch('app_core.features.time.time',return_value=10**12):
            for item in features.overview()['undo']:self.fail('Expired undo was listed')
            self.assertFalse(features.undo_change(identifier))

    def test_group_settings_undo(self):
        before=storage.load_automations()
        storage.save_automations({'123': {'is_active':False,'group_name':'Test'}})
        item=features.overview()['undo'][0]
        self.assertTrue(features.undo_change(item['id']))
        self.assertEqual(storage.load_automations(),before)

    def test_settings_undo(self):
        before=storage.get_global_automation_settings()
        storage.set_global_automation_settings({'times':'19:00'})
        item=features.overview()['undo'][0]
        self.assertTrue(features.undo_change(item['id']))
        self.assertEqual(storage.get_global_automation_settings(),before)

    def test_post_exemption_undo(self):
        storage.save_exemptions({'https://example.com':['alice']})
        storage.save_exemptions({})
        candidates=features.overview()['undo']
        self.assertTrue(any(features.undo_change(x['id']) for x in candidates))
        self.assertEqual(storage.load_exemptions(),{'https://example.com':['alice']})

    def test_presets_authorization_render_and_duplicate_start(self):
        client=self.client();storage.cache_group_names([{'id':'123','name':'Test Grubu'}])
        self.assertEqual(client.post('/tools/presets',data={'name':'Test','thread_id':'123','kind':'comments','only_sharers':'on'}).status_code,302)
        preset=features.overview()['presets'][0]
        first=client.post('/tools/presets/'+preset['id']+'/start')
        second=client.post('/tools/presets/'+preset['id']+'/start')
        self.assertEqual(first.location,second.location)
        self.assertEqual(client.get('/tools').status_code,200)
        with client.session_transaction() as s:s.clear()
        self.assertEqual(client.post('/tools/presets/'+preset['id']+'/start').status_code,302)
        self.assertEqual(client.get('/api/management_overview').status_code,401)

    def test_preset_uses_current_members_and_filters(self):
        payload=dict(thread_id='123',date='2026-09-09',check_likes=False,low_likes=True,only_sharers=True)
        with patch('app_core.token_service.fetch_group_members_with_failover',return_value={'ok':True,'members':[{'username':'alice'},{'username':'bob'}]}),patch('app_core.token_service.fetch_group_media_with_failover',return_value={'ok':True,'posts':[{'url':'https://a','username':'alice','like_count':40},{'url':'https://b','username':'bob','like_count':100}]}),patch('app_core.routes.main.run_manual_control',return_value={}) as run:
            features.run_preset(payload,lambda *a:None)
            self.assertEqual(run.call_args.args[:2],('https://a','alice'))

    def test_summary_excludes_failed_posts_and_separates_types(self):
        data=dict(thread_id='123',check_likes=False,links=[{'eksikler':['bob'],'commenters':['alice']},{'error':'API failed','eksikler':['a','b','c']}])
        identifier=jobs.enqueue('manual',{});jobs.claim('owner');jobs.complete(identifier,'owner',data)
        summary=features.group_summary()[0]
        self.assertEqual(summary['latest'],50)
        self.assertEqual(summary['frequent'],[('bob',1)])

if __name__=='__main__':unittest.main()
