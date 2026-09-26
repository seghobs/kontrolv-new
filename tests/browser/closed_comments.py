"""No Instagram writes: UI fixtures mirror the verified closed-comment flags."""
from playwright.sync_api import sync_playwright

closed='https://www.instagram.com/p/DWy2bcUCNG0/'
with sync_playwright() as p:
    browser=p.chromium.launch(channel='chrome',headless=True)
    for width in (390,1440):
        page=browser.new_page(viewport={'width':width,'height':900});errors=[]
        page.on('pageerror',lambda e:errors.append(str(e)))
        page.route('**/api/get_groups',lambda r:r.fulfill(json={'ok':True,'groups':[]}))
        page.route('**/api/get_group_posts/*',lambda r:r.fulfill(json={'ok':True,'posts':[
            {'url':closed,'username':'closed_owner','date':'26 Eylül','comments_disabled':True,'commenting_disabled_for_viewer':True,'comment_count':0,'like_count':20},
            {'url':'https://www.instagram.com/p/OPEN/','username':'open_owner','date':'26 Eylül','comments_disabled':False,'comment_count':0,'like_count':10},
            {'url':'https://www.instagram.com/p/UNKNOWN/','username':'unknown_owner','date':'26 Eylül','comments_disabled':None,'commenting_disabled_for_viewer':True,'like_count':5}]}))
        page.goto('http://127.0.0.1:5087/')
        page.evaluate("document.getElementById('postDropdown').style.display='block';loadGroupPosts('fixture')")
        page.wait_for_function('window.allFetchedPosts?.length===3 && !window.isPostsLoading')
        assert page.locator('#postSelect option').count()==2
        assert '1 paylaşımın yorumları kapalı' in page.locator('#postListSummary').inner_text()
        page.evaluate("setControlType('likes')")
        assert page.locator('#postSelect option').count()==3
        assert 'Yorumlara kapalı' in page.locator('#postDropdown .dropdown-options').text_content()
        page.evaluate('(url)=>selectPostInUI(url)',closed)
        assert page.locator('#post_link_single').input_value()==closed
        page.evaluate("setControlType('comments')")
        assert page.locator('#post_link_single').input_value()==''
        page.locator('#modeMulti').click()
        assert closed not in page.locator('#post_link_multi').input_value()
        page.evaluate("setControlType('likes')")
        assert closed in page.locator('#post_link_multi').input_value()
        page.evaluate("setControlType('comments')")
        assert closed not in page.locator('#post_link_multi').input_value()
        assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
        page.screenshot(path=f'scratch/closed-comments-{width}.png',full_page=True)
        assert not errors,errors
        page.close()
    browser.close()
print('Closed comments: comment/like switching, viewer-only restriction, zero comments, stale selections and bulk links pass on mobile/desktop.')
