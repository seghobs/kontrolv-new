"""Check complete day rendering on mobile/desktop with isolated API fixtures."""
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(channel='chrome', headless=True)
    for width in (390, 1440):
        page = browser.new_page(viewport={'width': width, 'height': 900})
        errors = []
        page.on('pageerror', lambda error: errors.append(str(error)))
        page.route('**/api/get_groups', lambda r: r.fulfill(json={'ok': True, 'groups': []}))
        page.route('**/api/get_group_posts/*', lambda r: r.fulfill(json={
            'ok': True, 'story_count': 5, 'posts': [
                {'code': f'POST{i}', 'url': f'https://www.instagram.com/p/POST{i}/',
                 'username': f'member{i}', 'date': '18 Eylül 2026',
                 'media_type': 'video' if i == 4 else 'image', 'like_count': 10+i*30}
                for i in range(5)]}))
        page.goto('http://127.0.0.1:5087/')
        page.evaluate("document.getElementById('postDropdown').style.display='block';loadGroupPosts('fixture')")
        page.wait_for_function('window.allFetchedPosts?.length===5 && !window.isPostsLoading')
        assert page.locator('#postSelect option').count() == 5
        assert '5 / 5' in page.locator('#postListSummary').inner_text()
        assert '5 hikâye' in page.locator('#postListSummary').inner_text()
        page.evaluate("document.getElementById('lowLikesCheck').checked=true;renderPosts()")
        assert page.locator('#postSelect option').count() == 3
        assert '3 / 5' in page.locator('#postListSummary').inner_text()
        page.evaluate("document.getElementById('lowLikesCheck').checked=false;renderPosts()")
        assert page.locator('#postSelect option').count() == 5
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
        assert not errors, errors
        page.close()
    browser.close()
print('Complete day: all posts/Reels, separate story count, filter counts, mobile/desktop and no JavaScript errors passed.')
