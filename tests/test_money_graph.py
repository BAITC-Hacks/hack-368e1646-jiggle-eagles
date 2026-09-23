"""Deterministic, credential-free tests using hand-checkable synthetic motifs."""
import csv
import re
from datetime import date
import json
from pathlib import Path
import tempfile
import threading
import time
from unittest.mock import patch
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pandas as pd

from money_graph.pipeline import SCHEMAS, ValidationError, analyze, assign_role, run, validate
from money_graph.server import MAX_UPLOAD_BYTES, NODE_LIMIT, Snapshot, make_server, parse_upload

BASE = 9007199254740993  # Beyond JavaScript's exact Number range.


def fixture():
    nodes = pd.DataFrame({'gid': [BASE + i for i in range(30)],
        'depth': [0] + [1] * 28 + [4], 'is_seed': [True] + [False] * 29})
    pairs = [(0, 1, 10000), (0, 1, 10000), (1, 2, 20000), (3, 2, 5000),
             (4, 2, 5000), (2, 5, 30000), (5, 29, 30000)]
    tx = pd.DataFrame([dict(src=BASE+a, dst=BASE+b, date=date(2026, 7, 1), sum_kzt=float(s)) for a, b, s in pairs])
    edges = tx.groupby(['src', 'dst'], as_index=False).agg(sum_kzt=('sum_kzt', 'sum'), n_tx=('sum_kzt', 'size'))
    edges['depth'] = 1
    return nodes, edges, tx


def write_fixture(path, frames=None):
    path.mkdir(parents=True, exist_ok=True)
    for name, frame in zip(['nodes', 'edges', 'transactions'], frames or fixture()):
        frame.to_parquet(path / f'{name}.parquet', index=False)


def expansion_fixture():
    nodes = pd.DataFrame({'gid': [BASE + i for i in range(80)],
        'depth': [0] + [1] * 78 + [4], 'is_seed': [True] + [False] * 79})
    pairs = [(0, i) for i in range(1, 61)] + [(1, 2), (2, 1), (2, 61), (61, 62), (5, 5)]
    tx = pd.DataFrame([dict(src=BASE+a, dst=BASE+b, date=date(2026, 7, 1), sum_kzt=5000.) for a, b in pairs])
    edges = tx.groupby(['src', 'dst'], as_index=False).agg(sum_kzt=('sum_kzt', 'sum'), n_tx=('sum_kzt', 'size'))
    edges['depth'] = 1
    return nodes, edges, tx


def upload_body(path):
    boundary = 'money-graph-test-boundary'
    chunks = []
    for name in ['nodes', 'edges', 'transactions']:
        chunks.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"; filename="{name}.parquet"\r\nContent-Type: application/octet-stream\r\n\r\n'.encode())
        chunks.extend([(path / f'{name}.parquet').read_bytes(), b'\r\n'])
    chunks.append(f'--{boundary}--\r\n'.encode())
    return b''.join(chunks), f'multipart/form-data; boundary={boundary}'


