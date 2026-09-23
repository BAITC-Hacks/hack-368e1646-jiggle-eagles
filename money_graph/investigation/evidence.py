"""Verified calculation snapshots and exact, addressable measured evidence."""
from copy import deepcopy
from pathlib import Path
import hashlib

from .contracts import ReviewError, digest, parse

TEMPORAL_LIMIT = 'Dates have day precision; daily activity cannot establish intraday order or trace the same funds.'


def load_calculation(path: Path, analysis_id: str) -> dict:
    try:
        manifest = parse((path / 'run_manifest.json').read_bytes())
        names = ('dashboard.json', 'nodes_roles.csv', 'clusters.csv', 'top_nodes.csv')
        payloads = {name: (path / name).read_bytes() for name in names}
        if any(hashlib.sha256(body).hexdigest() != manifest['outputs'][name] for name, body in payloads.items()):
            raise ValueError('checksum')
        data = parse(payloads['dashboard.json'])
        content = dict(data=data, inputs=manifest['inputs'], outputs=manifest['outputs'],
                       versions=manifest['versions'], started_utc=manifest['started_utc'])
        return dict(analysis_id=analysis_id, snapshot_id=digest(content), **content)
    except FileNotFoundError as error:
        raise ReviewError('analysis_missing', 404) from error
    except (OSError, ValueError, KeyError, TypeError) as error:
        raise ReviewError('analysis_damaged', 422) from error


class EvidenceIndex:
    """One review's owned copy; only measured records leave this boundary."""
    def __init__(self, snapshot: dict):
        self.snapshot = deepcopy(snapshot)
        self.data = self.snapshot['data']
        self.nodes = {n['gid']: n for n in self.data['nodes']}
        self.edges = self.data['edges']
        self.daily = self.data.get('daily', [])
        self.limitations = list(self.data['warnings']) + [TEMPORAL_LIMIT]
        if 'daily' not in self.data:
            self.limitations.append('This legacy analysis has no saved daily aggregates. Calculate a new analysis for temporal investigation.')
        if 'methods' not in self.data:
            self.limitations.append('This legacy analysis has incomplete saved method metadata; use its recorded rules and measurements without assuming current settings.')
        self.records: dict[str, dict] = {}
        self.account_refs = {}
        self.edge_refs = {}
        self.daily_refs = {}
        self.community_refs = {}
        self.incident = {gid: [] for gid in self.nodes}
        for node in self.nodes.values():
            metrics = {key: (node[key], unit) for key, unit in {
                'in_deg': 'accounts', 'out_deg': 'accounts', 'in_kzt': 'KZT', 'out_kzt': 'KZT',
                'in_tx': 'transfers', 'out_tx': 'transfers', 'active_days': 'days',
                'depth': 'hops', 'cross_cluster_peers': 'accounts'}.items()}
            metrics.update(boundary=(int(node['boundary']), 'flag'), is_seed=(int(node['is_seed']), 'flag'))
            if node['observed_out_in_ratio'] is not None:
                metrics['observed_out_in_ratio'] = (node['observed_out_in_ratio'], 'ratio')
            self.account_refs[node['gid']] = self.add('account', [node['gid']], metrics,
                dict(gid=node['gid'], cluster_id=node['cluster_id'], role=node['role'],
                     first_date=node['first_date'], last_date=node['last_date']))
        for edge in self.edges:
            a, b = edge['src'], edge['dst']
            ref = self.add('connection', [a, b], {'sum_kzt': (edge['sum_kzt'], 'KZT'), 'n_tx': (edge['n_tx'], 'transfers')},
                           dict(src=a, dst=b))
            self.edge_refs[a, b] = ref
            self.incident[a].append(edge)
            if a != b:
                self.incident[b].append(edge)
        for row in self.daily:
            self.daily_refs[row['src'], row['dst'], row['date']] = self.add('daily', [row['src'], row['dst']],
                {'sum_kzt': (row['sum_kzt'], 'KZT'), 'n_tx': (row['n_tx'], 'transfers')},
                dict(src=row['src'], dst=row['dst'], date=row['date']))
        for cluster in self.data['clusters']:
            cid = cluster['cluster_id']
            members = sorted((n['gid'] for n in self.nodes.values() if n['cluster_id'] == cid), key=int)
            self.community_refs[cid] = self.add('community', members,
                {'n_nodes': (cluster['n_nodes'], 'accounts'), 'n_seed': (cluster['n_seed'], 'accounts'),
                 'sum_kzt_internal': (cluster['sum_kzt_internal'], 'KZT')}, dict(cluster_id=cid))

    def add(self, kind: str, accounts: list[str], metrics: dict, details: dict) -> str:
        record = dict(snapshot_id=self.snapshot['snapshot_id'], kind=kind,
            accounts=sorted(set(accounts), key=int), details=details,
            measurements={key: dict(value=value, unit=unit) for key, (value, unit) in metrics.items()},
            limitations=list(self.limitations))
        ref = digest(record)
        self.records[ref] = dict(evidence_id=ref, **record)
        return ref

    def record(self, ref: str) -> dict:
        if ref not in self.records:
            raise ReviewError('evidence_missing', 404)
        return deepcopy(self.records[ref])
