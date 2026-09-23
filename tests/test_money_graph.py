"""Deterministic, credential-free tests using hand-checkable synthetic motifs."""
import csv
from datetime import date
import json
from pathlib import Path
import tempfile
import threading
import unittest
from urllib.error import HTTPError
from urllib.request import urlopen

import pandas as pd

from money_graph.pipeline import SCHEMAS, ValidationError, analyze, assign_role, run, validate
from money_graph.server import make_server

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


class HttpTests(unittest.TestCase):
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


if __name__ == '__main__':
    unittest.main()
