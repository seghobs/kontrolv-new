from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT='http://127.0.0.1:5087'
with sync_playwright() as p:
 b=p.chromium.launch(channel='chrome',headless=True); page=b.new_page(); errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
 routes=['/','/history','/tools','/admin/login','/token_al','/result/'+'c'*32,'/member-analysis/'+'b'*32,'/reports/'+'c'*32+'/matrix','/followup/'+'a'*32,'/members/alice','/_preview/login','/admin','/backups','/trash']
 for width in [320,390,768,1440]:
  page.set_viewport_size({'width':width,'height':900})
  for route in routes:
   r=page.goto(ROOT+route);assert r.status==200,(route,r.status)
   page.wait_for_timeout(100)
   assert page.evaluate('document.documentElement.scrollWidth<=innerWidth'),(width,route)
  page.goto(ROOT+'/');page.wait_for_timeout(400)
  assert not page.locator('#homeOptions').evaluate('(e)=>e.open')
  assert not page.locator('.home-member-editor').evaluate('(e)=>e.open')
  page.locator('.home-member-editor>summary').click();page.locator('#tagAddInput').fill('testmember');page.locator('#tagAddInput').press('Enter')
  assert 'testmember' in page.locator('#grup_uye').input_value()
  page.locator('.home-member-editor>summary').click()
  page.screenshot(path=f'scratch/design-home-{width}.png',full_page=True)
 assert not errors,errors
 b.close()
 print('56 responsive route checks; 4 manual member entry and collapsed home checks passed; no JavaScript errors.')

