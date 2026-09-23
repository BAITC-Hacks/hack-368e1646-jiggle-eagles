"""Independent dated examples; amounts in KZT and dates at day precision."""
from datetime import date
import math
import unittest

import pandas as pd

from money_graph.pipeline import analyze, assign_role
from money_graph.temporal import empty_temporal, temporal_features


def dated_fixture(events):
    # Events: payer, recipient, July day, KZT. Account 2 is the inspected client.
    tx = pd.DataFrame([dict(src=a, dst=b, date=date(2026, 7, day), sum_kzt=float(amount))
                       for a, b, day, amount in events])
    gids = sorted(set(tx.src) | set(tx.dst))
    nodes = pd.DataFrame({'gid': gids, 'depth': [0 if g == 1 else 1 for g in gids],
                          'is_seed': [g == 1 for g in gids]})
    edges = tx.groupby(['src', 'dst'], as_index=False).agg(
        sum_kzt=('sum_kzt', lambda amounts: math.fsum(amounts)), n_tx=('sum_kzt', 'size'))
    edges['depth'] = 1
    return nodes, edges, tx


def inspected(events):
    return next(n for n in analyze(*dated_fixture(events)).nodes if n['gid'] == 2)


class TemporalTests(unittest.TestCase):
    def test_order_and_window_change_role_despite_identical_monthly_totals(self):
        for incoming, outgoing, matched, role in [
            (2, 1, 0, 'peripheral'), (2, 2, 0, 'peripheral'),
            (2, 3, 10000, 'transit'), (2, 4, 10000, 'transit'),
            (2, 5, 0, 'peripheral')]:
            with self.subTest(incoming=incoming, outgoing=outgoing):
                node = inspected([(1, 2, incoming, 10000), (2, 3, outgoing, 10000)])
                self.assertEqual(node['observed_out_in_ratio'], 1)
                self.assertEqual(node['temporal']['matched_kzt'], matched)
                self.assertEqual(node['role'], role)

    def test_fifo_partial_allocation_conserves_both_sides(self):
        node = inspected([(1, 2, 1, 10000), (1, 2, 2, 10000),
                          (2, 3, 3, 15000), (2, 3, 4, 10000)])
        tf = node['temporal']
        self.assertEqual(tf['matched_kzt'], 20000)
        self.assertEqual(tf['matched_day1_kzt'], 5000)
        self.assertEqual(tf['matched_day2_kzt'], 15000)
        self.assertEqual([(m['in_date'], m['out_date'], m['amount_kzt']) for m in tf['matches']],
                         [('2026-07-01', '2026-07-03', 10000),
                          ('2026-07-02', '2026-07-03', 5000),
                          ('2026-07-02', '2026-07-04', 5000)])
        # One outgoing amount cannot explain two complete incoming amounts.
        one = inspected([(1, 2, 1, 10000), (1, 2, 2, 10000), (2, 3, 3, 10000)])
        self.assertEqual(one['temporal']['matched_kzt'], 10000)
        self.assertEqual(one['temporal']['matched_in_share'], .5)

    def test_same_day_is_separate_non_additive_and_self_transfers_excluded(self):
        node = inspected([(1, 2, 1, 10000), (2, 3, 1, 10000), (2, 3, 2, 10000), (2, 2, 1, 50000)])
        tf = node['temporal']
        self.assertEqual(tf['incoming_kzt'], 10000)
        self.assertEqual(tf['outgoing_kzt'], 20000)
        self.assertEqual(tf['matched_kzt'], 10000)
        self.assertEqual(tf['same_day_overlap_kzt'], 10000)
        self.assertEqual(tf['same_day'], [{'date': '2026-07-01', 'amount_kzt': 10000}])
        self.assertEqual(inspected([(2, 2, 1, 10000)])['temporal'], empty_temporal())

    def test_duplicates_fractions_shuffle_and_end_of_window(self):
        frames = dated_fixture([(1, 2, 29, 5000.25), (1, 2, 29, 5000.25),
                                (1, 2, 30, 5000), (1, 2, 31, 5000), (2, 3, 31, 10000.5)])
        first = analyze(*frames)
        second = analyze(*(frame.sample(frac=1, random_state=42) for frame in frames))
        self.assertEqual(first.nodes, second.nodes)
        tf = next(n for n in first.nodes if n['gid'] == 2)['temporal']
        self.assertEqual(tf['matched_kzt'], 10000.5)
        self.assertEqual(tf['end_window_incoming_kzt'], 10000)
        self.assertEqual(tf['same_day_overlap_kzt'], 5000)

    def test_temporal_threshold_is_required_in_addition_to_monthly_rule(self):
        base = dict(in_deg=1, out_deg=1, neighbor_clusters=1, observed_out_in_ratio=1,
                    is_seed=False, depth=2)
        for share, expected in [(None, 'peripheral'), (0, 'peripheral'), (.799, 'peripheral'),
                                (.8, 'transit'), (1, 'transit')]:
            self.assertEqual(assign_role(dict(base, temporal={'matched_in_share': share}))[0], expected)
        node = inspected([(1, 2, 1, 10000), (2, 3, 2, 8000), (2, 3, 5, 5000)])
        self.assertEqual(node['temporal']['matched_in_share'], .8)
        self.assertNotEqual(node['role'], 'transit')  # Monthly ratio is 1.3.

    def test_empty_transactions(self):
        _, _, tx = dated_fixture([(1, 2, 1, 5000)])
        self.assertEqual(temporal_features(tx.iloc[:0]), {})

    def test_patterns_coexist_without_replacing_primary_role(self):
        node = inspected([(1, 2, 1, 5000), (4, 2, 1, 5000), (5, 2, 1, 5000),
                          (2, 3, 2, 15000)])
        self.assertEqual(node['role'], 'transit')
        self.assertEqual([p['key'] for p in node['patterns']], ['pattern.collection', 'pattern.transit'])
        self.assertEqual(node['patterns'][0]['params'], {'incoming': 3, 'outgoing': 1})
        self.assertEqual(node['patterns'][1]['params'], {'amount': 15000, 'share': 1})
        distributor = inspected([(1, 2, 1, 25000)] + [(2, g, 2, 5000) for g in range(3, 8)])
        self.assertEqual([p['key'] for p in distributor['patterns']], ['pattern.transit', 'pattern.distribution'])

    def test_patterns_are_independent_of_seed_and_monthly_role_eligibility(self):
        frames = dated_fixture([(1, 2, 1, 10000), (2, 3, 2, 10000), (2, 3, 5, 10000)])
        node = next(n for n in analyze(*frames).nodes if n['gid'] == 2)
        self.assertNotEqual(node['role'], 'transit')
        self.assertEqual([p['key'] for p in node['patterns']], ['pattern.transit'])
        frames[0].loc[frames[0].gid == 2, ['depth', 'is_seed']] = [0, True]
        seed = next(n for n in analyze(*frames).nodes if n['gid'] == 2)
        self.assertNotEqual(seed['role'], 'transit')
        self.assertEqual([p['key'] for p in seed['patterns']], ['pattern.transit'])
        same_day = inspected([(1, 2, 1, 10000), (2, 3, 1, 10000)])
        self.assertEqual(same_day['patterns'], [])
