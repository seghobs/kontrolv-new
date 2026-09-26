import unittest
from datetime import datetime, timedelta
from unittest.mock import patch
import test_jobs
from app_core import create_app, storage
from app_core.followup import read, write
from app_core.save_control import prepare, window, screenshot_urls, summary, validate_answer, result_overview, TZ

GROUP = '340282366841710301281157258447286771667'


def fixture():
    posts, items = [], []
    for code, uid in [('ABC','1'),('DEF','2')]:
        at = datetime(2026,9,25,12,tzinfo=TZ)
        posts.append(dict(code=code, shared_at=at.isoformat(), url='https://www.instagram.com/p/'+code+'/', thumbnail_url='https://x.fbcdn.net/'+code, username=uid, media_type='image'))
        items.append(dict(item_id=code,item_type='xma_media_share',user_id=uid,timestamp=at.timestamp()*1e6,xma_media_share={'code':code}))
    for hour, minute, day, identifier in [(23,0,25,'early'),(17,59,26,'late'),(18,0,26,'boundary'),(18,1,26,'outside')]:
        at=datetime(2026,9,day,hour,minute,tzinfo=TZ)
        items.append(dict(item_id=identifier,item_type='generic_xma',user_id='1',timestamp=at.timestamp()*1e6,generic_xma=[dict(preview_url='https://x.fbcdn.net/'+identifier+'a'),dict(preview_url='https://x.fbcdn.net/'+identifier+'b')]))
    return prepare(GROUP,'Group','2026-09-25',posts,items,{'1':'alice','2':'bob'})


