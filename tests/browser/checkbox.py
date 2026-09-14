from playwright.sync_api import sync_playwright
with sync_playwright() as p:
 b=p.chromium.launch(channel='chrome',headless=True);page=b.new_page(viewport={'width':390,'height':844})
 for path in ['/','/_preview/login','/tools','/followup/'+'a'*32]:
  page.goto('http://127.0.0.1:5087'+path)
  for box in page.locator('input[type=checkbox]:visible').all():
   assert box.evaluate("e=>{const s=getComputedStyle(e);return s.appearance==='none'&&s.width==='20px'&&s.height==='20px'&&s.borderRadius==='6px'}"),path
  assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
 member=page.locator('[name=member]').first;member.check();assert member.is_checked()
 assert member.evaluate('e=>new FormData(e.form).getAll("member").includes(e.value)')
 member.focus();page.keyboard.press('Space');assert not member.is_checked()
 member.evaluate('e=>e.indeterminate=true');assert 'svg' in member.evaluate('e=>getComputedStyle(e).backgroundImage')
 member.evaluate('e=>{e.indeterminate=false;e.disabled=true}');assert member.is_disabled()
 member.evaluate('e=>{e.disabled=false;e.checked=true}')
 page.screenshot(path='scratch/checkbox-mobile.png',full_page=True)
 page.set_viewport_size({'width':1440,'height':1000});page.screenshot(path='scratch/checkbox-desktop.png',full_page=True)
 page.evaluate("() => {const label=document.createElement('label');label.className='toggle-switch';const input=document.createElement('input');input.type='checkbox';input.id='dynamic-check';const span=document.createElement('span');span.className='slider';label.append(input,span);document.body.append(label)}")
 dynamic=page.locator('#dynamic-check');dynamic.check();assert dynamic.is_checked();assert dynamic.evaluate("e=>getComputedStyle(e).width==='20px'")
 b.close();print('Checkboxes: shared style across four pages, mobile, keyboard, form data, disabled, indeterminate and dynamic toggle passed.')
