"""Extend the organizer's load → DiGraph → features → CSV starter.

All money values describe observed transfers in KZT, never balances. Dates
have day precision. No external services are used. See methodology.md for rules.
"""
from __future__ import annotations

from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass, field
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

from .i18n import message, render
from .methods import CONFIG, configuration, rule_parameters, scoring_description

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



class ValidationError(ValueError):
    """Invalid input with a stable, localizable descriptor."""

    def __init__(self, key: str, **params: object):
        self.message = message(key, **params)
        super().__init__(render(self.message))


@dataclass
class Analysis:
    graph: nx.DiGraph
    nodes: list[dict]
    clusters: list[dict]
    top: list[dict]
    profile: dict
    config: dict = field(default_factory=configuration)
    daily: list[dict] = field(default_factory=list)


def require(condition: bool, key: str, **params: object) -> None:
    if not condition:
        raise ValidationError(key, **params)


def validate(nodes: pd.DataFrame, edges: pd.DataFrame, tx: pd.DataFrame, config: dict | None = None) -> pd.DataFrame:
    """Fail on bad rows; never deduplicate legitimate repeated transaction rows."""
    c = configuration(config)
    for name, frame, columns in [('nodes', nodes, ['gid', 'depth', 'is_seed']),
                                  ('edges', edges, ['src', 'dst', 'sum_kzt', 'n_tx', 'depth']),
                                  ('transactions', tx, ['src', 'dst', 'date', 'sum_kzt'])]:
        require(set(columns) <= set(frame.columns), 'validation.columns', name=name)
        require(not frame[columns].isna().any().any(), 'validation.null', name=name)
        for col in set(columns) & {'gid', 'src', 'dst', 'depth', 'n_tx'}:
            values = frame[col]
            require(pd.api.types.is_integer_dtype(values.dtype) and not pd.api.types.is_bool_dtype(values.dtype),
                    'validation.integer', name=name, col=col)
            require(all(-(2**63) <= int(x) < 2**63 for x in values), 'validation.range', name=name, col=col)
        if 'sum_kzt' in columns:
            require(pd.api.types.is_numeric_dtype(frame.sum_kzt) and not pd.api.types.is_bool_dtype(frame.sum_kzt),
                    'validation.numeric', name=name)
            require(np.isfinite(frame.sum_kzt.to_numpy(dtype=float)).all(), 'validation.finite', name=name)
            require((frame.sum_kzt >= 5000).all(), 'validation.threshold', name=name)
    require(len(nodes) > 0, 'validation.emptyNodes')
    require(not nodes.gid.duplicated().any(), 'validation.duplicateId')
    require(not edges.duplicated(['src', 'dst']).any(), 'validation.duplicatePair')
    require(pd.api.types.is_bool_dtype(nodes.is_seed), 'validation.boolean')
    require(nodes.depth.between(0, 4).all(), 'validation.nodeDepth')
    require((nodes.is_seed == (nodes.depth == 0)).all(), 'validation.seedDepth')
    require(edges.depth.between(1, 4).all(), 'validation.edgeDepth')
    require((edges.n_tx > 0).all(), 'validation.positiveCount')
    universe = set(nodes.gid)
    for name, frame in [('edges', edges), ('transactions', tx)]:
        require(set(frame.src) | set(frame.dst) <= universe, 'validation.endpoint', name=name)
    try:
        dates = pd.to_datetime(tx.date, errors='raise')
        require(dates.dt.tz is None, 'validation.timezone')
        require((dates == dates.dt.normalize()).all(), 'validation.dayPrecision')
        require(dates.between('2026-07-01', '2026-07-31').all(), 'validation.dateRange')
    except ValidationError:
        raise
    except (ValueError, TypeError, AttributeError) as error:
        raise ValidationError('validation.date') from error
    # fsum avoids row-order-dependent accumulation of float64 source values.
    agg = tx.groupby(['src', 'dst'], sort=True).agg(
        total=('sum_kzt', lambda x: math.fsum(x)), count=('sum_kzt', 'size')).reset_index()
    joined = edges.merge(agg, on=['src', 'dst'], how='outer', indicator=True, validate='one_to_one')
    require((joined['_merge'] == 'both').all(), 'validation.pairs')
    require((joined.n_tx == joined['count']).all(), 'validation.counts')
    require(np.isclose(joined.sum_kzt, joined.total, atol=c['amount_absolute_tolerance_kzt'], rtol=c['amount_relative_tolerance']).all(),
            'validation.sums')
    return tx.assign(date=dates)


