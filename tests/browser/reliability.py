from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser=p.chromium.launch(channel='chrome',headless=True)
    for width in (390,1440):
        page=browser.new_page(viewport={'width':width,'height':950})
        errors=[];page.on('pageerror',lambda error:errors.append(str(error)))
        page.goto('http://127.0.0.1:5087/member-analysis/'+'b'*32)
        assert page.locator('#member-present-comments blockquote').inner_text()=='Gerçekten güzel bir paylaşım 🌸'
        assert page.locator('#member-present-likes [data-state=present]').count()==1
        assert page.locator('#copy-member-missing-comments').is_disabled()
        assert page.locator('#member-missing-text-comments').is_hidden()
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
        pending=[]
        page.route('**/api/member_analysis/*/retry-unknown',lambda route:pending.append(route))
        buttons=page.locator('[data-retry-unknown]')
        buttons.first.click()
        page.wait_for_timeout(80)
        assert len(pending)==1
        assert buttons.nth(1).is_disabled()
        buttons.nth(1).evaluate('e=>e.click()')
        assert len(pending)==1
        pending.pop().fulfill(status=502,content_type='text/html',body='<h1>Bad gateway</h1>')
        page.wait_for_function("!document.querySelector('[data-retry-unknown]').disabled")
        assert 'geçerli yanıt' in page.locator('[data-retry-feedback]').first.inner_text()
        buttons.first.click();page.wait_for_timeout(80)
        pending.pop().fulfill(status=400,json={'error':'Yeniden deneyin.'})
        page.wait_for_function("!document.querySelector('[data-retry-unknown]').disabled")
        assert page.locator('[data-retry-feedback]').first.inner_text()=='Yeniden deneyin.'
        assert not errors,errors
        page.screenshot(path=f'scratch/reliability-member-{width}.png',full_page=True)
        page.close()
    browser.close()
print('Reliability UI: completed comments/likes, mobile layout, duplicate guard and error recovery passed.')
