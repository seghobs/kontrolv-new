"""Display nearby sender messages verbatim, without interpreting audit rules."""
import json
import re
from datetime import datetime
from zoneinfo import ZoneInfo

WINDOW_US = 30 * 60 * 1000000
STORIES = {'reel_share', 'story_share', 'story_reply', 'xma_story_share'}

def post_codes(message):
    if message.get('item_type') in STORIES:
        return set()
    codes = set()
    def visit(value):
        if isinstance(value, dict):
            code = value.get('code')
            if isinstance(code, str) and re.fullmatch(r'[\w-]+', code): codes.add(code)
            for key, child in value.items():
                if key not in ('replied_to_message', 'user', 'reactions'): visit(child)
        elif isinstance(value, list):
            for child in value: visit(child)
        elif isinstance(value, str):
            codes.update(re.findall(r'https?://(?:www\.)?instagram\.com/(?:p|reels?|tv)/([\w-]+)', value))
    visit(message)
    return codes

def nearby_notes(messages, users, min_ts, max_ts):
    unique = {}
    for m in messages:
        if isinstance(m, dict) and m.get('item_id') and m.get('user_id') and isinstance(m.get('timestamp'), (int, float)):
            unique[str(m['item_id'])] = m
    shares = []
    for m in unique.values():
        codes = post_codes(m)
        if codes: shares.append((m, codes))
    result = {}
    for m in unique.values():
        text = m.get('text')
        if m.get('item_type') != 'text' or not isinstance(text, str) or not text.strip(): continue
        candidates = [(s, codes) for s, codes in shares if str(s['user_id']) == str(m['user_id']) and s['item_id'] != m['item_id'] and abs(s['timestamp']-m['timestamp']) <= WINDOW_US]
        reply = (m.get('replied_to_message') or {}).get('item_id') if isinstance(m.get('replied_to_message'), dict) else None
        if reply:
            candidates = [(s,codes) for s,codes in candidates if str(s['item_id']) == str(reply)]
        if not candidates: continue
        distance = min(abs(s['timestamp']-m['timestamp']) for s,codes in candidates)
        nearest = [(s,codes) for s,codes in candidates if abs(s['timestamp']-m['timestamp']) == distance]
        for s,codes in nearest:
            if not min_ts <= s['timestamp'] <= max_ts: continue
            note = dict(id=str(m['item_id']), sender_id=str(m['user_id']), username=users.get(str(m['user_id']), ''), text=text,
                        time=datetime.fromtimestamp(m['timestamp']/1e6, ZoneInfo('Europe/Istanbul')).strftime('%d.%m.%Y %H:%M'),
                        timestamp=m['timestamp'], shared_at=s['timestamp'], ambiguous=len(nearest)>1)
            for code in codes:
                bucket=result.setdefault(code, [])
                if not any(n['id']==note['id'] for n in bucket):bucket.append(note)
    for notes in result.values(): notes.sort(key=lambda n:n['timestamp'])
    return result

def cache_notes(thread_id, posts, notes, day):
    from app_core.followup import read, write
    key='nearby-notes:'+str(thread_id)
    saved=read(key,{})
    for post in posts:
        code=post.get('code')
        if code: saved.setdefault(code,{})[day]=notes.get(code,[])
    write(key,saved)

def attach_notes(thread_id, posts):
    from app_core.followup import read
    saved=read('nearby-notes:'+str(thread_id),{}) if thread_id else {}
    for post in posts or []:
        codes=post_codes({'text':post.get('post_link','')})
        notes={}
        for code in codes:
            for rows in saved.get(code,{}).values():
                for note in rows: notes[note['id']]=note
        post['nearby_notes']=sorted(notes.values(),key=lambda n:n['timestamp'])
