"""Complete comment verification, retaining comment identities and child replies."""
import json
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
                raise ValueError('Comment request failed')
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
        params = {'can_support_threading': 'true'}
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
            cursors.add((key, str(cursor)));params = {key: cursor}
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
    except Exception:
        complete = False
    return dict(ok=complete, incomplete=not complete, comments=list(records.values()), comment_ids=list(records))
