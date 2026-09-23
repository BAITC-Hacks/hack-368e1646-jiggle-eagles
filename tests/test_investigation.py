"""Calculation, evidence, budget and lifecycle regressions; no paid requests."""
from copy import deepcopy
from dataclasses import replace
import json
from pathlib import Path
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from money_graph.pipeline import dashboard_data, run
from money_graph.server import Snapshot, make_server
from money_graph.investigation.agent import Limits, run_review
from money_graph.investigation.contracts import ReviewError, digest, encode, parse, validate
from money_graph.investigation.discovery import DiscoveryConfig, discover
from money_graph.investigation.evidence import EvidenceIndex, load_calculation
from money_graph.investigation.provider import AISettings, ResponsesProvider
from money_graph.investigation.service import ReviewService
from money_graph.investigation.tools import InvestigationTools, TOOL_SCHEMAS
from investigation_fixtures import BASE, ScriptedProvider, case
from test_money_graph import write_fixture


class InvestigationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        write_fixture(self.root / 'input', case())
        self.result, self.manifest = run(self.root / 'input', self.root / 'out')
        self.snapshot = load_calculation(self.root / 'out', 'startup')
        self.index = EvidenceIndex(self.snapshot)

    def tools(self, limit=100):
        return InvestigationTools(self.index, discover(self.index), limit)

    def test_daily_aggregates_and_complete_diverse_discovery(self):
        row = next(r for r in self.result.daily if r['src'] == str(BASE) and r['date'] == '2026-07-01')
        self.assertEqual(row, dict(src=str(BASE), dst=str(BASE + 3), date='2026-07-01', sum_kzt=5000., n_tx=1))
        candidates = discover(self.index)
        shared = [c for c in candidates if c['pattern'] == 'shared_recipient']
        self.assertEqual({c['center'] for c in shared}, {str(BASE + 3), str(BASE + 9)})
        self.assertEqual(len({c['component'] for c in shared}), 2)
        repeated = [c for c in candidates if c['pattern'] == 'repeated_connection']
        self.assertEqual(len(repeated), 3)
        for candidate in repeated:
            record = self.index.record(candidate['evidence_refs'][0])
            self.assertEqual(record['measurements'], dict(active_days=dict(value=2, unit='days'), sum_kzt=dict(value=10000., unit='KZT'), n_tx=dict(value=2, unit='transfers')))
        context = self.tools().execute('analysis_context', {})
        self.assertEqual(context['data']['accounts_scanned'], 16)
        self.assertEqual(context['data']['candidates_examined'], 0)
        self.assertEqual(discover(self.index), candidates)
        changed = discover(self.index, DiscoveryConfig(shared_min_payers=4))
        self.assertFalse(any(c['pattern'] == 'shared_recipient' for c in changed))

    def test_methods_and_old_evidence_survive_threshold_and_algorithm_replacement(self):
        original = (self.root / 'out/dashboard.json').read_bytes()
        original_snapshot = self.snapshot['snapshot_id']
        new_result, _ = run(self.root / 'input', self.root / 'new', config={'consolidator_min': 7, 'community_algorithm': 'connected_components'})
        self.assertNotEqual(self.result.config, new_result.config)
        self.assertEqual(dashboard_data(new_result)['rule_parameters']['consolidator'], 7)
        self.assertNotIn('consolidator', {c['role'] for c in new_result.nodes[3]['candidates']})
        self.assertIn('consolidator', {c['role'] for c in self.result.nodes[3]['candidates']})
        loaded = Snapshot.load(self.root / 'out', 'startup')
        self.assertEqual(loaded.data, json.loads(original))
        self.assertEqual(load_calculation(self.root / 'out', 'startup')['snapshot_id'], original_snapshot)
        self.assertEqual(loaded.data['config']['consolidator_min'], 3)
        self.assertEqual(loaded.data['methods']['community'], self.snapshot['data']['methods']['community'])
        new_index = EvidenceIndex(load_calculation(self.root / 'new', 'startup'))
        self.assertNotEqual(new_index.snapshot['snapshot_id'], original_snapshot)
        self.assertFalse(any(c['pattern'] == 'community_connection' for c in discover(new_index)))
        # Historical method text is read from the saved artifact, never a current function.
        with patch('money_graph.pipeline.cluster_description_parts', side_effect=AssertionError('must not recalculate')):
            self.assertEqual(Snapshot.load(self.root / 'out', 'startup').data, loaded.data)

    def test_tools_paginate_beyond_graph_limit_and_reject_invalid_arguments_and_results(self):
        write_fixture(self.root / 'large', case(many=True))
        run(self.root / 'large', self.root / 'largeout')
        index = EvidenceIndex(load_calculation(self.root / 'largeout', 'startup'))
        tools = InvestigationTools(index, discover(index), 100)
        a = tools.execute('connections', dict(gid=str(BASE + 3), direction='incoming', offset=0, limit=50))
        b = tools.execute('connections', dict(gid=str(BASE + 3), direction='incoming', offset=50, limit=50))
        self.assertEqual((a['coverage']['total'], a['coverage']['returned'], a['coverage']['omitted']), (77, 50, 27))
        self.assertEqual(b['coverage']['returned'], 27)
        self.assertEqual(len({e['src'] for e in a['data']['connections'] + b['data']['connections']}), 77)
        for name, args in [('inspect_account', {'gid': BASE}), ('inspect_account', {'gid': str(BASE), 'snapshot_id': 'x'}),
                           ('connections', {'gid': str(BASE), 'direction': 'both', 'offset': -1, 'limit': 1}), ('fake', {})]:
            with self.subTest(name=name, args=args), self.assertRaises(ReviewError): tools.execute(name, args)
        forged = deepcopy(a); forged['evidence'][0]['measurements']['sum_kzt']['value'] = 123
        with self.assertRaises(ReviewError): tools.validate_result(forged)
        for mutation in ('coverage', 'pagination', 'limitations'):
            forged = deepcopy(a)
            if mutation == 'coverage': forged['coverage']['omitted'] = 0
            if mutation == 'pagination': forged['coverage']['next_offset'] = None
            if mutation == 'limitations': forged['limitations'] = []
            with self.subTest(mutation=mutation), self.assertRaises(ReviewError): tools.validate_result(forged)

    def test_adaptive_loop_records_checks_and_rejects_fabricated_findings(self):
        tools, provider, updates = self.tools(), ScriptedProvider(), []
        outcome = run_review(tools, AISettings(), Limits(), provider, threading.Event(), lambda **x: updates.append(deepcopy(x)))
        self.assertEqual(outcome['state'], 'partial')
        self.assertEqual(len(outcome['suggestions']), 1)
        self.assertGreater(updates[-1]['coverage']['candidates_found'], updates[-1]['coverage']['candidates_examined'])
        self.assertEqual(updates[-1]['coverage']['candidates_examined'], 1)
        self.assertEqual(updates[-1]['usage']['model_calls'], 8)
        self.assertTrue(any(item.get('type') == 'reasoning' for item in provider.requests[-1]['input']))
        decision = provider.decision()
        for mutation in ('reference', 'value', 'unit', 'unrelated', 'prose'):
            bad = deepcopy(decision)
            if mutation == 'reference': bad['findings'][0]['evidence_id'] = 'f' * 64
            if mutation == 'value': bad['findings'][0]['value'] = 99
            if mutation == 'unit': bad['findings'][0]['unit'] = 'USD'
            if mutation == 'unrelated': bad['graph_selection'].append(str(BASE + 15))
            if mutation == 'prose': bad['reason'] = 'Received 999 KZT.'
            with self.subTest(mutation=mutation), self.assertRaises(ReviewError): tools.validate_decisions([bad])

    def test_missing_daily_is_explicit_and_boundary_counterexample(self):
        old = deepcopy(self.snapshot); old['data'].pop('daily')
        tools = InvestigationTools(EvidenceIndex(old), [], 5)
        output = tools.execute('daily_activity', dict(gid=str(BASE), offset=0, limit=10))
        self.assertFalse(output['data']['available'])
        self.assertTrue(any('legacy' in limit for limit in output['limitations']))
        write_fixture(self.root / 'boundary', case(boundary=True, onward=False))
        run(self.root / 'boundary', self.root / 'boundaryout')
        index = EvidenceIndex(load_calculation(self.root / 'boundaryout', 'startup'))
        tools = InvestigationTools(index, discover(index), 100)
        provider = ScriptedProvider()
        result = run_review(tools, AISettings(), Limits(), provider, threading.Event(), lambda **_: None)
        self.assertEqual(result['suggestions'][0]['disposition'], 'insufficient_evidence')
        self.assertIn('boundary', result['suggestions'][0]['next_step'])
        self.assertNotEqual(provider.requests[5]['input'][-1]['output'], '')

    def test_budget_failure_and_cancel_do_not_fake_success(self):
        for limits, settings, reason in [(replace(Limits(), tool_calls=1), AISettings(), 'tool_limit'),
                (replace(Limits(), total_tokens=1), AISettings(), 'token_limit'),
                (Limits(), AISettings(max_usd=0.0000001), 'spending_limit'),
                (replace(Limits(), runtime_seconds=0), AISettings(), 'runtime_limit')]:
            provider = ScriptedProvider()
            result = run_review(self.tools(), settings, limits, provider, threading.Event(), lambda **_: None)
            self.assertEqual((result['state'], result['stop_reason']), ('partial', reason))
            if reason != 'tool_limit': self.assertFalse(provider.requests)
        def failing(payload, timeout): raise ReviewError('provider_network')
        updates = []
        result = run_review(self.tools(), AISettings(), Limits(), failing, threading.Event(), lambda **x: updates.append(x))
        self.assertEqual(result['state'], 'failed')
        self.assertGreater(updates[-1]['usage']['uncertain_usd'], 0)
        cancelled = threading.Event(); cancelled.set()
        result = run_review(self.tools(), AISettings(), Limits(), ScriptedProvider(), cancelled, lambda **_: None)
        self.assertEqual(result['state'], 'cancelled')

    def wait(self, service, identifier):
        service.workers[identifier][0].join(timeout=10)
        self.assertFalse(service.workers[identifier][0].is_alive())
        return service.get('startup', identifier)

    def test_lifecycle_persistence_briefs_reuse_and_version_isolation(self):
        provider = ScriptedProvider()
        service = ReviewService(self.root / 'out', settings=AISettings(), provider=provider)
        exports = {name: (self.root / 'out' / name).read_bytes() for name in self.manifest['outputs']}
        result = service.start('startup', dict(snapshot_id=self.snapshot['snapshot_id'], locale='en'))
        identifier = result['review_id']; review = self.wait(service, identifier)
        suggestion = review['suggestions'][0]
        service.follow_up('startup', identifier, dict(suggestion_id=suggestion['suggestion_id'], marked=True))
        brief = service.brief('startup', identifier, dict(suggestion_id=suggestion['suggestion_id']))
        restarted = ReviewService(self.root / 'out', settings=AISettings(), provider=ScriptedProvider())
        self.assertTrue(restarted.get('startup', identifier)['suggestions'][0]['follow_up'])
        self.assertEqual(restarted.list('startup')['briefs'][0], brief)
        for name, body in exports.items(): self.assertEqual((self.root / 'out' / name).read_bytes(), body)
        run(self.root / 'input', self.root / 'out', config={'consolidator_min': 7, 'community_algorithm': 'connected_components'})
        self.assertEqual(restarted.get('startup', identifier)['snapshot_id'], self.snapshot['snapshot_id'])
        self.assertEqual(restarted.graph('startup', identifier, suggestion['suggestion_id'])['snapshot_id'], self.snapshot['snapshot_id'])
        self.assertEqual(restarted.store.read('briefs', brief['brief_id']), brief)
        with self.assertRaises(ReviewError): restarted.start('startup', dict(snapshot_id=self.snapshot['snapshot_id'], locale='en'))
        new_snapshot = restarted.calculation('startup')
        newer = restarted.start('startup', dict(snapshot_id=new_snapshot['snapshot_id'], locale='en'))
        new_review = self.wait(restarted, newer['review_id'])
        context = next(check['result']['data'] for check in new_review['checks'] if check['tool'] == 'analysis_context')
        self.assertEqual(context['parameters']['consolidator_min'], 7)
        self.assertEqual(context['parameters']['community_algorithm'], 'connected_components')
        self.assertNotEqual(new_review['compatibility_key'], review['compatibility_key'])
        self.assertEqual(restarted.store.read('briefs', brief['brief_id']), brief)
        # An edgeless fixture completes without calling the model and is reusable.
        nodes, edges, tx = case(); write_fixture(self.root / 'empty', (nodes, edges.iloc[:0], tx.iloc[:0]))
        run(self.root / 'empty', self.root / 'emptyout')
        no_calls = lambda *_: self.fail('No candidates must not call provider')
        empty = ReviewService(self.root / 'emptyout', settings=AISettings(), provider=no_calls)
        body = dict(snapshot_id=empty.calculation('startup')['snapshot_id'], locale='en')
        first = empty.start('startup', body); done = self.wait(empty, first['review_id'])
        self.assertEqual(done['state'], 'completed')
        self.assertTrue(empty.start('startup', body)['reused'])

    def test_cancellation_ignores_late_response_and_restart_marks_interrupted(self):
        entered, release = threading.Event(), threading.Event()
        def blocked(payload, timeout):
            entered.set(); release.wait(timeout=5)
            return dict(status='completed', model=payload['model'], usage=dict(input_tokens=123, output_tokens=10), output=[])
        service = ReviewService(self.root / 'out', settings=AISettings(), provider=blocked)
        created = service.start('startup', dict(snapshot_id=self.snapshot['snapshot_id'], locale='en'))
        identifier = created['review_id']; self.assertTrue(entered.wait(timeout=5))
        with self.assertRaises(ReviewError): service.get('a' * 32, identifier)
        service.cancel('startup', identifier); release.set()
        review = self.wait(service, identifier)
        self.assertEqual(review['state'], 'cancelled')
        self.assertFalse(review['suggestions'])
        self.assertEqual(review['usage']['input_tokens'], 123)
        self.assertTrue(review['usage_final'])
        unfinished = deepcopy(review); unfinished.update(state='running')
        service.store.write('reviews', identifier, unfinished)
        self.assertEqual(ReviewService(self.root / 'out').get('startup', identifier)['state'], 'interrupted')

    def test_http_analysis_bound_routes_body_validation_and_evidence(self):
        with make_server(self.result, self.root / 'out', 0) as server:
            server.reviews = ReviewService(self.root / 'out', settings=AISettings(), provider=ScriptedProvider())
            thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
            base = f'http://127.0.0.1:{server.server_port}'
            def request(path, body=None):
                headers = {'Origin': base, 'Content-Type': 'application/json'}
                with urlopen(Request(base + path, data=encode(body) if body is not None else None, headers=headers)) as response:
                    return json.load(response)
            try:
                route = '/api/analyses/startup/reviews'
                listing = request(route)
                record = request(route, dict(snapshot_id=listing['snapshot_id'], locale='en'))
                saved = self.wait(server.reviews, record['review_id'])
                review_route = route + '/' + record['review_id']
                self.assertEqual(request(review_route)['review_id'], record['review_id'])
                ref = next(iter(saved['evidence']))
                self.assertEqual(request(review_route + '/evidence/' + ref), saved['evidence'][ref])
                with self.assertRaises(HTTPError) as error: request(route, {})
                self.assertEqual(error.exception.code, 400)
                error.exception.close()
                with self.assertRaises(HTTPError) as error: request('/api/analyses/' + 'a' * 32 + '/reviews/' + record['review_id'])
                self.assertEqual(error.exception.code, 404)
                error.exception.close()
            finally:
                server.shutdown(); thread.join()

    def test_strict_json_and_schema_contracts(self):
        for body in ('{"x":1,"x":2}', '{"x":NaN}', '{"x":Infinity}', '{"x":1e400}'):
            with self.assertRaises(ReviewError): parse(body)
        for schema in TOOL_SCHEMAS:
            self.assertTrue(schema['strict'])
            self.assertFalse(schema['parameters']['additionalProperties'])
            self.assertEqual(set(schema['parameters']['required']), set(schema['parameters']['properties']))
        with patch.dict('os.environ', {'OPENAI_API_KEY': '', 'OPENAI_MODEL': 'unknown'}, clear=True), \
                patch('money_graph.investigation.provider.Path.is_file', return_value=False):
            with self.assertRaises(ReviewError): AISettings.from_env()


if __name__ == '__main__': unittest.main()
