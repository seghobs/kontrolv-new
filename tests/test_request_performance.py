import unittest
from unittest.mock import patch, AsyncMock
from app_core import jobs, storage
from app_core.nlp_scorer import calculate_comment_spam_score
from app_core.routes import main
import test_jobs

class RequestPerformanceTests(unittest.TestCase):
    setUp = test_jobs.JobTests.setUp

    def test_status_reads_once_without_decoding_comment_payload(self):
        from app_core import create_app
        identifier = jobs.enqueue('manual', {})
        with jobs.transaction() as conn:
            conn.execute('UPDATE jobs SET result=? WHERE id=?', ('not-json-' + 'x'*100000, identifier))
        with patch('app_core.init_storage'): app = create_app()
        with patch.object(storage, '_connect', wraps=storage._connect) as connect:
            response = app.test_client().get('/api/task_status/' + identifier)
        self.assertEqual(response.json['status'], 'running')
        self.assertTrue(response.json['execute_in_request'])
        self.assertEqual(connect.call_count, 1)

    def test_shared_connection_preserves_history_scores_and_records(self):
        records = [('g','alice','a','renkler harika bir uyum yakalamış',1),
                   ('g','alice','b','renkler harika bir uyum yakalamış',1),
                   ('g','bob','c','iyi',0)]
        expected = []
        for group,user,post,text,valid in records:
            score = calculate_comment_spam_score(user,text)
            expected.append(score)
            storage.save_comment_log(group,user,post,text,score,valid)
        with jobs.transaction() as conn: conn.execute('DELETE FROM comment_history')
        with patch.object(storage, '_connect', wraps=storage._connect) as connect:
            storage.score_and_save_comment_logs(records)
        self.assertEqual(connect.call_count,1)
        with jobs.transaction() as conn:
            rows=conn.execute('SELECT post_code,spam_score FROM comment_history ORDER BY post_code').fetchall()
        self.assertEqual([r['spam_score'] for r in rows],expected)
        self.assertEqual(len(rows),len(records))

    def test_multiple_posts_load_shared_inputs_once(self):
        with patch.object(main,'get_working_active_token',return_value={'token':'test'}) as token, \
             patch.object(main,'load_exemptions',return_value={}) as exemptions, \
             patch.object(main,'get_global_exempted_users',return_value=set()) as globals_, \
             patch.object(main,'add_audit_log'), \
             patch('app_core.instagram_api.get_post_details_async',new=AsyncMock(return_value={})), \
             patch('app_core.instagram_api.fetch_comment_usernames_async',new=AsyncMock(return_value={'ok':True,'comments':[('alice','merhaba dünya')]})), \
             patch('asyncio.sleep',new=AsyncMock()):
            result=main.run_manual_control('https://www.instagram.com/p/ABC/\nhttps://www.instagram.com/p/DEF/','alice bob','',[],False)
        self.assertEqual(len(result['links']),2)
        for post in result['links']: self.assertEqual(post['eksikler'],['bob'])
        token.assert_called_once(); exemptions.assert_called_once(); globals_.assert_called_once()