class SaveControlTests(unittest.TestCase):
    setUp=test_jobs.JobTests.setUp

    def client(self):
        with patch('app_core.init_storage'):
            return create_app().test_client()

    def test_group_default_override_and_name_change(self):
        c=self.client(); url='/api/group_control_preferences/'+GROUP
        self.assertEqual(c.get(url).json['control_mode'],'saves')
        c.post(url,json=dict(only_sharers=False,low_likes=False,control_mode='likes'))
        storage.cache_group_names([{'id':GROUP,'name':'Renamed'}])
        self.assertEqual(c.get(url).json['control_mode'],'likes')
        c.post(url,json=dict(only_sharers=False,low_likes=False,control_mode='saves'))
        c.post(url,json=dict(only_sharers=True,low_likes=False))
        self.assertEqual(self.client().get(url).json['control_mode'],'saves')

    def test_saves_submit_without_link_never_enqueues_comments(self):
        with patch('app_core.jobs.enqueue') as enqueue:
            r=self.client().post('/',data=dict(control_mode='saves',thread_id=GROUP))
        self.assertEqual(r.status_code,303)
        self.assertIn('/save-control?',r.location)
        enqueue.assert_not_called()

    def test_deadline_and_multiple_images_own_id_excluded(self):
        run=fixture()
        self.assertEqual(len(run['evidence']),6)
        self.assertEqual(len(run['tasks']),6)
        self.assertTrue(all(t['refs']==['P002'] for t in run['tasks']))
        self.assertNotIn('outside',str(run['evidence']))
        self.assertEqual(window('2026-09-25')[2].isoformat(),'2026-09-26T18:00:00+03:00')

    def test_multi_images_union_and_review(self):
        run=fixture()
        run['answers']['0']={'is_collection':True,'results':[dict(id='P002',status='not_visible')]}
        run['answers']['1']={'is_collection':True,'results':[dict(id='P002',status='matched',row=1,column=2)]}
        rows=summary(run)
        self.assertEqual(rows[0]['findings'][0]['state'],'candidate')
        self.assertEqual(rows[1]['findings'][0]['hits'],[])
        run['reviews']['1:P002']='confirmed'
        self.assertEqual(summary(run)[0]['findings'][0]['state'],'confirmed')

    def test_evidence_starts_at_twenty_inclusive(self):
        posts=[dict(code='ABC',shared_at='2026-09-25T12:00:00+03:00',url='https://www.instagram.com/p/ABC/',thumbnail_url='https://x.fbcdn.net/ABC',media_type='image')]
        items=[dict(item_id='post',item_type='xma_media_share',user_id='1',timestamp=datetime(2026,9,25,12,tzinfo=TZ).timestamp()*1e6,code='ABC')]
        for hour in [19,20,21]:
            items.append(dict(item_id=str(hour),item_type='generic_xma',user_id='2',timestamp=datetime(2026,9,25,hour,tzinfo=TZ).timestamp()*1e6,generic_xma=[dict(preview_url='https://x.fbcdn.net/'+str(hour))]))
        run=prepare(GROUP,'Group','2026-09-25',posts,items,{'1':'alice','2':'bob'})
        self.assertEqual([e['id'] for e in run['evidence']],['20-0','21-0'])
        self.assertEqual([e['id'] for e in run['skipped']],['19-0'])
        self.assertEqual(run['evidence_start'],'2026-09-25T20:00:00+03:00')

    def test_window_rolls_to_next_calendar_day(self):
        for day, following in [('2026-09-30','2026-10-01'),('2026-12-31','2027-01-01')]:
            _, close, end = window(day)
            self.assertEqual(close.isoformat(),day+'T22:30:00+03:00')
            self.assertEqual(end.isoformat(),following+'T18:00:00+03:00')

    def test_evidence_boundaries_to_the_second(self):
        posts=[dict(code='ABC',shared_at='2026-09-25T12:00:00+03:00',url='https://www.instagram.com/p/ABC/',thumbnail_url='https://x.fbcdn.net/ABC',media_type='image')]
        items=[dict(item_id='post',item_type='xma_media_share',user_id='1',timestamp=datetime(2026,9,25,12,tzinfo=TZ).timestamp()*1e6,code='ABC')]
        start, _, end=window('2026-09-25')
        evidence_start=start.replace(hour=20)
        for label, at in [('before',evidence_start-timedelta(seconds=1)),('start',evidence_start),('end',end),('after',end+timedelta(seconds=1))]:
            items.append(dict(item_id=label,item_type='generic_xma',user_id='2',timestamp=at.timestamp()*1e6,generic_xma=[dict(preview_url='https://x.fbcdn.net/'+label)]))
        run=prepare(GROUP,'Group','2026-09-25',posts,items,{'1':'alice','2':'bob'})
        self.assertEqual([e['id'] for e in run['evidence']],['start-0','end-0'])

    def test_null_media_and_non_collection(self):
        self.assertEqual(screenshot_urls({'item_type':'media','media':None}),[])
        run=fixture();run['answers']['0']={'is_collection':False,'results':[dict(id='P002',status='matched',row=1,column=1)]}
        self.assertNotEqual(summary(run)[0]['findings'][0]['state'],'candidate')

    def test_completed_report_shows_results_above_waiting_members(self):
        run=fixture()
        run['answers']['0']={'is_collection':True,'results':[dict(id='P002',status='matched',row=1,column=1)]}
        members=summary(run)
        overview=result_overview(members)
        self.assertEqual(overview,dict(all_visible=1,no_evidence=1,not_visible=0,review=0))
        write('save-run:'+run['id'],run)
        response=self.client().get('/save-control/'+run['id'])
        self.assertEqual(response.status_code,200)
        text=response.get_data(as_text=True)
        self.assertLess(text.index('id="saveResults"'),text.index('id="saveAnalyze"'))
        self.assertIn('1/1 paylaşım görünür',text)

    def test_overview_never_counts_unknown_as_missing(self):
        run=fixture()
        run['answers']['0']={'is_collection':True,'results':[dict(id='P002',status='uncertain')]}
        overview=result_overview(summary(run))
        self.assertEqual(overview['not_visible'],0)
        self.assertEqual(overview['review'],1)
        self.assertEqual(overview['all_visible'],0)

    def test_invalid_model_answers_rejected(self):
        for result in [{},dict(is_collection=True,results=[]),dict(is_collection=True,results=[dict(id='wrong',status='matched')]),dict(is_collection=True,results=[dict(id='P001',status='matched',row=None,column=None)])]:
            with self.assertRaises(ValueError):validate_answer(result,['P001'])

    def test_error_does_not_create_missing_or_drop_results(self):
        run=fixture();write('save-run:'+run['id'],run)
        with patch('app_core.save_control.compare',side_effect=RuntimeError('failure')):
            response=self.client().post('/api/save-control/'+run['id']+'/step')
        self.assertEqual(response.status_code,503)
        saved=read('save-run:'+run['id'])
        self.assertEqual(saved['answers'],{})
        self.assertEqual(saved['lease'],0)
        self.assertTrue(saved['error'])

    def test_step_resume_and_lease(self):
        run=fixture();run['tasks']=run['tasks'][:1];write('save-run:'+run['id'],run)
        answer=dict(is_collection=True,results=[dict(id='P002',status='matched',row=1,column=1)])
        with patch('app_core.save_control.compare',return_value=answer) as compare:
            c=self.client();url='/api/save-control/'+run['id']+'/step'
            self.assertTrue(c.post(url).json['done'])
            self.assertTrue(c.post(url).json['done'])
            self.assertEqual(compare.call_count,1)

    def test_report_and_review_own_post_prohibited(self):
        run=fixture();write('save-run:'+run['id'],run);c=self.client()
        self.assertEqual(c.get('/save-control/'+run['id']).status_code,200)
        url='/api/save-control/'+run['id']+'/review'
        self.assertEqual(c.post(url,json=dict(member='1',ref='P001',state='confirmed')).status_code,400)
        self.assertEqual(c.post(url,json=dict(member='1',ref='P002',state='confirmed')).status_code,200)

    def test_invalid_date_missing_key_and_collect_failure(self):
        c=self.client()
        with patch('app_core.save_control.api_key',side_effect=ValueError('No key')):
            self.assertEqual(c.post('/api/save-control',json=dict(group=GROUP,day='2026-09-25')).status_code,400)
        with patch('app_core.save_control.api_key',return_value='test'),patch('app_core.save_control.collect',return_value=fixture()):
            r=c.post('/api/save-control',json=dict(group=GROUP,day='2026-09-25'))
        self.assertEqual(r.status_code,200)
        self.assertEqual(c.get(r.json['url']).status_code,200)


if __name__=='__main__':unittest.main()