class PipelineTests(unittest.TestCase):
    def test_directed_features_isolates_boundary_and_repeated_transactions(self):
        result = analyze(*fixture())
        self.assertEqual(result.graph.number_of_nodes(), 30)
        self.assertEqual(result.graph.number_of_edges(), 6)
        self.assertEqual(result.profile['isolates'], 23)
        self.assertEqual(result.profile['weak_components'], 24)
        self.assertEqual(result.profile['repeated_transaction_rows'], 1)
        self.assertEqual(result.profile['observed_kzt'], 110000)
        center = next(n for n in result.nodes if n['gid'] == BASE + 2)
        self.assertEqual((center['in_deg'], center['out_deg']), (3, 1))
        self.assertEqual((center['in_kzt'], center['out_kzt']), (30000, 30000))
        self.assertEqual(center['observed_out_in_ratio'], 1)
        boundary = result.nodes[-1]
        self.assertEqual(boundary['role'], 'peripheral')
        self.assertIn('onward unknown', boundary['evidence'])
        isolate = next(n for n in result.nodes if n['gid'] == BASE + 6)
        self.assertEqual(isolate['priority_score'], 0)
        self.assertIsNone(isolate['observed_out_in_ratio'])
        self.assertEqual(len(result.top), 30)
        self.assertEqual(sum(c['n_nodes'] for c in result.clusters), 30)
        membership = {n['gid']: n['cluster_id'] for n in result.nodes}
        for c in result.clusters:
            expected = sum(e['sum_kzt'] for a, b, e in result.graph.edges(data=True)
                           if membership[a] == membership[b] == c['cluster_id'])
            self.assertEqual(c['sum_kzt_internal'], expected)
        for n in result.nodes:
            self.assertLessEqual(len(n['evidence']), 200)
            self.assertAlmostEqual(n['priority_score'], sum(n['priority_contributions'].values()), places=6)
            self.assertTrue(0 <= n['role_score'] <= 1)
        self.assertEqual([n['gid'] for n in result.top], [n['gid'] for n in sorted(result.nodes, key=lambda n: (-n['priority_score'], n['gid']))])

    def test_explicit_role_rules_and_scores(self):
        f = dict(in_deg=0, out_deg=0, neighbor_clusters=0, observed_out_in_ratio=None, is_seed=False, depth=2)
        cases = [
            ({'in_deg': 10, 'out_deg': 1}, 'consolidator', .9),
            ({'in_deg': 1, 'out_deg': 20}, 'distributor', .9),
            ({'in_deg': 2, 'out_deg': 2, 'neighbor_clusters': 6}, 'coordinator', .9),
            ({'in_deg': 1, 'out_deg': 1, 'observed_out_in_ratio': 1}, 'transit', .9),
            ({'in_deg': 1}, 'terminal', .48),
            ({'in_deg': 1, 'depth': 4}, 'peripheral', .12),
            ({'in_deg': 1, 'is_seed': True, 'depth': 0}, 'peripheral', .17),
            ({'in_deg': 1, 'out_deg': 1, 'observed_out_in_ratio': 1, 'is_seed': True, 'depth': 0}, 'peripheral', .17),
            ({'in_deg': 1, 'out_deg': 1, 'observed_out_in_ratio': 20}, 'peripheral', .2),
            ({'in_deg': 10, 'out_deg': 1, 'depth': 4}, 'consolidator', .54),
            ({}, 'peripheral', .1),
        ]
        for changes, role, expected in cases:
            with self.subTest(changes=changes):
                actual = assign_role(dict(f, **changes))
                self.assertEqual(actual[0], role)
                self.assertAlmostEqual(actual[1], expected)
        # Equal 0.9 scores: consolidator precedes transit; ambiguity subtracts 0.1.
        actual = assign_role(dict(f, in_deg=10, out_deg=1, observed_out_in_ratio=1))
        self.assertEqual(actual[:2], ('consolidator', .8))

    def test_rejects_invalid_data_without_dropping_rows(self):
        def bad(case):
            nodes, edges, tx = fixture()
            if case == 'duplicate node': nodes = pd.concat([nodes, nodes.iloc[:1]])
            if case == 'duplicate edge': edges = pd.concat([edges, edges.iloc[:1]])
            if case == 'float id': nodes['gid'] = nodes.gid.astype(float)
            if case == 'missing field': nodes = nodes.drop(columns='is_seed')
            if case == 'null': edges.loc[0, 'sum_kzt'] = float('nan')
            if case == 'infinity': edges.loc[0, 'sum_kzt'] = float('inf')
            if case == 'threshold': tx.loc[0, 'sum_kzt'] = 4999
            if case == 'seed': nodes.loc[0, 'is_seed'] = False
            if case == 'depth': nodes.loc[0, 'depth'] = 5
            if case == 'edge depth': edges.loc[0, 'depth'] = 0
            if case == 'count': edges.loc[0, 'n_tx'] = 99
            if case == 'amount': edges.loc[0, 'sum_kzt'] += 1
            if case == 'endpoint': edges.loc[0, 'src'] = -999
            if case == 'pair': tx.loc[0, 'dst'] = BASE + 4
            if case == 'month': tx.loc[0, 'date'] = date(2026, 8, 1)
            if case == 'time': tx.loc[0, 'date'] = '2026-07-01 12:00:00'
            validate(nodes, edges, tx)
        for case in ['duplicate node', 'duplicate edge', 'float id', 'missing field', 'null', 'infinity',
                     'threshold', 'seed', 'depth', 'edge depth', 'count', 'amount', 'endpoint', 'pair', 'month', 'time']:
            with self.subTest(case=case), self.assertRaises(ValidationError):
                bad(case)

    def test_schema_exact_ids_reproducibility_and_invalid_run_keeps_exports(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            write_fixture(root / 'input')
            _, first = run(root / 'input', root / 'one')
            # Reordering any input must not change deterministic artifacts.
            write_fixture(root / 'input', [frame.sample(frac=1, random_state=17).reset_index(drop=True) for frame in fixture()])
            _, second = run(root / 'input', root / 'two')
            self.assertEqual(first['outputs'], second['outputs'])
            for name, columns in SCHEMAS.items():
                with (root / 'one' / name).open() as file:
                    reader = csv.DictReader(file)
                    self.assertEqual(reader.fieldnames, columns)
                    self.assertTrue(all(all(value != '' for value in row.values()) for row in reader))
            output = pd.read_csv(root / 'one' / 'nodes_roles.csv', dtype={'gid': 'int64'})
            self.assertEqual(set(output.gid), set(fixture()[0].gid))
            data = json.loads((root / 'one' / 'dashboard.json').read_text())
            self.assertEqual(data['nodes'][0]['gid'], str(BASE))
            before = (root / 'one' / 'nodes_roles.csv').read_bytes()
            nodes, edges, tx = fixture()
            edges.loc[0, 'n_tx'] = 99
            write_fixture(root / 'input', (nodes, edges, tx))
            with self.assertRaises(ValidationError):
                run(root / 'input', root / 'one')
            self.assertEqual(before, (root / 'one' / 'nodes_roles.csv').read_bytes())

    def test_edgeless_and_self_transfer(self):
        nodes, edges, tx = fixture()
        result = analyze(nodes, edges.iloc[:0].copy(), tx.iloc[:0].copy())
        self.assertEqual(len(result.clusters), 30)
        self.assertTrue(all(n['priority_score'] == 0 for n in result.nodes))
        tx = tx.iloc[:1].copy()
        tx['dst'] = tx.src
        edges = edges.iloc[:1].copy()
        edges['dst'] = edges.src
        edges['n_tx'] = 1
        edges['sum_kzt'] = 10000.
        result = analyze(nodes, edges, tx)
        self.assertEqual(result.profile['self_loops'], 1)
        self.assertEqual(result.nodes[0]['in_deg'], 0)
        self.assertEqual(result.nodes[0]['in_kzt'], 10000)
        self.assertEqual(sum(c['sum_kzt_internal'] for c in result.clusters), 10000)


    def test_measured_cluster_patterns_and_caveats(self):
        result = analyze(*fixture())
        center = next(n for n in result.nodes if n['gid'] == BASE + 2)
        text = result.clusters[center['cluster_id']]['hypothesis']
        self.assertIn('Fan-in candidates=1', text)
        self.assertIn(f'Fan-in example {BASE + 2}: peers in/out=3/1', text)
        self.assertIn('observed KZT in/out=30000.00/30000.00', text)
        # Fix community membership for a hand-checkable bridge, independent of Louvain.
        nodes, edges, tx = fixture()
        membership = {int(g): 0 for g in nodes.gid}
        membership[BASE + 1] = 1
        membership[BASE + 5] = 2
        with patch('money_graph.pipeline.communities', return_value=membership):
            bridge_result = analyze(nodes, edges, tx)
        text = bridge_result.clusters[0]['hypothesis']
        self.assertIn('Potential bridging accounts=1', text)
        self.assertIn(f'Bridging example {BASE + 2}: 3 neighbor communities, 2 cross-community peers', text)
        wide = analyze(*expansion_fixture())
        distributor = next(n for n in wide.nodes if n['gid'] == BASE)
        text = wide.clusters[distributor['cluster_id']]['hypothesis']
        self.assertIn('fan-out candidates=1', text)
        self.assertIn(f'Fan-out example {BASE}: peers in/out=0/60', text)
        isolated = next(c for c in wide.clusters if c['top_gids'] == [str(BASE + 79)])
        self.assertIn('No measured fan-in, fan-out or bridging pattern', isolated['hypothesis'])
        for cluster in wide.clusters:
            for caveat in ['hypothesis', 'four hops', '5,000 KZT', 'incoming flows outside', 'not balances', 'not proof of an organization']:
                self.assertIn(caveat, cluster['hypothesis'])


class HttpTests(unittest.TestCase):
    def test_upload_requires_three_named_nonempty_files_and_preserves_bytes(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary)
            write_fixture(path)
            body, content_type = upload_body(path)
            parsed = parse_upload(content_type, body)
            self.assertEqual(parsed, {name: (path / f'{name}.parquet').read_bytes()
                                      for name in ['nodes', 'edges', 'transactions']})
            for malformed in [body.replace(b'name="transactions"', b'name="nodes"'),
                              body.replace(b'filename="nodes.parquet"', b'filename="../nodes.parquet"'),
                              body.split(b'--money-graph-test-boundary')[0] + b'--money-graph-test-boundary--\r\n']:
                with self.assertRaises(ValidationError):
                    parse_upload(content_type, malformed)
            (path / 'nodes.parquet').write_bytes(b'')
            body, content_type = upload_body(path)
            with self.assertRaisesRegex(ValidationError, 'file is empty'):
                parse_upload(content_type, body)

    def test_real_server_routes_and_errors(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            write_fixture(root / 'input')
            result, _ = run(root / 'input', root / 'output')
            with make_server(result, root / 'output', 0) as server:
                thread = threading.Thread(target=server.serve_forever, daemon=True)
                thread.start()
                base = f'http://127.0.0.1:{server.server_port}'
                try:
                    with urlopen(base + '/api/account?gid=' + str(BASE)) as response:
                        data = json.load(response)
                        self.assertEqual(data['account']['gid'], str(BASE))
                        self.assertEqual(data['edges'][0]['src'], str(BASE))
                        self.assertEqual(data['edges'][0]['dst'], str(BASE + 1))
                    with urlopen(base + '/exports/nodes_roles.csv') as response:
                        self.assertIn(str(BASE).encode(), response.read())
                    for route, status in [('/api/account?gid=missing', 400), ('/api/account?gid=1', 404),
                                          ('/api/account?gid=9223372036854775808', 400),
                                          ('/api/account?gid=1&gid=2', 400), ('/../pipeline.py', 404)]:
                        with self.subTest(route=route), self.assertRaises(HTTPError) as caught:
                            urlopen(base + route)
                        self.assertEqual(caught.exception.code, status)
                        caught.exception.close()
                finally:
                    server.shutdown()
                    thread.join()


    def test_bounded_two_hop_induced_graph(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            write_fixture(root / 'input', expansion_fixture())
            result, _ = run(root / 'input', root / 'out')
            snapshot = Snapshot.create(result, root / 'out', 'test')
            one = snapshot.neighborhood(str(BASE), 1)
            two = snapshot.neighborhood(str(BASE), 2)
            self.assertEqual((one['total_nodes'], two['total_nodes']), (61, 62))
            self.assertEqual(len(two['nodes']), NODE_LIMIT)
            self.assertEqual(two['omitted_nodes'], 12)
            self.assertEqual([n['gid'] for n in two['nodes']], [str(BASE+i) for i in range(50)])
            visible = {int(n['gid']) for n in two['nodes']}
            expected = {(a, b) for a, b in result.graph.edges if a in visible and b in visible}
            self.assertEqual({(int(e['src']), int(e['dst'])) for e in two['edges']}, expected)
            self.assertIn((BASE+1, BASE+2), expected)
            self.assertIn((BASE+2, BASE+1), expected)
            self.assertIn((BASE+5, BASE+5), expected)
            small = snapshot.neighborhood(str(BASE+61), 2)
            self.assertEqual({n['gid'] for n in small['nodes']}, {str(BASE+i) for i in [0, 1, 2, 61, 62]})
            isolate = snapshot.neighborhood(str(BASE+79), 2)
            self.assertEqual((len(isolate['nodes']), isolate['edges'], isolate['omitted_nodes']), (1, [], 0))

    def test_upload_publication_failures_status_concurrency_and_reproduction(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            write_fixture(root / 'initial')
            write_fixture(root / 'upload', expansion_fixture())
            result, _ = run(root / 'initial', root / 'output')
            with make_server(result, root / 'output', 0) as server:
                thread = threading.Thread(target=server.serve_forever, daemon=True)
                thread.start()
                base = f'http://127.0.0.1:{server.server_port}'
                def get(route):
                    with urlopen(base + route) as response:
                        return response.read()
                def post(path, origin=base, body=None, content_type=None):
                    if body is None:
                        body, content_type = upload_body(path)
                    request = Request(base + '/api/analysis', data=body, headers={'Origin': origin, 'Content-Type': content_type})
                    return urlopen(request)
                def finished():
                    deadline = time.monotonic() + 10
                    while time.monotonic() < deadline:
                        status = json.loads(get('/api/status'))
                        if status['state'] in {'failed', 'succeeded'}:
                            return status
                        time.sleep(.02)
                    self.fail('Analysis never completed')
                try:
                    before = {route: get(route) for route in ['/api/overview', '/api/account?gid='+str(BASE), *['/exports/'+name for name in [*SCHEMAS, 'run_manifest.json']]]}
                    release, entered = threading.Event(), threading.Event()
                    def delayed_run(*args):
                        entered.set()
                        if not release.wait(5):
                            raise RuntimeError('Test worker was not released')
                        return run(*args)
                    with patch('money_graph.server.run', side_effect=delayed_run):
                        try:
                            with post(root / 'upload') as response:
                                self.assertEqual(response.status, 202)
                            self.assertTrue(entered.wait(2))
                            self.assertEqual(json.loads(get('/api/status'))['state'], 'validating')
                            for route, body in before.items():
                                self.assertEqual(get(route), body)
                            with self.assertRaises(HTTPError) as caught:
                                post(root / 'upload')
                            self.assertEqual(caught.exception.code, 409)
                            caught.exception.close()
                        finally:
                            release.set()
                        status = finished()
                    self.assertEqual(status['state'], 'succeeded')
                    self.assertEqual(json.loads(get('/api/overview'))['profile']['nodes'], 80)
                    saved = Path(status['run_directory'])
                    _, replay = run(saved / 'input', root / 'replayed')
                    manifest = json.loads(get('/exports/run_manifest.json'))
                    self.assertEqual(manifest['outputs'], replay['outputs'])
                    self.assertEqual(manifest['inputs'], replay['inputs'])
                    baseline = {route: get(route) for route in before}
                    bad = list(expansion_fixture())
                    bad[1].loc[0, 'n_tx'] = 999
                    write_fixture(root / 'bad', bad)
                    with post(root / 'bad') as response:
                        self.assertEqual(response.status, 202)
                    self.assertIn('counts differ', finished()['message'])
                    for route, body in baseline.items():
                        self.assertEqual(get(route), body)
                    # Unexpected calculation/storage failures must also retain every active artifact.
                    with patch('money_graph.server.Snapshot.create', side_effect=OSError('synthetic save failure')):
                        with post(root / 'upload') as response:
                            self.assertEqual(response.status, 202)
                        self.assertEqual(finished()['state'], 'failed')
                    for route, body in baseline.items():
                        self.assertEqual(get(route), body)
                    for origin, body, content_type, code in [('http://example.invalid', b'x', 'text/plain', 403),
                                                             (base, b'not multipart', 'text/plain', 400)]:
                        with self.assertRaises(HTTPError) as caught:
                            post(None, origin=origin, body=body, content_type=content_type)
                        self.assertEqual(caught.exception.code, code)
                        caught.exception.close()
                    request = Request(base + '/api/analysis', data=b'x', headers={
                        'Origin': base, 'Content-Length': str(MAX_UPLOAD_BYTES + 1)})
                    with self.assertRaises(HTTPError) as caught:
                        urlopen(request)
                    self.assertEqual(caught.exception.code, 413)
                    caught.exception.close()
                    for route, code in [('/api/graph?gid='+str(BASE)+'&hops=3', 400),
                                        ('/api/graph?gid='+str(BASE)+'&hops=2&revision=startup', 409)]:
                        with self.assertRaises(HTTPError) as caught:
                            get(route)
                        self.assertEqual(caught.exception.code, code)
                        caught.exception.close()
                    self.assertEqual(len(list((root / 'output' / 'uploads').iterdir())), 1)
                finally:
                    server.shutdown()
                    thread.join()


class StaticAssetTests(unittest.TestCase):
    """The dashboard is inert unless index.html actually loads its behaviour scripts."""
    STATIC = Path(__file__).resolve().parents[1] / 'money_graph' / 'static'

    def scripts(self):
        markup = (self.STATIC / 'index.html').read_text(encoding='utf-8')
        return re.findall(r'<script\b([^>]*)>', markup)

    def test_index_loads_the_dashboard_script(self):
        srcs = [re.search(r'src="([^"]+)"', tag).group(1) for tag in self.scripts()]
        self.assertIn('app.js', [src.rsplit('/', 1)[-1] for src in srcs],
                      'index.html must load app.js; without it the upload inputs, '
                      'analyse button, search and language selector have no listeners.')

    def test_referenced_scripts_exist(self):
        for tag in self.scripts():
            name = re.search(r'src="([^"]+)"', tag).group(1).rsplit('/', 1)[-1]
            with self.subTest(script=name):
                self.assertTrue((self.STATIC / name).is_file(), f'{name} is referenced but missing')

    def test_module_scripts_declare_type_module(self):
        for tag in self.scripts():
            name = re.search(r'src="([^"]+)"', tag).group(1).rsplit('/', 1)[-1]
            path = self.STATIC / name
            if not path.is_file():
                continue
            uses_esm = re.search(r'^\s*(import|export)\s', path.read_text(encoding='utf-8'), re.M)
            with self.subTest(script=name):
                self.assertEqual(bool(uses_esm), 'type="module"' in tag,
                                 f'{name} uses ES module syntax iff it is loaded as type="module"')


if __name__ == '__main__':
    unittest.main()
