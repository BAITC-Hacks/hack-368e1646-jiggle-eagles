"""Theme preferences and the approved interface, against the real local server."""
import json
from pathlib import Path
import tempfile
import threading
import unittest

from playwright.sync_api import expect, sync_playwright

from money_graph.pipeline import run
from money_graph.server import make_server
from test_money_graph import BASE, expansion_fixture, write_fixture


class ThemeJourney(unittest.TestCase):
    def test_themes_preserve_investigation_and_upload_state(self):
        with tempfile.TemporaryDirectory() as temporary, sync_playwright() as playwright:
            root = Path(temporary)
            write_fixture(root / 'input', expansion_fixture())
            result, _ = run(root / 'input', root / 'out')
            with make_server(result, root / 'out', 0) as server:
                thread = threading.Thread(target=server.serve_forever, daemon=True)
                thread.start()
                browser = playwright.chromium.launch()
                page = browser.new_page(locale='en-GB', color_scheme='light', viewport={'width': 1440, 'height': 1000})
                failures, requests = [], []
                page.on('pageerror', lambda error: failures.append(str(error)))
                page.on('request', lambda request: requests.append(request.url))
                base = f'http://127.0.0.1:{server.server_port}'
                try:
                    page.goto(base + '/analyses/startup')
                    expect(page.locator('#account-area')).to_be_visible()
                    expect(page.locator('#theme')).to_have_value('system')
                    page.locator('#gid').fill(str(BASE + 61))
                    page.locator('#search-form button').click()
                    expect(page.locator('#account-id')).to_have_text(f'Client {BASE + 61}')
                    page.locator('#expand').click()
                    expect(page.locator('#graph-caption')).to_contain_text('2 hops')
                    page.locator('#zoom-in').click()
                    page.locator('#color-mode').select_option('cluster')
                    transform = page.locator('#graph-viewport').get_attribute('transform')
                    edges = page.locator('.edge').count()
                    page.locator('#gid').fill('unsent-search')
                    page.locator('#show-analyses').click()
                    expect(page.locator('#results')).to_be_hidden()
                    for name in ('nodes', 'edges', 'transactions'):
                        page.locator('#upload-' + name).set_input_files(root / 'input' / f'{name}.parquet')
                    page.locator('#show-results').click()
                    before = len(requests)
                    fills = []
                    for theme, canvas, surface, text in [
                            ('dark', 'rgb(23, 26, 24)', 'rgb(34, 39, 36)', 'rgb(242, 245, 242)'),
                            ('light', 'rgb(245, 246, 247)', 'rgb(255, 255, 255)', 'rgb(25, 25, 25)')]:
                        page.locator('#theme').select_option(theme)
                        expect(page.locator('html')).to_have_attribute('data-theme', theme)
                        self.assertEqual(page.locator('html').evaluate('(el) => getComputedStyle(el).backgroundColor'), canvas)
                        self.assertEqual(page.locator('.account').evaluate('(el) => getComputedStyle(el).backgroundColor'), surface)
                        self.assertEqual(page.locator('#account-id').evaluate('(el) => getComputedStyle(el).color'), text)
                        fills.append(page.locator('.graph-node circle:not(.selection-ring)').first.evaluate('(el) => getComputedStyle(el).fill'))
                        self.assertEqual(page.locator('#graph-viewport').get_attribute('transform'), transform)
                        self.assertEqual(page.locator('.edge').count(), edges)
                        expect(page.locator('#gid')).to_have_value('unsent-search')
                        expect(page.locator('#color-mode')).to_have_value('cluster')
                        expect(page.locator('#graph-caption')).to_contain_text('2 hops')
                        page.locator('#back-analyses').click()
                        for name in ('nodes', 'edges', 'transactions'):
                            self.assertEqual(page.locator('#upload-' + name).evaluate('(el) => el.files[0].name'), f'{name}.parquet')
                        for locale in ('ru', 'kk', 'en'):
                            page.locator('#language').select_option(locale)
                            expect(page.locator('#theme')).to_have_value(theme)
                            page.set_viewport_size({'width': 390, 'height': 844})
                            self.assertLessEqual(page.evaluate('document.documentElement.scrollWidth'), 390)
                            expect(page.locator('#theme')).to_be_visible()
                            page.locator('.edit-details').click()
                            expect(page.locator('#details-dialog')).to_be_visible()
                            self.assertEqual(page.locator('#details-dialog').evaluate('(el) => getComputedStyle(el).backgroundColor'), surface)
                            page.locator('#details-title').fill('Unchanged draft')
                            page.keyboard.press('Escape')
                            expect(page.locator('#details-dialog')).to_be_hidden()
                        page.locator('#show-results').click()
                        self.assertLessEqual(page.evaluate('document.documentElement.scrollWidth'), 390)
                        page.set_viewport_size({'width': 1440, 'height': 1000})
                        page.locator('#gid').focus()
                        self.assertNotEqual(page.locator('#gid').evaluate('(el) => getComputedStyle(el).outlineStyle'), 'none')
                    self.assertNotEqual(fills[0], fills[1], 'SVG colors must adapt with the surrounding surfaces')
                    self.assertEqual(len(requests), before, 'Theme, locale and view changes must not refetch the analysis')
                    page.reload()
                    expect(page.locator('#theme')).to_have_value('light')
                    expect(page.locator('html')).to_have_attribute('data-theme', 'light')
                    self.assertEqual(failures, [])
                    self.assertTrue(all(url.startswith(base) for url in requests))
                finally:
                    browser.close()
                    server.shutdown()
                    thread.join()

    def test_system_preference_persistence_invalid_and_blocked_storage(self):
        with tempfile.TemporaryDirectory() as temporary, sync_playwright() as playwright:
            with make_server(None, Path(temporary), 0) as server:
                thread = threading.Thread(target=server.serve_forever, daemon=True)
                thread.start()
                browser = playwright.chromium.launch()
                base = f'http://127.0.0.1:{server.server_port}'
                try:
                    for saved, expected in [(None, 'dark'), ('invalid', 'dark'), ('light', 'light'), ('dark', 'dark')]:
                        context = browser.new_context(locale='en-GB', color_scheme='dark')
                        if saved is not None:
                            context.add_init_script(f'localStorage.setItem("money-graph.theme", {json.dumps(saved)})')
                        page = context.new_page()
                        page.goto(base)
                        expect(page.locator('html')).to_have_attribute('data-theme', expected)
                        page.emulate_media(color_scheme='light')
                        expect(page.locator('html')).to_have_attribute('data-theme', 'dark' if saved == 'dark' else 'light')
                        context.close()
                    context = browser.new_context(locale='en-GB', color_scheme='light')
                    page = context.new_page()
                    page.goto(base)
                    page.locator('#theme').select_option('dark')
                    page.reload()
                    expect(page.locator('#theme')).to_have_value('dark')
                    expect(page.locator('html')).to_have_attribute('data-theme', 'dark')
                    page.locator('#theme').select_option('system')
                    expect(page.locator('html')).to_have_attribute('data-theme', 'light')
                    page.emulate_media(color_scheme='dark')
                    expect(page.locator('html')).to_have_attribute('data-theme', 'dark')
                    context.close()
                    context = browser.new_context(locale='en-GB', color_scheme='dark')
                    context.add_init_script('Object.defineProperty(window, "localStorage", {get() {throw new Error("blocked")}})')
                    page = context.new_page()
                    failures = []
                    page.on('pageerror', lambda error: failures.append(str(error)))
                    page.goto(base)
                    expect(page.locator('html')).to_have_attribute('data-theme', 'dark')
                    page.locator('#theme').select_option('light')
                    expect(page.locator('html')).to_have_attribute('data-theme', 'light')
                    page.reload()
                    expect(page.locator('#theme')).to_have_value('system')
                    expect(page.locator('html')).to_have_attribute('data-theme', 'dark')
                    self.assertEqual(failures, [])
                    context.close()
                finally:
                    browser.close()
                    server.shutdown()
                    thread.join()
