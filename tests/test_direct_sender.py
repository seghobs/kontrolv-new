"""Synthetic accounts and blocked sockets: these tests never send a real DM."""
import json
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch, Mock
import unittest

import requests
import test_jobs
from app_core import direct_sender as dm


class DirectSenderTests(unittest.TestCase):
    def account(self, name='synthetic'):
        return dict(username=name, token='synthetic-token', user_agent='synthetic-agent',
                    android_id_yeni='a' * 16, device_id='synthetic-device-uuid')

    def response(self, body=None, status=200):
        response = requests.Response()
        response.status_code = status
        response._content = json.dumps(body if body is not None else {
            'status': 'ok', 'payload': {'item_id': '99', 'thread_id': '123'}}).encode()
        return response

    def setUp(self):
        test_jobs.JobTests.setUp(self)
        for name in ('socket.socket.connect', 'socket.create_connection'):
            guard = patch(name, side_effect=AssertionError('Network forbidden in DM tests'))
            guard.start(); self.addCleanup(guard.stop)
        headers = patch('app_core.instagram_api.build_auth_headers', return_value={})
        headers.start(); self.addCleanup(headers.stop)
        update = patch('app_core.instagram_api._update_session_from_response')
        update.start(); self.addCleanup(update.stop)

    def test_three_equal_numeric_identities_device_fields_and_no_invented_navigation(self):
        endpoint, data = dm.build_payload('123', 'hello', self.account(), '6800011111111111234')
        self.assertTrue(endpoint.endswith('/text/'))
        for key in ('client_context', 'mutation_token', 'offline_threading_id'):
            self.assertEqual(data[key], '6800011111111111234')
        self.assertEqual(data['_uuid'], 'synthetic-device-uuid')
        self.assertEqual(data['device_id'], 'android-' + 'a' * 16)
        self.assertEqual(json.loads(data['thread_ids']), [123])
        self.assertNotIn('nav_chain', data); self.assertNotIn('send_attribution', data)

    def test_link_endpoint_and_recipient_shape(self):
        endpoint, data = dm.build_payload('123', 'see https://example.com', self.account(), '1', to_user=True)
        self.assertTrue(endpoint.endswith('/link/'))
        self.assertEqual(json.loads(data['recipient_users']), [[123]])
        self.assertEqual(json.loads(data['link_urls']), ['https://example.com'])
        self.assertNotIn('text', data); self.assertNotIn('thread_ids', data)

    def test_accepted_request_returns_saved_ack_without_replay(self):
        with patch.object(dm, '_post_once', return_value=self.response()) as post:
            first = dm.send_text('123', 'hello', self.account(), request_id='one')
            second = dm.send_text('123', 'hello', self.account(), request_id='one')
        self.assertTrue(first); self.assertEqual(first, second); self.assertEqual(post.call_count, 1)
        payload = post.call_args.args[3]
        self.assertTrue(payload['client_context'].isdigit())

    def test_timeout_stays_unknown_across_new_invocation(self):
        with patch.object(dm, '_post_once', side_effect=requests.Timeout()) as post:
            first = dm.send_text('123', 'hello', self.account(), request_id='one')
            again = dm.send_text('123', 'hello', self.account(), request_id='one')
        self.assertEqual(first.state, 'unknown'); self.assertEqual(again.state, 'unknown')
        self.assertEqual(post.call_count, 1)

    def test_changed_content_cannot_reuse_request_id(self):
        with patch.object(dm, '_post_once', return_value=self.response()) as post:
            dm.send_text('123', 'hello', self.account(), request_id='one')
            result = dm.send_text('123', 'changed', self.account(), request_id='one')
        self.assertEqual(result.code, 'identity_conflict'); self.assertEqual(post.call_count, 1)

    def test_scope_is_stable_and_distinct_sends_remain_distinct(self):
        with patch.object(dm, '_post_once', return_value=self.response()) as post:
            for _ in range(2):
                with dm.send_scope('job-one'):
                    dm.send_text('123', 'hello', self.account())
            with dm.send_scope('job-two'):
                dm.send_text('123', 'hello', self.account())
        self.assertEqual(post.call_count, 2)

    def test_concurrent_claims_only_dispatch_once(self):
        with patch.object(dm, '_post_once', return_value=self.response()) as post:
            with ThreadPoolExecutor(max_workers=4) as pool:
                results = list(pool.map(lambda _: dm.send_text('123', 'hello', self.account(), request_id='race'), range(4)))
        self.assertEqual(post.call_count, 1)
        self.assertTrue(any(result.state == 'accepted' for result in results))

    def test_wrong_thread_context_or_missing_recipient_thread_is_not_success(self):
        cases = [({'item_id': '99', 'thread_id': '999'}, False),
                 ({'item_id': '99', 'thread_id': '123', 'client_context': 'wrong'}, False),
                 ({'item_id': '99'}, True), ({'item_id': True, 'thread_id': '123'}, False)]
        for i, (payload, to_user) in enumerate(cases):
            with patch.object(dm, '_post_once', return_value=self.response({'status': 'ok', 'payload': payload})):
                result = dm.send_text('123', 'hello', self.account(), to_user=to_user, request_id=str(i))
            self.assertFalse(result)

    def test_feedback_and_rate_limit_stop_without_replay(self):
        with patch.object(dm, '_post_once', return_value=self.response({'message': 'feedback_required'}, 429)) as post:
            first = dm.send_text('123', 'hello', self.account(), request_id='limited')
            dm.send_text('123', 'hello', self.account(), request_id='limited')
        self.assertEqual(first.state, 'rejected'); self.assertEqual(post.call_count, 1)

    def test_storage_failure_prevents_dispatch(self):
        with patch.object(dm, '_claim', side_effect=RuntimeError('DB unavailable')), patch.object(dm, '_post_once') as post:
            result = dm.send_text('123', 'hello', self.account())
        self.assertEqual(result.code, 'storage_error'); post.assert_not_called()

    def test_isolated_transport_disables_redirects_and_retries(self):
        client = Mock()
        with patch('app_core.instagram_api.PersistedSession', return_value=client):
            dm._post_once('synthetic', 'https://example.invalid', {}, {})
        self.assertFalse(client.post.call_args.kwargs['allow_redirects'])
        self.assertEqual(client.mount.call_args_list[0].args[1].max_retries.total, 0)
        client.close.assert_called_once()

    def test_request_identity_is_account_scoped(self):
        with patch.object(dm, '_post_once', return_value=self.response()) as post:
            dm.send_text('123', 'hello', self.account('one'), request_id='shared')
            dm.send_text('123', 'hello', self.account('two'), request_id='shared')
        self.assertEqual(post.call_count, 2)

    def test_ack_survives_local_persistence_error_but_is_never_replayed(self):
        with patch.object(dm, '_post_once', return_value=self.response()) as post, \
                patch.object(dm, '_finish', side_effect=RuntimeError('DB unavailable')):
            first = dm.send_text('123', 'hello', self.account(), request_id='saved')
            again = dm.send_text('123', 'hello', self.account(), request_id='saved')
        self.assertTrue(first); self.assertEqual(again.state, 'unknown')
        self.assertEqual(post.call_count, 1)

    def test_invalid_inputs_never_reach_transport(self):
        with patch.object(dm, '_post_once') as post:
            for target, text, account in [('bad', 'hello', self.account()), ('1', '', self.account()), ('1', 'hello', {})]:
                self.assertEqual(dm.send_text(target, text, account).state, 'rejected')
        post.assert_not_called()
