"""Upload failure recovery against synthetic data and the real local HTTP server."""
from contextlib import contextmanager
import errno
from http.client import HTTPConnection
from io import BytesIO
import json
from pathlib import Path
import socket
import tempfile
import threading
import time
import unittest
from unittest.mock import Mock, patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from money_graph.pipeline import SCHEMAS, ValidationError, run
from money_graph.server import make_server
from money_graph.uploads import analysis_failure, parse_upload, read_upload
from test_money_graph import fixture, upload_body, write_fixture


class UploadReliabilityTests(unittest.TestCase):
    @contextmanager
    def server(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            write_fixture(root / 'input')
            result, _ = run(root / 'input', root / 'out')
            with make_server(result, root / 'out', 0) as server:
                thread = threading.Thread(target=server.serve_forever, daemon=True)
                thread.start()
                try:
                    yield root, server, f'http://127.0.0.1:{server.server_port}'
                finally:
                    server.shutdown()
                    thread.join()

    def get(self, base, route):
        with urlopen(base + route, timeout=5) as response:
            return response.read()

    def post(self, base, root):
        body, content_type = upload_body(root / 'input')
        request = Request(base + '/api/analysis', data=body,
                          headers={'Origin': base, 'Content-Type': content_type})
        with urlopen(request, timeout=5) as response:
            return response.status

    def finished(self, server):
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            status = server.status()
            if status['state'] in {'failed', 'succeeded'}:
                return status
            time.sleep(.01)
        self.fail('Upload did not reach a terminal state')

    def test_binary_preservation_and_malformed_multipart(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            write_fixture(root)
            body, content_type = upload_body(root)
            self.assertEqual(parse_upload(content_type, body), {
                name: (root / f'{name}.parquet').read_bytes()
                for name in ('nodes', 'edges', 'transactions')})
            cases = [
                (content_type, body.rsplit(b'--money-graph-test-boundary--', 1)[0]),
                (content_type, body.replace(b'name="transactions"', b'name="nodes"')),
                (content_type, body.replace(b'filename="nodes.parquet"', b'filename="edges.parquet"')),
                (content_type, body.replace(b'Content-Type: application/octet-stream', b'Content-Transfer-Encoding: base64')),
                (content_type, body.replace(b'Content-Type: application/octet-stream', b'Content-Encoding: gzip')),
                ('multipart/form-data; boundary=недопустимо', body),
                ('multipart/form-data\r\nX-Test: injected', body),
            ]
            for kind, payload in cases:
                with self.subTest(kind=kind, size=len(payload)), self.assertRaises(ValidationError):
                    parse_upload(kind, payload)

    def test_short_read_timeout_and_disconnect_are_distinct(self):
        connection = Mock()
        for stream, key in [(BytesIO(b'short'), 'error.interrupted'),
                            (Mock(read=Mock(side_effect=TimeoutError())), 'error.uploadTimeout'),
                            (Mock(read=Mock(side_effect=ConnectionResetError())), 'error.interrupted')]:
            with self.subTest(key=key), self.assertRaises(ValidationError) as caught:
                read_upload(stream, connection, 'multipart/form-data', 100)
            self.assertEqual(caught.exception.message['key'], key)

    def test_failure_categories_do_not_expose_paths(self):
        for code, key in [(errno.ENOSPC, 'error.storageFull'), (errno.EDQUOT, 'error.storageFull'),
                          (errno.EACCES, 'error.storagePermission'), (errno.EROFS, 'error.storagePermission'),
                          (errno.EIO, 'error.analysis')]:
            with self.subTest(code=code):
                error = analysis_failure(OSError(code, 'sensitive detail', '/private/customer-data'))
                self.assertEqual(error.message['key'], key)
                self.assertNotIn('customer-data', str(error))
                self.assertNotIn('sensitive', str(error))

    def test_storage_failures_preserve_active_artifacts_and_allow_retry(self):
        with self.server() as (root, server, base):
            routes = ['/api/overview', *['/exports/' + name for name in [*SCHEMAS, 'run_manifest.json']]]
            before = {route: self.get(base, route) for route in routes}
            for code, key in [(errno.ENOSPC, 'error.storageFull'), (errno.EACCES, 'error.storagePermission')]:
                with self.subTest(code=code), patch('money_graph.server.run', side_effect=OSError(code, 'private')):
                    self.assertEqual(self.post(base, root), 202)
                    status = self.finished(server)
                    self.assertEqual(status['error_message']['key'], key)
                    self.assertEqual(status['revision'], 'startup')
                self.assertEqual({route: self.get(base, route) for route in routes}, before)
                self.assertEqual(len(server.history()['analyses']), 1)
                self.assertEqual(list((root / 'out' / 'uploads').iterdir()), [])
            self.assertEqual(self.post(base, root), 202)
            self.assertEqual(self.finished(server)['state'], 'succeeded')
            self.assertEqual(len(server.history()['analyses']), 2)

    def test_invalid_datasets_report_specific_causes_and_preserve_results(self):
        with self.server() as (root, server, base):
            previous = self.get(base, '/exports/nodes_roles.csv')
            cases = []
            frames = list(fixture())
            frames[0] = frames[0].drop(columns=['gid'])
            cases.append((frames, 'validation.columns'))
            frames = list(fixture())
            frames[0]['gid'] = frames[0].gid.astype(float)
            cases.append((frames, 'validation.integer'))
            frames = list(fixture())
            frames[1].loc[0, 'src'] = -1
            cases.append((frames, 'validation.endpoint'))
            frames = list(fixture())
            frames[1].loc[0, 'n_tx'] = 999
            cases.append((frames, 'validation.counts'))
            frames = list(fixture())
            frames[2].loc[0, 'sum_kzt'] = 6000.
            cases.append((frames, 'validation.sums'))
            for value, key in [('2026-08-01', 'validation.dateRange'),
                               ('2026-07-01 12:00:00', 'validation.dayPrecision'),
                               ('2026-07-01T00:00:00+05:00', 'validation.timezone')]:
                frames = list(fixture())
                frames[2]['date'] = value
                cases.append((frames, key))
            for frames, key in cases:
                with self.subTest(key=key):
                    write_fixture(root / 'input', frames)
                    self.assertEqual(self.post(base, root), 202)
                    status = self.finished(server)
                    self.assertEqual(status['state'], 'failed')
                    self.assertEqual(status['error_message']['key'], key)
                    self.assertEqual(status['revision'], 'startup')
                    self.assertEqual(self.get(base, '/exports/nodes_roles.csv'), previous)
                    self.assertEqual(len(server.history()['analyses']), 1)
            write_fixture(root / 'input')
            self.assertEqual(self.post(base, root), 202)
            self.assertEqual(self.finished(server)['state'], 'succeeded')

    def test_interrupted_http_upload_releases_busy_state_and_can_retry(self):
        with self.server() as (root, server, base):
            previous = self.get(base, '/exports/nodes_roles.csv')
            body, content_type = upload_body(root / 'input')
            connection = HTTPConnection('127.0.0.1', server.server_port, timeout=5)
            try:
                connection.putrequest('POST', '/api/analysis')
                connection.putheader('Origin', base)
                connection.putheader('Content-Type', content_type)
                connection.putheader('Content-Length', str(len(body)))
                connection.endheaders()
                connection.send(body[:100])
                connection.sock.shutdown(socket.SHUT_WR)
                response = connection.getresponse()
                self.assertEqual(response.status, 400)
                self.assertEqual(json.loads(response.read())['error_message']['key'], 'error.interrupted')
            finally:
                connection.close()
            self.assertEqual(server.status()['state'], 'failed')
            self.assertEqual(self.get(base, '/exports/nodes_roles.csv'), previous)
            self.assertEqual(self.post(base, root), 202)
            self.assertEqual(self.finished(server)['state'], 'succeeded')

    def test_http_receive_timeout_is_actionable_and_recovers(self):
        with self.server() as (root, server, base):
            with patch('money_graph.uploads.RECEIVE_TIMEOUT_SECONDS', .05):
                connection = HTTPConnection('127.0.0.1', server.server_port, timeout=5)
                try:
                    connection.putrequest('POST', '/api/analysis')
                    connection.putheader('Origin', base)
                    connection.putheader('Content-Length', '100')
                    connection.endheaders()
                    response = connection.getresponse()
                    self.assertEqual(response.status, 408)
                    self.assertEqual(json.loads(response.read())['error_message']['key'], 'error.uploadTimeout')
                finally:
                    connection.close()
            self.assertEqual(server.status()['state'], 'failed')
            self.assertEqual(server.status()['revision'], 'startup')
            self.assertEqual(self.post(base, root), 202)
            self.assertEqual(self.finished(server)['state'], 'succeeded')

    def test_worker_start_failure_does_not_leave_server_busy(self):
        with self.server() as (root, server, base):
            real_thread = threading.Thread
            def create_thread(*args, **kwargs):
                if kwargs.get('target') == server.analyze_upload:
                    return Mock(start=Mock(side_effect=RuntimeError('cannot start new thread')))
                return real_thread(*args, **kwargs)
            with patch('money_graph.server.threading.Thread', side_effect=create_thread):
                with self.assertRaises(HTTPError) as caught:
                    self.post(base, root)
                with caught.exception as response:
                    self.assertEqual(response.code, 503)
                    self.assertEqual(json.load(response)['error_message']['key'], 'error.workerStart')
            self.assertEqual(server.status()['state'], 'failed')
            self.assertEqual(server.status()['revision'], 'startup')
            self.assertEqual(self.post(base, root), 202)
            self.assertEqual(self.finished(server)['state'], 'succeeded')
