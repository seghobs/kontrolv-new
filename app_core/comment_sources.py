"""Bounded, read-only recovery of comments omitted by the main mobile list.

Only real comment identities count. Captions and aggregate counters never do.
"""
import json
import logging
import time

import aiohttp

from app_core import instagram_api as api
from app_core.validators import is_valid_username

logger = logging.getLogger(__name__)
MAX_RECOVERY_REQUESTS = 24
RECOVERY_SECONDS = 30


async def fetch_comment_supplements(media_id, token_record, session, known_ids=(), expected_count=None):
    records = {}
    parents = {}
    diagnostics = []
    totals = {expected_count} if type(expected_count) is int and expected_count >= 0 else set()
    started = time.monotonic()
    requests_left = MAX_RECOVERY_REQUESTS
    stopped_status = None
    username = api._get_username(token_record)

    async def fetch(path, params, *, graphql=False):
        nonlocal requests_left
        remaining = RECOVERY_SECONDS - (time.monotonic() - started)
        if requests_left <= 0 or remaining <= 0:
            raise TimeoutError('Recovery budget exhausted')
        requests_left -= 1
        token = api.current_token(username, token_record.get('token', ''))
        headers = api.build_auth_headers(token, token_record.get('user_agent', ''),
                                         token_record.get('android_id_yeni', ''),
                                         token_record.get('device_id', ''), username=username)
        headers['Accept-Encoding'] = 'gzip, deflate'
        url = ('https://www.instagram.com/graphql/query/' if graphql else
               f'https://i.instagram.com/api/v1/media/{media_id}/{path}')
        if graphql:
            headers['Accept-Encoding'] = 'gzip, deflate'
            headers['Referer'] = 'https://www.instagram.com/'
        headers, revision = api.prepare_async_headers(username, url, headers)
        request = session.post if graphql else session.get
        payload = {'data' if graphql else 'params': params}
        async with request(url, **payload, headers=headers,
                               proxy=api.get_outbound_proxy(),
                               timeout=aiohttp.ClientTimeout(total=min(8, remaining))) as response:
            from app_core.session_state import update_session, response_cookies
            update_session(username, response.headers, expected_token=headers.get('authorization'),
                           cookies=response_cookies(response), expected_revision=revision)
            if response.status != 200:
                error = ValueError('Recovery request failed')
                error.status = response.status
                raise error
            chunks = [json.loads(line) for line in (await response.text()).splitlines() if line.strip()]
            if not chunks or any(not isinstance(c, dict) or c.get('status') == 'fail' for c in chunks):
                raise ValueError('Invalid recovery response')
            return chunks

    def add(items):
        ids = set()
        if not isinstance(items, list):
            return ids
        for item in items:
            if not isinstance(item, dict) or item.get('type') == 1:
                continue  # Instagram captions have their own PK and author.
            cid = item.get('pk') or item.get('id')
            user = item.get('user') or item.get('owner') or {}
            name = user.get('username') if isinstance(user, dict) else None
            if not cid or not isinstance(name, str) or not is_valid_username(name):
                continue
            cid = str(cid)
            ids.add(cid)
            records[cid] = (name, item.get('text') if isinstance(item.get('text'), str) else '')
            children = add(item.get('preview_child_comments', []))
            expected = item.get('child_comment_count', 0)
            if type(expected) is int and expected > 0:
                old_expected, old_ids = parents.get(cid, (0, set()))
                parents[cid] = (max(expected, old_expected), old_ids | children)
        return ids

    def consume(data):
        count = data.get('comment_count')
        if type(count) is int and count >= 0:
            totals.add(count)
        for key in ('comments', 'preview_comments', 'hoisted_comments', 'pinned_comments', 'child_comments'):
            add(data.get(key, []))

    # Media metadata may hoist/pin comments outside the normal comment array.
    try:
        for data in await fetch('info/', {}):
            for media in data.get('items') or []:
                consume(media)
                diagnostics.append(dict(source='media_info', counts={k: len(media.get(k) or [])
                    for k in ('preview_comments', 'hoisted_comments', 'pinned_comments')
                    if isinstance(media.get(k), list)}))
    except Exception as error:
        diagnostics.append(dict(source='media_info', status=getattr(error, 'status', 502)))
        if getattr(error, 'status', None) in (401, 403, 429):
            return dict(comments=list(records.values()), comment_ids=list(records), sources=diagnostics,
                        reported_max_comment_count=max(totals) if totals else None,
                        stopped_status=error.status)

    # NDJSON stream and the legacy, unthreaded list are independent recovery views.
    # Both cursor directions can coexist. Traverse each pending cursor once.
    for path, base_params in (
        ('stream_comments/', {'can_support_threading': 'true', 'sort_order': 'popular',
                              'inventory_source': 'explore_story', 'analytics_module': 'comments_v2_feed_timeline',
                              'is_carousel_bumped_post': 'false', 'feed_position': '1'}),
        ('comments/', {'can_support_threading': 'false', 'permalink_enabled': 'false'}),
    ):
        queue = [{}]
        seen = set()
        try:
            while queue:
                cursor_params = queue.pop(0)
                chunks = await fetch(path, {**base_params, **cursor_params})
                for data in chunks:
                    consume(data)
                    for cursor_key, param in (('next_min_id', 'min_id'), ('next_max_id', 'max_id')):
                        cursor = data.get(cursor_key)
                        if cursor and (param, str(cursor)) not in seen:
                            seen.add((param, str(cursor)))
                            queue.append({param: cursor})
            diagnostics.append(dict(source=path, status=200))
        except Exception as error:
            diagnostics.append(dict(source=path, status=getattr(error, 'status', 502)))
            if getattr(error, 'status', None) in (401, 403, 429):
                stopped_status = error.status
                break

    # Current public doc_id connection (instagrapi CommentMixin), rather than
    # relying solely on the legacy query_hash used by the main scanner.
    if totals and len(set(known_ids) | set(records)) < max(totals) and not stopped_status:
        seen = set()
        cursor = None
        try:
            while True:
                variables = dict(after=cursor, before=None, first=50, last=None,
                                 media_id=str(media_id).split('_')[0], sort_order='popular')
                chunks = await fetch('', {'doc_id': '6974885689225067',
                    'variables': json.dumps(variables), 'server_timestamps': 'true'}, graphql=True)
                data = chunks[-1].get('data')
                if not isinstance(data, dict):
                    raise ValueError('Missing GraphQL data')
                connection = next((value for key, value in data.items()
                                   if 'comments' in key and isinstance(value, dict)), None)
                if not connection or not isinstance(connection.get('edges'), list):
                    raise ValueError('Missing GraphQL comment connection')
                add([edge.get('node') for edge in connection['edges'] if isinstance(edge, dict)])
                page = connection.get('page_info') or {}
                if page.get('has_next_page') is False:
                    break
                cursor = page.get('end_cursor')
                if not cursor or str(cursor) in seen:
                    break
                seen.add(str(cursor))
            diagnostics.append(dict(source='web_doc_id', status=200))
        except Exception as error:
            diagnostics.append(dict(source='web_doc_id', status=getattr(error, 'status', 502)))
            if getattr(error, 'status', None) in (401, 403, 429):
                stopped_status = error.status

    # Retrieve actual replies, never infer authors from a child counter.
    for cid, (expected, children) in list(parents.items()):
        if stopped_status:
            break
        if len(children) >= expected:
            continue
        params = {}
        seen = set()
        try:
            while len(children) < expected:
                chunks = await fetch(f'comments/{cid}/inline_child_comments/', params)
                data = chunks[-1]
                for chunk in chunks:
                    children.update(add(chunk.get('child_comments', [])))
                cursor = data.get('next_min_child_cursor') or data.get('next_max_child_cursor')
                if not cursor or str(cursor) in seen:
                    break
                seen.add(str(cursor))
                params = {'min_id' if data.get('next_min_child_cursor') else 'max_id': cursor}
        except Exception as error:
            diagnostics.append(dict(source='replies', status=getattr(error, 'status', 502)))
            if getattr(error, 'status', None) in (401, 403, 429):
                stopped_status = error.status
                break
    logger.info('COMMENT_SOURCES records=%s new=%s sources=%s', len(records),
                len(set(records) - set(known_ids)), diagnostics)
    return dict(comments=list(records.values()), comment_ids=list(records), sources=diagnostics,
                reported_max_comment_count=max(totals) if totals else None, stopped_status=stopped_status)
