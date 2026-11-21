import re
import unittest
from unittest.mock import patch
import test_jobs
from app_core import create_app


class LoginAPITests(unittest.TestCase):
    def setUp(self):
        test_jobs.JobTests.setUp(self)
        with patch('app_core.init_storage'):self.app=create_app()
        self.client=self.app.test_client()

    def authorize(self):
        with self.client.session_transaction() as session:session['admin_logged_in']=True
        page=self.client.get('/token_al')
        token=re.search(r'<meta name="csrf-token" content="([^"]+)"',page.text)[1]
        return {'X-CSRFToken':token}

    def test_login_api_requires_admin_and_token_page_redirects(self):
        self.assertEqual(self.client.post('/api/luma-login/start',json={'username':'alice'}).status_code,401)
        self.assertEqual(self.client.get('/token_al').location,'/admin/login')

    def test_even_when_global_csrf_is_disabled_login_requires_csrf(self):
        self.authorize()
        with patch('app_core.luma_login.start') as start:
            response=self.client.post('/api/luma-login/start',json={'username':'alice'})
        self.assertEqual(response.status_code,400);start.assert_not_called()

    def test_start_accepts_credentials_without_manual_device_ids(self):
        headers=self.authorize()
        flow={'id':'test','stage':'approval','message':'Onayla','username':'alice'}
        with patch('app_core.luma_login.start',return_value=flow) as start:
            response=self.client.post('/api/luma-login/start',headers=headers,json={'username':'alice','password':'secret','profile':'s23'})
        self.assertEqual(response.status_code,200);self.assertEqual(response.json['flow']['stage'],'approval')
        self.assertEqual(start.call_args.kwargs['profile_name'],'s23');self.assertNotIn('secret',response.text)

    def test_cross_origin_start_is_rejected(self):
        headers=self.authorize();headers['Origin']='https://another.example'
        with patch('app_core.luma_login.start') as start:
            response=self.client.post('/api/luma-login/start',headers=headers,json={'username':'alice'})
        self.assertEqual(response.status_code,403);start.assert_not_called()

    def test_legacy_endpoint_never_replays_the_old_device_specific_flow(self):
        self.authorize()
        with patch('app_core.routes.main.giris_yap') as old:
            response=self.client.post('/giris_yaps',data={'kullanici_adi':'alice','sifre':'secret'})
        self.assertEqual(response.status_code,409);old.assert_not_called()

    def test_step_errors_do_not_leak_sdk_exception_or_credentials(self):
        headers=self.authorize()
        with patch('app_core.luma_login.advance',side_effect=RuntimeError('SECRET')):
            response=self.client.post('/api/luma-login/test/step',headers=headers,json={'action':'poll'})
        self.assertEqual(response.status_code,503);self.assertNotIn('SECRET',response.text)
