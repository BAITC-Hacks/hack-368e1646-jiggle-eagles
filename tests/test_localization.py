"""Catalog and API localization contracts, with synthetic data only."""
import ast
import json
from pathlib import Path
import re
import tempfile
import threading
import unittest
from urllib.error import HTTPError
from urllib.request import urlopen

from money_graph.i18n import render
from money_graph.pipeline import ValidationError, run
from money_graph.server import make_server
from test_money_graph import BASE, write_fixture

ROOT = Path(__file__).resolve().parents[1]


class LocalizationTests(unittest.TestCase):
    def test_catalog_parity_placeholders_and_message_references(self):
        def unique_keys(pairs):
            result = {}
            for key, value in pairs:
                self.assertNotIn(key, result, f'Duplicate translation: {key}')
                self.assertIsInstance(value, str)
                self.assertTrue(value.strip(), key)
                result[key] = value
            return result

        catalogs = {locale: json.loads((ROOT / f'money_graph/static/locales/{locale}.json').read_text(),
                                      object_pairs_hook=unique_keys) for locale in ['en', 'kk', 'ru']}
        for locale, catalog in catalogs.items():
            self.assertEqual(catalog.keys(), catalogs['en'].keys(), locale)
            for key, value in catalog.items():
                self.assertEqual(set(re.findall(r'\{\w+\}', value)),
                                 set(re.findall(r'\{\w+\}', catalogs['en'][key])), (locale, key))
        for source in ['pipeline.py', 'server.py']:
            tree = ast.parse((ROOT / 'money_graph' / source).read_text())
            for node in ast.walk(tree):
                if isinstance(node, ast.Constant) and isinstance(node.value, str):
                    value = node.value
                    if re.fullmatch(r'(validation|error|status|cluster|rule)\.[A-Za-z]+', value):
                        self.assertIn(value, catalogs['en'], source)
        html = (ROOT / 'money_graph/static/index.html').read_text()
        for key in re.findall(r'data-i18n(?:-[a-z-]+)?="([^"]+)"', html):
            self.assertIn(key, catalogs['en'])

    def test_validation_retains_english_and_provides_named_parameters(self):
        error = ValidationError('validation.integer', name='nodes', col='gid')
        self.assertEqual(str(error), 'nodes.gid: expected integer dtype (IDs must not pass through floats)')
        self.assertEqual(error.message, {'key': 'validation.integer', 'params': {'name': 'nodes', 'col': 'gid'}})

    def test_http_catalogs_errors_and_structured_hypotheses(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            write_fixture(root / 'input')
            result, _ = run(root / 'input', root / 'out')
            original = (root / 'out' / 'clusters.csv').read_bytes()
            with make_server(result, root / 'out', 0) as server:
                thread = threading.Thread(target=server.serve_forever, daemon=True)
                thread.start()
                base = f'http://127.0.0.1:{server.server_port}'
                try:
                    for locale in ['en', 'kk', 'ru']:
                        with urlopen(base + f'/locales/{locale}.json') as response:
                            self.assertEqual(response.headers.get_content_type(), 'application/json')
                            self.assertIn('language.label', json.load(response))
                    for route, code, key in [('/api/account?gid=bad', 400, 'error.invalidId'),
                                             ('/api/account?gid=-1', 404, 'error.missingId'),
                                             ('/locales/../../pipeline.py', 404, 'error.notFound')]:
                        with self.assertRaises(HTTPError) as caught:
                            urlopen(base + route)
                        with caught.exception as response:
                            data = json.load(response)
                            self.assertEqual(response.code, code)
                            self.assertEqual(data['error_message']['key'], key)
                            self.assertEqual(data['error'], render(data['error_message']))
                    with urlopen(base + f'/api/account?gid={BASE}') as response:
                        data = json.load(response)
                    self.assertEqual(data['account']['gid'], str(BASE))
                    self.assertEqual(data['cluster']['hypothesis'], ' '.join(map(render, data['cluster']['description_parts'])))
                    self.assertTrue(all(isinstance(part['params'].get('gid', ''), str)
                                        for part in data['cluster']['description_parts']))
                    with urlopen(base + '/exports/clusters.csv') as response:
                        self.assertEqual(response.read(), original)
                    # HTTP metadata must not mutate pipeline artifacts.
                    self.assertTrue(all('description_parts' not in c for c in result.clusters))
                finally:
                    server.shutdown()
                    thread.join()
