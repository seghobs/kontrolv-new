from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    browser=p.chromium.launch(channel='chrome',headless=True)
    for width in (390,1440):
        page=browser.new_page(viewport={'width':width,'height':900});errors=[]
        page.on('pageerror',lambda e:errors.append(str(e)))
        page.route('**/api/get_groups',lambda r:r.fulfill(json={'ok':True,'groups':[]}))
        page.route('**/api/get_post_thumbnail?*',lambda r:r.fulfill(json={'ok':True,'comments_disabled':True if 'CLOSED' in r.request.url else False if 'OPEN' in r.request.url else None}))
        page.goto('http://127.0.0.1:5087/')
        field=page.locator('#post_link_single');notice=page.locator('#manualCommentNotice')
        field.fill('https://www.instagram.com/p/CLOSED/')
        notice.wait_for(state='visible');assert 'yorumlara kapalı' in notice.inner_text()
        page.locator('#closedCommentsDialog .scope-edit').click()
        page.locator('#controlLikes').click()
        page.wait_for_function("document.getElementById('manualCommentNotice').textContent.includes('Beğeni kontrolü yapılabilir')")
        field.fill('https://www.instagram.com/p/OPEN/')
        page.wait_for_timeout(800);assert notice.is_hidden()
        field.fill('https://www.instagram.com/p/UNKNOWN/')
        notice.wait_for(state='visible');assert 'doğrulanamadı' in notice.inner_text()
        field.fill('');assert notice.is_hidden()
        # A late closed response cannot label the newly entered open post.
        page.evaluate("""() => {const original=fetch;window.fetch=async (...args)=>{const response=await original(...args);if(String(args[0]).includes('SLOWCLOSED'))await new Promise(r=>setTimeout(r,900));return response;}}""")
        field.fill('https://www.instagram.com/p/SLOWCLOSED/')
        page.wait_for_timeout(600);field.fill('https://www.instagram.com/p/OPEN/')
        page.wait_for_timeout(1100);assert notice.is_hidden()
        field.fill('https://www.instagram.com/p/CLOSED/')
        notice.wait_for(state='visible')
        assert page.locator('#closedCommentsDialog').count()==0
        page.screenshot(path=f'scratch/manual-comment-warning-{width}.png',full_page=True)
        assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
        assert not errors,errors
        page.close()
    browser.close()
print('Manual warning: closed/open/unknown, likes mode, clearing and stale responses passed on mobile/desktop.')
