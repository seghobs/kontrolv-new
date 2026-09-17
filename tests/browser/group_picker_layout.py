import os
from playwright.sync_api import sync_playwright
BASE=os.environ.get('PICKER_TEST_BASE','http://127.0.0.1:5087')
with sync_playwright() as p:
 b=p.chromium.launch(channel='chrome',headless=True);page=b.new_page();errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
 page.route('**/api/get_groups',lambda r:r.fulfill(json={'ok':True,'groups':[{'id':'picker'+str(i),'name':'Test Group '+str(i).zfill(2),'member_count':25} for i in range(30)]}))
 page.route('**/api/group_control_preferences/*',lambda r:r.fulfill(json={'ok':True,'preferences':{'only_sharers':False,'low_likes':False}}))
 page.route('**/api/get_group_members/*',lambda r:r.fulfill(json={'ok':True,'members':[],'usernames':[]}))
 page.route('**/api/get_group_posts/*',lambda r:r.fulfill(json={'ok':True,'posts':[]}))
 for width,height in [(320,568),(390,844),(390,420),(1440,900)]:
  page.set_viewport_size({'width':width,'height':height});page.goto(BASE+'/',wait_until='domcontentloaded');page.wait_for_timeout(400)
  trigger=page.locator('#groupDropdown .dropdown-trigger');trigger.scroll_into_view_if_needed()
  page.evaluate("window.scrollBy(0,document.querySelector('#groupDropdown').getBoundingClientRect().top-innerHeight+190)")
  trigger.click();menu=page.locator('#groupDropdown .dropdown-menu');page.wait_for_timeout(150)
  assert menu.evaluate("e=>e.matches(':popover-open')")
  box=menu.bounding_box();nav=page.locator('.mobile-bottom-nav');bottom=nav.bounding_box()['y']-7 if nav.is_visible() else height
  assert box['y']>=0 and box['y']+box['height']<=bottom+1,(width,height,box,bottom)
  options=page.locator('#groupDropdown .dropdown-options');options.evaluate('e=>e.scrollTop=e.scrollHeight');page.wait_for_timeout(100)
  last=options.locator('.dropdown-option').last
  assert last.evaluate("e=>{const r=e.getBoundingClientRect();return e.contains(document.elementFromPoint(r.x+r.width/2,r.y+r.height/2))}"),'Last group obscured'
  page.locator('#groupDropdown .dropdown-search').fill('Test Group 29');page.wait_for_timeout(400);assert options.locator('.dropdown-option:visible').count()==1
  last.click();page.wait_for_timeout(200);assert not menu.evaluate("e=>e.matches(':popover-open')")
  assert page.locator('#thread_id_input').input_value()=='picker29'
  trigger.click();page.keyboard.press('Escape');page.wait_for_timeout(100);assert not menu.evaluate("e=>e.matches(':popover-open')")
  assert page.evaluate('document.documentElement.scrollWidth<=innerWidth'), page.evaluate("[...document.querySelectorAll('body *')].filter(e=>e.getBoundingClientRect().right>innerWidth+1).map(e=>[e.tagName,e.className,e.getBoundingClientRect().right]).slice(0,12)")
 assert not errors,errors;b.close()
print('30-group picker: top layer, last-row hit test, scrolling, search, selection and Escape passed at 320/390/1440px and short keyboard-height viewport.')