def build_graph(nodes: pd.DataFrame, edges: pd.DataFrame) -> nx.DiGraph:
    graph = nx.DiGraph()
    # Organizer starter added only edge endpoints. Add ALL nodes, including isolates, first.
    for r in nodes.sort_values('gid').itertuples(index=False):
        graph.add_node(int(r.gid), depth=int(r.depth), is_seed=bool(r.is_seed))
    for r in edges.sort_values(['src', 'dst']).itertuples(index=False):
        graph.add_edge(int(r.src), int(r.dst), sum_kzt=float(r.sum_kzt), n_tx=int(r.n_tx), depth=int(r.depth))
    return graph


def communities(graph: nx.DiGraph, config: dict | None = None) -> dict[int, int]:
    c = configuration(config)
    projection = nx.Graph()
    projection.add_nodes_from(graph)
    # Reciprocal amounts add; self-transfers do not define community affinity.
    for a, b, data in graph.edges(data=True):
        if a != b:
            previous = projection.get_edge_data(a, b, {}).get('weight', 0.0)
            projection.add_edge(a, b, weight=previous + data['sum_kzt'])
    isolated = list(nx.isolates(projection))
    active = projection.subgraph([g for g in projection if projection.degree(g) > 0]).copy()
    groups = (list(nx.connected_components(active)) if c['community_algorithm'] == 'connected_components' else
              nx.community.louvain_communities(active, weight='weight', seed=c['louvain_seed'],
                 resolution=c['resolution'], threshold=c['threshold'])) if active.number_of_edges() else []
    groups.extend({g} for g in isolated)
    ordered = sorted((sorted(group) for group in groups), key=lambda group: group[0])
    return {gid: cluster for cluster, group in enumerate(ordered) for gid in group}


def assign_role(f: dict, config: dict | None = None) -> tuple[str, float, str, list[dict]]:
    c = configuration(config)
    params = rule_parameters(c)
    i, o, k, ratio = f['in_deg'], f['out_deg'], f['neighbor_clusters'], f['observed_out_in_ratio']
    candidates = []

    def add(role: str, score: float, rule: str) -> None:
        candidates.append({'role': role, 'base_score': round(score, 6), 'rule': rule})

    if i >= c['coordinator_in'] and o >= c['coordinator_out'] and k >= c['coordinator_communities']:
        add('coordinator', c['confidence_base'] + c['confidence_gain'] * min(k / c['coordinator_scale'], 1), render(message('rule.coordinator', **params)))
    if i >= c['consolidator_min'] and i >= c['fan_ratio'] * o:
        add('consolidator', c['confidence_base'] + c['confidence_gain'] * min(i / c['consolidator_scale'], 1), render(message('rule.consolidator', **params)))
    if o >= c['distributor_min'] and o >= c['fan_ratio'] * i:
        add('distributor', c['confidence_base'] + c['confidence_gain'] * min(o / c['distributor_scale'], 1), render(message('rule.distributor', **params)))
    if not f['is_seed'] and i > 0 and o > 0 and ratio is not None and 1 - c['transit_tolerance'] <= ratio <= 1 + c['transit_tolerance']:
        add('transit', c['confidence_base'] + c['confidence_gain'] * max(0, 1 - abs(ratio - 1) / c['transit_tolerance']), render(message('rule.transit', **params)))
    if f['depth'] < 4 and not f['is_seed'] and i > 0 and o == 0:
        add('terminal', c['terminal_base'] + c['terminal_gain'] * min(i / c['terminal_scale'], 1), render(message('rule.terminal', **params)))
    if not candidates:
        add('peripheral', c['peripheral_isolate'] if i + o == 0 else c['peripheral_connected'], render(message('rule.peripheral', **params)))
    candidates.sort(key=lambda c: (-c['base_score'], ROLES.index(c['role'])))
    best = candidates[0]
    score = best['base_score'] - (c['ambiguity_deduction'] if len(candidates) > 1 else 0)
    score *= c['boundary_multiplier'] if f['depth'] == 4 else 1
    score *= c['seed_multiplier'] if f['is_seed'] else 1
    return best['role'], round(score, 6), best['rule'], candidates


