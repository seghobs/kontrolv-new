"""Complete comment verification, retaining comment identities and child replies."""
import json
import logging
logger = logging.getLogger(__name__)
import aiohttp
from app_core import instagram_api as api
from app_core.validators import is_valid_username


async def fetch_complete_comments(media_id, token_record, session):
    records = {}
    parents = {}
    complete = True
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
                raise ValueError('Comment request failed: HTTP '+str(response.status))
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
            records[cid] = (name, item.get('text') if isinstance(item.get('text'), str) else '')
            children = add(item.get('preview_child_comments', []))
            expected = item.get('child_comment_count', 0)
            if type(expected) is int and expected > len(children):
                parents[cid] = (expected, children)
        return ids

    try:
        params = {'can_support_threading': 'true', 'sort_order': 'recent'}
        cursors = set()
        for _ in range(api.MAX_COMMENT_PAGES):
            data = await fetch('comments/', params)
            add(data.get('comments'))
            cursor = data.get('next_min_id') or data.get('next_max_id')
            if not cursor:
                if data.get('has_more_comments') or data.get('has_more_headload_comments'): complete = False
                break
            key = 'min_id' if data.get('next_min_id') else 'max_id'
            if (key, str(cursor)) in cursors:
                complete = False;break
            cursors.add((key, str(cursor)));params = {'can_support_threading':'true','sort_order':'recent',key:cursor}
        else: complete = False
        for cid, (expected, children) in list(parents.items()):
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
    return dict(ok=complete, incomplete=not complete, comments=list(records.values()), comment_ids=list(records))


async def recover_comment_list(media_id, token, session, details, response):
    """Recover a partial stream through the full comment and reply endpoint."""
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
