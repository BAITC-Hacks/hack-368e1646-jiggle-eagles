"""Regression for opening the dashboard HTML directly instead of its local URL."""
from pathlib import Path
import unittest

from playwright.sync_api import expect, sync_playwright


class FilePreviewJourney(unittest.TestCase):
    def test_file_entry_is_styled_actionable_and_never_calls_the_api(self):
        entry = Path(__file__).resolve().parents[1] / 'money_graph' / 'static' / 'index.html'
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            try:
                for locale, heading, language in [
                    ('en-US', 'Open the local dashboard', 'en'),
                    ('ru-RU', 'Откройте локальную панель', 'ru'),
                    ('kk-KZ', 'Жергілікті бақылау тақтасын ашыңыз', 'kk'),
                    ('kz', 'Жергілікті бақылау тақтасын ашыңыз', 'kk'),
                    ('fr-FR', 'Open the local dashboard', 'en'),
                ]:
                    with self.subTest(locale=locale):
                        page = browser.new_page(locale=locale, color_scheme='light', viewport={'width': 390, 'height': 844})
                        requests, errors, failed = [], [], []
                        page.on('request', lambda request: requests.append(request.url))
                        page.on('pageerror', lambda error: errors.append(str(error)))
                        page.on('requestfailed', lambda request: failed.append(request.url))
                        try:
                            page.goto(entry.as_uri())
                            expect(page.get_by_role('heading', name=heading, exact=True)).to_be_visible()
                            expect(page.locator('html')).to_have_attribute('lang', language)
                            expect(page.locator('#file-preview a')).to_have_attribute('href', 'http://127.0.0.1:8765/')
                            expect(page.locator('#file-preview code')).to_have_text('./scripts/money-graph.sh --serve --upload-only')
                            expect(page.locator('input, button, form')).to_have_count(0)
                            # Relative assets must load even from a file URL.
                            self.assertEqual(page.locator('header').evaluate('(node) => getComputedStyle(node).backgroundColor'), 'rgb(255, 255, 255)')
                            self.assertLessEqual(page.evaluate('document.documentElement.scrollWidth'), 390)
                            self.assertFalse(any('/api/' in url or url.startswith(('http:', 'https:')) for url in requests))
                            self.assertFalse(any(url.endswith('/app.js') for url in requests))
                            self.assertEqual(errors, [])
                            self.assertEqual(failed, [])
                        finally:
                            page.close()
            finally:
                browser.close()
