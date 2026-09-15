"""Multi-mode saved reports. Existing report snapshots are never mutated."""
from copy import deepcopy
from app_core import jobs
from app_core.followup import link_key, read, write


def reports(data):
    if data.get('dual_check'):
        return {'comments': data['comment_report'], 'likes': data['like_report']}
    return {'likes' if data.get('check_likes') else 'comments': data}


def combine(parts, scope):
    first = parts.get('comments', parts.get('likes', {}))
    result = {**first, 'report_scope': scope}
    if len(parts) == 2:
        result.update(dual_check=True, comment_report=parts['comments'], like_report=parts['likes'])
    return result


def merge_report(previous, fresh):
    result = deepcopy(previous)
    existing = {link_key(p['post_link']) for p in result.get('links', [])}
    result.setdefault('links', []).extend(deepcopy(p) for p in fresh.get('links', []) if link_key(p['post_link']) not in existing)
    missing = {}; texts = {}; present = set(); blocked = set()
    for post in result['links']:
        for user in post.get('eksikler') or []:
            missing.setdefault(user, []).append(post['post_link'])
        present.update(post.get('commenters') or [])
        blocked.update(post.get('unknown_members') or [])
        for comment in post.get('comments_list') or []:
            if isinstance(comment, dict) and comment.get('username') and isinstance(comment.get('text'), str):
                values = texts.setdefault(comment['username'].lower(), [])
                if comment['text'] not in values: values.append(comment['text'])
    result.update(user_missing_posts=missing, user_comments=texts,
                  all_commented=sorted(present - set(missing) - blocked) if not any(p.get('error') for p in result['links']) else [],
                  duplicate_comment_users=sorted(set(previous.get('duplicate_comment_users', [])) | set(fresh.get('duplicate_comment_users', []))),
                  invalid_comment_users=sorted(set(previous.get('invalid_comment_users', [])) | set(fresh.get('invalid_comment_users', []))))
    return result


def execute(payload, progress):
    from datetime import datetime
    from app_core.token_service import fetch_group_members_with_failover, fetch_group_media_with_failover
    from app_core.routes.main import run_manual_control
    tid = payload['thread_id']; operation = payload.get('_operation', 'start')
    source = jobs.get_job(payload.get('_source_id', '')) if payload.get('_source_id') else None
    if operation != 'start' and (not source or source['state'] != 'completed'):
        raise ValueError('Tamamlanmış kaynak rapor bulunamadı.')
    previous = reports(source['result']) if source else {}
    saved_dates = (source['result'].get('report_scope', {}).get('shared_dates') or {}) if source else {}
    modes = list(previous) if previous else (['comments', 'likes'] if payload.get('dual_check') else ['likes' if payload.get('check_likes') else 'comments'])
    scope = {key: payload.get(key) for key in ('date', 'thread_id', 'only_sharers', 'low_likes', 'preset_id')}
    if source:
        users = set(source['result'].get('group') or [])
    else:
        progress(0, 1, 'Güncel grup üyeleri alınıyor…')
        members = fetch_group_members_with_failover(tid)
        if not members.get('ok'): raise ValueError('Grup üyeleri alınamadı.')
        users = {m['username'] for m in members.get('members') or [] if isinstance(m, dict) and m.get('username')}
    if operation == 'refresh':
        posts = [{'url': p['post_link'], 'username': p.get('sender')} for p in next(iter(previous.values())).get('links', [])]
    else:
        progress(0, 1, 'Seçilen günün paylaşımları alınıyor…')
        media = fetch_group_media_with_failover(tid, datetime.strptime(payload['date'], '%Y-%m-%d'), complete=True)
        if not media.get('ok'): raise ValueError('Paylaşımlar alınamadı; önceki sonuçlar korunuyor.')
        posts = [p for p in media.get('posts') or [] if isinstance(p, dict) and p.get('url')]
        posts = list({link_key(p['url']): p for p in posts}.values())
        if payload.get('low_likes'):
            posts = [p for p in posts if type(p.get('like_count')) in (int, float) and 0 <= p['like_count'] <= 90]
        if not source and payload.get('only_sharers'): users &= {p.get('username') for p in posts}
        if source:
            known = {link_key(p['post_link']) for report in previous.values() for p in report.get('links', [])}
            posts = [p for p in posts if link_key(p['url']) not in known]
    if not users: raise ValueError('Kontrol edilecek üye bulunamadı.')
    if not posts:
        if source:
            result = deepcopy(source['result']); result['added_posts'] = 0
            return result
        raise ValueError('Bu gün ve filtreler için paylaşım bulunamadı.')
    saved_dates = {**saved_dates, **{link_key(p['url']): p['shared_at'] for p in posts if p.get('shared_at')}}
    scope['shared_dates'] = saved_dates
    parts = {}
    for index, mode in enumerate(modes):
        checkpoint_key = 'preset-phase:' + str(payload.get('_job_id', '')) + ':' + mode
        checkpoints = read(checkpoint_key, {}) if payload.get('_job_id') else {}
        if not checkpoints and payload.get('_retry_parent'):
            checkpoints = read('preset-phase:' + payload['_retry_parent'] + ':' + mode, {})
        def save(url, row):
            checkpoints[url] = row
            if payload.get('_job_id'): write(checkpoint_key, checkpoints)
        def mode_progress(current, total, message):
            progress(index * 100 + int(current / max(1, total) * 100), len(modes) * 100, ('Beğeni: ' if mode == 'likes' else 'Yorum: ') + message)
        kwargs = dict(progress_callback=mode_progress, shared_dates=saved_dates or None)
        if payload.get('_job_id'): kwargs.update(checkpoints=checkpoints, save_checkpoint=save)
        if operation == 'refresh': kwargs.update(prev_result=previous[mode], only_missing=bool(payload.get('only_missing')), unknown_only=bool(payload.get('unknown_only')))
        fresh = run_manual_control('\n'.join(p['url'] for p in posts), ' '.join(sorted(users)), tid,
            [p['url'] + '|' + p['username'] for p in posts if p.get('username')], mode == 'likes', **kwargs)
        parts[mode] = merge_report(previous[mode], fresh) if operation == 'extend' else fresh
    result = combine(parts, scope)
    if operation == 'extend': result['added_posts'] = len(posts)
    return result


