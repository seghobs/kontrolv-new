from playwright.sync_api import sync_playwright
with sync_playwright() as p:
 b=p.chromium.launch(channel='chrome',headless=True);page=b.new_page(viewport={'width':390,'height':844})
 page.goto('http://127.0.0.1:5087/history')
 for cell in page.locator('.history-records td').all():
  box=cell.bounding_box();assert box['x']>=0 and box['x']+box['width']<=390
 page.screenshot(path='scratch/history-fixed-mobile.png',full_page=True)
 page.goto('http://127.0.0.1:5087/followup/'+'a'*32)
 pending=[];page.route('**/api/member_analysis/*',lambda r:pending.append(r))
 page.check('[name=member][value=bob]');page.fill('[name=date]','2026-09-01');page.fill('[name=end_date]','2026-09-02')
 page.locator('[data-batch-submit]').click();page.wait_for_timeout(100)
 assert len(pending)==1;assert page.locator('[data-batch-submit]').is_disabled();assert page.locator('[data-copy-user]').is_enabled()
 page.locator('[data-batch]').evaluate("e=>e.dispatchEvent(new Event('submit',{bubbles:true,cancelable:true}))")
 page.wait_for_timeout(100);assert len(pending)==1
 pending[0].fulfill(status=503,json={'error':'Servis geçici olarak kullanılamıyor'})
 page.wait_for_function("!document.querySelector('[data-batch-submit]').disabled")
 assert 'geçici' in page.locator('#followup-feedback').inner_text()
 page.locator('[data-batch-submit]').click();page.wait_for_timeout(100);pending[-1].fulfill(status=502,content_type='text/html',body='<h1>Bad gateway</h1>')
 page.wait_for_function("document.querySelector('#followup-feedback').textContent.includes('geçerli yanıt')")
 assert page.locator('[data-batch-submit]').is_enabled()
 page.locator('[data-filter]').evaluate("e=>{e.value='missing';document.querySelectorAll('.followup-post').forEach(p=>p.dataset.state='present');e.dispatchEvent(new Event('change',{bubbles:true}))}")
 assert page.locator('[data-filter-empty]').is_visible()
 b.close();print('Audit regressions: mobile history actions, duplicate batch guard, correct button, failure recovery and filter empty state passed.')
