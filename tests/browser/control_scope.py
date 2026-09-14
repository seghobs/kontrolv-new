from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(channel='chrome', headless=True)
    page = browser.new_page()
    page.goto('http://127.0.0.1:5087/')
    for width in [390, 1100]:
        page.set_viewport_size({'width': width, 'height': 844})
        page.evaluate("""() => {
            const form = document.createElement('form');
            for (const [name,value] of Object.entries({post_link:'https://www.instagram.com/p/ABC/',grup_uye:'alice bob',check_likes:'on'})) {
                const input=document.createElement('input');input.name=name;input.value=value;form.append(input);
            }
            window.scopeResult=null;
            confirmControlScope(form).then(value=>window.scopeResult=value);
        }""")
        assert page.locator('[data-scope-members]').inner_text() == '2'
        assert page.locator('[data-scope-type]').inner_text() == 'Beğeni'
        page.screenshot(path=f'scratch/scope-{width}.png')
        assert page.locator('.control-scope-dialog').evaluate('(e)=>e.scrollWidth<=e.clientWidth')
        page.locator('.scope-edit').click()
        assert page.evaluate('window.scopeResult') is False
    for action, expected in [('start', True), ('escape', False), ('close', False)]:
        page.evaluate("() => {window.scopeResult=null;confirmControlScope(document.querySelector('#checkForm')).then(v=>window.scopeResult=v)}")
        if action == 'escape':
            page.keyboard.press('Escape')
        else:
            page.locator('.scope-' + action).click()
        assert page.evaluate('window.scopeResult') is expected
    browser.close()
    print('Scope desktop/mobile layout, counts, likes mode, edit, start, close and Escape passed.')
