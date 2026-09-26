from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    b=p.chromium.launch(channel='chrome',headless=True)
    for width in (390,1440):
        page=b.new_page(viewport={'width':width,'height':900});errors=[];dialogs=[];writes=[]
        page.on('pageerror',lambda e:errors.append(str(e)))
        page.on('dialog',lambda d:(dialogs.append(d.message),d.dismiss()))
        page.on('request',lambda r:writes.append(r.url) if r.method=='POST' else None)
        page.route('**/api/get_groups',lambda r:r.fulfill(json={'ok':True,'groups':[]}))
        page.goto('http://127.0.0.1:5087/')
        page.locator('#homeOptions>summary').click()
        page.locator('#post_link_single').fill('https://www.instagram.com/p/ABC/')
        page.locator('#grup_uye').evaluate("e=>e.value='alice bob'")
        for id in ('onlySharersCheck','lowLikesCheck'):
            assert page.locator('#'+id).is_enabled()
            page.locator('#'+id).check()
            assert page.locator('#'+id).is_checked()
        page.locator('#controlLikes').click()
        assert page.locator('#controlMode').input_value()=='likes'
        assert page.locator('#post_link_single').input_value().endswith('/ABC/')
        assert page.locator('#grup_uye').input_value()=='alice bob'
        for id in ('onlySharersCheck','lowLikesCheck'):page.locator('#'+id).uncheck()
        assert not errors and not dialogs and not writes,(errors,dialogs,writes)
        assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
        page.close()
    b.close()
print('No group: filters visible and selectable, mode works, manual inputs preserved, no alerts/writes on mobile/desktop.')
