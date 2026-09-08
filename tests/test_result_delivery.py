import json
import unittest
from unittest.mock import patch
from app_core import create_app


class ResultDeliveryTests(unittest.TestCase):
    def setUp(self):
        with patch("app_core.init_storage"):
            self.app = create_app()
        self.app.config.update(TESTING=True, SESSION_COOKIE_SECURE=False)
        self.client = self.app.test_client()
        with self.client.session_transaction() as session:
            session["admin_logged_in"] = True

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

    def test_loading_page_uses_only_lightweight_poller(self):
        with patch("app_core.routes.main.get_db_value", return_value=json.dumps({"status":"running", "progress":20})):
            response = self.client.get("/result/test")
        self.assertEqual(response.status_code, 200)
        text = response.get_data(as_text=True)
        self.assertIn("js/result_polling.js?v=", text)
        self.assertNotIn("js/result.js?v=", text)
        self.assertNotIn("setInterval", text)
        self.assertIn("no-store", response.headers["Cache-Control"])
        self.assertIn("app;dur=", response.headers["Server-Timing"])

    def test_completed_page_renders_without_network_requests(self):
        result = {"links":[], "all_commented":[], "group":[], "user_missing_posts":{}, "user_comments":{}}
        with patch("app_core.routes.main.get_db_value", side_effect=[json.dumps({"status":"completed"}), json.dumps(result)]):
            response = self.client.get("/result/test")
        self.assertEqual(response.status_code, 200)
        text = response.get_data(as_text=True)
        self.assertIn("js/result.js?v=", text)
        self.assertNotIn("js/result_polling.js?v=", text)
        self.assertIn("no-store", response.headers["Cache-Control"])
