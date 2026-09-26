import unittest
from unittest.mock import patch
import test_jobs
from app_core import create_app
from app_core.followup import read
from app_core.save_control import api_key

class GeminiSettingsTests(unittest.TestCase):
    setUp=test_jobs.JobTests.setUp
    def client(self, admin=True):
        with patch('app_core.init_storage'): app=create_app()
        client=app.test_client()
        if admin:
            with client.session_transaction() as session:session['admin_logged_in']=True
        return client

    def test_admin_only_read_and_write(self):
        c=self.client(False)
        self.assertEqual(c.get('/admin/gemini_settings').status_code,401)
        self.assertEqual(c.post('/admin/gemini_settings',json={'api_key':'test-secret-key-123456789'}).status_code,401)
        self.assertIsNone(read('settings:gemini_api'))

    def test_persist_and_immediate_priority_over_environment(self):
        key='test-only-new-key-1234567890';c=self.client()
        with patch.dict('os.environ',{'GEMINI_API_KEY':'test-only-old-key-1234567890'}):
            self.assertEqual(c.post('/admin/gemini_settings',json={'api_key':key}).status_code,200)
            self.assertEqual(api_key(),key)
            self.assertEqual(self.client().get('/admin/gemini_settings').json['api_key'],key)
        self.assertNotIn(key,c.get('/admin/').get_data(as_text=True))
        self.assertIn('no-store',c.get('/admin/gemini_settings').headers['Cache-Control'])

    def test_invalid_input_preserves_existing_key(self):
        c=self.client();key='test-only-original-1234567890'
        c.post('/admin/gemini_settings',json={'api_key':key})
        for value in ['',None,123,'short','a'*513,'a'*20+'\n'+'b'*20]:
            self.assertEqual(c.post('/admin/gemini_settings',json={'api_key':value}).status_code,400)
            self.assertEqual(api_key(),key)

    def test_failed_write_and_legacy_fallback(self):
        c=self.client()
        with patch.dict('os.environ',{'GEMINI_API_KEY':'test-only-env-key-123456789'}):
            self.assertEqual(c.get('/admin/gemini_settings').json['api_key'],'test-only-env-key-123456789')
            with patch('app_core.followup.write',side_effect=RuntimeError('disk full')):
                self.assertEqual(c.post('/admin/gemini_settings',json={'api_key':'test-only-new-key-123456789'}).status_code,503)
            self.assertEqual(api_key(),'test-only-env-key-123456789')
