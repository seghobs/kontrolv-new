from pathlib import Path
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
 b=p.chromium.launch(channel='chrome',headless=True);page=b.new_page(viewport={'width':390,'height':844})
 page.set_content('<body class="report-page"><ul class="eksikler-list"><li data-username="test_user">Üye</li></ul></body>')
 for f in ['result.css','member_analysis.css']:page.add_style_tag(content=Path('static/css/'+f).read_text(encoding='utf-8'))
 page.evaluate("() => {window.postCode='test';window.resultThreadId='group';window.fetch=async()=>{throw Error('Should not submit')}}")
 page.add_script_tag(content=Path('static/js/member_analysis.js').read_text(encoding='utf-8'));page.locator('.member-analyze-button').click()
 today=page.locator('[name=date]').input_value();page.locator('[data-preset=yesterday]').click()
 from datetime import date,timedelta
 assert page.locator('[name=date]').input_value()==str(date.fromisoformat(today)-timedelta(days=1))
 assert page.locator('[name=end_date]').input_value()==page.locator('[name=date]').input_value()
 page.locator('[data-preset=today]').click();assert page.locator('[name=date]').input_value()==today
 page.locator('[name=date]').evaluate("e=>{e.value='2024-02-15';e.dispatchEvent(new Event('change'))}")
 page.locator('[data-date-field=date]').click();page.locator('[data-day="2024-02-29"]').click();assert page.locator('[name=date]').input_value()=='2024-02-29'
 page.locator('[name=end_date]').evaluate("e=>e.value=''");page.locator('[data-date-field=end_date]').click()
 assert page.locator('[data-day="2024-02-28"]').is_disabled()
 page.locator('[data-month-step="1"]').click();page.locator('[data-day="2024-03-03"]').click();assert page.locator('[name=end_date]').input_value()=='2024-03-03'
 page.locator('[data-date-field=date]').click();assert page.locator('.in-range').count()>0
 page.screenshot(path='scratch/daily-calendar-mobile.png');assert page.locator('dialog').evaluate('(e)=>e.scrollWidth<=e.clientWidth')
 page.keyboard.press('Escape');assert page.locator('.daily-calendar').is_hidden();assert page.locator('dialog').is_visible()
 page.locator('[data-date-field=end_date]').click();page.locator('[data-clear-end]').click();assert page.locator('[name=end_date]').input_value()==''
 page.locator('[name=date]').evaluate("e=>e.value='2024-12-15'");page.locator('[data-date-field=date]').click();page.locator('[data-month-step="1"]').click();assert '2025' in page.locator('.daily-calendar-head strong').inner_text()
 page.locator('[data-day="2025-01-01"]').click();assert page.locator('[name=date]').input_value()=='2025-01-01'
 page.locator('[name=end_date]').evaluate("e=>e.value='2024-12-01'");page.locator('[type=submit]').click();assert 'önce olamaz' in page.locator('.member-error').inner_text()
 b.close();print('Calendar: presets, leap day, year/month navigation, range, disabled dates, clear end, Escape and mobile passed.')
