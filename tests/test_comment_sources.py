import asyncio
import json
import unittest
from contextlib import ExitStack
from unittest.mock import patch

from app_core.comment_sources import fetch_comment_supplements


def comment(cid, **extra):
    return dict(pk=cid, user={'username': 'alice'}, text='same text', **extra)


class Response:
    headers = {}
    cookies = {}

    def __init__(self, body, status=200):
        self.body = body
        self.status = status

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        pass

    async def text(self):
        return self.body if isinstance(self.body, str) else json.dumps(self.body)


class Session:
    def __init__(self, responses):
        self.responses = iter(responses)
        self.requests = []

    def get(self, url, **kwargs):
        self.requests.append((url, kwargs['params']))
        return next(self.responses)

    def post(self, url, **kwargs):
        self.requests.append((url, kwargs['data']))
        return next(self.responses)


class CommentSourceTests(unittest.TestCase):
    def fetch(self, responses):
        session = Session(responses)
        with ExitStack() as stack:
            stack.enter_context(patch('app_core.instagram_api.current_token', return_value='test'))
            stack.enter_context(patch('app_core.instagram_api.build_auth_headers', return_value={}))
            stack.enter_context(patch('app_core.instagram_api.prepare_async_headers', side_effect=lambda u, url, h: (h, 0)))
            stack.enter_context(patch('app_core.instagram_api.get_outbound_proxy', return_value=None))
            stack.enter_context(patch('app_core.session_state.update_session'))
            result = asyncio.run(fetch_comment_supplements('123', {'username': 'test'}, session, ['1']))
        return result, session

    def test_hoisted_comment_recovered_caption_never_counted(self):
        result, _ = self.fetch([
            Response({'items': [{'comment_count': 2, 'preview_comments': [comment('1')],
                                 'hoisted_comments': [comment('2')], 'caption': comment('caption', type=1)}]}),
            Response({'comments': [comment('1')]}), Response({'comments': [comment('1')]}),
        ])
        self.assertEqual(set(result['comment_ids']), {'1', '2'})
        self.assertEqual(result['reported_max_comment_count'], 2)

    def test_all_ndjson_chunks_and_both_cursors_are_retained(self):
        stream = '\n'.join(json.dumps(x) for x in [
            {'comments': [comment('1')], 'next_min_id': 'older', 'next_max_id': 'newer'},
            {'comments': [comment('2')], 'caption': comment('caption', type=1)},
        ])
        result, session = self.fetch([
            Response({'items': []}), Response(stream), Response({'comments': [comment('3')]}),
            Response({'comments': [comment('4')]}), Response({'comments': [comment('1')]}),
        ])
        self.assertEqual(set(result['comment_ids']), {'1', '2', '3', '4'})
        self.assertEqual(session.requests[2][1]['min_id'], 'older')
        self.assertEqual(session.requests[3][1]['max_id'], 'newer')

    def test_reply_pagination_and_preview_are_deduplicated(self):
        parent = comment('1', child_comment_count=2, preview_child_comments=[comment('2')])
        result, _ = self.fetch([
            Response({'items': [{'hoisted_comments': [parent]}]}),
            Response({'comments': []}), Response({'comments': []}),
            Response({'child_comments': [comment('2')], 'next_min_child_cursor': 'next'}),
            Response({'child_comments': [comment('3')]}),
        ])
        self.assertEqual(set(result['comment_ids']), {'1', '2', '3'})

    def test_repeated_cursor_terminates(self):
        page = Response({'comments': [comment('1')], 'next_min_id': 'loop'})
        result, session = self.fetch([Response({'items': []}), page, page, Response({'comments': []})])
        self.assertEqual(result['comment_ids'], ['1'])
        self.assertEqual(len(session.requests), 4)

    def test_rate_limit_stops_further_requests(self):
        result, session = self.fetch([Response({'items': []}), Response({}, 429)])
        self.assertEqual(result['stopped_status'], 429)
        self.assertEqual(len(session.requests), 2)

    def test_anonymous_and_caption_like_records_do_not_fill_count_gap(self):
        result, _ = self.fetch([
            Response({'items': [{'hoisted_comments': [comment('1', type=1), {'pk': '2', 'user': None}]}]}),
            Response({'comments': []}), Response({'comments': []}),
        ])
        self.assertEqual(result['comments'], [])

    def test_current_graphql_connection_recovers_missing_identity(self):
        connection = {'edges': [{'node': comment('2')}], 'page_info': {'has_next_page': False}}
        result, session = self.fetch([
            Response({'items': [{'comment_count': 2}]}), Response({'comments': []}),
            Response({'comments': []}), Response({'comments': []}),
            Response({'data': {'xdt_comments_connection': connection}}),
        ])
        self.assertEqual(result['comment_ids'], ['2'])
        self.assertEqual(session.requests[-1][1]['doc_id'], '6974885689225067')

    def test_native_hidden_endpoint_uses_full_media_id_and_its_own_cursor(self):
        result, session = self.fetch([
            Response({'items': [{'id': '123_99', 'comment_count': 3}]}),
            Response({'comments': [comment('2')], 'next_min_id': 'hidden-next', 'has_more_headload_comments': True}),
            Response({'comments': [comment('2'), comment('3')], 'has_more_headload_comments': False}),
            Response({'comments': []}), Response({'comments': []}),
        ])
        self.assertEqual(set(result['comment_ids']), {'2', '3'})
        self.assertTrue(session.requests[1][0].endswith('/api/v1/hidden_comments/123_99/hidden_comments/'))
        self.assertEqual(session.requests[1][1], {'directly_hidden_only': 1})
        self.assertEqual(session.requests[2][1], {'directly_hidden_only': 1, 'next_min_id': 'hidden-next'})

    def test_native_hidden_permission_failure_stops_recovery_without_guessing_authors(self):
        result, session = self.fetch([
            Response({'items': [{'comment_count': 2}]}), Response({}, 403),
        ])
        self.assertEqual(result['comment_ids'], [])
        self.assertEqual(result['stopped_status'], 403)
        self.assertEqual(len(session.requests), 2)


if __name__ == '__main__':
    unittest.main()
