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
from test_money_graph import BASE, expansion_fixture, write_fixture


class BrowserJourney(unittest.TestCase):
    def test_analysis_page_urls_reload_history_and_direct_reopen(self):
        with tempfile.TemporaryDirectory() as temporary, sync_playwright() as playwright:
            root = Path(temporary)
            write_fixture(root / 'first')
            write_fixture(root / 'second', expansion_fixture())
            startup, _ = run(root / 'first', root / 'out')
            saved_id = 'a' * 32
            run(root / 'second', root / 'out' / 'uploads' / saved_id / 'output')
            browser = playwright.chromium.launch()
            try:
                for restarting in (False, True):
                    with make_server(None if restarting else startup, root / 'out', 0) as server:
                        thread = threading.Thread(target=server.serve_forever, daemon=True)
                        thread.start()
                        page = browser.new_page(locale='en-GB')
                        failures, failed_requests = [], []
                        page.on('pageerror', lambda error: failures.append(str(error)))
                        page.on('response', lambda response: failed_requests.append(response.url)
                                if response.status >= 400 else None)
                        base = f'http://127.0.0.1:{server.server_port}'
                        try:
                            if not restarting:
                                page.goto(base)
                                expect(page).to_have_url(base + '/analyses')
                                expect(page.locator('#analysis-home')).to_be_visible()
                                expect(page.locator('#results')).to_be_hidden()
                                expect(page.locator('.history-row')).to_have_count(2)
                                page.locator('[data-analysis-id="startup"]').get_by_role('button', name='View results').click()
                                expect(page).to_have_url(base + '/analyses/startup')
                                expect(page.locator('#summary')).to_contain_text('30')
                                expect(page.locator('#account-area')).to_be_visible()
                                expect(page.locator('#analysis-home')).to_be_hidden()
                                page.locator('#zoom-in').click()
                                transform = page.locator('#graph-viewport').get_attribute('transform')
                                page.go_back()
                                expect(page).to_have_url(base + '/analyses')
                                expect(page.locator('#results')).to_be_hidden()
                                page.go_forward()
                                expect(page.locator('#account-area')).to_be_visible()
                                self.assertEqual(page.locator('#graph-viewport').get_attribute('transform'), transform)
                                page.locator('#back-analyses').click()
                                page.reload()
                                expect(page).to_have_url(base + '/analyses')
                                expect(page.locator('#results')).to_be_hidden()
                            # A pasted nested URL also restores the run after an upload-only restart.
                            page.goto(base + '/analyses/' + saved_id)
                            expect(page.locator('#account-area')).to_be_visible()
                            expect(page.locator('#summary')).to_contain_text('80')
                            expect(page.locator('#analysis-home')).to_be_hidden()
                            self.assertEqual(server.status()['revision'], saved_id)
                            # Refresh must obey the URL even when another tab selected another analysis.
                            response = page.request.post(base + '/api/analyses/startup/open', headers={'Origin': base})
                            self.assertEqual(response.status, 200)
                            export = page.locator('.downloads a').first.get_attribute('href')
                            self.assertEqual(page.request.get(export).status, 409)
                            page.reload()
                            expect(page).to_have_url(base + '/analyses/' + saved_id)
                            expect(page.locator('#account-area')).to_be_visible()
                            expect(page.locator('#summary')).to_contain_text('80')
                            self.assertEqual(server.status()['revision'], saved_id)
                            self.assertEqual(failed_requests, [], 'Nested pages must load all scripts, styles and API data')
                            page.goto(base + '/analyses/' + '0' * 32)
                            expect(page.locator('#error')).to_contain_text('no longer available')
                            expect(page.locator('#analysis-home')).to_be_hidden()
                            expect(page.locator('#results-workspace')).to_be_hidden()
                            self.assertEqual(server.status()['revision'], saved_id)
                            page.locator('#back-analyses').click()
                            expect(page).to_have_url(base + '/analyses')
                            expect(page.locator('#analysis-home')).to_be_visible()
                            expect(page.locator('#error')).to_be_hidden()
                            page.locator('#show-results').click()
                            expect(page).to_have_url(base + '/analyses/' + saved_id)
                            expect(page.locator('#summary')).to_contain_text('80')
                            expect(page.locator('#account-area')).to_be_visible()
                            self.assertEqual(failures, [])
                        finally:
                            page.close()
                            server.shutdown()
                            thread.join()
            finally:
                browser.close()

    def test_analysis_home_history_reopen_and_restart(self):
        with tempfile.TemporaryDirectory() as temporary, sync_playwright() as playwright:
            root = Path(temporary)
            write_fixture(root / 'first')
            write_fixture(root / 'second', expansion_fixture())
            browser = playwright.chromium.launch()
            first_id = None
            first_export = None
            title = 'July review · Шілде <img src=x>'
            description = 'Notes for review.\nПроверить переводы.'
            try:
                for restarting in (False, True):
                    with make_server(None, root / 'out', 0) as server:
                        thread = threading.Thread(target=server.serve_forever, daemon=True)
                        thread.start()
                        page = browser.new_page(viewport={'width': 1440, 'height': 1000}, locale='en-GB')
                        failures = []
                        page.on('pageerror', lambda error: failures.append(str(error)))
                        base = f'http://127.0.0.1:{server.server_port}'
                        try:
                            page.goto(base)
                            expect(page.locator('#results')).to_be_hidden()
                            if not restarting:
                                expect(page.locator('#history-list')).to_contain_text('No analyses yet')
                                self.assertLess(page.locator('.upload').bounding_box()['y'], page.locator('.history').bounding_box()['y'])
                                for index, directory in enumerate(('first', 'second', 'second')):
                                    page.locator('#show-analyses').click()
                                    for name in ('nodes', 'edges', 'transactions'):
                                        page.locator('#upload-' + name).set_input_files(root / directory / f'{name}.parquet')
                                    page.locator('#analyze').click()
                                    expect(page.locator('.history-row')).to_have_count(index + 1)
                                    expect(page.locator('#results')).to_be_visible()
                                    expect(page.locator('#analyze')).to_be_enabled()
                                    if index == 0:
                                        first_id = page.locator('.history-row').get_attribute('data-analysis-id')
                                        expect(page).to_have_url(base + '/analyses/' + first_id)
                                        first_export = page.request.get(base + '/exports/nodes_roles.csv').body()
                                page.locator('#show-analyses').click()
                                expect(page.locator('.history-row').first).to_contain_text('Same files as an earlier analysis')
                                expect(page.locator('#summary')).to_contain_text('80')
                            else:
                                expect(page.locator('.history-row')).to_have_count(3)
                                expect(page.locator('#account-area')).to_be_hidden()
                            first = page.locator(f'.history-row[data-analysis-id="{first_id}"]')
                            if restarting:
                                expect(first.locator('h3')).to_have_text(title)
                                expect(first.locator('.history-description')).to_have_text(description)
                            first.get_by_role('button', name='Open analysis', exact=True).click()
                            expect(first).to_contain_text('Current analysis')
                            expect(page.locator('#account-area')).to_be_visible()
                            expect(page.locator('#summary')).to_contain_text('30')
                            self.assertEqual(page.request.get(base + '/exports/nodes_roles.csv').body(), first_export)
                            page.locator('#show-analyses').click()
                            first.get_by_role('button', name='Edit details', exact=True).click()
                            expect(page.locator('#details-dialog')).to_be_visible()
                            if not restarting:
                                page.get_by_label('Title', exact=True).fill('   ')
                                page.get_by_role('button', name='Save changes', exact=True).click()
                                expect(page.locator('#details-error')).to_contain_text('1–120')
                                page.get_by_label('Title', exact=True).fill(title)
                                page.get_by_label('Description (optional)', exact=True).fill(description)
                                # Language changes preserve an unsaved draft and localize the dialog.
                                page.evaluate("document.getElementById('language').value = 'kk'; document.getElementById('language').dispatchEvent(new Event('change'))")
                                expect(page.locator('#details-heading')).to_have_text('Талдау мәліметтерін өңдеу')
                                expect(page.locator('#details-title')).to_have_value(title)
                                expect(page.locator('#details-description')).to_have_value(description)
                                page.get_by_role('button', name='Өзгерістерді сақтау', exact=True).click()
                                expect(page.locator('#details-dialog')).to_be_hidden()
                                page.locator('#language').select_option('en')
                                expect(first.locator('h3')).to_have_text(title)
                                expect(first.locator('.history-description')).to_have_text(description)
                                expect(first.locator('img')).to_have_count(0)
                                expect(page.locator('#selected-analysis')).to_have_text(title)
                                first.get_by_role('button', name='Edit details', exact=True).click()
                                page.get_by_label('Title', exact=True).fill('Discard this draft')
                                page.get_by_role('button', name='Cancel', exact=True).click()
                                expect(first.locator('h3')).to_have_text(title)
                                page.reload()
                                expect(page).to_have_url(base + '/analyses')
                                expect(page.locator('#results')).to_be_hidden()
                                expect(first.locator('h3')).to_have_text(title)
                                expect(first.locator('.history-description')).to_have_text(description)
                            else:
                                expect(page.locator('#details-title')).to_have_value(title)
                                page.get_by_label('Description (optional)', exact=True).fill('')
                                page.get_by_role('button', name='Save changes', exact=True).click()
                                expect(page.locator('#details-dialog')).to_be_hidden()
                                expect(first.locator('.history-description')).to_have_count(0)
                            self.assertEqual(page.request.get(base + '/exports/nodes_roles.csv').body(), first_export)
                            for language, heading in [('kk', 'Алдыңғы талдаулар'), ('ru', 'Предыдущие анализы'), ('en', 'Previous analyses')]:
                                page.locator('#language').select_option(language)
                                expect(page.locator('#history-title')).to_have_text(heading)
                                expect(page.locator('.history-row')).to_have_count(3)
                            if not restarting:
                                # A damaged older run reports the error without losing the selected analysis.
                                damaged = page.locator('.history-row').first.get_attribute('data-analysis-id')
                                (root / 'out' / 'uploads' / damaged / 'output' / 'top_nodes.csv').write_bytes(b'damaged')
                                page.locator('.history-row').first.get_by_role('button', name='Open analysis').click()
                                expect(page.locator('#error')).to_contain_text('missing or damaged')
                                expect(page.locator('#results-workspace')).to_be_hidden()
                                page.locator('#back-analyses').click()
                                expect(first).to_contain_text('Current analysis')
                                page.locator('#show-results').click()
                                expect(page.locator('#summary')).to_contain_text('30')
                                expect(page.locator('#account-area')).to_be_visible()
                                page.locator('#back-analyses').click()
                                self.assertEqual(page.request.get(base + '/exports/nodes_roles.csv').body(), first_export)
                            page.evaluate('window.scrollTo(0, 0)')
                            screenshot = os.environ.get('MONEY_GRAPH_INTERFACE_SCREENSHOT')
                            if restarting and screenshot:
                                page.screenshot(path=screenshot)
                            page.set_viewport_size({'width': 390, 'height': 844})
                            page.locator('#language').select_option('ru')
                            first.get_by_role('button', name='Изменить сведения', exact=True).click()
                            expect(page.locator('#details-dialog')).to_be_visible()
                            self.assertLessEqual(page.locator('#details-dialog').bounding_box()['width'], 390)
                            self.assertLessEqual(page.evaluate('document.documentElement.scrollWidth'), 390)
                            if restarting and screenshot:
                                page.screenshot(path=str(Path(screenshot).with_stem('interface-mobile')))
                            page.get_by_role('button', name='Отмена', exact=True).click()
                            self.assertEqual(failures, [])
                        finally:
                            page.close()
                            server.shutdown()
                            thread.join()
            finally:
                browser.close()

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
                                page.goto(f'http://127.0.0.1:{server.server_port}/analyses/startup')
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

                                # Expansion is bounded even on the supplied high-degree graph.
                                search(result.top[0]['gid'])
                                page.get_by_role('button', name='Expand to two hops', exact=True).click()
                                expect(page.locator('#graph-caption')).to_contain_text('2 hops')
                                self.assertLessEqual(page.locator('.graph-node').count(), 50)
                                expect(page.locator('#node-limit')).to_contain_text('50 accounts')
                                page.get_by_role('button', name='Reset graph', exact=True).click()
                                expect(page.locator('#graph-caption')).to_contain_text('1 hop')

                                for gid, message in [('not-an-id', 'exact decimal'), ('-9223372036854775808', 'not found')]:
                                    page.get_by_label('Find a client ID').fill(gid)
                                    page.get_by_role('button', name='Inspect account →', exact=True).click()
                                    expect(page.locator('#error')).to_contain_text(message)
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


    def test_upload_validation_preserves_results_and_two_hop_controls(self):
        with tempfile.TemporaryDirectory() as temporary, sync_playwright() as playwright:
            root = Path(temporary)
            write_fixture(root / 'initial')
            write_fixture(root / 'valid', expansion_fixture())
            bad = list(expansion_fixture())
            bad[1].loc[0, 'n_tx'] = 999
            write_fixture(root / 'bad', bad)
            write_fixture(root / 'corrupt')
            (root / 'corrupt' / 'nodes.parquet').write_bytes(b'not parquet')
            result, _ = run(root / 'initial', root / 'output')
            with make_server(result, root / 'output', 0) as server:
                thread = threading.Thread(target=server.serve_forever, daemon=True)
                thread.start()
                browser = playwright.chromium.launch()
                page = browser.new_page(viewport={'width': 1440, 'height': 1200})
                failures, external = [], []
                page.on('pageerror', lambda error: failures.append(str(error)))
                page.on('request', lambda request: external.append(request.url) if not request.url.startswith('http://127.0.0.1:') else None)
                base = f'http://127.0.0.1:{server.server_port}'
                try:
                    page.goto(base + '/analyses/startup')
                    expect(page.locator('#account-area')).to_be_visible()
                    previous_id = page.locator('#account-id').inner_text()
                    previous_summary = page.locator('#summary').inner_text()
                    previous_queue = page.locator('#queue').inner_text()
                    routes = ['/api/overview', '/api/account?gid='+str(BASE), '/exports/nodes_roles.csv', '/exports/clusters.csv', '/exports/top_nodes.csv', '/exports/run_manifest.json']
                    before = {route: page.request.get(base + route).body() for route in routes}
                    def upload(directory):
                        page.locator('#show-analyses').click()
                        for name in ['nodes', 'edges', 'transactions']:
                            page.locator('#upload-' + name).set_input_files(directory / f'{name}.parquet')
                        page.get_by_role('button', name='Analyze files', exact=True).click()
                    for folder, message in [('bad', 'counts differ'), ('corrupt', 'nodes.parquet: could not read valid Parquet')]:
                        upload(root / folder)
                        expect(page.locator('#upload-error')).to_contain_text(message)
                        expect(page.locator('#analysis-status')).to_contain_text('failed')
                        expect(page.locator('#analyze')).to_be_enabled()
                        page.locator('#show-results').click()
                        expect(page.locator('#account-id')).to_have_text(previous_id)
                        expect(page.locator('#summary')).to_have_text(previous_summary, use_inner_text=True)
                        expect(page.locator('#queue')).to_have_text(previous_queue, use_inner_text=True)
                        for route in routes:
                            self.assertEqual(before[route], page.request.get(base + route).body())
                    upload(root / 'valid')
                    expect(page.locator('#analysis-status')).to_contain_text('Analysis complete')
                    expect(page.locator('#summary')).to_contain_text('80')
                    expect(page.locator('#queue .queue-item')).to_have_count(50)
                    expect(page.locator('#upload-error')).to_be_hidden()
                    expect(page.locator('#analyze')).to_be_enabled()
                    manifest = page.request.get(base + '/exports/run_manifest.json').json()
                    self.assertEqual(manifest['profile']['nodes'], 80)
                    self.assertLess(manifest['elapsed_seconds'], 300)
                    def search(gid):
                        page.get_by_label('Find a client ID').fill(str(gid))
                        page.get_by_role('button', name='Inspect account →', exact=True).click()
                        expect(page.locator('#account-id')).to_have_text(f'Client {gid}')
                        expect(page.locator('#account-area')).to_be_visible()
                    search(BASE + 61)
                    expect(page.locator('.graph-node')).to_have_count(3)
                    expect(page.locator('#graph-caption')).to_contain_text('1 hop')
                    page.get_by_role('button', name='Expand to two hops', exact=True).click()
                    expect(page.locator('#graph-caption')).to_contain_text('2 hops')
                    expect(page.locator('.graph-node')).to_have_count(5)
                    expect(page.locator(f'.graph-node[data-gid="{BASE}"]')).to_have_count(1)
                    # This connection joins two visible peers, neither is the inspected account.
                    expect(page.locator(f'path.edge[data-src="{BASE}"][data-dst="{BASE+1}"]')).to_have_count(1)
                    before_zoom = page.locator('#graph-viewport').get_attribute('transform')
                    page.get_by_role('button', name='Zoom in', exact=True).click()
                    self.assertNotEqual(page.locator('#graph-viewport').get_attribute('transform'), before_zoom)
                    page.get_by_role('button', name='Zoom out', exact=True).click()
                    page.locator('#graph').scroll_into_view_if_needed()
                    box = page.locator('#graph').bounding_box()
                    before_pan = page.locator('#graph-viewport').get_attribute('transform')
                    page.mouse.move(box['x']+15, box['y']+15)
                    page.mouse.down()
                    page.mouse.move(box['x']+80, box['y']+70, steps=4)
                    page.mouse.up()
                    self.assertNotEqual(page.locator('#graph-viewport').get_attribute('transform'), before_pan)
                    page.get_by_role('button', name='Reset graph', exact=True).click()
                    expect(page.locator('#graph-caption')).to_contain_text('1 hop')
                    expect(page.locator('.graph-node')).to_have_count(3)
                    search(BASE)
                    expect(page.locator('.graph-node')).to_have_count(50)
                    expect(page.locator('#graph-caption')).to_contain_text('11 accounts omitted')
                    page.get_by_role('button', name='Expand to two hops', exact=True).click()
                    expect(page.locator('#graph-caption')).to_contain_text('12 accounts omitted')
                    expect(page.locator('.graph-node')).to_have_count(50)
                    expect(page.locator('#node-limit')).to_contain_text('50 accounts')
                    search(BASE + 79)
                    expect(page.locator('#graph-caption')).to_contain_text('Isolated account')
                    page.get_by_role('button', name='Expand to two hops', exact=True).click()
                    expect(page.locator('#graph-caption')).to_contain_text('2 hops')
                    expect(page.locator('.graph-node')).to_have_count(1)
                    expect(page.locator('#account-warning')).to_contain_text('onward transfers are unknown')
                    # Repeating the same upload yields byte-identical deterministic exports.
                    csvs = {name: page.request.get(base + '/exports/' + name).body() for name in ['nodes_roles.csv', 'clusters.csv', 'top_nodes.csv']}
                    previous_revision = page.request.get(base + '/api/status').json()['revision']
                    upload(root / 'valid')
                    expect(page.locator('#analysis-status')).to_contain_text('Analysis complete')
                    expect(page.locator('#analyze')).to_be_enabled()
                    self.assertNotEqual(previous_revision, page.request.get(base + '/api/status').json()['revision'])
                    for name, content in csvs.items():
                        self.assertEqual(content, page.request.get(base + '/exports/' + name).body())
                    page.set_viewport_size({'width': 390, 'height': 844})
                    self.assertLessEqual(page.evaluate('document.documentElement.scrollWidth'), 390)
                    self.assertEqual(failures, [])
                    self.assertEqual(external, [])
                    if os.environ.get('MONEY_GRAPH_V2_SCREENSHOT'):
                        page.set_viewport_size({'width': 1440, 'height': 1200})
                        search(BASE + 61)
                        page.locator('#expand').click()
                        expect(page.locator('#graph-caption')).to_contain_text('2 hops')
                        page.screenshot(path=os.environ['MONEY_GRAPH_V2_SCREENSHOT'], full_page=True)
                finally:
                    page.close()
                    browser.close()
                    server.shutdown()
                    thread.join()

    def test_first_upload_without_startup_data(self):
        with tempfile.TemporaryDirectory() as temporary, sync_playwright() as playwright:
            root = Path(temporary)
            write_fixture(root / 'input')
            with make_server(None, root / 'out', 0) as server:
                thread = threading.Thread(target=server.serve_forever, daemon=True)
                thread.start()
                browser = playwright.chromium.launch()
                page = browser.new_page()
                try:
                    page.goto(f'http://127.0.0.1:{server.server_port}')
                    expect(page.locator('#summary')).to_contain_text('Upload the three Parquet files to begin')
                    expect(page.locator('#account-area')).to_be_hidden()
                    for name in ['nodes', 'edges', 'transactions']:
                        page.locator('#upload-'+name).set_input_files(root / 'input' / f'{name}.parquet')
                    page.locator('#analyze').click()
                    expect(page.locator('#analysis-status')).to_contain_text('Analysis complete')
                    expect(page.locator('#account-area')).to_be_visible()
                    expect(page.locator('#summary')).to_contain_text('30')
                finally:
                    page.close()
                    browser.close()
                    server.shutdown()
                    thread.join()
    def test_language_switching_preserves_inspection_uploads_and_exports(self):
        with tempfile.TemporaryDirectory() as temporary, sync_playwright() as playwright:
            root = Path(temporary)
            write_fixture(root / 'input', expansion_fixture())
            bad = list(expansion_fixture())
            bad[1].loc[0, 'n_tx'] = 999
            write_fixture(root / 'bad', bad)
            result, _ = run(root / 'input', root / 'out')
            with make_server(result, root / 'out', 0) as server:
                thread = threading.Thread(target=server.serve_forever, daemon=True)
                thread.start()
                browser = playwright.chromium.launch()
                page = browser.new_page(locale='en-GB', viewport={'width': 1440, 'height': 1100})
                failures, requests = [], []
                page.on('pageerror', lambda error: failures.append(str(error)))
                page.on('request', lambda request: requests.append(request.url))
                base = f'http://127.0.0.1:{server.server_port}'
                try:
                    page.goto(base + '/analyses/startup')
                    expect(page.locator('#account-area')).to_be_visible()
                    page.locator('#gid').fill(str(BASE + 61))
                    page.locator('#search-form button').click()
                    expect(page.locator('#account-id')).to_have_text(f'Client {BASE + 61}')
                    page.locator('#expand').click()
                    expect(page.locator('#graph-caption')).to_contain_text('2 hops')
                    page.locator('#zoom-in').click()
                    page.locator('#color-mode').select_option('cluster')
                    page.locator('.account > details').evaluate('(node) => {node.open = true}')
                    transform = page.locator('#graph-viewport').get_attribute('transform')
                    edges = page.locator('.edge').count()
                    csvs = {name: page.request.get(base + '/exports/' + name).body()
                            for name in ['nodes_roles.csv', 'clusters.csv', 'top_nodes.csv']}
                    page.locator('#show-analyses').click()
                    for name in ['nodes', 'edges', 'transactions']:
                        page.locator('#upload-' + name).set_input_files(root / 'input' / f'{name}.parquet')
                    page.locator('#show-results').click()
                    page.locator('#gid').fill('unsent-search')
                    before = len(requests)
                    for locale, client, analyze, caption, community, month in [
                            ('ru', 'Клиент', 'Анализировать файлы', '2 шага', 'Гипотеза о наблюдаемом сообществе', 'июля'),
                            ('kk', 'Клиент', 'Файлдарды талдау', '2 қадам', 'Бақыланған қауымдастық туралы болжам', 'шілде'),
                            ('en', 'Client', 'Analyze files', '2 hops', 'Observed community hypothesis', 'July')]:
                        page.locator('#language').select_option(locale)
                        expect(page.locator('html')).to_have_attribute('lang', locale)
                        expect(page.locator('#account-id')).to_have_text(f'{client} {BASE + 61}')
                        expect(page.locator('#analyze')).to_have_text(analyze)
                        expect(page.locator('#graph-caption')).to_contain_text(caption)
                        expect(page.locator('#cluster-description')).to_contain_text(community)
                        expect(page.locator('#observation-period')).to_contain_text(month)
                        formatted = page.evaluate('async () => (await import("/i18n.js")).number(12345.67)')
                        self.assertEqual(formatted, '12,345.67' if locale == 'en' else '12\u00a0345,67')
                        expect(page.locator('#zoom-in')).to_have_attribute('aria-label', {'en': 'Zoom in', 'kk': 'Үлкейту', 'ru': 'Увеличить'}[locale])
                        expect(page.locator('#gid')).to_have_value('unsent-search')
                        expect(page.locator('#color-mode')).to_have_value('cluster')
                        self.assertTrue(page.locator('.account > details').evaluate('(node) => node.open'))
                        self.assertEqual(page.locator('#graph-viewport').get_attribute('transform'), transform)
                        self.assertEqual(page.locator('.edge').count(), edges)
                        for name in ['nodes', 'edges', 'transactions']:
                            self.assertEqual(page.locator('#upload-' + name).evaluate('(node) => node.files[0].name'), f'{name}.parquet')
                        self.assertEqual(len(requests), before, 'Language switching must not refetch analysis')
                        page.set_viewport_size({'width': 390, 'height': 844})
                        self.assertLessEqual(page.evaluate('document.documentElement.scrollWidth'), 390)
                        expect(page.locator('#language')).to_be_visible()
                        page.set_viewport_size({'width': 1440, 'height': 1100})
                    page.locator('#language').select_option('ru')
                    page.locator('#search-form button').click()
                    expect(page.locator('#error')).to_contain_text('точный десятичный ID')
                    page.locator('#language').select_option('kk')
                    expect(page.locator('#error')).to_contain_text('нақты ондық ID')
                    expect(page.locator('#account-area')).to_be_hidden()
                    page.locator('#show-results').click()
                    page.locator('#gid').fill(str(BASE + 79))
                    page.locator('#search-form button').click()
                    expect(page.locator('#account-warning')).to_contain_text('кейінгі аударымдар белгісіз')
                    expect(page.locator('#graph-caption')).to_contain_text('Оқшауланған шот')
                    expect(page.locator('#role-badge')).to_contain_text('шеткі')
                    expect(page.locator('#scoring')).to_contain_text('анықталмаған')
                    page.reload()
                    expect(page.locator('html')).to_have_attribute('lang', 'kk')
                    expect(page.locator('#account-area')).to_be_visible()
                    page.locator('#show-analyses').click()
                    for name in ['nodes', 'edges', 'transactions']:
                        page.locator('#upload-' + name).set_input_files(root / 'bad' / f'{name}.parquet')
                    page.locator('#analyze').click()
                    expect(page.locator('#upload-error')).to_contain_text('сандары сәйкес келмейді')
                    expect(page.locator('#analysis-status')).to_contain_text('Белсенді нәтижелер сақталды')
                    page.locator('#language').select_option('ru')
                    expect(page.locator('#upload-error')).to_contain_text('количество переводов не совпадает')
                    expect(page.locator('#analysis-status')).to_contain_text('Активные результаты сохранены')
                    for name, body in csvs.items():
                        self.assertEqual(body, page.request.get(base + '/exports/' + name).body())
                    page.locator('#show-analyses').click()
                    for name in ['nodes', 'edges', 'transactions']:
                        page.locator('#upload-' + name).set_input_files(root / 'input' / f'{name}.parquet')
                    page.locator('#analyze').click()
                    expect(page.locator('#analysis-status')).to_contain_text('Анализ завершён')
                    expect(page.locator('#upload-error')).to_be_hidden()
                    self.assertEqual(failures, [])
                    self.assertTrue(all(url.startswith(base) for url in requests))
                finally:
                    browser.close()
                    server.shutdown()
                    thread.join()

    def test_locale_detection_fallback_storage_and_empty_state(self):
        import json
        with tempfile.TemporaryDirectory() as temporary, sync_playwright() as playwright:
            with make_server(None, Path(temporary), 0) as server:
                thread = threading.Thread(target=server.serve_forever, daemon=True)
                thread.start()
                browser = playwright.chromium.launch()
                base = f'http://127.0.0.1:{server.server_port}'
                try:
                    for browser_locale, saved, expected in [('ru-RU', None, 'ru'), ('kk-KZ', None, 'kk'),
                            ('fr-FR', None, 'en'), ('ru-RU', 'en', 'en'), ('ru-RU', 'invalid', 'ru'),
                            ('en-GB', 'kz', 'kk')]:
                        with self.subTest(browser_locale=browser_locale, saved=saved):
                            context = browser.new_context(locale=browser_locale)
                            if saved:
                                context.add_init_script(f'localStorage.setItem("money-graph.locale", {json.dumps(saved)})')
                            page = context.new_page()
                            page.goto(base)
                            expect(page.locator('html')).to_have_attribute('lang', expected)
                            expect(page.locator('#language')).to_be_enabled()
                            empty = {'ru': 'Для начала загрузите три файла', 'kk': 'Бастау үшін үш Parquet', 'en': 'Upload the three Parquet'}
                            expect(page.locator('#summary')).to_contain_text(empty[expected])
                            expect(page.locator('#account-area')).to_be_hidden()
                            context.close()
                    context = browser.new_context(locale='ru-RU')
                    context.add_init_script('Object.defineProperty(window, "localStorage", {get() {throw new Error("blocked")}})')
                    page = context.new_page()
                    failures = []
                    page.on('pageerror', lambda error: failures.append(str(error)))
                    page.goto(base)
                    expect(page.locator('#analyze')).to_have_text('Анализировать файлы')
                    page.locator('#language').select_option('kk')
                    expect(page.locator('#analyze')).to_have_text('Файлдарды талдау')
                    page.locator('#analyze').click()
                    expect(page.locator('#upload-error')).to_contain_text('үш бос емес файлды таңдаңыз')
                    page.locator('#language').select_option('ru')
                    expect(page.locator('#upload-error')).to_contain_text('три непустых файла')
                    self.assertEqual(failures, [])
                    context.close()
                    # A missing message falls back to English; plain text interpolation cannot inject HTML.
                    context = browser.new_context(locale='ru-RU')
                    page = context.new_page()
                    def missing_message(route):
                        response = route.fetch()
                        catalog = response.json()
                        del catalog['upload.analyze']
                        route.fulfill(response=response, json=catalog)
                    page.route('**/locales/ru.json', missing_message)
                    page.goto(base)
                    expect(page.locator('html')).to_have_attribute('lang', 'ru')
                    expect(page.locator('#analyze')).to_have_text('Analyze files')
                    self.assertEqual(page.evaluate('''async () => {
                        const i18n = await import('/i18n.js');
                        return i18n.t('account.title', {gid: '$&<img src=x>'});
                    }'''), 'Клиент $&<img src=x>')
                    context.close()
                    context = browser.new_context(locale='ru-RU')
                    page = context.new_page()
                    page.route('**/locales/ru.json', lambda route: route.fulfill(status=404, body='missing'))
                    page.goto(base)
                    expect(page.locator('#error')).to_contain_text('Could not load the language files')
                    expect(page.locator('html')).to_have_attribute('lang', 'en')
                    expect(page.locator('#language option[value=ru]')).to_have_js_property('disabled', True)
                    expect(page.locator('#summary')).to_contain_text('Upload the three Parquet')
                    context.close()
                finally:
                    browser.close()
                    server.shutdown()
                    thread.join()