def matrix(data):
    parts = reports(data)
    posts = {}; users = set(data.get('group') or [])
    for mode, report in parts.items():
        for post in report.get('links') or []:
            entry = posts.setdefault(link_key(post['post_link']), {**post, 'mode_times': {}})
            if post.get('checked_at'): entry['mode_times'][mode] = post['checked_at']
    lookup = {mode: {link_key(p['post_link']): p for p in report.get('links', [])} for mode, report in parts.items()}
    def status(post, user):
        if post is None: return 'unchecked'
        if user in (post.get('unknown_members') or []): return 'unknown'
        if user in (post.get('excluded_members') or []) or post.get('skipped_reason'): return 'excluded'
        if user in (post.get('commenters') or []): return 'present'
        if post.get('error') or user in (post.get('unknown_members') or []): return 'unknown'
        if user in (post.get('eksikler') or []): return 'missing'
        return 'unknown'
    return list(posts.values()), [dict(username=user, cells=[{mode: status(lookup.get(mode, {}).get(key), user) for mode in ('comments', 'likes')} for key in posts]) for user in sorted(users)]


def missing_text(report):
    lines = []
    for post in report.get('links') or []:
        if post.get('error') or post.get('skipped_reason'): continue
        missing = post.get('eksikler') or []
        if missing:
            lines.append(('@' + post['sender'] + ' · ' if post.get('sender') else '') + post['post_link'])
            lines.append(', '.join('@' + user for user in sorted(missing)))
            lines.append('')
    return '\n'.join(lines).strip() or 'Doğrulanmış eksik bulunmuyor.'


def enqueue_active(payload, parent_id, key):
    import json, time, uuid
    with jobs.transaction() as conn:
        row = conn.execute("SELECT id FROM jobs WHERE kind='preset' AND state IN ('queued','running','cancelling') AND json_extract(payload,'$._request_key')=?", (key,)).fetchone()
        if row: return row['id']
        identifier = uuid.uuid4().hex; now = time.time()
        conn.execute("INSERT INTO jobs(id,kind,payload,created,updated,available,parent_id,message) VALUES (?,?,?,?,?,?,?,?)",
            (identifier,'preset',json.dumps({**payload,'_request_key':key}),now,now,now,parent_id,'Denetim başlatılmaya hazır.'))
        return identifier
