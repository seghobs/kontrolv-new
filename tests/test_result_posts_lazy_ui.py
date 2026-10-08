from pathlib import Path
from playwright.sync_api import sync_playwright
URL='https://kontrolyeni.pythonanywhere.com/result/7eec7fe59df941d687fd1eae172fe652'
def main():
    with sync_playwright() as p:
     browser=p.chromium.launch(channel='chrome',headless=True)
     page=browser.new_page(viewport={'width':390,'height':844});pending=[];calls=[];errors=[]
     page.on('pageerror',lambda e:errors.append(str(e)))
     page.route('**/static/js/result.js*',lambda route:route.fulfill(path=str(Path('static/js/result.js').resolve())))
     def group(route):calls.append(route.request.url);pending.append(route)
     page.route('**/api/get_group_posts/**',group)
     page.goto(URL,wait_until='networkidle')
     assert not calls,'Page load must not fetch Instagram posts'
     page.locator('#togglePostSelectorBtnWrapper button').click()
     page.wait_for_function("document.getElementById('resultPostDropdownText').textContent.includes('yükleniyor')")
     page.wait_for_timeout(300)
     assert len(calls)==2,len(calls)
     page.evaluate('togglePostSelectorCard()');page.wait_for_timeout(250)
     page.evaluate('togglePostSelectorCard()');page.wait_for_timeout(250)
     assert len(calls)==2,'Reopening during load must share in-flight requests'
     for route in pending:route.fulfill(json={'ok':True,'posts':[{'url':'https://www.instagram.com/p/TestPost/','username':'test_member','date':'08.10.2026'}]})
     pending.clear()
     page.locator('#resultPostDropdownOptions .dropdown-option').wait_for()
     assert page.locator('#resultPostSelectorContainer').is_visible(),'Late response must not close selector'
     assert page.locator('#resultPostDropdownOptions .dropdown-option').count()==1
     page.evaluate('togglePostSelectorCard()');page.wait_for_timeout(250);page.evaluate('togglePostSelectorCard()');page.wait_for_timeout(250)
     assert len(calls)==2,'Reuse successful list in current page'
     assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
     page.reload(wait_until='networkidle');assert len(calls)==2
     page.locator('#togglePostSelectorBtnWrapper button').click();page.wait_for_timeout(250)
     assert len(pending)==2
     for route in pending:route.fulfill(status=503,json={'ok':False})
     pending.clear()
     page.get_by_role('button',name='Tekrar dene',exact=True).wait_for()
     assert page.locator('.result-header-title').is_visible()
     page.get_by_role('button',name='Tekrar dene',exact=True).click();page.wait_for_timeout(250)
     assert len(pending)==2
     for route in pending:route.fulfill(json={'ok':True,'posts':[]})
     page.wait_for_function("document.getElementById('resultPostDropdownOptions').textContent.includes('bulunamadı')")
     assert page.locator('#resultPostSelectorContainer').is_visible()
     assert not errors,errors
     print('PASS: no eager requests; click loads; in-flight dedup; URL dedup; panel stays open; loaded reuse; failure retry; empty state; mobile; no JS errors')
     browser.close()

if __name__ == "__main__":
    main()
