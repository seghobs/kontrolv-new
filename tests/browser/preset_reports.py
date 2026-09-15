from playwright.sync_api import sync_playwright
BASE='http://127.0.0.1:5087'
with sync_playwright() as p:
 browser=p.chromium.launch(channel='chrome',headless=True)
 for width in (390,1440):
  page=browser.new_page(viewport={'width':width,'height':950});page.context.grant_permissions(['clipboard-read','clipboard-write']);errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
  page.goto(BASE+'/tools');page.locator('[data-preset-start]').first.click()
  page.locator('[data-day=yesterday]').click();yesterday=page.locator('.preset-date-value').inner_text()
  page.locator('[data-day=today]').click();assert yesterday!=page.locator('.preset-date-value').inner_text()
  page.locator('[data-day=custom]').click();assert page.locator('.preset-calendar').is_visible()
  page.locator('[data-month="-1"]').click();page.locator('[data-date]').first.click();selected=page.locator('[data-date][aria-pressed=true]').get_attribute('data-date')
  page.screenshot(path=f'scratch/preset-date-{width}.png')
  captured=[]
  page.route('**/tools/presets/*/start',lambda route:(captured.append(route.request.post_data),route.fulfill(status=200,body='Date submitted')))
  page.locator('[data-submit]').click();page.wait_for_url('**/start');assert 'date='+selected in captured[0]
  page.goto(BASE+'/tools/presets/browser/edit');page.locator('[name=name]').fill('Düzenlenmiş şablon')
  page.locator('button',has_text='Değişiklikleri kaydet').click();page.wait_for_url('**/tools#presets');assert page.locator('.tools-preset').first.inner_text().startswith('Düzenlenmiş şablon')
  page.goto(BASE+'/result/'+'c'*32)
  page.locator('[data-report-copy=comments]').click();comments=page.evaluate('navigator.clipboard.readText()')
  page.locator('[data-report-copy=likes]').click();likes=page.evaluate('navigator.clipboard.readText()')
  assert '@bob' in comments and '@alice' not in comments;assert '@alice' in likes
  page.locator('.dual-report-nav a[href="?mode=likes"]').click();page.wait_for_url('**?mode=likes');assert 'Beğeni Durumu' in page.locator('h1').inner_text()
  page.locator('[data-extend]').click();page.locator('[data-day=yesterday]').click()
  assert 'Önceki üyeler' in page.locator('.preset-dialog').inner_text();page.locator('[data-close]').click()
  page.locator('a[href$="/matrix"]').click();page.wait_for_url('**/matrix');assert page.locator('[data-matrix-user]').count()==3
  page.locator('[data-matrix-missing]').check();assert page.locator('[data-matrix-user]:visible').count()==2
  page.locator('[data-matrix-search]').fill('alice');assert page.locator('[data-matrix-user]:visible').count()==1
  page.locator('[data-matrix-search]').fill('nobody');assert page.locator('[data-matrix-empty]').is_visible()
  page.locator('[data-matrix-search]').fill('');page.locator('[data-matrix-missing]').uncheck()
  assert page.evaluate('document.documentElement.scrollWidth<=innerWidth'),width
  page.screenshot(path=f'scratch/preset-matrix-{width}.png')
  assert not errors,errors
  page.close()
 browser.close()
print('Preset editing, date submission, separate clipboard lists, dual views, append dialog, matrix filtering and mobile layout passed.')



