"""Extend the organizer's load → DiGraph → features → CSV starter.

All money values describe observed transfers in KZT, never balances. Dates
have day precision. No external services are used. See methodology.md for rules.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
import math
from pathlib import Path
import platform
import tempfile
import time

import networkx as nx
import numpy as np
import pandas as pd

SCHEMAS = {
    'nodes_roles.csv': ['gid', 'role', 'role_score', 'cluster_id', 'priority_score', 'evidence'],
    'clusters.csv': ['cluster_id', 'n_nodes', 'n_seed', 'sum_kzt_internal', 'top_gids', 'hypothesis'],
    'top_nodes.csv': ['rank', 'gid', 'role', 'priority_score', 'why'],
}
ROLES = ('coordinator', 'consolidator', 'distributor', 'transit', 'terminal', 'peripheral')
WARNINGS = [
    'Roles, scores and communities are hypotheses for human review, not accusations or calibrated probabilities.',
    'Depth 4 is the collection boundary; missing outgoing links cannot establish a terminal recipient.',
    'Observed flows are not complete balances. Incoming transfers outside the sample are unobserved.',
    'July 2026, intra-bank transfers only, at least 5,000 KZT. Smaller transfers and other banks are absent.',
]
CONFIG = {'rules_version': 1, 'louvain_seed': 42, 'resolution': 1.0, 'threshold': 1e-7,
          'amount_absolute_tolerance_kzt': 0.01, 'amount_relative_tolerance': 1e-12}


class ValidationError(ValueError):
    """Invalid input; no results should be published."""


@dataclass
class Analysis:
    graph: nx.DiGraph
    nodes: list[dict]
    clusters: list[dict]
    top: list[dict]
    profile: dict


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValidationError(message)


def validate(nodes: pd.DataFrame, edges: pd.DataFrame, tx: pd.DataFrame) -> pd.DataFrame:
    """Fail on bad rows; never deduplicate legitimate repeated transaction rows."""
    for name, frame, columns in [('nodes', nodes, ['gid', 'depth', 'is_seed']),
                                  ('edges', edges, ['src', 'dst', 'sum_kzt', 'n_tx', 'depth']),
                                  ('transactions', tx, ['src', 'dst', 'date', 'sum_kzt'])]:
        require(set(columns) <= set(frame.columns), f'{name}: missing required columns')
        require(not frame[columns].isna().any().any(), f'{name}: null required values')
        for col in set(columns) & {'gid', 'src', 'dst', 'depth', 'n_tx'}:
            values = frame[col]
            require(pd.api.types.is_integer_dtype(values.dtype) and not pd.api.types.is_bool_dtype(values.dtype),
                    f'{name}.{col}: expected integer dtype (IDs must not pass through floats)')
            require(all(-(2**63) <= int(x) < 2**63 for x in values), f'{name}.{col}: outside int64 range')
        if 'sum_kzt' in columns:
            require(pd.api.types.is_numeric_dtype(frame.sum_kzt) and not pd.api.types.is_bool_dtype(frame.sum_kzt),
                    f'{name}.sum_kzt: expected numeric amounts')
            require(np.isfinite(frame.sum_kzt.to_numpy(dtype=float)).all(), f'{name}: nonfinite amounts')
            require((frame.sum_kzt >= 5000).all(), f'{name}: amount below 5,000 KZT')
    require(len(nodes) > 0, 'nodes: empty universe')
    require(not nodes.gid.duplicated().any(), 'nodes: duplicate gid')
    require(not edges.duplicated(['src', 'dst']).any(), 'edges: duplicate ordered pair')
    require(pd.api.types.is_bool_dtype(nodes.is_seed), 'nodes.is_seed: expected boolean dtype')
    require(nodes.depth.between(0, 4).all(), 'nodes: depth must be 0–4')
    require((nodes.is_seed == (nodes.depth == 0)).all(), 'nodes: seeds must have depth zero and vice versa')
    require(edges.depth.between(1, 4).all(), 'edges: discovery depth must be 1–4')
    require((edges.n_tx > 0).all(), 'edges: n_tx must be positive')
    universe = set(nodes.gid)
    for name, frame in [('edges', edges), ('transactions', tx)]:
        require(set(frame.src) | set(frame.dst) <= universe, f'{name}: endpoint missing from nodes')
    try:
        dates = pd.to_datetime(tx.date, errors='raise')
        require(dates.dt.tz is None, 'transactions.date: timezone is not part of the source contract')
        require((dates == dates.dt.normalize()).all(), 'transactions.date: expected day precision')
        require(dates.between('2026-07-01', '2026-07-31').all(), 'transactions.date: outside July 2026')
    except (ValueError, TypeError, AttributeError) as error:
        raise ValidationError('transactions.date: expected valid July 2026 dates without time or timezone') from error
    # fsum avoids row-order-dependent accumulation of float64 source values.
    agg = tx.groupby(['src', 'dst'], sort=True).agg(
        total=('sum_kzt', lambda x: math.fsum(x)), count=('sum_kzt', 'size')).reset_index()
    joined = edges.merge(agg, on=['src', 'dst'], how='outer', indicator=True, validate='one_to_one')
    require((joined['_merge'] == 'both').all(), 'edges/transactions: ordered pairs differ')
    require((joined.n_tx == joined['count']).all(), 'edges/transactions: counts differ')
    require(np.isclose(joined.sum_kzt, joined.total, atol=0.01, rtol=1e-12).all(),
            'edges/transactions: KZT sums differ (tolerance 0.01 + 1e-12 × transaction sum)')
    return tx.assign(date=dates)


def build_graph(nodes: pd.DataFrame, edges: pd.DataFrame) -> nx.DiGraph:
    graph = nx.DiGraph()
    # Organizer starter added only edge endpoints. Add ALL nodes, including isolates, first.
    for r in nodes.sort_values('gid').itertuples(index=False):
        graph.add_node(int(r.gid), depth=int(r.depth), is_seed=bool(r.is_seed))
    for r in edges.sort_values(['src', 'dst']).itertuples(index=False):
        graph.add_edge(int(r.src), int(r.dst), sum_kzt=float(r.sum_kzt), n_tx=int(r.n_tx), depth=int(r.depth))
    return graph


def communities(graph: nx.DiGraph) -> dict[int, int]:
    projection = nx.Graph()
    projection.add_nodes_from(graph)
    # Reciprocal amounts add; self-transfers do not define community affinity.
    for a, b, data in graph.edges(data=True):
        if a != b:
            previous = projection.get_edge_data(a, b, {}).get('weight', 0.0)
            projection.add_edge(a, b, weight=previous + data['sum_kzt'])
    isolated = list(nx.isolates(projection))
    active = projection.subgraph([g for g in projection if projection.degree(g) > 0]).copy()
    groups = nx.community.louvain_communities(active, weight='weight', seed=42,
                 resolution=1.0, threshold=1e-7) if active.number_of_edges() else []
    groups.extend({g} for g in isolated)
    ordered = sorted((sorted(group) for group in groups), key=lambda group: group[0])
    return {gid: cluster for cluster, group in enumerate(ordered) for gid in group}


def assign_role(f: dict) -> tuple[str, float, str, list[dict]]:
    i, o, k, ratio = f['in_deg'], f['out_deg'], f['neighbor_clusters'], f['observed_out_in_ratio']
    candidates = []

    def add(role: str, score: float, rule: str) -> None:
        candidates.append({'role': role, 'base_score': round(score, 6), 'rule': rule})

    if i >= 2 and o >= 2 and k >= 3:
        add('coordinator', .55 + .35 * min(k / 6, 1), 'At least 2 incoming and 2 outgoing peers across at least 3 neighbor communities.')
    if i >= 3 and i >= 2 * o:
        add('consolidator', .55 + .35 * min(i / 10, 1), 'At least 3 incoming peers, at least twice the outgoing peer count.')
    if o >= 5 and o >= 2 * i:
        add('distributor', .55 + .35 * min(o / 20, 1), 'At least 5 outgoing peers, at least twice the incoming peer count.')
    if not f['is_seed'] and i > 0 and o > 0 and ratio is not None and .8 <= ratio <= 1.2:
        add('transit', .55 + .35 * max(0, 1 - abs(ratio - 1) / .2), 'Both directions observed; out/in KZT ratio is 0.8–1.2; not a seed. This does not trace the same funds.')
    if f['depth'] < 4 and not f['is_seed'] and i > 0 and o == 0:
        add('terminal', .45 + .15 * min(i / 5, 1), 'Incoming peers but no observed outgoing peers below depth 4; not a seed. Candidate endpoint only.')
    if not candidates:
        add('peripheral', .1 if i + o == 0 else .2, 'No stronger rule matched; insufficient structural evidence, not a judgment about the customer.')
    candidates.sort(key=lambda c: (-c['base_score'], ROLES.index(c['role'])))
    best = candidates[0]
    score = best['base_score'] - (.1 if len(candidates) > 1 else 0)
    score *= .6 if f['depth'] == 4 else 1
    score *= .85 if f['is_seed'] else 1
    return best['role'], round(score, 6), best['rule'], candidates


def analyze(nodes: pd.DataFrame, edges: pd.DataFrame, tx: pd.DataFrame) -> Analysis:
    tx = validate(nodes, edges, tx)
    graph = build_graph(nodes, edges)
    membership = communities(graph)
    days: dict[int, set[str]] = {gid: set() for gid in graph}
    for r in tx.itertuples(index=False):
        day = r.date.date().isoformat()
        days[int(r.src)].add(day)
        days[int(r.dst)].add(day)
    features = []
    for gid, attrs in graph.nodes(data=True):
        incoming, outgoing = list(graph.in_edges(gid, data=True)), list(graph.out_edges(gid, data=True))
        # Self-transfers contribute to flow sums, but not to distinct OTHER clients.
        in_peers, out_peers = set(graph.predecessors(gid)) - {gid}, set(graph.successors(gid)) - {gid}
        peers = in_peers | out_peers
        inflow = math.fsum(d['sum_kzt'] for _, _, d in incoming)
        outflow = math.fsum(d['sum_kzt'] for _, _, d in outgoing)
        features.append(dict(gid=gid, **attrs, in_deg=len(in_peers), out_deg=len(out_peers),
            in_kzt=inflow, out_kzt=outflow, in_tx=sum(d['n_tx'] for _, _, d in incoming),
            out_tx=sum(d['n_tx'] for _, _, d in outgoing), cluster_id=membership[gid],
            neighbor_clusters=len({membership[p] for p in peers}),
            cross_cluster_peers=sum(membership[p] != membership[gid] for p in peers),
            observed_out_in_ratio=outflow / inflow if inflow > 0 else None,
            boundary=attrs['depth'] == 4, active_days=len(days[gid]),
            first_date=min(days[gid]) if days[gid] else None, last_date=max(days[gid]) if days[gid] else None,
            self_transfer=graph.has_edge(gid, gid)))
    max_volume = max(f['in_kzt'] + f['out_kzt'] for f in features)
    for f in features:
        role, score, rule, candidates = assign_role(f)
        volume = f['in_kzt'] + f['out_kzt']
        contributions = {
            'incoming_peers': round(.30 * min(f['in_deg'] / 10, 1), 6),
            'outgoing_peers': round(.25 * min(f['out_deg'] / 10, 1), 6),
            'cross_cluster_peers': round(.20 * min(f['cross_cluster_peers'] / 5, 1), 6),
            'transaction_count': round(.15 * min((f['in_tx'] + f['out_tx']) / 30, 1), 6),
            'observed_volume': round(.10 * math.log1p(volume) / math.log1p(max_volume), 6) if max_volume else 0.0,
        }
        caveat = 'Depth 4: onward unknown.' if f['boundary'] else 'Partial observed network.'
        if f['is_seed']:
            caveat += ' Seed inflow incomplete.'
        evidence = (f"Hypothesis: {role}; peers in/out={f['in_deg']}/{f['out_deg']}; "
                    f"KZT in/out={f['in_kzt']:.4g}/{f['out_kzt']:.4g}. {caveat}")
        require(len(evidence) <= 200, 'Generated evidence exceeds 200 characters')
        priority = round(sum(contributions.values()), 6)
        why = (f"{evidence} Priority={priority:.6f}: " + '; '.join(f'{k}={v:.6f}' for k, v in contributions.items()) +
               f". Rule: {rule} Neighbor communities={f['neighbor_clusters']}; "
               f"cross-community peers={f['cross_cluster_peers']}; transactions in/out={f['in_tx']}/{f['out_tx']}.")
        f.update(role=role, role_score=score, role_rule=rule, candidates=candidates, priority_score=priority,
                 priority_contributions=contributions, evidence=evidence, why=why)
    ranked = sorted(features, key=lambda f: (-f['priority_score'], f['gid']))
    top = [dict(rank=rank, **{k: f[k] for k in SCHEMAS['top_nodes.csv'] if k != 'rank'})
           for rank, f in enumerate(ranked[:max(20, min(50, len(ranked)))], 1)]
    clusters = []
    for cid in sorted(set(membership.values())):
        members = [f for f in ranked if f['cluster_id'] == cid]
        internal = [(a, b, d) for a, b, d in graph.edges(data=True) if membership[a] == cid == membership[b]]
        role_counts = Counter(f['role'] for f in members)
        shape = ', '.join(f'{role}={role_counts[role]}' for role in sorted(role_counts))
        hypothesis = (f"Observed community hypothesis: {len(members)} accounts, {len(internal)} internal directed links; "
                      f"{shape}; boundary={sum(f['boundary'] for f in members)}. Grouping is not proof of an organization.")
        clusters.append(dict(cluster_id=cid, n_nodes=len(members), n_seed=sum(f['is_seed'] for f in members),
            sum_kzt_internal=math.fsum(d['sum_kzt'] for _, _, d in internal),
            top_gids=[str(f['gid']) for f in members[:5]], hypothesis=hypothesis))
    components = sorted((len(c) for c in nx.weakly_connected_components(graph)), reverse=True)
    profile = dict(nodes=len(nodes), edges=len(edges), transactions=len(tx), seeds=int(nodes.is_seed.sum()),
        isolates=len(list(nx.isolates(graph))), weak_components=len(components), component_sizes=components,
        self_loops=nx.number_of_selfloops(graph), clusters=len(clusters),
        depth_counts={str(int(k)): int(v) for k, v in nodes.depth.value_counts().sort_index().items()},
        repeated_transaction_rows=int(tx.duplicated().sum()), observed_kzt=math.fsum(edges.sum_kzt),
        date_start=tx.date.min().date().isoformat() if len(tx) else None,
        date_end=tx.date.max().date().isoformat() if len(tx) else None,
        role_counts=dict(sorted(Counter(f['role'] for f in features).items())))
    return Analysis(graph, features, clusters, top, profile)


def dashboard_data(result: Analysis) -> dict:
    return dict(profile=result.profile, config=CONFIG, warnings=WARNINGS, clusters=result.clusters,
        top=[dict(r, gid=str(r['gid'])) for r in result.top],
        nodes=[dict(n, gid=str(n['gid'])) for n in result.nodes],
        edges=[dict(src=str(a), dst=str(b), **d) for a, b, d in result.graph.edges(data=True)])


def json_bytes(data: object) -> bytes:
    return (json.dumps(data, ensure_ascii=False, sort_keys=True, allow_nan=False, indent=2) + '\n').encode('utf-8')


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(data_dir: Path, out_dir: Path) -> tuple[Analysis, dict]:
    started = time.perf_counter()
    started_utc = datetime.now(timezone.utc).isoformat()
    names = ['nodes.parquet', 'edges.parquet', 'transactions.parquet']
    # Hash before and after reading to reject changing inputs.
    hashes = {name: sha256(data_dir / name) for name in names}
    frames = [pd.read_parquet(data_dir / name, engine='pyarrow') for name in names]
    require(hashes == {name: sha256(data_dir / name) for name in names}, 'Inputs changed while reading')
    result = analyze(*frames)
    out_dir.mkdir(parents=True, exist_ok=True)
    payloads = {'nodes_roles.csv': result.nodes, 'clusters.csv': [dict(c, top_gids=json.dumps(c['top_gids'], separators=(',', ':'))) for c in result.clusters], 'top_nodes.csv': result.top}
    # Stage complete artifacts before replacing previous results; invalid inputs leave them untouched.
    with tempfile.TemporaryDirectory(prefix='.money-graph-', dir=out_dir) as temporary:
        stage = Path(temporary)
        for name, rows in payloads.items():
            pd.DataFrame(rows, columns=SCHEMAS[name]).to_csv(stage / name, index=False, encoding='utf-8',
                lineterminator='\n', float_format='%.6f')
        (stage / 'dashboard.json').write_bytes(json_bytes(dashboard_data(result)))
        output_hashes = {name: sha256(stage / name) for name in [*SCHEMAS, 'dashboard.json']}
        for name in output_hashes:
            (stage / name).replace(out_dir / name)
    manifest = dict(config=CONFIG, inputs=hashes, outputs=output_hashes, profile=result.profile,
        versions={name: importlib.metadata.version(name) for name in ['pandas', 'pyarrow', 'networkx', 'numpy']},
        python=platform.python_version(), machine=platform.machine(), platform=platform.platform(),
        started_utc=started_utc, elapsed_seconds=round(time.perf_counter() - started, 6))
    (out_dir / 'run_manifest.json').write_bytes(json_bytes(manifest))
    return result, manifest
