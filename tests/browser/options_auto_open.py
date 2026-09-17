import os
from playwright.sync_api import sync_playwright
base=os.environ.get('OPTIONS_TEST_BASE','http://127.0.0.1:5087')
with sync_playwright() as p:
 b=p.chromium.launch(channel='chrome',headless=True);page=b.new_page()
 for width in [390,1440]:
  page.set_viewport_size({'width':width,'height':900});page.goto(base+'/',wait_until='domcontentloaded');page.wait_for_timeout(400)
  options=page.locator('#homeOptions');assert not options.evaluate('e=>e.open')
  page.evaluate("document.getElementById('postSelect').add(new Option('Test post','https://www.instagram.com/p/ABC/'));document.getElementById('postSelect').value='https://www.instagram.com/p/ABC/';addPostLink()")
  assert options.evaluate('e=>e.open')
  options.locator('>summary').click();page.evaluate('validateForm()');assert not options.evaluate('e=>e.open')
  page.locator('#post_link_single').fill('https://www.instagram.com/p/DEF/');assert options.evaluate('e=>e.open')
  options.locator('>summary').click();page.locator('#post_link_single').fill('');assert not options.evaluate('e=>e.open')
  page.locator('#modeMulti').click();page.wait_for_timeout(400);assert options.evaluate('e=>e.open')
  assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
 b.close()
print('Mobile/desktop: initially closed, post selection/manual link/bulk selection open options; manual collapse preserved for unchanged selection.')
