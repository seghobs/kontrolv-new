"""Browser regressions for the shared pickers, card animation and modal focus.
Runs against Flask's test client and an isolated DB; never starts real audits.
"""
import json
import mimetypes
import re
import requests
import unittest
from pathlib import Path
from urllib.parse import urlparse
from unittest.mock import patch
import test_jobs
from app_core import create_app, jobs
try:
    from playwright.sync_api import sync_playwright
except ImportError:
    sync_playwright = None
ROOT = Path(__file__).resolve().parents[1]

@unittest.skipUnless(sync_playwright, 'Optional Playwright browser test dependency is not installed')
class SharedUIBrowserTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.assets = {}
        for name in ('form.html','result.html','tools.html'):
            for url in re.findall(r'https://[^"\s]+(?:\.js|\.css)', (ROOT/'templates'/name).read_text(encoding='utf-8')):
                if url in cls.assets: continue
                try:
                    response = requests.get(url, timeout=10); response.raise_for_status()
                    cls.assets[url] = (response.content, response.headers.get('Content-Type','text/plain'))
                except requests.RequestException:
                    raise unittest.SkipTest('Required CDN test assets are unavailable')
        cls.runtime = sync_playwright().start()
        try:
            cls.browser = cls.runtime.chromium.launch(channel='chrome', headless=True)
        except Exception:
            cls.runtime.stop()
            raise unittest.SkipTest('Chrome is not available for browser regression tests')
    @classmethod
    def tearDownClass(cls):
        cls.browser.close(); cls.runtime.stop()
    def setUp(self):
        test_jobs.JobTests.setUp(self)
        with patch('app_core.init_storage'):
            self.client = create_app().test_client()
        with self.client.session_transaction() as session:
            session['admin_logged_in'] = True
        self.identifier = jobs.enqueue('manual', {'members':'member', 'thread_id':'ui-group', 'selected_date':'2026-10-08'})
        jobs.claim_request(self.identifier, 'ui-owner')
        jobs.complete(self.identifier, 'ui-owner', {'thread_id':'ui-group','selected_date':'2026-10-08',
            'links':[{'post_link':'https://www.instagram.com/p/UItest/','sender':'member','eksikler':['member']}],
            'group':['member'], 'all_commented':[], 'user_comments':{}})
    def page(self, width):
        page=self.browser.new_page(viewport={'width':width,'height':900})
        self.addCleanup(page.close)
        page.set_default_timeout(8000)
        errors=[];page.on('pageerror',lambda error:errors.append(error.stack))
        def serve(route):
            parsed=urlparse(route.request.url)
            if parsed.hostname!='ui.test':
                asset=self.assets.get(route.request.url)
                if asset:route.fulfill(body=asset[0],content_type=asset[1])
                else:route.fulfill(status=204,body='')
                return
            path=parsed.path
            if path.startswith('/static/'):
                asset=ROOT/path.lstrip('/')
                route.fulfill(body=asset.read_bytes(),content_type=mimetypes.guess_type(asset)[0] or 'application/octet-stream');return
            data=None
            if path=='/api/get_groups':data={'ok':True,'groups':[{'id':'ui-group','name':'UI grubu','member_count':1}]}
            elif path.startswith('/api/group_control_preferences/'):
                data={'ok':True,'control_mode':'comments','selected_date':'2026-10-08','preferences':{'only_sharers':False,'low_likes':False}}
            elif path.startswith('/api/get_group_members/'):
                data={'ok':True,'usernames':['member'],'members':[{'username':'member'}]}
            elif path.startswith('/api/get_group_posts/'):
                data={'ok':True,'posts':[{'url':'https://www.instagram.com/p/UItest'+str(i)+'/','username':'member','date':'8 Ekim','like_count':10} for i in range(40)]}
            elif path=='/api/get_selected_post':data={'ok':True,'post_url':''}
            elif path=='/api/save_selected_post':data={'ok':True}
            if data is not None:route.fulfill(json=data);return
            if path.startswith('/api/'):
                route.fulfill(json={'ok':False,'error':'No external API in UI tests'});return
            if route.request.method!='GET':route.fulfill(status=400,json={'ok':False});return
            response=self.client.get(path+('?' + parsed.query if parsed.query else ''))
            route.fulfill(status=response.status_code,body=response.data,content_type=response.content_type)
        page.route('**/*',serve)
        return page,errors
    def test_main_pickers_fit_viewport_and_scroll_calendar(self):
        for width in (1440,390):
            page,errors=self.page(width);page.goto('http://ui.test/',wait_until='domcontentloaded')
            page.locator('#groupDropdown .dropdown-trigger').click()
            page.locator('#groupDropdown .dropdown-option').click()
            page.wait_for_selector('#postDropdown .dropdown-option', state='attached')
            for name in ('groupDropdown','dateDropdown','postDropdown'):
                trigger=page.locator('#'+name+' .dropdown-trigger');trigger.click()
                menu=page.locator('#'+name+' .dropdown-menu')
                self.assertTrue(menu.evaluate("e=>e.matches(':popover-open')"))
                rect=menu.bounding_box();self.assertGreaterEqual(rect['x'],0);self.assertLessEqual(rect['x']+rect['width'],width)
                trigger.press('ArrowDown');page.keyboard.press('Escape');self.assertFalse(menu.is_visible())
            page.locator('#dateDropdown .dropdown-trigger').click();page.locator('#dateOptCustom').click()
            calendar=page.locator('#customDateContainer');self.assertTrue(calendar.is_visible())
            page.locator('#dateDropdown .dropdown-menu').evaluate('e=>e.scrollTop=e.scrollHeight')
            page.locator('button[onclick="selectCalendarToday()"]').click()
            self.assertRegex(page.locator('#dateFilter').input_value(),r'^\d{4}-\d{2}-\d{2}$')
            self.assertFalse(errors,errors)
    def test_search_keyboard_and_modal_escape(self):
        for width in (1440,390):
            page,errors=self.page(width);page.goto('http://ui.test/tools',wait_until='domcontentloaded')
            page.locator('.tool-details summary').click()
            trigger=page.locator('select[name=kind]').locator('..').locator('.coffee-select-trigger');trigger.click()
            search=page.locator('.coffee-select-search');search.fill('no matching option')
            self.assertTrue(page.locator('.coffee-select-empty').is_visible())
            search.fill('');search.press('ArrowDown');page.keyboard.press('Enter')
            self.assertFalse(page.locator('.coffee-select-dialog').is_visible())
            page.goto('http://ui.test/',wait_until='domcontentloaded');page.evaluate('openPostFilterModal()')
            modal=page.locator('#postFilterModal');page.wait_for_timeout(450)
            self.assertEqual(modal.locator('[role=dialog]').count(),1)
            modal.locator('button').last.focus();page.keyboard.press('Tab')
            self.assertTrue(modal.evaluate('e=>e.contains(document.activeElement)'))
            page.keyboard.press('Escape');modal.wait_for(state='hidden')
            self.assertFalse(errors,errors)
    def test_result_card_reverses_and_nested_picker_keeps_modal_open(self):
        for width in (1440,390):
            page,errors=self.page(width);page.goto('http://ui.test/result/'+self.identifier,wait_until='domcontentloaded')
            header=page.locator('.eksikler-section-header[data-index]').first
            body=page.locator('#eksiklerSection-1');header.press('Enter');page.wait_for_timeout(350)
            header.press('Enter');header.press('Enter');page.wait_for_timeout(350)
            self.assertFalse(body.evaluate("e=>e.classList.contains('collapsed')"))
            header.press('Enter');page.wait_for_timeout(350)
            self.assertEqual(body.bounding_box(),None)
            header.press('Enter');page.wait_for_timeout(350)
            self.assertGreater(body.bounding_box()['height'],0)
            page.get_by_role('button',name='Grubu Değiştir',exact=True).click()
            dialog=page.locator('.result-group-dialog');page.wait_for_function("document.querySelector('.result-group-dialog [data-preferences]').textContent.includes('1 üye')")
            for field in ('group','mode','post'):
                dialog.locator('[data-'+field+']').locator('..').locator('.coffee-select-trigger').click()
                menu=page.locator('.coffee-select-dialog');self.assertTrue(menu.evaluate("e=>!!e.closest('dialog[open]')"))
                menu.locator('input').press('Escape');self.assertTrue(dialog.is_visible())
            self.assertFalse(errors,errors)
