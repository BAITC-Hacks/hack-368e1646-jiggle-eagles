"""Real browser/backend uploads with deliberate transport faults, synthetic data only."""
from contextlib import contextmanager
from pathlib import Path
import socket
import tempfile
import threading
import unittest
from unittest.mock import patch

from playwright.sync_api import expect, sync_playwright

from money_graph.pipeline import run
from money_graph.server import make_server
from test_money_graph import write_fixture


class BrowserUploadReliability(unittest.TestCase):
    @contextmanager
    def browser(self):
        with tempfile.TemporaryDirectory() as temporary, sync_playwright() as playwright:
            root = Path(temporary)
            write_fixture(root / 'input')
            result, _ = run(root / 'input', root / 'out')
            with make_server(result, root / 'out', 0) as server:
                thread = threading.Thread(target=server.serve_forever, daemon=True)
                thread.start()
                browser = playwright.chromium.launch()
                page = browser.new_page(locale='en-GB')
                failures = []
                page.on('pageerror', lambda error: failures.append(str(error)))
                base = f'http://127.0.0.1:{server.server_port}'
                try:
                    page.goto(base + '/analyses')
                    expect(page.locator('#analysis-status')).to_contain_text('Ready for a local upload')
                    expect(page.locator('#analyze')).to_be_enabled()
                    yield root, server, page, base
                    self.assertEqual(failures, [])
                finally:
                    browser.close()
                    server.shutdown()
                    thread.join()

    def select_files(self, page, root):
        for name in ('nodes', 'edges', 'transactions'):
            page.locator('#upload-' + name).set_input_files(root / 'input' / f'{name}.parquet')

    def test_wrong_empty_and_missing_files_are_clear_and_never_uploaded(self):
        with self.browser() as (root, server, page, base):
            requests = []
            page.on('request', lambda request: requests.append(request.url)
                    if request.method == 'POST' and request.url.endswith('/api/analysis') else None)
            page.locator('#analyze').click()
            expect(page.locator('#upload-error')).to_contain_text('Choose three nonempty files')
            self.select_files(page, root)
            page.locator('#upload-nodes').set_input_files(root / 'input' / 'edges.parquet')
            page.locator('#analyze').click()
            expect(page.locator('#upload-error')).to_contain_text('Selected edges.parquet; this field needs nodes.parquet')
            page.locator('#language').select_option('ru')
            expect(page.locator('#upload-error')).to_contain_text('для этого поля нужен nodes.parquet')
            page.locator('#language').select_option('kk')
            expect(page.locator('#upload-error')).to_contain_text('бұл өріске nodes.parquet қажет')
            page.locator('#language').select_option('en')
            page.locator('#upload-nodes').set_input_files(root / 'input' / 'nodes.parquet')
            page.locator('#upload-edges').set_input_files({'name': 'edges.parquet', 'mimeType': 'application/octet-stream', 'buffer': b''})
            page.locator('#analyze').click()
            expect(page.locator('#upload-error')).to_contain_text('edges.parquet: file is empty')
            self.assertEqual(requests, [])
            self.assertEqual(server.status()['revision'], 'startup')
            self.assertEqual(len(server.history()['analyses']), 1)
            self.select_files(page, root)
            page.locator('#analyze').click()
            expect(page.locator('#analysis-status')).to_contain_text('Analysis complete')
            expect(page.locator('#account-area')).to_be_visible()
            self.assertEqual(len(requests), 1)

    def test_status_disconnect_retries_preserves_files_and_never_resubmits(self):
        with self.browser() as (root, server, page, base):
            self.select_files(page, root)
            release = threading.Event()
            failures_left = 2
            posts = []
            page.on('request', lambda request: posts.append(request.url)
                    if request.method == 'POST' and request.url.endswith('/api/analysis') else None)
            def delayed_run(*args):
                if not release.wait(15):
                    raise RuntimeError('Test did not release analysis')
                return run(*args)
            def status_route(route):
                nonlocal failures_left
                if failures_left:
                    failures_left -= 1
                    route.abort('failed')
                else:
                    route.continue_()
            page.route('**/api/status', status_route)
            before = page.request.get(base + '/exports/nodes_roles.csv').body()
            with patch('money_graph.server.run', side_effect=delayed_run):
                try:
                    page.locator('#analyze').click()
                    expect(page.locator('#upload-error')).to_contain_text('Retrying automatically')
                    expect(page.locator('#analyze')).to_be_disabled()
                    self.assertEqual(server.status()['state'], 'validating')
                    self.assertEqual(page.request.get(base + '/exports/nodes_roles.csv').body(), before)
                    for name in ('nodes', 'edges', 'transactions'):
                        self.assertEqual(page.locator('#upload-' + name).evaluate('(input) => input.files[0].name'), f'{name}.parquet')
                finally:
                    release.set()
                expect(page.locator('#account-area')).to_be_visible(timeout=15000)
                expect(page.locator('#analyze')).to_be_enabled()
                expect(page.locator('#upload-error')).to_be_hidden()
            self.assertEqual(len(posts), 1)
            self.assertEqual(len(server.history()['analyses']), 2)
            self.assertEqual(page.url, base + '/analyses/' + server.status()['revision'])

    def test_lost_upload_response_checks_status_without_duplicate_submission(self):
        with self.browser() as (root, server, page, base):
            self.select_files(page, root)
            posts = []
            page.on('request', lambda request: posts.append(request.url)
                    if request.method == 'POST' and request.url.endswith('/api/analysis') else None)
            release = threading.Event()
            def delayed_run(*args):
                if not release.wait(15):
                    raise RuntimeError('Test did not release analysis')
                return run(*args)
            original_send = server.RequestHandlerClass.send
            dropped = []
            def drop_response(handler, status, body, content_type):
                if handler.path == '/api/analysis' and status == 202:
                    dropped.append(status)
                    handler.close_connection = True
                    handler.connection.shutdown(socket.SHUT_RDWR)
                else:
                    original_send(handler, status, body, content_type)
            # Drop only the acknowledgement after the real multipart request starts a worker.
            with patch('money_graph.server.run', side_effect=delayed_run), \
                    patch.object(server.RequestHandlerClass, 'send', new=drop_response):
                try:
                    page.locator('#analyze').click()
                    expect(page.locator('#upload-error')).to_contain_text('The upload response was lost')
                    expect(page.locator('#analyze')).to_be_disabled()
                finally:
                    release.set()
                expect(page.locator('.history-row')).to_have_count(2, timeout=15000)
                expect(page.locator('#analyze')).to_be_enabled()
            self.assertEqual(len(posts), 1)
            self.assertEqual(dropped, [202])
            self.assertEqual(len(server.history()['analyses']), 2)
            self.assertEqual(page.url, base + '/analyses')

    def test_initial_status_outage_recovers_without_reload(self):
        with self.browser() as (root, server, page, base):
            failures_left = 1
            def status_route(route):
                nonlocal failures_left
                if failures_left:
                    failures_left -= 1
                    route.abort('failed')
                else:
                    route.continue_()
            page.route('**/api/status', status_route)
            page.reload()
            expect(page.locator('#upload-error')).to_contain_text('Retrying automatically')
            expect(page.locator('#analyze')).to_be_disabled()
            expect(page.locator('#upload-error')).to_be_hidden(timeout=10000)
            expect(page.locator('#analyze')).to_be_enabled()
            expect(page.locator('.history-row')).to_have_count(1)
