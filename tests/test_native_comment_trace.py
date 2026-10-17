"""Regressions from the real native Android traffic, with identifying data removed."""
import json
import unittest
from pathlib import Path
from app_core.instagram_api import parse_comment_page

class NativeCommentTraceTests(unittest.TestCase):
    def test_all_stream_chunks_are_retained_and_caption_is_excluded(self):
        fixture=json.loads((Path(__file__).parent/'fixtures/native_comment_stream.json').read_text(encoding='utf-8'))
        records=set();sizes=[]
        for chunks in fixture['requests']:
            last,comments,incomplete=parse_comment_page('\n'.join(json.dumps(chunk) for chunk in chunks))
            self.assertFalse(incomplete)
            self.assertEqual(last['comment_count'],25)
            sizes.append(len(comments));records.update(comments)
        self.assertEqual(sizes,[14,10,0])
        self.assertEqual(len(records),24)
        self.assertNotIn('owner',{user for user,_ in records})
        self.assertIs(last['has_more_comments'],False)
        self.assertIs(last['has_more_headload_comments'],False)
