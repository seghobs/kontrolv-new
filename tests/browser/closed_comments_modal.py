from playwright.sync_api import sync_playwright
with sync_playwright() as p:
 b=p.chromium.launch(channel='chrome',headless=True)
 for width in (390,1440):
  page=b.new_page(viewport={'width':width,'height':900});errors=[]
  page.on('pageerror',lambda e:errors.append(str(e)))
  page.route('**/api/get_groups',lambda r:r.fulfill(json={'ok':True,'groups':[]}))
  page.route('**/api/get_post_thumbnail?*',lambda r:r.fulfill(json={'ok':True,'comments_disabled':True}))
  page.goto('http://127.0.0.1:5087/')
  page.locator('#post_link_single').fill('https://www.instagram.com/p/AAA/')
  dialog=page.locator('#closedCommentsDialog');dialog.wait_for(state='visible')
  assert dialog.evaluate('e=>e.scrollWidth<=e.clientWidth')
  page.screenshot(path=f'scratch/closed-modal-{width}.png')
  dialog.locator('.scope-start').click()
  assert page.locator('#controlMode').input_value()=='likes'
  assert dialog.count()==0
  page.evaluate('checkManualCommentWarning()')
  assert dialog.count()==0
  page.locator('#post_link_single').fill('https://www.instagram.com/p/BBB/')
  dialog.wait_for(state='visible');assert dialog.locator('.scope-start').is_hidden()
  page.keyboard.press('Escape');assert dialog.count()==0
  assert not errors,errors
  page.close()
 b.close()
print('Closed modal: mobile/desktop, switch to likes, one alert per link, new link and Escape passed.')
