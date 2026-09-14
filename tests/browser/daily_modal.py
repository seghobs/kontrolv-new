from pathlib import Path
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
 b=p.chromium.launch(channel='chrome',headless=True);page=b.new_page()
 page.set_content('<body class="report-page"><ul class="eksikler-list"><li data-username="zulg arbat"><span>Üye</span></li></ul></body>')
 for f in ['result.css','member_analysis.css']:page.add_style_tag(content=Path('static/css/'+f).read_text(encoding='utf-8'))
 page.evaluate("() => {window.postCode='test';window.resultThreadId='group';window.fetch=async (url,opts)=>{window.sent=JSON.parse(opts.body);return {ok:false,json:async()=>({error:'Test hata mesajı'})}};}")
 page.add_script_tag(content=Path('static/js/member_analysis.js').read_text(encoding='utf-8'))
 for width in [390,1100]:
  page.set_viewport_size({'width':width,'height':844});page.locator('.member-analyze-button').click()
  page.locator('[name=date]').fill('2026-09-14');page.locator('[name=end_date]').fill('2026-09-15')
  assert page.locator('.daily-analysis-dialog').evaluate('(e)=>e.scrollWidth<=e.clientWidth')
  a=page.locator('[name=date]').bounding_box();c=page.locator('[name=end_date]').bounding_box();assert abs(a['y']-c['y'])<2
  page.screenshot(path=f'scratch/daily-modal-{width}.png')
  page.locator('.member-close').click();assert not page.locator('dialog').is_visible()
 page.locator('.member-analyze-button').click();page.locator('[name=skip_owner]').uncheck();page.locator('[type=submit]').click()
 page.wait_for_function('window.sent!==undefined');assert page.evaluate('window.sent')=={'username':'zulg arbat','date':'2026-09-14','end_date':'2026-09-15','skip_owner':False}
 assert page.locator('.member-error').inner_text()=='Test hata mesajı';assert page.locator('[type=submit]').is_enabled()
 page.keyboard.press('Escape');assert not page.locator('dialog').is_visible()
 b.close();print('Daily modal: desktop/mobile alignment, cancel, Escape, request payload and error recovery passed.')
