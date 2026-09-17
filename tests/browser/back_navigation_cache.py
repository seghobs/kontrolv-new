"""Exercise an actual warm HTTP cache; Playwright routing is deliberately not used."""
import hashlib,json,threading
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
from playwright.sync_api import sync_playwright
poll=Path('static/js/result_polling.js').read_text()
old=poll.replace(', onFinished)', ')').replace('                if (onFinished) onFinished();\n','').replace('                        if (onFinished) onFinished();\n','')
control=Path('static/js/control_submit.js').read_text()
version=hashlib.sha256(poll.encode()).hexdigest()[:16]
phase='warm';asset_requests=[]
class Handler(BaseHTTPRequestHandler):
 def log_message(self,*args):pass
 def send(self,body,kind='text/html',cache='no-store'):
  body=body.encode();self.send_response(200);self.send_header('Content-Type',kind);self.send_header('Content-Length',str(len(body)));self.send_header('Cache-Control',cache);self.end_headers();self.wfile.write(body)
 def do_GET(self):
  if self.path.startswith('/static/js/result_polling.js'):
   asset_requests.append(self.path);self.send(old if phase=='warm' else poll,'text/javascript','public, max-age=3600');return
  if self.path.startswith('/static/js/control_submit.js'):self.send(control,'text/javascript');return
  if self.path.startswith('/api/task_status/'):self.send(json.dumps({'status':'completed'}),'application/json');return
  if self.path.startswith('/result/'):self.send('<h1>Result</h1>');return
  v=version if phase=='fixed' else 'web-execution-1'
  self.send('<form id="checkForm" action="/"><button type="button" id="submitCheckBtn" onclick="submitControl(this.form)">Check</button></form><p id="loading-message"></p>'+f'<script src="/static/js/result_polling.js?v={v}"></script><script src="/static/js/control_submit.js"></script>')
 def do_POST(self):
  self.rfile.read(int(self.headers.get('Content-Length',0)));self.send(json.dumps({'success':True,'job_id':'abc'}),'application/json')
server=ThreadingHTTPServer(('127.0.0.1',0),Handler);threading.Thread(target=server.serve_forever,daemon=True).start();base=f'http://127.0.0.1:{server.server_port}'
try:
 with sync_playwright() as p:
  b=p.chromium.launch(channel='chrome',headless=True);page=b.new_page();cdp=page.context.new_cdp_session(page)
  page.goto(base+'/warm');assert not page.evaluate("startResultPolling.toString().includes('onFinished')")
  phase='broken';page.goto(base+'/')
  assert not page.evaluate("startResultPolling.toString().includes('onFinished')"),'Old script must really come from cache'
  assert len(asset_requests)==1,asset_requests
  page.click('#submitCheckBtn');page.wait_for_url('**/result/abc')
  history=cdp.send('Page.getNavigationHistory');previous=history['entries'][history['currentIndex']-1]['url'];assert '?task=abc' in previous,previous
  phase='fixed';page.goto(base+'/')
  assert page.evaluate("startResultPolling.toString().includes('onFinished')")
  assert len(asset_requests)==2,asset_requests
  page.click('#submitCheckBtn');page.wait_for_url('**/result/abc');page.go_back();page.wait_for_timeout(600)
  assert page.url==base+'/',page.url
  assert not page.locator('#submitCheckBtn').is_disabled()
  page.click('#submitCheckBtn');page.wait_for_url('**/result/abc')
  b.close()
finally:server.shutdown()
for name in ['form.html','result.html']:
 assert "filename='js/result_polling.js', v=" not in Path('templates',name).read_text(encoding='utf-8')
print('Warm-cache bug reproduced with the old URL; content-versioned URL loads new script and Back/new check pass without clearing cache.')
