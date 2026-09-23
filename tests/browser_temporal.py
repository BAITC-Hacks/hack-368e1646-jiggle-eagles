"""Real HTTP + browser checks for dated evidence and translated presentation."""
from pathlib import Path
import tempfile
import threading
import unittest

from playwright.sync_api import sync_playwright, expect

from money_graph.pipeline import run
from money_graph.server import make_server
from test_money_graph import write_fixture
from test_temporal import dated_fixture


class TemporalBrowserTests(unittest.TestCase):
    def test_dated_evidence_and_same_day_ambiguity(self):
        with tempfile.TemporaryDirectory() as directory, sync_playwright() as p:
            root = Path(directory)
            write_fixture(root / 'input', dated_fixture([
                (1, 2, 1, 5000), (5, 2, 1, 5000), (6, 2, 1, 5000), (2, 3, 2, 15000),
                (1, 4, 3, 10000), (4, 3, 3, 10000)]))
            result, _ = run(root / 'input', root / 'output')
            with make_server(result, root / 'output', 0) as server:
                thread = threading.Thread(target=server.serve_forever, daemon=True)
                thread.start()
                browser = p.chromium.launch()
                try:
                    page = browser.new_page(locale='en-GB')
                    errors = []
                    page.on('pageerror', lambda error: errors.append(str(error)))
                    page.goto(f'http://127.0.0.1:{server.server_port}')
                    expect(page.locator('#account-area')).to_be_visible()
                    def search(gid):
                        page.locator('#gid').fill(gid)
                        page.locator('#search-form button').click()
                        expect(page.locator('#account-id')).to_contain_text(gid)
                    search('2')
                    expect(page.locator('#role-badge')).to_contain_text('transit')
                    expect(page.locator('#patterns li')).to_have_count(2)
                    expect(page.locator('[data-pattern="pattern.collection"]')).to_contain_text('3 incoming')
                    expect(page.locator('[data-pattern="pattern.transit"]')).to_contain_text('100%')
                    expect(page.locator('#temporal')).to_contain_text('100%')
                    page.locator('#temporal summary').click()
                    expect(page.locator('#temporal li')).to_contain_text('15,000')
                    search('4')
                    expect(page.locator('#role-badge')).not_to_contain_text('transit')
                    expect(page.locator('#patterns')).to_contain_text('None of these three')
                    expect(page.locator('#temporal')).to_contain_text('Order within the day is unknown')
                    expect(page.locator('#temporal')).to_contain_text('(0%')
                    page.locator('#language').select_option('ru')
                    expect(page.locator('#temporal')).to_contain_text('Порядок внутри дня неизвестен')
                    expect(page.locator('#patterns')).to_contain_text('Наблюдаемые признаки')
                    page.locator('#language').select_option('kk')
                    expect(page.locator('#temporal')).to_contain_text('Күн ішіндегі реті белгісіз')
                    self.assertEqual(errors, [])
                finally:
                    browser.close()
                    server.shutdown()
                    thread.join()
