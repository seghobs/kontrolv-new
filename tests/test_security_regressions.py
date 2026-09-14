import asyncio
import socket
import unittest
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

from flask import Flask
from flask_wtf.csrf import CSRFProtect
import app_core.routes.admin as admin
import app_core.routes.main as main
import app_core.instagram_api as instagram
import app_core.token_service as tokens
from app_core import media_proxy as media


class SecurityTests(unittest.TestCase):
    def setUp(self):
        import tempfile
        import app_core.storage as storage
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        database = patch.object(storage, "DB_FILE", str(Path(tmp.name) / "test.db"))
        database.start()
        self.addCleanup(database.stop)
        conn = storage._connect()
        storage._init_db(conn)
        conn.close()
        self.app = Flask("review", template_folder=str(Path(__file__).resolve().parents[1] / "templates"))
        self.app.secret_key = "test-only"
        self.app.config.update(TESTING=True, WTF_CSRF_ENABLED=False)
        CSRFProtect(self.app)
        self.app.register_blueprint(admin.admin_bp)
        self.app.register_blueprint(main.main_bp)
        from app_core.routes.history import history_bp
        self.app.register_blueprint(history_bp)
        self.client = self.app.test_client()

    def login(self):
        with self.client.session_transaction() as session:
            session["admin_logged_in"] = True

    def test_only_configured_password_works(self):
        with patch.object(admin, "ADMIN_PASSWORD", "configured-password"):
            for password in ("legacy-invalid-password", "segho", "wrong", "configured-password"):
                client = self.app.test_client()
                response = client.post("/admin/login", data={"password": password})
                self.assertEqual(response.status_code, 302 if password == "configured-password" else 200)
                with client.session_transaction() as session:
                    self.assertEqual(bool(session.get("admin_logged_in")), password == "configured-password")

    def test_unconfigured_password_denies_login(self):
        with patch.object(admin, "ADMIN_PASSWORD", ""):
            self.client.post("/admin/login", data={"password": "segho"})
            with self.client.session_transaction() as session:
                self.assertFalse(session.get("admin_logged_in"))

    def test_only_admin_routes_require_login(self):
        self.assertEqual(self.client.get('/admin').location, '/admin/login')
        self.assertEqual(self.client.get('/debug_logs').status_code, 401)
        self.assertEqual(self.client.get('/debug_db/test').status_code, 401)
        self.assertEqual(self.client.get('/').status_code, 200)
        with patch.object(main, 'fetch_group_threads_with_failover', return_value={'ok': True, 'groups': []}):
            self.assertEqual(self.client.get('/api/get_groups').json, {'ok': True, 'groups': []})
        with patch('app_core.jobs.enqueue', return_value='public-test-job') as enqueue:
            response = self.client.post('/', data={'post_link': 'https://www.instagram.com/p/ABC123/', 'grup_uye': 'alice'})
            self.assertEqual(response.location, '/result/public-test-job')
            enqueue.assert_called_once()

    def test_authenticated_group_access(self):
        self.login()
        with patch.object(main, "fetch_group_threads_with_failover", return_value={"ok": True, "groups": []}):
            self.assertEqual(self.client.get("/api/get_groups").json, {"ok": True, "groups": []})

    def test_failed_api_never_produces_missing_list(self):
        for likes in (False, True):
            for status in (401, 403, 429, 500):
                with self.subTest(likes=likes, status=status), ExitStack() as stack:
                    stack.enter_context(patch.object(main, "get_working_active_token", return_value={"token": "fake"}))
                    stack.enter_context(patch.object(main, "get_global_exempted_users", return_value=set()))
                    stack.enter_context(patch.object(main, "get_exempted_users", return_value=set()))
                    audit = stack.enter_context(patch.object(main, "add_audit_log"))
                    stack.enter_context(patch.object(instagram, "get_post_details_async", new=AsyncMock(return_value={})))
                    stack.enter_context(patch.object(instagram, "fetch_comment_usernames_async", new=AsyncMock(return_value={"ok": False, "status": status, "comments": []})))
                    stack.enter_context(patch.object(instagram, "fetch_liker_usernames_async", new=AsyncMock(return_value={"ok": False, "status": status, "usernames": set()})))
                    result = main.run_manual_control("https://www.instagram.com/p/ABC123/", "alice bob", "", [], likes)
                    self.assertTrue(result['links'][0]['error'])
                    self.assertEqual(result['links'][0]['eksikler'], [])
                    self.assertEqual(result['all_commented'], [])
                    self.assertEqual(audit.call_args.kwargs['action'], 'kontrol_dogrulanamadi')

    def test_successful_comments_still_classify_members(self):
        with ExitStack() as stack:
            stack.enter_context(patch.object(main, "get_working_active_token", return_value={"token": "fake"}))
            stack.enter_context(patch.object(main, "get_global_exempted_users", return_value=set()))
            stack.enter_context(patch.object(main, "get_exempted_users", return_value=set()))
            stack.enter_context(patch.object(main, "add_audit_log"))
            stack.enter_context(patch.object(instagram, "get_post_details_async", new=AsyncMock(return_value={"like_count": 73, "comment_count": 24})))
            stack.enter_context(patch.object(instagram, "fetch_comment_usernames_async", new=AsyncMock(return_value={"ok": True, "comments": [("alice", "Nice photo!")]})))
            result = main.run_manual_control("https://www.instagram.com/p/ABC123/", "alice bob", "", [], False)
            self.assertEqual(result["links"][0]["eksikler"], ["bob"])
            self.assertEqual(result["links"][0]["like_count"], 73)
            self.assertEqual(result["links"][0]["comment_count"], 24)

    def test_successful_likes_preserve_post_counts(self):
        with ExitStack() as stack:
            stack.enter_context(patch.object(main, "get_working_active_token", return_value={"token": "fake"}))
            stack.enter_context(patch.object(main, "get_global_exempted_users", return_value=set()))
            stack.enter_context(patch.object(main, "get_exempted_users", return_value=set()))
            stack.enter_context(patch.object(main, "add_audit_log"))
            stack.enter_context(patch.object(instagram, "get_post_details_async", new=AsyncMock(return_value={"like_count": 73, "like_count_verified": True, "comment_count": 24})))
            stack.enter_context(patch.object(instagram, "fetch_liker_usernames_async", new=AsyncMock(return_value={"ok": True, "usernames": {"alice"} | {f"other{i}" for i in range(72)}})))
            result = main.run_manual_control("https://www.instagram.com/p/ABC123/", "alice bob", "", [], True)
            self.assertEqual(result["links"][0]["like_count"], 73)
            self.assertEqual(result["links"][0]["comment_count"], 24)

    def test_sync_fallback_error_does_not_create_results(self):
        with ExitStack() as stack:
            stack.enter_context(patch.object(main, "get_working_active_token", return_value={"token": "fake"}))
            stack.enter_context(patch.object(main, "get_global_exempted_users", return_value=set()))
            stack.enter_context(patch.object(main, "get_exempted_users", return_value=set()))
            stack.enter_context(patch.object(instagram, "get_post_details_async", new=AsyncMock(side_effect=RuntimeError("transport failure"))))
            stack.enter_context(patch.object(main, "get_media_taken_at", return_value=(None, None)))
            stack.enter_context(patch.object(main, "get_post_details", return_value={}))
            stack.enter_context(patch.object(main, "fetch_comments_with_failover", return_value={"ok": False, "comments": []}))
            result = main.run_manual_control("https://www.instagram.com/p/ABC123/", "alice", "", [], False)
            self.assertTrue(result['links'][0]['error'])
            self.assertEqual(result['user_missing_posts'], {})
            self.assertEqual(result['all_commented'], [])

    def test_exhausted_failover_remains_failure(self):
        token = {"token": "fake", "username": "test"}
        with patch.object(tokens, "fetch_comment_usernames", return_value={"ok": False, "status": 500}), patch.object(instagram, "fetch_liker_usernames", return_value={"ok": False, "status": 500}):
            self.assertFalse(tokens.fetch_comments_with_failover("1", token_record=token)["ok"])
            self.assertFalse(tokens.fetch_likers_with_failover("1", token_record=token)["ok"])

    def test_transport_failure_is_not_empty_success(self):
        with patch.object(instagram, "build_auth_headers", return_value={}), patch.object(instagram, "_get_http_session", return_value=Mock(get=Mock(side_effect=TimeoutError))):
            self.assertFalse(instagram.fetch_comment_usernames("1", {})["ok"])
            self.assertFalse(instagram.fetch_liker_usernames("1", {})["ok"])

    def test_partial_async_comments_remain_failure(self):
        response = Mock(status=200)
        response.text = AsyncMock(return_value='{"comments": [], "next_min_id": "next"}')
        context = AsyncMock()
        context.__aenter__.return_value = response
        session = Mock(get=Mock(side_effect=[context, TimeoutError()]))
        with patch.object(instagram, "build_auth_headers", return_value={}), patch.object(instagram, "get_outbound_proxy", return_value=None):
            result = asyncio.run(instagram.fetch_comment_usernames_async("1", {}, session))
            self.assertFalse(result["ok"])

    def test_media_response_headers(self):
        self.login()
        with patch.object(media, "fetch_media", return_value=(b"image", "image/jpeg")):
            response = self.client.get("/api/proxy_image?url=test")
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.headers["X-Content-Type-Options"], "nosniff")
            self.assertIn("sandbox", response.headers["Content-Security-Policy"])


