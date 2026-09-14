from pathlib import Path
Path("scratch").mkdir(exist_ok=True)
from playwright.sync_api import sync_playwright
from pathlib import Path

def choose(page, selector, value):
    select=page.locator(selector)
    text=select.evaluate("(e,value)=>[...e.options].find(o=>o.value===value).textContent",value)
    select.locator('xpath=following-sibling::button[1]').click()
    page.locator('.coffee-select-option').filter(has_text=text).click()

with sync_playwright() as p:
 browser=p.chromium.launch(headless=True,channel='chrome')
 page=browser.new_page(viewport={'width':390,'height':844})
 errors=[];page.on('pageerror',lambda error:errors.append(str(error)))
 for path in ['/followup/'+'a'*32,'/members/alice','/_preview/login','/backups','/trash','/']:
  response=page.goto('http://127.0.0.1:5087'+path);assert response.status==200,(path,response.status)
  assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'),path
 page.goto('http://127.0.0.1:5087/followup/'+'a'*32)
 choose(page,'[data-filter]','unknown');assert page.locator('.followup-post:visible').count()==1
 choose(page,'[data-filter]','all');assert page.locator('.followup-post:visible').count()==2
 page.check('[data-compact]');assert page.locator('body').evaluate("e=>e.classList.contains('compact')")
 page.uncheck('[data-compact]')
 page.screenshot(path='scratch/followup-mobile.png',full_page=True)
 page.set_viewport_size({'width':1440,'height':1000});page.screenshot(path='scratch/followup-desktop.png',full_page=True)
 assert not errors,errors
 print('6 routes, mobile overflow, filter and compact interactions passed; no JS errors')
 browser.close()
