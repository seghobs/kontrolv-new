from pathlib import Path
from playwright.sync_api import sync_playwright
Path('scratch').mkdir(exist_ok=True)
with sync_playwright() as p:
    browser=p.chromium.launch(headless=True,channel='chrome')
    page=browser.new_page(viewport={'width':884,'height':900});errors=[]
    page.on('pageerror',lambda error:errors.append(str(error)))
    page.goto('http://127.0.0.1:5087/history')
    control=page.locator('select[name=before]')
    control.locator('xpath=following-sibling::button[1]').click()
    assert page.locator('.coffee-select-dialog').is_visible()
    page.locator('.coffee-select-search').fill('does-not-exist')
    assert page.locator('.coffee-select-empty').is_visible()
    page.locator('.coffee-select-search').fill('')
    menu=page.locator('.coffee-select-dialog');box=menu.bounding_box();anchor=control.locator('xpath=following-sibling::button[1]').bounding_box()
    assert abs(box['x']-anchor['x'])<2 and abs(box['width']-anchor['width'])<2
    assert abs(box['y']-(anchor['y']+anchor['height']+8))<2
    assert page.locator('dialog.coffee-select-dialog').count()==0
    page.screenshot(path='scratch/select-modal-desktop.png')
    page.keyboard.press('ArrowDown');page.keyboard.press('Enter')
    assert not page.locator('.coffee-select-dialog').is_visible()
    assert control.locator('xpath=following-sibling::button[1]').evaluate('(e)=>e===document.activeElement')
    page.goto('http://127.0.0.1:5087/_preview/login')
    select=page.locator('select[name=mode]');trigger=select.locator('xpath=following-sibling::button[1]')
    select.evaluate("e=>{window.changes=0;e.addEventListener('change',()=>window.changes++);e.value='likes'}")
    assert 'Beğeni' in trigger.inner_text()
    trigger.click();page.locator('.coffee-select-search').fill('yorum');page.locator('.coffee-select-option').click()
    assert select.input_value()=='comments';assert page.evaluate('window.changes')==1
    select.evaluate("e=>e.disabled=true");assert trigger.is_disabled()
    select.evaluate("e=>{e.disabled=false;const o=new Option('<img src=x onerror=alert(1)>','extra');e.append(o)}")
    trigger.click();page.locator('.coffee-select-search').fill('<img');assert page.locator('.coffee-select-option img').count()==0
    page.keyboard.press('Escape')
    # Form reset restores the original native value and visible label.
    select.evaluate('e=>e.form.reset()');page.wait_for_timeout(30);assert select.input_value()=='selected';assert 'Formdaki' in trigger.inner_text()
    # Dynamically inserted multi-select retains form data and emits change per action.
    page.evaluate("""() => {const f=document.createElement('form');f.id='fixture-form';f.innerHTML='<label>Etiket<select name="tags" multiple><option value="one">Bir</option><option value="two">İki</option></select></label>';document.querySelector('main').append(f)}""")
    multi=page.locator('select[name=tags]');multi.locator('xpath=following-sibling::button[1]').click()
    page.locator('.coffee-select-option').filter(has_text='Bir').click();page.locator('.coffee-select-option').filter(has_text='İki').click()
    page.locator('.coffee-select-footer button').click();assert page.evaluate("new FormData(document.querySelector('#fixture-form')).getAll('tags')")==['one','two']
    page.evaluate("() => {const f=document.querySelector('#fixture-form');f.innerHTML='<label>Zorunlu<select required name=required><option value="">Seçiniz</option><option value=ok>Tamam</option></select></label>'}")
    page.wait_for_timeout(30)
    assert not page.evaluate("document.querySelector('#fixture-form').reportValidity()")
    assert page.locator('.coffee-select-dialog').is_visible()
    page.locator('.coffee-select-option').filter(has_text='Tamam').click()
    assert page.evaluate("document.querySelector('#fixture-form').checkValidity()")
    page.set_viewport_size({'width':390,'height':844});trigger.click();page.screenshot(path='scratch/select-modal-mobile.png')
    assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
    page.keyboard.press('Escape');page.goto('http://127.0.0.1:5087/')
    assert page.locator('select.hidden-select + .coffee-select-trigger').count()==0
    assert not errors,errors
    browser.close()
    print('Select modal: search, empty state, keyboard, focus, dynamic options, value sync, disabled, reset, multiselect, form data, XSS and mobile passed')