class MediaTests(unittest.TestCase):
    def test_rejects_non_cdn_urls_without_dns(self):
        with patch.object(media.socket, "getaddrinfo") as dns:
            for url in ("http://x.cdninstagram.com/a", "https://127.0.0.1/a", "https://cdninstagram.com.evil.test/a", "https://evilcdninstagram.com/a", "https://user@x.fbcdn.net/a", "https://x.fbcdn.net:8080/a", "file:///etc/passwd", "https://x.fbcdn.net/a\n"):
                with self.subTest(url=url), self.assertRaises(media.InvalidMedia):
                    media.resolve_target(url)
            dns.assert_not_called()

    def test_rejects_private_dns_results(self):
        for ip in ("127.0.0.1", "10.0.0.1", "169.254.169.254", "::1", "fc00::1"):
            with patch.object(media.socket, "getaddrinfo", return_value=[(socket.AF_INET, socket.SOCK_STREAM, 6, "", (ip, 443))]), self.assertRaises(media.InvalidMedia):
                media.resolve_target("https://x.cdninstagram.com/a")

    def fetch_fixture(self, status=200, kind="image/jpeg", chunks=None, length="1"):
        response = Mock(status=status, headers={"Content-Type": kind, "Content-Length": length})
        response.read1.side_effect = chunks or [b"x", b""]
        pool = Mock()
        pool.urlopen.return_value = response
        return response, pool

    def test_pins_public_ip_and_preserves_tls_hostname(self):
        response, pool = self.fetch_fixture()
        with patch.object(media, "resolve_target", return_value=("x.fbcdn.net", "8.8.8.8", "/a")), patch.object(media.urllib3, "HTTPSConnectionPool", return_value=pool) as constructor:
            self.assertEqual(media.fetch_media("test"), (b"x", "image/jpeg"))
            self.assertEqual(constructor.call_args.args[0], "8.8.8.8")
            self.assertEqual(constructor.call_args.kwargs["assert_hostname"], "x.fbcdn.net")
            self.assertEqual(constructor.call_args.kwargs["server_hostname"], "x.fbcdn.net")
            self.assertFalse(pool.urlopen.call_args.kwargs["redirect"])
            response.close.assert_called_once()
            pool.close.assert_called_once()

    def test_rejects_redirects_html_svg_and_oversized_media(self):
        for status, kind, length in ((302, "image/jpeg", "0"), (200, "text/html", "1"), (200, "image/svg+xml", "1"), (200, "image/jpeg", str(media.MAX_BYTES + 1))):
            response, pool = self.fetch_fixture(status, kind, length=length)
            with patch.object(media, "resolve_target", return_value=("x.fbcdn.net", "8.8.8.8", "/a")), patch.object(media.urllib3, "HTTPSConnectionPool", return_value=pool), self.assertRaises(media.InvalidMedia):
                media.fetch_media("test")
            response.close.assert_called_once()

    def test_stream_limit_without_content_length(self):
        response, pool = self.fetch_fixture(chunks=[b"12345", b""], length="0")
        with patch.object(media, "MAX_BYTES", 4), patch.object(media, "resolve_target", return_value=("x.fbcdn.net", "8.8.8.8", "/a")), patch.object(media.urllib3, "HTTPSConnectionPool", return_value=pool), self.assertRaises(media.InvalidMedia):
            media.fetch_media("test")

    def test_reels_mp4_is_allowed(self):
        response, pool = self.fetch_fixture(kind="video/mp4")
        with patch.object(media, "resolve_target", return_value=("x.fbcdn.net", "8.8.8.8", "/a")), patch.object(media.urllib3, "HTTPSConnectionPool", return_value=pool):
            self.assertEqual(media.fetch_media("test")[1], "video/mp4")


if __name__ == "__main__":
    unittest.main()
