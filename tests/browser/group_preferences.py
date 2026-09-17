import uuid
from playwright.sync_api import sync_playwright
BASE='http://127.0.0.1:5087';a='pref_a_'+uuid.uuid4().hex;b='pref_b_'+uuid.uuid4().hex
with sync_playwright() as p:
 browser=p.chromium.launch(channel='chrome',headless=True)
 def setup():
  page=browser.new_page(viewport={'width':390,'height':900})
  page.route('**/api/get_groups',lambda r:r.fulfill(json={'ok':True,'groups':[{'id':a,'name':'Group A','member_count':2},{'id':b,'name':'Group B','member_count':2}]}))
  page.route('**/api/get_group_members/*',lambda r:r.fulfill(json={'ok':True,'members':[],'usernames':['alice','bob']}))
  page.route('**/api/get_group_posts/*',lambda r:r.fulfill(json={'ok':True,'posts':[{'url':'https://www.instagram.com/p/AAA/','username':'alice','date':'Today','like_count':10}]}))
  page.route('**/api/get_selected_post?*',lambda r:r.fulfill(json={'success':False}))
  page.route('**/api/save_selected_post',lambda r:r.fulfill(json={'success':True}))
  page.goto(BASE+'/');return page
 def select(page,name):
  page.locator('#groupDropdown .dropdown-trigger').click();page.locator('#groupDropdown .dropdown-option').filter(has_text=name).click()
  page.wait_for_function('!window.isMembersLoading && !window.isPostsLoading && !document.getElementById("lowLikesCheck").disabled')
  if not page.locator('#homeOptions').evaluate('e=>e.open'):page.locator('#homeOptions>summary').click()
 def saved(page,group,sharers,likes):
  page.evaluate('(group)=>groupPreferenceWrites.get(group)',group)
  assert page.request.get(BASE+'/api/group_control_preferences/'+group).json()['preferences']==dict(only_sharers=sharers,low_likes=likes)
 page=setup();select(page,'Group A');assert not page.locator('#lowLikesCheck').is_checked()
 page.locator('#onlySharersCheck').check();page.locator('#lowLikesCheck').check();saved(page,a,True,True)
 select(page,'Group B');assert not page.locator('#lowLikesCheck').is_checked();assert not page.locator('#onlySharersCheck').is_checked()
 select(page,'Group A');assert page.locator('#lowLikesCheck').is_checked();assert page.locator('#onlySharersCheck').is_checked();assert page.locator('#grup_uye').input_value()=='alice'
 page.locator('#lowLikesCheck').uncheck();page.locator('#onlySharersCheck').uncheck();saved(page,a,False,False)
 assert page.locator('#grup_uye').input_value()=='alice\nbob'
 # Rapid alternating clicks must leave the last snapshot in SQLite.
 page.evaluate("for(let i=0;i<6;i++){document.getElementById('lowLikesCheck').checked=i%2===0;handleLowLikesCheckbox()}")
 saved(page,a,False,False);page.close()
 page=setup();select(page,'Group A');assert not page.locator('#lowLikesCheck').is_checked();assert not page.locator('#onlySharersCheck').is_checked()
 # A delayed preference response for A must not alter B's UI.
 page.route('**/api/group_control_preferences/'+a,lambda r:r.fulfill(json={'ok':True,'preferences':{'only_sharers':True,'low_likes':True}}))
 page.evaluate("""() => { const original=window.fetch;window.fetch=async (...args)=>{const response=await original(...args);if(String(args[0]).endsWith('/"""+a+"""'))await new Promise(r=>setTimeout(r,350));return response;};document.querySelector('#groupDropdown .dropdown-options').children[0].click();document.querySelector('#groupDropdown .dropdown-options').children[1].click();}""")
 page.wait_for_timeout(700);assert page.locator('#thread_id_input').input_value()==b;assert not page.locator('#lowLikesCheck').is_checked()
 page.route('**/api/group_control_preferences/'+b,lambda r:r.fulfill(status=503,json={'ok':False,'error':'Preferences unavailable'}))
 page.evaluate("document.querySelector('#groupDropdown .dropdown-options').children[1].click()")
 page.wait_for_timeout(500);assert page.locator('#lowLikesCheck').is_disabled()
 assert 'Preferences unavailable' in page.locator('#validationToast').inner_text()
 page.close();browser.close()
print('Real SQLite persistence: per-group isolation, restore before filtering, unchecked persistence, new browser session, rapid writes and stale group response passed.')