def cluster_description_parts(members: list[dict], internal: list[tuple], graph: nx.DiGraph,
                              membership: dict[int, int], config: dict | None = None) -> list[dict]:
    """Measured motifs as message descriptors, independent of display language."""
    c = configuration(config)
    fan_in = [f for f in members if f['in_deg'] >= c['consolidator_min'] and f['in_deg'] >= c['fan_ratio'] * f['out_deg']]
    fan_out = [f for f in members if f['out_deg'] >= c['distributor_min'] and f['out_deg'] >= c['fan_ratio'] * f['in_deg']]
    bridges = []
    for f in members:
        gid = f['gid']
        incoming = {membership[p] for p in graph.predecessors(gid) if p != gid}
        outgoing = {membership[p] for p in graph.successors(gid) if p != gid}
        if incoming and outgoing and len(incoming | outgoing) >= 2:
            bridges.append((f, len(incoming | outgoing)))
    parts = [message('cluster.intro', accounts=len(members), links=len(internal)),
             message('cluster.fans', incoming=len(fan_in), outgoing=len(fan_out), consolidator=c['consolidator_min'], distributor=c['distributor_min'], ratio=c['fan_ratio'])]
    for candidates, direction, key in [(fan_in, 'in_deg', 'cluster.fanIn'), (fan_out, 'out_deg', 'cluster.fanOut')]:
        if candidates:
            f = min(candidates, key=lambda f: (-f[direction], f['gid']))
            parts.append(message(key, gid=str(f['gid']), incoming=f['in_deg'], outgoing=f['out_deg'],
                                 inKzt=f"{f['in_kzt']:.2f}", outKzt=f"{f['out_kzt']:.2f}"))
    parts.append(message('cluster.bridges', count=len(bridges)))
    if bridges:
        f, count = min(bridges, key=lambda pair: (-pair[1], pair[0]['gid']))
        parts.append(message('cluster.bridgeExample', gid=str(f['gid']), communities=count,
                             peers=f['cross_cluster_peers']))
    if not fan_in and not fan_out and not bridges:
        parts.append(message('cluster.noPattern'))
    role_counts = Counter(f['role'] for f in members)
    parts.append(message('cluster.roles', roles=', '.join(f'{role}={role_counts[role]}' for role in sorted(role_counts))))
    parts.append(message('cluster.caveats', boundary=sum(f['boundary'] for f in members),
                         seeds=sum(f['is_seed'] for f in members)))
    return parts


def cluster_description(members: list[dict], internal: list[tuple], graph: nx.DiGraph,
                        membership: dict[int, int], config: dict | None = None) -> str:
    return ' '.join(render(part) for part in cluster_description_parts(members, internal, graph, membership, config))


def analyze(nodes: pd.DataFrame, edges: pd.DataFrame, tx: pd.DataFrame,
            on_validated: Callable[[], None] | None = None, config: dict | None = None) -> Analysis:
    c = configuration(config)
    tx = validate(nodes, edges, tx, c)
    if on_validated:
        on_validated()
    graph = build_graph(nodes, edges)
    membership = communities(graph, c)
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
        role, score, rule, candidates = assign_role(f, c)
        volume = f['in_kzt'] + f['out_kzt']
        contributions = {
            'incoming_peers': round(c['priority_in_weight'] * min(f['in_deg'] / c['priority_in_scale'], 1), 6),
            'outgoing_peers': round(c['priority_out_weight'] * min(f['out_deg'] / c['priority_out_scale'], 1), 6),
            'cross_cluster_peers': round(c['priority_cross_weight'] * min(f['cross_cluster_peers'] / c['priority_cross_scale'], 1), 6),
            'transaction_count': round(c['priority_tx_weight'] * min((f['in_tx'] + f['out_tx']) / c['priority_tx_scale'], 1), 6),
            'observed_volume': round(c['priority_volume_weight'] * math.log1p(volume) / math.log1p(max_volume), 6) if max_volume else 0.0,
        }
        caveat = 'Depth 4: onward unknown.' if f['boundary'] else 'Partial observed network.'
        if f['is_seed']:
            caveat += ' Seed inflow incomplete.'
        evidence = (f"Hypothesis: {role}; peers in/out={f['in_deg']}/{f['out_deg']}; "
                    f"KZT in/out={f['in_kzt']:.4g}/{f['out_kzt']:.4g}. {caveat}")
        require(len(evidence) <= 200, 'validation.evidence')
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
        hypothesis = cluster_description(members, internal, graph, membership, c)
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
    daily = [dict(src=str(int(src)), dst=str(int(dst)), date=day.date().isoformat(),
                  sum_kzt=math.fsum(group.sum_kzt), n_tx=len(group))
             for (src, dst, day), group in tx.groupby(['src', 'dst', 'date'], sort=True)]
    return Analysis(graph, features, clusters, top, profile, c, daily)


