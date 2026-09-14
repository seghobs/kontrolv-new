from playwright.sync_api import sync_playwright
with sync_playwright() as p:
 browser=p.chromium.launch(channel='chrome',headless=True)
 for width in (390,1440):
  page=browser.new_page(viewport={'width':width,'height':900})
  errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
  page.goto('http://127.0.0.1:5087/result/'+'a'*32)
  page.locator('.detayli-rapor-header').click()
  page.locator('.user-detail-header').click()
  assert page.locator('.missing-post-owner').inner_text()=='@ornekhesap'
  page.evaluate('''() => {window.userComments={alice:['Bir yorum']};window.postDetailsData={1:{sender:'ornek',link:'https://www.instagram.com/p/ABC',comments_list:Array.from({length:20},(_,i)=>({username:'alice',text:'Güzel paylaşım '+i}))}};showCommentModal('alice')}''')
  assert page.locator('.comment-post-group p').count()==20
  assert page.locator('.comment-post-group a').get_attribute('href').endswith('/ABC')
  assert page.locator('#commentDetailModal .modal-content').bounding_box()['height']<=900*.89
  assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
  page.wait_for_timeout(400)
  page.screenshot(path=f'scratch/report-comments-{width}.png')
  assert not errors,errors
  page.close()
 # Test first paint without the end-of-page scripts/styles, as on a slow connection.
 context=browser.new_context(java_script_enabled=False)
 page=context.new_page()
 page.goto('http://127.0.0.1:5087/')
 assert page.locator('#groupSelect').evaluate("e=>getComputedStyle(e).display")=='none'
 assert page.locator('#groupDropdown .dropdown-trigger').evaluate("e=>getComputedStyle(e).backgroundColor") not in ('rgb(255, 255, 255)','rgba(0, 0, 0, 0)')
 assert page.locator('head link[href*="dropdown.css"]').count()==1
 print('Owner labels, grouped comments, modal bounds, mobile overflow and initial dropdown theme: OK')
 browser.close()


