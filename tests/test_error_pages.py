import unittest
from unittest.mock import patch
import test_jobs
from app_core import create_app
class ErrorPageTests(unittest.TestCase):
 setUp=test_jobs.JobTests.setUp
 def test_html_error_pages_and_api_json(self):
  with patch('app_core.init_storage'):app=create_app()
  client=app.test_client()
  for path,code in [('/not-a-page',404),('/backups',403)]:
   response=client.get(path,headers={'Accept':'text/html'})
   self.assertEqual(response.status_code,code);self.assertIn('suite-error',response.text)
   response=client.get(path,headers={'Accept':'application/json'})
   self.assertEqual(response.status_code,code);self.assertFalse(response.json['success'])
  response=client.get('/api/not-a-route',headers={'Accept':'text/html'})
  self.assertEqual(response.status_code,404);self.assertFalse(response.json['success'])
 def test_internal_error_does_not_expose_details(self):
  with patch('app_core.init_storage'):app=create_app()
  app.config['PROPAGATE_EXCEPTIONS']=False
  @app.get('/test-failure')
  def fail():raise RuntimeError('private diagnostic detail')
  response=app.test_client().get('/test-failure',headers={'Accept':'text/html'})
  self.assertEqual(response.status_code,500);self.assertIn('suite-error',response.text);self.assertNotIn('private diagnostic detail',response.text)
