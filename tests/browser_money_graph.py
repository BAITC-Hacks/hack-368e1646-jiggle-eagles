"""Real browser + local Python backend. Synthetic by default; opt in to private data.

MONEY_GRAPH_TEST_DATA=/path/to/parquet python -m unittest discover -s tests -p 'browser_*.py' -v
"""
import os
from pathlib import Path
import tempfile
import threading
import unittest

from playwright.sync_api import expect, sync_playwright

from money_graph.pipeline import run
from money_graph.server import make_server
from test_money_graph import write_fixture


class BrowserJourney(unittest.TestCase):
    def test_search_directed_links_coloring_explanations_isolate_boundary_and_errors(self):
        with tempfile.TemporaryDirectory() as temporary, sync_playwright() as playwright:
            root = Path(temporary)
            write_fixture(root / 'synthetic')
            datasets = [('synthetic', root / 'synthetic')]
            if os.environ.get('MONEY_GRAPH_TEST_DATA'):
                datasets.append(('official', Path(os.environ['MONEY_GRAPH_TEST_DATA'])))
            browser = playwright.chromium.launch()
            try:
                for name, data_dir in datasets:
                    with self.subTest(dataset=name):
                        result, _ = run(data_dir, root / name / 'output')
                        with make_server(result, root / name / 'output', 0) as server:
                            thread = threading.Thread(target=server.serve_forever, daemon=True)
                            thread.start()
                            page = browser.new_page(viewport={'width': 1440, 'height': 1100})
                            failures, external = [], []
                            page.on('pageerror', lambda error: failures.append(str(error)))
                            page.on('request', lambda request: external.append(request.url) if not request.url.startswith('http://127.0.0.1:') else None)
                            try:
                                page.goto(f'http://127.0.0.1:{server.server_port}')
                                expect(page.locator('#account-area')).to_be_visible()
                                expect(page.locator('.queue-item')).to_have_count(len(result.top))

                                def search(gid):
                                    page.get_by_label('Find a client ID').fill(str(gid))
                                    page.get_by_role('button', name='Inspect account →', exact=True).click()
                                    expect(page.locator('#account-id')).to_have_text(f'Client {gid}')
                                    expect(page.locator('#account-area')).to_be_visible()

                                node = next(n for n in result.nodes if n['in_deg'] > 0 and n['out_deg'] > 0)
                                search(node['gid'])
                                expect(page.locator('#evidence')).to_have_text(node['evidence'])
                                paths = page.locator('path.edge')
                                self.assertGreater(paths.count(), 0)
                                for path in paths.all():
                                    a, b = int(path.get_attribute('data-src')), int(path.get_attribute('data-dst'))
                                    self.assertTrue(result.graph.has_edge(a, b))
                                    self.assertEqual(path.get_attribute('marker-end'), 'url(#arrow)')
                                page.get_by_label('Color by').select_option('cluster')
                                expect(page.locator('#legend')).to_contain_text('Community')
                                page.get_by_text('How confidence and priority were calculated', exact=True).click()
                                expect(page.locator('#scoring')).to_contain_text('Priority contributions')
                                # A visible graph node opens its real account card.
                                visible = page.locator('.graph-node').all()
                                peer = next(g for g in visible if g.get_attribute('data-gid') != str(node['gid']))
                                peer_id = peer.get_attribute('data-gid')
                                peer.click()
                                expect(page.locator('#account-id')).to_have_text(f'Client {peer_id}')

                                isolate = next(n for n in result.nodes if result.graph.degree(n['gid']) == 0)
                                search(isolate['gid'])
                                expect(page.locator('#graph-caption')).to_contain_text('Isolated account')
                                expect(page.locator('.graph-node')).to_have_count(1)
                                expect(page.locator('path.edge')).to_have_count(0)
                                boundary = next(n for n in result.nodes if n['depth'] == 4 and n['out_deg'] == 0)
                                search(boundary['gid'])
                                expect(page.locator('#account-warning')).to_contain_text('onward transfers are unknown')
                                self.assertNotEqual(boundary['role'], 'terminal')
                                expect(page.locator('#role-badge')).not_to_contain_text('terminal')

                                large = next((n for n in result.nodes if len(set(result.graph.predecessors(n['gid'])) | set(result.graph.successors(n['gid']))) > 16), None)
                                if large:
                                    search(large['gid'])
                                    expect(page.locator('#next')).to_be_enabled()
                                    first = page.locator('#graph-caption').inner_text()
                                    page.locator('#next').click()
                                    self.assertNotEqual(first, page.locator('#graph-caption').inner_text())
                                    page.locator('#previous').click()
                                    expect(page.locator('#graph-caption')).to_have_text(first)

                                for gid, message in [('not-an-id', 'exact decimal'), ('-9223372036854775808', 'not found')]:
                                    page.get_by_label('Find a client ID').fill(gid)
                                    page.get_by_role('button', name='Inspect account →', exact=True).click()
                                    expect(page.get_by_role('alert')).to_contain_text(message)
                                    expect(page.locator('#account-area')).to_be_hidden()
                                search(result.top[0]['gid'])
                                with page.expect_download() as download:
                                    page.get_by_role('link', name='nodes_roles.csv ↗').click()
                                self.assertEqual(download.value.suggested_filename, 'nodes_roles.csv')
                                self.assertEqual(external, [])
                                self.assertEqual(failures, [])
                                if name == 'official' and os.environ.get('MONEY_GRAPH_SCREENSHOT'):
                                    page.screenshot(path=os.environ['MONEY_GRAPH_SCREENSHOT'], full_page=True)
                                page.set_viewport_size({'width': 390, 'height': 844})
                                search(isolate['gid'])
                                self.assertLessEqual(page.evaluate('document.documentElement.scrollWidth'), 390)
                            finally:
                                page.close()
                                server.shutdown()
                                thread.join()
            finally:
                browser.close()
