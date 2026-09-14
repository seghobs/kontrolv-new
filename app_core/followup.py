"""Report follow-up, dated group rules and additive local records."""
import json
import re
import time
from datetime import datetime, timezone
from app_core import storage, jobs
from app_core.validators import normalize_username


def read(key, default=None):
    conn = storage._connect()
    try:
        row = conn.execute('SELECT value FROM key_value WHERE key=?', (key,)).fetchone()
        return json.loads(row['value']) if row else default
    finally:
        conn.close()


def write(key, value):
    with jobs.transaction() as conn:
        conn.execute('INSERT INTO key_value(key,value) VALUES (?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value',
                     (key, json.dumps(value, ensure_ascii=False)))


def extract_links(text):
    found = re.findall(r'https?://(?:www\.)?instagram\.com/(?:p|reels?|tv)/([\w-]+)', str(text))
    return list(dict.fromkeys('https://www.instagram.com/p/' + code + '/' for code in found))


def link_key(url):
    links = extract_links(url)
    return links[0] if links else str(url).rstrip('/')


DEFAULT_RULES = dict(skip_owner=True, min_words=2, require_emoji=True, grace_hours=0,
                     mode='selected', joined={}, leave=[], excluded=[], exempt=[])


def rules_for(thread):
    return {**DEFAULT_RULES, **(read('rules:' + str(thread), {}) or {})}


def validate_rules(data):
    result = dict(DEFAULT_RULES)
    result['skip_owner'] = bool(data.get('skip_owner', True))
    result['require_emoji'] = bool(data.get('require_emoji', True))
    result['min_words'] = int(data.get('min_words', 2))
    result['grace_hours'] = float(data.get('grace_hours', 0))
    if not 0 <= result['min_words'] <= 100 or not 0 <= result['grace_hours'] <= 720:
        raise ValueError('Kelime sınırı 0–100, telafi süresi 0–720 saat olmalıdır.')
    result['mode'] = data.get('mode', 'selected')
    if result['mode'] not in ('selected','comments','likes'):
        raise ValueError('Kontrol türü geçersiz.')
    result['exempt'] = sorted({normalize_username(u) for u in data.get('exempt', []) if normalize_username(u)})
    result['excluded'] = extract_links('\n'.join(data.get('excluded', [])))
    result['joined'] = {}
    for user, date in data.get('joined', {}).items():
        datetime.strptime(date, '%Y-%m-%d')
        result['joined'][normalize_username(user)] = date
    result['leave'] = []
    for item in data.get('leave', []):
        start, end = item['start'], item['end']
        datetime.strptime(start, '%Y-%m-%d'); datetime.strptime(end, '%Y-%m-%d')
        if start > end: raise ValueError('İzin bitişi başlangıçtan önce olamaz.')
        result['leave'].append(dict(username=normalize_username(item['username']), start=start, end=end))
    return result


def eligibility(username, url, sender, shared_at, rules, now=None):
    """Return an exclusion reason. Missing date evidence is never guessed."""
    username = normalize_username(username)
    if link_key(url) in {link_key(u) for u in rules['excluded']}: return 'Paylaşım kapsam dışında'
    if username in rules['exempt']: return 'Grup muafiyeti'
    if rules['skip_owner'] and username == normalize_username(sender or ''): return 'Kendi paylaşımı'
    if not shared_at:
        if rules['grace_hours'] or username in rules['joined'] or any(i['username'] == username for i in rules['leave']):
            return 'Tarih doğrulanamadı; sorumluluk belirlenemedi'
        return None
    try:
        date = datetime.fromisoformat(str(shared_at).replace('Z', '+00:00'))
        if date.tzinfo is None:
            import pytz
            date = pytz.timezone('Europe/Istanbul').localize(date)
    except (ValueError, TypeError): return 'Tarih doğrulanamadı; sorumluluk belirlenemedi'
    import pytz
    day = date.astimezone(pytz.timezone('Europe/Istanbul')).date().isoformat()
    if rules['joined'].get(username, '') > day: return 'Gruba katılmadan önceki paylaşım'
    if any(i['username'] == username and i['start'] <= day <= i['end'] for i in rules['leave']): return 'İzinli olduğu tarih'
    if (now or time.time()) < date.timestamp() + rules['grace_hours'] * 3600: return 'Telafi süresi devam ediyor'
    return None


