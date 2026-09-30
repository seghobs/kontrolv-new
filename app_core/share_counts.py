"""Count chat share events by sender, not media owner or unique post."""
import re
from app_core.validators import normalize_username


def count_member_shares(messages, users, min_ts, max_ts, posts=()):
    kinds = {p.get('code'): ('reels' if p.get('media_type') in ('video','reel','reels',2) else 'post') for p in posts}
    result = {};seen = set()
    for msg in messages:
        if not isinstance(msg, dict) or not min_ts <= (msg.get('timestamp') or 0) <= max_ts: continue
        mid = msg.get('item_id') or msg.get('message_id')
        if not mid: continue
        if str(mid) in seen: continue
        seen.add(str(mid))
        uid = str(msg.get('user_id') or '')
        name = normalize_username(users.get(uid, ''))
        if not name: continue
        kind = msg.get('item_type')
        counts = []
        if kind in ('reel_share','story_share','xma_story_share'):
            counts = ['story']
        elif kind in ('xma_clip','clip'):
            counts = ['reels']
        elif kind in ('media_share','xma_media_share','text','link'):
            media = msg.get('media_share')
            if isinstance(media, dict):
                counts = ['reels' if media.get('product_type')=='clips' else kinds.get(media.get('code'),'post')]
            else:
                attachments = msg.get('xma_media_share') or []
                if isinstance(attachments, dict): attachments=[attachments]
                texts = [a.get('target_url','') for a in attachments if isinstance(a,dict)]
                if kind in ('text','link'):
                    texts += [msg.get('text') or '', (msg.get('link') or {}).get('text','')]
                links = set()
                for text in texts:
                    for typ,code in re.findall(r'instagram\.com/(p|reels?|tv|stories)/([\w.-]+)',text):
                        links.add((typ,code))
                counts = [('story' if typ=='stories' else 'reels' if typ in ('reel','reels','tv') else kinds.get(code,'post')) for typ,code in links]
        if counts:
            row=result.setdefault(name,dict(sender_id=uid,post=0,reels=0,story=0,total=0))
            for category in counts: row[category]+=1;row['total']+=1
    return result
