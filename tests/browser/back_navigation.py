import os
from playwright.sync_api import sync_playwright
BASE=os.environ.get('TEST_BASE_URL','http://127.0.0.1:5087')
JOB=os.environ.get('TEST_RESULT_ID','a'*32)
with sync_playwright() as p:
 browser=p.chromium.launch(channel='chrome',headless=True)
 for mode in ['completed','running','failed','cancelled']:
  page=browser.new_page(viewport={'width':390,'height':844});errors=[];calls=[]
  page.on('pageerror',lambda e:errors.append(str(e)))
  def intercept(route):
   req=route.request
   if '/api/task_status/' in req.url:
    calls.append('status');route.fulfill(json={'status':mode,'execute_in_request':mode=='running'})
   elif '/api/task_run/' in req.url:
    calls.append('run');route.fulfill(json={'status':'completed'})
   elif req.method=='POST' and req.url.rstrip('/')==BASE.rstrip('/'):
    calls.append('submit');route.fulfill(json={'success':True,'job_id':JOB})
   else:route.continue_()
  page.route('**/*',intercept)
  def submit():
   page.locator('#post_link_single').fill('https://www.instagram.com/p/ABC/')
   if not page.locator('.home-member-editor').evaluate('e=>e.open'):page.locator('.home-member-editor>summary').click()
   page.locator('#tagAddInput').fill('alice');page.locator('#tagAddInput').press('Enter')
   page.locator('#submitCheckBtn').click();page.locator('.scope-start').click()
   page.wait_for_url('**/result/'+JOB)
  page.goto(BASE+'/');submit()
  count=len(calls);page.go_back();page.wait_for_timeout(1200)
  assert page.url.rstrip('/')==BASE.rstrip('/'),page.url
  assert len(calls)==count,'Back restarted completed task'
  assert 'Kontrol ediliyor' not in page.locator('#submitCheckBtn').inner_text()
  page.reload();page.wait_for_timeout(300);assert len(calls)==count
  submit();assert calls.count('submit')==2
  assert not errors,errors
  page.close()
 # A pending bookmarked/reloaded task must still resume, then leave a clean form.
 page=browser.new_page();pending_calls=[]
 def pending(route):
  pending_calls.append(1);route.fulfill(json={'status':'running' if len(pending_calls)==1 else 'completed'})
 page.route('**/api/task_status/*',pending)
 page.goto(BASE+'/?task='+JOB+'&navigation_test=1');page.wait_for_url('**/result/'+JOB)
 page.go_back();page.wait_for_timeout(500)
 assert page.url==BASE+'/?navigation_test=1',page.url
 browser.close()
print('Back/reload/new submission passed for completed, executed, failed and cancelled jobs; pending task resume preserved. All task writes intercepted; no real audit or DM sent.')
