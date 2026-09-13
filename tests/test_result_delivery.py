import json
import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch
from app_core import create_app


class ResultDeliveryTests(unittest.TestCase):
    def setUp(self):
        from app_core import storage
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        database = patch.object(storage, 'DB_FILE', str(Path(temporary.name) / 'test.db'))
        database.start()
        self.addCleanup(database.stop)
        with storage._connect() as connection:
            storage._init_db(connection)
        connection.close()
        with patch("app_core.init_storage"):
            self.app = create_app()
        self.app.config.update(TESTING=True, SESSION_COOKIE_SECURE=False)
        self.client = self.app.test_client()

    def test_stable_versioned_assets_can_be_cached(self):
        with self.app.test_request_context():
            from flask import url_for
            url = url_for("static", filename="js/result.js")
            self.assertEqual(url, url_for("static", filename="js/result.js"))
        self.assertIn("v=", url)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertIn("max-age=3600", response.headers["Cache-Control"])
        self.assertNotIn("no-store", response.headers["Cache-Control"])
        self.assertNotIn("Set-Cookie", response.headers)
        response.close()

    def test_asset_version_updates_without_restarting_app(self):
        from flask import url_for
        with tempfile.NamedTemporaryFile(dir=self.app.static_folder, suffix='.css', delete=False) as asset:
            path = Path(asset.name)
            asset.write(b'body { color: red; }')
        try:
            with self.app.test_request_context():
                original = url_for('static', filename=path.name)
                self.assertEqual(original, url_for('static', filename=path.name))
                path.write_text('body { color: blue; }', encoding='utf-8')
                updated = url_for('static', filename=path.name)
                self.assertNotEqual(original, updated)
                self.assertEqual(updated, url_for('static', filename=path.name))
        finally:
            path.unlink()

    def test_running_job_returns_to_form(self):
        with patch("app_core.routes.main.get_db_value", return_value=json.dumps({"status":"running", "progress":20})):
            response = self.client.get("/result/test")
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.location, '/?task=test')
        response = self.client.get(response.location)
        text = response.get_data(as_text=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn('id="checkForm"', text)
        self.assertIn('js/control_submit.js', text)
        self.assertNotIn('loading-screen-card', text)
        self.assertNotIn('waiting.css', text)

    def test_inline_submission_returns_job_identifier(self):
        with patch('app_core.jobs.enqueue', return_value='inline-job'):
            response = self.client.post('/', data={'post_link':'https://www.instagram.com/p/ABC/'}, headers={'Accept':'application/json'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json, {'success':True, 'job_id':'inline-job'})

    def test_completed_page_renders_without_network_requests(self):
        result = {"links":[], "all_commented":[], "group":[], "user_missing_posts":{}, "user_comments":{}}
        with patch("app_core.routes.main.get_db_value", side_effect=[json.dumps({"status":"completed"}), json.dumps(result)]):
            response = self.client.get("/result/test")
        self.assertEqual(response.status_code, 200)
        text = response.get_data(as_text=True)
        self.assertIn("js/result.js?v=", text)
        self.assertIn("js/result_recheck.js", text)
        self.assertIn("no-store", response.headers["Cache-Control"])
