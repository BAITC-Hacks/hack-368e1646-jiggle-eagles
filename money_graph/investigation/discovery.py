"""Graph-wide deterministic discovery, independent of role priority and the UI."""
from collections import defaultdict, deque
from dataclasses import asdict, dataclass
import math

import networkx as nx

from .contracts import digest
from .evidence import EvidenceIndex


@dataclass(frozen=True)
class DiscoveryConfig:
    version: int = 1
    shared_min_payers: int = 3
    repeated_min_days: int = 2

    def __post_init__(self):
        if self.shared_min_payers < 2 or self.repeated_min_days < 2:
            raise ValueError('Discovery requires at least two peers/dates')


def discover(index: EvidenceIndex, config: DiscoveryConfig = DiscoveryConfig()) -> list[dict]:
    graph = nx.Graph()
    graph.add_nodes_from(index.nodes)
    graph.add_edges_from((e['src'], e['dst']) for e in index.edges)
    components = sorted((sorted(c, key=int) for c in nx.connected_components(graph)), key=lambda c: int(c[0]))
    membership = {gid: str(c[0]) for c in components for gid in c}
    candidates = []

    def add(pattern, accounts, refs, center, strength):
        key = dict(snapshot_id=index.snapshot['snapshot_id'], discovery=asdict(config), pattern=pattern,
                   accounts=sorted(set(accounts), key=int), evidence_refs=list(dict.fromkeys(refs)))
        candidates.append(dict(candidate_id=digest(key), **key, center=center,
                               component=membership[center], strength=strength))

    for gid in sorted(index.nodes, key=int):
        incoming = [e for e in index.incident[gid] if e['dst'] == gid and e['src'] != gid]
        if len(incoming) >= config.shared_min_payers:
            add('shared_recipient', [gid] + [e['src'] for e in incoming],
                [index.account_refs[gid]] + [index.edge_refs[e['src'], gid] for e in incoming], gid, len(incoming))
    bridges = defaultdict(list)
    for edge in index.edges:
        a, b = index.nodes[edge['src']]['cluster_id'], index.nodes[edge['dst']]['cluster_id']
        if a != b:
            bridges[a, b].append(edge)
    for (a, b), edges in sorted(bridges.items()):
        accounts = sorted({g for e in edges for g in (e['src'], e['dst'])}, key=int)
        ref = index.add('community_connection', accounts,
            {'connections': (len(edges), 'connections'), 'sum_kzt': (math.fsum(e['sum_kzt'] for e in edges), 'KZT'),
             'n_tx': (sum(e['n_tx'] for e in edges), 'transfers')}, dict(src_community=a, dst_community=b))
        # Separate disconnected components even if a replacement community method groups them together.
        for component in sorted({membership[g] for g in accounts}, key=int):
            subset = [e for e in edges if membership[e['src']] == component]
            gids = sorted({g for e in subset for g in (e['src'], e['dst'])}, key=int)
            add('community_connection', gids, [ref] + [index.edge_refs[e['src'], e['dst']] for e in subset],
                subset[0]['src'], len(subset))
    pairs = defaultdict(list)
    for row in index.daily:
        if row['src'] != row['dst']:
            pairs[row['src'], row['dst']].append(row)
    for (a, b), rows in sorted(pairs.items(), key=lambda p: (int(p[0][0]), int(p[0][1]))):
        days = sorted({r['date'] for r in rows})
        if len(days) >= config.repeated_min_days:
            ref = index.add('repeated_connection', [a, b],
                {'active_days': (len(days), 'days'), 'sum_kzt': (math.fsum(r['sum_kzt'] for r in rows), 'KZT'),
                 'n_tx': (sum(r['n_tx'] for r in rows), 'transfers')}, dict(src=a, dst=b, dates=days))
            add('repeated_connection', [a, b], [ref, index.edge_refs[a, b]], b, len(days))
    # Round-robin by pattern and component prevents one giant component or motif monopolizing the budget.
    buckets = defaultdict(list)
    for candidate in candidates:
        buckets[candidate['pattern'], candidate['component']].append(candidate)
    queues = [deque(sorted(bucket, key=lambda c: (-c['strength'], int(c['center']), c['candidate_id'])))
              for _, bucket in sorted(buckets.items(), key=lambda p: (p[0][0], int(p[0][1])))]
    ordered = []
    while any(queues):
        for queue in queues:
            if queue:
                ordered.append(queue.popleft())
    return ordered
