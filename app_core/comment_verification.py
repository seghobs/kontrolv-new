"""Complete comment verification, retaining comment identities and child replies."""
import json
import logging
logger = logging.getLogger(__name__)
import aiohttp
from app_core import instagram_api as api
from app_core.validators import is_valid_username


async def fetch_complete_comments(media_id, token_record, session, orders=('recent', 'popular')):
    records = {}
    parents = {}
    complete = True
    failure_status = 200
    order_ids = {}
    reported_totals = set()
    totals_valid = True
    active_ids = None
    username = api._get_username(token_record)
    async def fetch(path, params):
        token = api.current_token(username, token_record.get('token', ''))
        headers = api.build_auth_headers(token, token_record.get('user_agent', ''), token_record.get('android_id_yeni', ''), token_record.get('device_id', ''), username=username)
        headers['Accept-Encoding'] = 'gzip, deflate'
        url = 'https://i.instagram.com/api/v1/media/'+str(media_id)+'/'+path
        headers, revision = api.prepare_async_headers(username, url, headers)
        async with session.get(url, params=params, headers=headers, proxy=api.get_outbound_proxy(), timeout=aiohttp.ClientTimeout(total=10)) as response:
            from app_core.session_state import update_session, response_cookies
            update_session(username, response.headers, expected_token=headers.get('authorization'), cookies=response_cookies(response), expected_revision=revision)
            if response.status != 200:
                error=ValueError('Comment request failed: HTTP '+str(response.status))
                error.status=response.status
                raise error
            data = json.loads(await response.text())
            if not isinstance(data, dict) or data.get('status') == 'fail':
                raise ValueError('Invalid comment response')
            return data

    def add(items):
        nonlocal complete
        if not isinstance(items, list):
            complete = False
            return set()
        ids = set()
        for item in items:
            if not isinstance(item, dict):
                complete = False
                continue
            cid = item.get('pk') or item.get('id')
            user = item.get('user') or {}
            name = user.get('username') if isinstance(user, dict) else None
            if not cid or not isinstance(name, str) or not is_valid_username(name):
                complete = False
                continue
            cid = str(cid);ids.add(cid)
            if active_ids is not None: active_ids.add(cid)
            records[cid] = (name, item.get('text') if isinstance(item.get('text'), str) else '')
            children = add(item.get('preview_child_comments', []))
            expected = item.get('child_comment_count', 0)
            if type(expected) is int and expected > len(children):
                previous_expected, previous_children = parents.get(cid, (0, set()))
                parents[cid] = (max(expected, previous_expected), previous_children | children)
        return ids

    for order in orders:
        active_ids = set()
        order_ids[order] = active_ids
        try:
            params = {'can_support_threading': 'true', 'sort_order': order}
            cursors = set()
            for _ in range(api.MAX_COMMENT_PAGES):
                data = await fetch('comments/', params)
                if (data.get('sort_order') != order or data.get('geoblocked_comment_notices')
                        or data.get('comment_filter_param') not in (None, '', 'no_filter')):
                    totals_valid = False
                total = data.get('comment_count')
                if type(total) is int and total >= 0: reported_totals.add(total)
                else: totals_valid = False
                add(data.get('comments'))
                cursor = data.get('next_min_id') or data.get('next_max_id')
                if not cursor:
                    if data.get('has_more_comments') or data.get('has_more_headload_comments'): complete = False
                    break
                key = 'min_id' if data.get('next_min_id') else 'max_id'
                if (key, str(cursor)) in cursors:
                    complete = False;break
                cursors.add((key, str(cursor)));params = {'can_support_threading':'true','sort_order':order,key:cursor}
            else: complete = False
        except Exception as error:
            logger.warning('Comment sort %s failed: %s', order, type(error).__name__)
            complete = False
            failure_status = getattr(error, 'status', 502)
            if failure_status in (401,403,429): break
    active_ids = None
    try:
        for cid, (expected, children) in ([] if failure_status in (401,403,429) else list(parents.items())):
            if len(children) >= expected: continue
            params = {};cursors = set()
            for _ in range(api.MAX_COMMENT_PAGES):
                data = await fetch('comments/'+cid+'/inline_child_comments/', params)
                children.update(add(data.get('child_comments')))
                cursor = data.get('next_min_child_cursor') or data.get('next_max_child_cursor')
                if len(children) >= expected: break
                if not cursor or str(cursor) in cursors: break
                cursors.add(str(cursor))
                params = {'min_id' if data.get('next_min_child_cursor') else 'max_id': cursor}
            if len(children) < expected: complete = False
    except Exception as error:
        logger.warning('Full comment endpoint failed: %s', type(error).__name__)
        complete = False
    list_count = next(iter(reported_totals)) if len(reported_totals) == 1 else None
    list_verified = bool(complete and totals_valid and {'recent','popular'} <= set(order_ids)
                         and type(list_count) is int and len(records) == list_count
                         and all(ids == set(records) for ids in order_ids.values()))
    return dict(ok=complete, status=200 if complete else failure_status, incomplete=not complete,
                comments=list(records.values()), comment_ids=list(records), scanned_orders=list(orders),
                list_count_verified=list_verified, list_comment_count=list_count if list_verified else None)


async def recover_comment_list(media_id, token, session, details, response):
    """Recover a partial stream through the full comment and reply endpoint."""
    details = api.reconcile_comment_total(details, response)
    comments = response.get('comments', []) if isinstance(response, dict) else response
    if isinstance(response, dict) and response.get('status') not in (None, 200):
        return details, response
    if isinstance(response, dict) and not response.get('incomplete') and api.comments_cover_total(details, comments):
        return details, response
    verified = await fetch_complete_comments(media_id, token, session)
    logger.info('COMMENT_RECOVERY expected=%s stream=%s recovered=%s complete=%s',details.get('comment_count'),len(comments),len(verified.get('comments',[])),verified.get('ok'))
    if verified.get('ok'):
        refreshed = await api.get_post_details_async(media_id, token, session)
        if refreshed and refreshed.get('comment_count_verified'):
            details = refreshed
        details = api.reconcile_comment_total(details, verified)
        if len(verified.get('comments',[])) >= len(comments):
            response = verified
        if not api.comments_cover_total(details, response.get('comments', [])):
            retry = await api.fetch_comment_usernames_async(media_id, token, session)
            if retry.get('ok') and not retry.get('incomplete') and api.comments_cover_total(details, retry.get('comments', [])):
                response = retry
            logger.info('COMMENT_RECOVERY retry=%s complete=%s',len(retry.get('comments',[])),api.comments_cover_total(details,response.get('comments',[])))
    return details, response


def recover_comment_list_sync(media_id, token, details, response):
    import asyncio
    async def run():
        async with aiohttp.ClientSession() as session:
            return await recover_comment_list(media_id, token, session, details, response)
    return asyncio.run(run())


def fetch_complete_comments_sync(media_id, token):
    import asyncio
    async def run():
        async with aiohttp.ClientSession() as session:
            return await fetch_complete_comments(media_id, token, session)
    return asyncio.run(run())
