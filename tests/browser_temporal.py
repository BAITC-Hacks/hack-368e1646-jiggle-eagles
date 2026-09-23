"""Real HTTP + browser checks for dated evidence and translated presentation."""
import json
from pathlib import Path
import tempfile
import threading
import unittest

from playwright.sync_api import sync_playwright, expect

from money_graph.pipeline import SCHEMAS, json_bytes, run, sha256
from money_graph.server import make_server
from test_money_graph import write_fixture
from test_temporal import dated_fixture


class TemporalBrowserTests(unittest.TestCase):
    def test_reopen_saved_analysis_without_temporal_fields(self):
        with tempfile.TemporaryDirectory() as directory, sync_playwright() as p:
            root = Path(directory)
            write_fixture(root / 'input', dated_fixture([
                (1, 2, 1, 15000), (2, 3, 2, 15000)]))
            out = root / 'output'
            _, manifest = run(root / 'input', out)
            # Reproduce the saved dashboard schema from before MG-TIME-01.
            dashboard = json.loads((out / 'dashboard.json').read_bytes())
            for account in dashboard['nodes']:
                del account['temporal']
                del account['patterns']
            (out / 'dashboard.json').write_bytes(json_bytes(dashboard))
            manifest['outputs']['dashboard.json'] = sha256(out / 'dashboard.json')
            (out / 'run_manifest.json').write_bytes(json_bytes(manifest))
            original = {name: (out / name).read_bytes()
                        for name in [*SCHEMAS, 'dashboard.json', 'run_manifest.json']}
            new_id = 'a' * 32
            run(root / 'input', out / 'uploads' / new_id / 'output')
            with make_server(None, out, 0) as server:
                thread = threading.Thread(target=server.serve_forever, daemon=True)
                thread.start()
                browser = p.chromium.launch()
                try:
                    page = browser.new_page(locale='en-GB')
                    errors = []
                    page.on('pageerror', lambda error: errors.append(str(error)))
                    base = f'http://127.0.0.1:{server.server_port}'
                    page.goto(base + '/analyses/startup')
                    expect(page.locator('#account-area')).to_be_visible()
                    page.locator('#gid').fill('2')
                    page.locator('#search-form button').click()
                    expect(page.locator('#account-id')).to_contain_text('2')
                    expect(page.locator('#role-badge')).to_contain_text('transit')
                    for locale in ['en', 'ru', 'kk']:
                        catalog = json.loads((Path(__file__).resolve().parents[1] /
                            f'money_graph/static/locales/{locale}.json').read_bytes())
                        page.locator('#language').select_option(locale)
                        expect(page.locator('#patterns')).to_contain_text(catalog['pattern.unavailable'])
                        expect(page.locator('#temporal')).to_contain_text(catalog['temporal.unavailable'])
                        expect(page.locator('#rule')).to_have_text(catalog['rule.transitLegacy'])
                        expect(page.locator('#temporal details')).to_have_count(0)
                    for name in [*SCHEMAS, 'run_manifest.json']:
                        response = page.request.get(base + '/exports/' + name + '?revision=startup')
                        self.assertEqual(response.status, 200)
                        self.assertEqual(response.body(), original[name])
                    page.locator('#language').select_option('en')
                    page.goto(base + '/analyses/' + new_id)
                    expect(page.locator('#account-area')).to_be_visible()
                    page.locator('#gid').fill('2')
                    page.locator('#search-form button').click()
                    expect(page.locator('#temporal')).to_contain_text('100%')
                    expect(page.locator('#patterns li')).to_have_count(1)
                    expect(page.locator('#rule')).to_contain_text('80%')
                    self.assertEqual(errors, [])
                    self.assertEqual({name: (out / name).read_bytes() for name in original}, original)
                finally:
                    browser.close()
                    server.shutdown()
                    thread.join()

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
                    page.goto(f'http://127.0.0.1:{server.server_port}/analyses/startup')
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
