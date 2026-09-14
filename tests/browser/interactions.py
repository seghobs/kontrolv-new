from pathlib import Path
Path("scratch").mkdir(exist_ok=True)
from playwright.sync_api import sync_playwright
import json
with sync_playwright() as p:
 browser=p.chromium.launch(headless=True,channel='chrome')
 context=browser.new_context(permissions=['clipboard-read','clipboard-write'],viewport={'width':390,'height':844})
 page=context.new_page(); errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
 page.goto('http://127.0.0.1:5087/followup/'+'a'*32)
 page.click('[data-copy-user="bob"]');assert '@bob' in page.evaluate('navigator.clipboard.readText()')
 page.select_option('[data-copy-format]','links');page.locator('[data-copy-post]').first.click();assert page.evaluate('navigator.clipboard.readText()')=='https://www.instagram.com/p/ABC'
 calls=[]
 def start(route):
  calls.append(route.request.post_data_json['username']);route.fulfill(json=dict(success=True,job_id='b'*32,result_url='/member-analysis/'+'b'*32))
 page.route('**/api/member_analysis/*',start)
 page.route('**/api/task_run/*',lambda route:route.fulfill(json={'status':'completed'}))
 page.check('[name=member][value=alice]');page.check('[name=member][value=bob]')
 page.fill('[name=date]','2026-09-01');page.fill('[name=end_date]','2026-09-02');page.locator('[data-batch] button').last.click()
 page.wait_for_function("document.querySelectorAll('[data-batch-results] li').length===2")
 assert calls==['alice','bob'];assert page.locator('[data-batch-results]').inner_text().count('Tamamlandı')==2
 page.select_option('[data-sort]','missing');assert page.locator('.followup-post').first.get_attribute('data-missing')=='1'
 page.goto('http://127.0.0.1:5087/')
 page.locator('summary').filter(has_text='Mesajdan').click()
 page.fill('[data-pasted-message]','mesaj https://instagram.com/p/ABC/ https://instagram.com/reel/ABC/')
 page.click('[data-extract]');assert '1 tekrar' in page.locator('[data-extract-status]').inner_text()
 assert page.locator('#post_link_single').input_value()=='https://www.instagram.com/p/ABC/'
 page.fill('[data-pasted-message]','https://instagram.com/p/ABC/ https://instagram.com/reel/DEF/')
 page.click('[data-extract]');page.wait_for_function('!document.getElementById("post_link_multi").disabled')
 assert page.locator('#post_link_multi').input_value().count('https://')==2
 page.evaluate('window.scopePromise=window.confirmControlScope(document.getElementById("checkForm"))') if False else None
 page.evaluate('() => {window.scopePromise=window.confirmControlScope(document.getElementById("checkForm"));}')
 page.get_by_role('button',name='Düzenle',exact=True).click();assert page.evaluate('window.scopePromise') is False
 page.goto('http://127.0.0.1:5087/_preview/login');page.screenshot(path='scratch/group-rules-mobile.png',full_page=True)
 assert not errors,errors
 print('Clipboard modes, member reminders, sequential batch completion, duplicate extraction and scope cancellation passed')
 browser.close()