def dashboard_data(result: Analysis) -> dict:
    membership = {n['gid']: n['cluster_id'] for n in result.nodes}
    clusters = []
    for cluster in result.clusters:
        cid = cluster['cluster_id']
        members = [n for n in result.nodes if n['cluster_id'] == cid]
        internal = [(a, b, d) for a, b, d in result.graph.edges(data=True) if membership[a] == cid == membership[b]]
        clusters.append(dict(cluster, description_parts=cluster_description_parts(members, internal, result.graph, membership, result.config),
                             role_counts=dict(sorted(Counter(n['role'] for n in members).items()))))
    # Templates are frozen too: updating translations must not rewrite old methods.
    catalogs = {locale: {key: value for key, value in json.loads((Path(__file__).parent / f'static/locales/{locale}.json').read_text()).items()
                        if key.startswith(('rule.', 'cluster.'))} for locale in ('en', 'kk', 'ru')}
    return dict(schema_version=2, profile=result.profile, config=result.config, warnings=WARNINGS,
        methods=scoring_description(result.config), rule_parameters=rule_parameters(result.config), method_catalogs=catalogs,
        clusters=clusters, daily=result.daily,
        top=[dict(r, gid=str(r['gid'])) for r in result.top],
        nodes=[dict(n, gid=str(n['gid'])) for n in result.nodes],
        edges=[dict(src=str(a), dst=str(b), **d) for a, b, d in result.graph.edges(data=True)])


def json_bytes(data: object) -> bytes:
    return (json.dumps(data, ensure_ascii=False, sort_keys=True, allow_nan=False, indent=2) + '\n').encode('utf-8')


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(data_dir: Path, out_dir: Path, progress: Callable[[str], None] | None = None, config: dict | None = None) -> tuple[Analysis, dict]:
    started = time.perf_counter()
    started_utc = datetime.now(timezone.utc).isoformat()
    names = ['nodes.parquet', 'edges.parquet', 'transactions.parquet']
    if progress:
        progress('validating')
    # Hash before and after reading to reject changing inputs.
    hashes = {name: sha256(data_dir / name) for name in names}
    frames = []
    for name in names:
        try:
            frames.append(pd.read_parquet(data_dir / name, engine='pyarrow'))
        except (ValueError, OSError) as error:
            raise ValidationError('validation.parquet', name=name) from error
    require(hashes == {name: sha256(data_dir / name) for name in names}, 'validation.changed')
    result = analyze(*frames, on_validated=(lambda: progress('analyzing')) if progress else None, config=config)
    if progress:
        progress('exporting')
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
    manifest = dict(config=result.config, inputs=hashes, outputs=output_hashes, profile=result.profile,
        versions={name: importlib.metadata.version(name) for name in ['pandas', 'pyarrow', 'networkx', 'numpy']},
        python=platform.python_version(), machine=platform.machine(), platform=platform.platform(),
        started_utc=started_utc, elapsed_seconds=round(time.perf_counter() - started, 6))
    (out_dir / 'run_manifest.json').write_bytes(json_bytes(manifest))
    return result, manifest
