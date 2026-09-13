import unittest
from unittest.mock import patch, Mock
from app_core import create_app, storage
from app_core.routes import admin
import test_jobs


class AdminWorkflows(unittest.TestCase):
    setUp = test_jobs.JobTests.setUp

    def client(self, authenticated=True):
        with patch('app_core.init_storage'):app=create_app()
        app.config['TESTING']=True
        client=app.test_client()
        if authenticated:
            with client.session_transaction() as session:session['admin_logged_in']=True
        return app,client

    def test_every_admin_endpoint_is_protected_before_work(self):
        app,client=self.client(False)
        for rule in app.url_map.iter_rules():
            if not rule.rule.startswith('/admin/') or rule.endpoint in ('admin.login','admin.logout','admin.panel'):continue
            path=rule.rule.replace('<thread_id>','test').replace('<username>','alice')
            response=client.post(path,json={}) if 'POST' in rule.methods else client.get(path)
            self.assertEqual(response.status_code,401,path)

    def test_admin_login_opens_admin_panel(self):
        _,client=self.client(False)
        with patch.object(admin,'ADMIN_PASSWORD','test-only'):
            response=client.post('/admin/login',data={'password':'test-only'})
        self.assertEqual(response.location.rstrip('/'),'/admin')

    def test_post_and_global_exemption_crud(self):
        _,client=self.client()
        data={'post_link':'https://www.instagram.com/p/ABC/','username':'alice'}
        for endpoint in ('add_exemption','add_exemption'):
            self.assertTrue(client.post('/admin/'+endpoint,json=data).json['success'])
        self.assertEqual(client.get('/admin/get_exemptions').json['total'],1)
        self.assertTrue(client.post('/admin/delete_exemption',json=data).json['success'])
        self.assertEqual(client.get('/admin/get_exemptions').json['total'],0)
        self.assertTrue(client.post('/admin/add_global_exemption',json={'username':'alice','days':2}).json['success'])
        self.assertTrue(client.get('/admin/get_global_exemptions').json['exemptions'])
        self.assertTrue(client.post('/admin/remove_global_exemption',json={'username':'alice'}).json['success'])
        self.assertFalse(client.get('/admin/get_global_exemptions').json['exemptions'])

    def test_token_add_toggle_export_delete_in_isolated_database(self):
        _,client=self.client()
        data={'token':'test-only','password':'test-only','android_id':'a'*16,'device_id':'a'*8,'user_agent':'test-only'}
        with patch.object(admin,'fetch_current_user',return_value=Mock(status_code=200,json=lambda:{'user':{'username':'alice','full_name':'Test'}})):
            self.assertTrue(client.post('/admin/add_token',json=data).json['success'])
        self.assertEqual(len(storage.load_tokens()),1)
        self.assertTrue(client.post('/admin/toggle_token',json={'username':'alice'}).json['success'])
        self.assertEqual(client.get('/admin/export_tokens').status_code,200)
        self.assertTrue(client.post('/admin/delete_token',json={'username':'alice'}).json['success'])
        self.assertFalse(storage.load_tokens())