def apply_rules(result, thread, shared_dates=None):
    rules = rules_for(thread)
    group = result.get('group', [])
    missing = {}
    for post in result.get('links', []):
        reasons = {u: reason for u in group if (reason := eligibility(u, post['post_link'], post.get('sender'),
                   (shared_dates or {}).get(link_key(post['post_link'])) or post.get('shared_at'), rules))}
        post['excluded_members'] = reasons
        post['unknown_members'] = [u for u, reason in reasons.items() if reason.startswith('Tarih doğrulanamadı')]
        post['eksikler'] = [u for u in post.get('eksikler', []) if u not in reasons]
        post['commenters'] = [u for u in post.get('commenters', []) if u not in reasons]
        for u in post['eksikler']: missing.setdefault(u, []).append(post['post_link'])
    result['user_missing_posts'] = missing
    return result


def changes(before, after):
    old = {link_key(p['post_link']): p for p in before.get('links', [])}
    rows = []
    for post in after.get('links', []):
        previous = old.get(link_key(post['post_link']))
        if not previous or previous.get('error') or post.get('error') or post.get('source') == 'previous': continue
        def texts(p):
            users = {}
            for c in p.get('comments_list', []):
                if isinstance(c, dict) and c.get('username') and c.get('text'):
                    users.setdefault(c['username'], []).append(c['text'])
            return users
        first, second = texts(previous), texts(post)
        rows.append(dict(url=post['post_link'], resolved=sorted((set(previous.get('eksikler', []))-set(post.get('eksikler', []))) & set(post.get('commenters', []))),
                         new_missing=sorted(set(post.get('eksikler', []))-set(previous.get('eksikler', []))),
                         no_longer_visible=sorted(set(first)-set(second)),
                         changed=sorted(u for u in first.keys() & second.keys() if sorted(first[u]) != sorted(second[u]))))
    return rows


def member_history(username, days=7):
    username = normalize_username(username)
    conn = storage._connect()
    try:
        rows = conn.execute("SELECT id,created,result FROM jobs WHERE state='completed' AND created>=? ORDER BY created DESC", (time.time()-days*86400,)).fetchall()
        records = []
        seen = set()
        for row in rows:
            result = json.loads(row['result'] or '{}')
            identities=read('member-names:'+str(result.get('thread_id')), {})
            matches=[set(names) for names in identities.values() if username in names]
            aliases=matches[0] if len(matches)==1 else {username}
            member=next((u for u in result.get('group',[]) if u in aliases), username)
            for post in result.get('links', []):
                mode = 'Beğeni' if result.get('check_likes') else 'Yorum'
                key = (result.get('thread_id'), mode, link_key(post['post_link']))
                if key in seen or member not in result.get('group', []): continue
                seen.add(key)
                excluded = post.get('excluded_members', {}).get(member)
                state = 'Doğrulanamadı' if post.get('error') or member in post.get('unknown_members',[]) else ('Muaf' if excluded else ('Eksik' if member in post.get('eksikler', []) else ('Tamamlandı' if member in post.get('commenters', []) else 'Değerlendirilmedi')))
                records.append(dict(job=row['id'], url=post['post_link'], mode=mode, state=state, checked_at=post.get('checked_at'), reason=excluded))
        return records
    finally: conn.close()


def track_members(thread, members):
    current = {str(m.get('pk') or m.get('id') or m.get('username')): normalize_username(m.get('username', '')) for m in members if isinstance(m, dict) and m.get('username')}
    previous = read('members:' + str(thread))
    result = dict(added=[], removed=[], renamed=[], baseline=previous is None)
    if previous is not None:
        result.update(added=sorted(current[k] for k in current.keys()-previous.keys()), removed=sorted(previous[k] for k in previous.keys()-current.keys()),
                      renamed=[dict(before=previous[k], after=current[k]) for k in current.keys() & previous.keys() if previous[k] != current[k]])
    identities=read('member-names:'+str(thread), {})
    for identity, name in current.items():
        # Username-only IDs cannot prove a rename.
        if identity == name:continue
        names=set(identities.get(identity, []));names.add(name)
        if previous and identity in previous:names.add(previous[identity])
        identities[identity]=sorted(names)
    write('member-names:'+str(thread), identities)
    write('members:' + str(thread), current)
    write('member-diff:' + str(thread), result)
    return result
