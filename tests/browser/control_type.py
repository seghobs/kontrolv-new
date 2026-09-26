from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    b=p.chromium.launch(channel='chrome',headless=True)
    for width in (390,1440):
        page=b.new_page(viewport={'width':width,'height':900});errors=[]
        page.on('pageerror',lambda e:errors.append(str(e)))
        page.route('**/api/get_groups',lambda r:r.fulfill(json={'ok':True,'groups':[]}))
        page.goto('http://127.0.0.1:5087/')
        page.locator('#homeOptions>summary').click()
        assert page.locator('.control-extractor').count()==0
        page.locator('#post_link_single').fill('https://www.instagram.com/p/ABC/')
        for button,mode,value in [('controlLikes','likes','on'),('controlComments','comments','')]:
            page.locator('#'+button).click()
            assert page.locator('#'+button).get_attribute('aria-pressed')=='true'
            assert page.locator('#controlMode').input_value()==mode
            assert page.evaluate("new FormData(document.getElementById('checkForm')).get('check_likes')")==value
            assert page.locator('#post_link_single').input_value().endswith('/ABC/')
        page.locator('#controlLikes').click()
        page.screenshot(path=f'scratch/control-type-{width}.png',full_page=True)
        assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
        assert not errors,errors
        page.close()
    b.close()
print('Control type buttons: mobile/desktop, form payload, accessibility state, manual link preservation and removed extractor passed.')
