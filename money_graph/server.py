"""Loopback dashboard with isolated upload runs and atomic in-memory publication."""
from collections import Counter
from dataclasses import dataclass
from email import policy
from email.parser import BytesParser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import re
import tempfile
import threading
from urllib.parse import parse_qs, urlsplit
import uuid

from .pipeline import Analysis, SCHEMAS, ValidationError, cluster_description_parts, dashboard_data, json_bytes, run
from .i18n import message, render

NODE_LIMIT = 50
# Compact per-account projection: the overview map plots every account at once.
MAP_FIELDS = ('gid', 'role', 'cluster_id', 'depth', 'is_seed', 'boundary', 'in_deg', 'out_deg',
              'in_kzt', 'out_kzt', 'in_tx', 'out_tx', 'role_score', 'priority_score')
# Grouped flow schematic: how the network works, before any single account is opened.
CLUSTER_GROUPS = 12
MAX_UPLOAD_BYTES = 64 * 1024 * 1024
INPUT_NAMES = ('nodes', 'edges', 'transactions')
BUSY = {'receiving', 'validating', 'analyzing', 'exporting'}


@dataclass(frozen=True)
class Snapshot:
    revision: str
    data: dict
    nodes: dict
    incident: dict
    peers: dict
    exports: dict[str, bytes]
    map_payload: bytes
    flow_payload: bytes

    @classmethod
    def create(cls, result: Analysis, out_dir: Path, revision: str) -> 'Snapshot':
        data = dashboard_data(result)
        membership = {n['gid']: n['cluster_id'] for n in result.nodes}
        data['clusters'] = [dict(cluster) for cluster in data['clusters']]
        for cluster in data['clusters']:
            cid = cluster['cluster_id']
            members = [n for n in result.nodes if n['cluster_id'] == cid]
            internal = [(a, b, d) for a, b, d in result.graph.edges(data=True)
                        if membership[a] == cid == membership[b]]
            cluster['description_parts'] = cluster_description_parts(members, internal, result.graph, membership)
            cluster['role_counts'] = {role: sum(n['role'] == role for n in members)
                                      for role in sorted({n['role'] for n in members})}
        nodes = {n['gid']: n for n in data['nodes']}
        incident: dict[str, list[dict]] = {gid: [] for gid in nodes}
        peers: dict[str, set[str]] = {gid: set() for gid in nodes}
        for edge in data['edges']:
            a, b = edge['src'], edge['dst']
            incident[a].append(edge)
            if b != a:
                incident[b].append(edge)
                peers[a].add(b)
                peers[b].add(a)
        exports = {name: (out_dir / name).read_bytes() for name in [*SCHEMAS, 'run_manifest.json']}
        map_payload = json_bytes(dict(revision=revision, profile=data['profile'],
                                      nodes=[{field: node[field] for field in MAP_FIELDS} for node in data['nodes']]))
        flow_payload = json_bytes(dict(revision=revision, modes=flow_modes(data['nodes'], data['edges'])))
        return cls(revision, data, nodes, incident, peers, exports, map_payload, flow_payload)

    def neighborhood(self, gid: str, hops: int) -> dict:
        # Either direction defines hop distance; all display edges stay directed.
        distances = {gid: 0}
        frontier = {gid}
        for depth in range(1, hops + 1):
            frontier = {peer for account in frontier for peer in self.peers[account]} - distances.keys()
            distances.update((peer, depth) for peer in frontier)
        ordered = sorted(distances, key=lambda peer: (distances[peer], int(peer)))
        visible = set(ordered[:NODE_LIMIT])
        edges = [e for peer in ordered[:NODE_LIMIT] for e in self.incident[peer]
                 if e['src'] == peer and e['dst'] in visible]
        return dict(revision=self.revision, center=gid, hops=hops, node_limit=NODE_LIMIT,
                    total_nodes=len(ordered), omitted_nodes=max(0, len(ordered) - NODE_LIMIT),
                    nodes=[dict(self.nodes[peer], hop=distances[peer]) for peer in ordered[:NODE_LIMIT]],
                    edges=edges)


def flow_modes(nodes: list[dict], edges: list[dict]) -> dict:
    """Collapse 2k accounts into a handful of groups per mode, keeping every KZT accounted for.

    Grouping is presentation only: roles, scores and the CSV exports are untouched. Each mode
    reports its groups and the directed money between them, so the schematic stays checkable
    against nodes_roles.csv.
    """
    by_gid = {n['gid']: n for n in nodes}
    ranked = [cluster for cluster, _ in Counter(n['cluster_id'] for n in nodes).most_common(CLUSTER_GROUPS)]
    largest = set(ranked)

    def role_key(node: dict) -> str:
        return node['role']

    def depth_role_key(node: dict) -> str:
        return f"d{node['depth']}:{node['role']}"

    def cluster_key(node: dict) -> str:
        return f"c{node['cluster_id']}" if node['cluster_id'] in largest else 'other'

    modes = {}
    for name, key_of in [('role', role_key), ('depth_role', depth_role_key), ('cluster', cluster_key)]:
        members: dict[str, list[dict]] = {}
        for node in nodes:
            members.setdefault(key_of(node), []).append(node)
        internal: Counter = Counter()
        internal_tx: Counter = Counter()
        links: Counter = Counter()
        link_tx: Counter = Counter()
        for edge in edges:
            source, target = key_of(by_gid[edge['src']]), key_of(by_gid[edge['dst']])
            if source == target:
                internal[source] += edge['sum_kzt']
                internal_tx[source] += edge['n_tx']
            else:
                links[(source, target)] += edge['sum_kzt']
                link_tx[(source, target)] += edge['n_tx']
        groups = []
        for key, group in members.items():
            incoming = sum(value for (_, target), value in links.items() if target == key)
            outgoing = sum(value for (source, _), value in links.items() if source == key)
            sample = group[0]
            groups.append(dict(
                id=key, kind=name,
                role=Counter(n['role'] for n in group).most_common(1)[0][0],
                depth=sample['depth'] if name == 'depth_role' else None,
                cluster_id=sample['cluster_id'] if name == 'cluster' and key != 'other' else None,
                n_nodes=len(group), n_seed=sum(n['is_seed'] for n in group),
                n_boundary=sum(n['boundary'] for n in group),
                in_kzt=round(incoming, 2), out_kzt=round(outgoing, 2),
                self_kzt=round(internal[key], 2), self_tx=internal_tx[key],
                throughput=round(incoming + outgoing + internal[key], 2)))
        groups.sort(key=lambda g: -g['throughput'])
        modes[name] = dict(
            groups=groups,
            links=sorted((dict(src=source, dst=target, sum_kzt=round(value, 2), n_tx=link_tx[(source, target)])
                          for (source, target), value in links.items()),
                         key=lambda link: -link['sum_kzt']),
            total_kzt=round(sum(links.values()) + sum(internal.values()), 2))
    return modes


def parse_upload(content_type: str, body: bytes) -> dict[str, bytes]:
    message = BytesParser(policy=policy.default).parsebytes(
        f'Content-Type: {content_type}\r\nMIME-Version: 1.0\r\n\r\n'.encode('ascii') + body)
    if message.get_content_type() != 'multipart/form-data' or not message.is_multipart() or message.defects:
        raise ValidationError('error.multipart')
    files = {}
    for part in message.iter_parts():
        name = part.get_param('name', header='content-disposition')
        if (part.defects or part.is_multipart() or part.get_content_disposition() != 'form-data'
                or name not in INPUT_NAMES or name in files or part.get_filename() != f'{name}.parquet'):
            raise ValidationError('error.exactFiles')
        payload = part.get_payload(decode=True)
        if not payload:
            raise ValidationError('error.emptyFile', name=name)
        files[name] = payload
    if set(files) != set(INPUT_NAMES):
        raise ValidationError('error.threeFiles')
    return files


class DashboardServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, result: Analysis | None, out_dir: Path, port: int, handler):
        self.out_dir = out_dir
        self.lock = threading.Lock()
        self.active = Snapshot.create(result, out_dir, 'startup') if result else None
        self.job = dict(state='idle', message=render(message('status.idle')), run_directory=None)
        self.worker: threading.Thread | None = None
        super().__init__(('127.0.0.1', port), handler)

    def status(self) -> dict:
        with self.lock:
            return dict(self.job, revision=self.active.revision if self.active else None,
                        node_limit=NODE_LIMIT, max_upload_bytes=MAX_UPLOAD_BYTES)

    def progress(self, state: str) -> None:
        with self.lock:
            self.job.update(state=state, message=render(message('status.' + state)))

    def fail(self, error: ValidationError) -> None:
        with self.lock:
            self.job.update(state='failed', message=str(error) + ' ' + render(message('status.preserved')),
                            error_message=error.message)

    def analyze_upload(self, files: dict[str, bytes]) -> None:
        try:
            uploads = self.out_dir / 'uploads'
            uploads.mkdir(parents=True, exist_ok=True)
            revision = uuid.uuid4().hex
            with tempfile.TemporaryDirectory(prefix='.pending-', dir=uploads) as temporary:
                stage = Path(temporary)
                inputs, outputs = stage / 'input', stage / 'output'
                inputs.mkdir()
                for name, payload in files.items():
                    (inputs / f'{name}.parquet').write_bytes(payload)
                result, manifest = run(inputs, outputs, self.progress)
                snapshot = Snapshot.create(result, outputs, revision)
                destination = uploads / revision
                # Retain reproducible raw inputs and complete artifacts only on success.
                stage.rename(destination)
                with self.lock:
                    self.active = snapshot
                    self.job = dict(state='succeeded', message=render(message('status.succeeded')),
                                    run_directory=str(destination.resolve()), elapsed_seconds=manifest['elapsed_seconds'])
        except ValidationError as error:
            self.fail(error)
        except Exception:
            # Do not leak raw data or filesystem details from parser/runtime errors.
            self.fail(ValidationError('error.analysis'))

    def server_close(self) -> None:
        super().server_close()
        if self.worker:
            self.worker.join()


def make_server(result: Analysis | None, out_dir: Path, port: int = 8765) -> DashboardServer:
    static = Path(__file__).parent / 'static'
    assets = {'/': ('index.html', 'text/html'), '/style.css': ('style.css', 'text/css'),
              '/file-preview.js': ('file-preview.js', 'text/javascript'),
              '/app.js': ('app.js', 'text/javascript'), '/i18n.js': ('i18n.js', 'text/javascript'),
              '/map.js': ('map.js', 'text/javascript'),
              '/flows.js': ('flows.js', 'text/javascript'),
              **{f'/locales/{locale}.json': (f'locales/{locale}.json', 'application/json')
                 for locale in ('en', 'kk', 'ru')}}

    class Handler(BaseHTTPRequestHandler):
        server: DashboardServer

        def log_message(self, format: str, *args: object) -> None:
            # Avoid logging customer queries/IDs. The UI displays explicit errors.
            return

        def send(self, status: int, body: bytes, content_type: str) -> None:
            self.send_response(status)
            self.send_header('Content-Type', content_type + '; charset=utf-8')
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
            self.end_headers()
            self.wfile.write(body)

        def error(self, status: int, key: str, **params: object) -> None:
            part = message(key, **params)
            self.send(status, json_bytes({'error': render(part), 'error_message': part}), 'application/json')

        def local_request(self, mutation: bool = False) -> bool:
            allowed_hosts = {f'127.0.0.1:{self.server.server_port}', f'localhost:{self.server.server_port}'}
            host = self.headers.get('Host')
            if host not in allowed_hosts or (mutation and self.headers.get('Origin') != f'http://{host}'):
                self.close_connection = True
                self.error(403, 'error.origin')
                return False
            return True

        def do_POST(self) -> None:
            if not self.local_request(mutation=True):
                return
            if self.path != '/api/analysis':
                self.close_connection = True
                self.error(404, 'error.notFound')
                return
            lengths = self.headers.get_all('Content-Length', [])
            if self.headers.get('Transfer-Encoding') or len(lengths) != 1 or not lengths[0].isdigit():
                self.close_connection = True
                self.error(400, 'error.contentLength')
                return
            length = int(lengths[0])
            if not 0 < length <= MAX_UPLOAD_BYTES:
                self.close_connection = True
                self.error(413, 'error.uploadLimit')
                return
            with self.server.lock:
                busy = self.server.job['state'] in BUSY
                if not busy:
                    self.server.job = dict(state='receiving', message=render(message('status.receiving')), run_directory=None)
            if busy:
                self.close_connection = True
                self.error(409, 'error.busy')
                return
            try:
                self.connection.settimeout(30)
                body = self.rfile.read(length)
                if len(body) != length:
                    raise ValidationError('error.interrupted')
                files = parse_upload(self.headers.get('Content-Type', ''), body)
            except (ValidationError, ValueError, OSError) as error:
                failure = error if isinstance(error, ValidationError) else ValidationError('error.receive')
                self.server.fail(failure)
                self.error(400, failure.message['key'], **failure.message['params'])
                return
            self.server.progress('validating')
            self.server.worker = threading.Thread(target=self.server.analyze_upload, args=(files,), daemon=True)
            self.server.worker.start()
            self.send(202, json_bytes({'message': render(message('status.accepted'))}), 'application/json')

        def do_GET(self) -> None:
            if not self.local_request():
                return
            url = urlsplit(self.path)
            if url.path in assets:
                filename, content_type = assets[url.path]
                self.send(200, (static / filename).read_bytes(), content_type)
                return
            if url.path == '/api/status':
                self.send(200, json_bytes(self.server.status()), 'application/json')
                return
            with self.server.lock:
                snapshot = self.server.active
            if url.path not in {'/api/overview', '/api/map', '/api/flows', '/api/account', '/api/graph'} and not (
                    url.path.startswith('/exports/') and url.path.removeprefix('/exports/') in [*SCHEMAS, 'run_manifest.json']):
                self.error(404, 'error.notFound')
                return
            if snapshot is None:
                self.error(503, 'error.noAnalysis')
                return
            if url.path == '/api/map':
                self.send(200, snapshot.map_payload, 'application/json')
            elif url.path == '/api/flows':
                self.send(200, snapshot.flow_payload, 'application/json')
            elif url.path == '/api/overview':
                self.send(200, json_bytes(dict(revision=snapshot.revision, **{k: snapshot.data[k]
                    for k in ['profile', 'config', 'warnings', 'clusters', 'top']})), 'application/json')
            elif url.path in {'/api/account', '/api/graph'}:
                query = parse_qs(url.query, keep_blank_values=True)
                allowed = {'gid', 'revision', 'hops'} if url.path == '/api/graph' else {'gid', 'revision'}
                gid = query.get('gid', [''])[0]
                if (set(query) - allowed or any(len(v) != 1 for v in query.values())
                        or not re.fullmatch(r'-?(0|[1-9][0-9]{0,18})', gid)):
                    self.error(400, 'error.invalidId')
                    return
                if not -(2**63) <= int(gid) < 2**63:
                    self.error(400, 'error.idRange')
                    return
                if query.get('revision', [snapshot.revision])[0] != snapshot.revision:
                    self.error(409, 'error.stale')
                    return
                if gid not in snapshot.nodes:
                    self.error(404, 'error.missingId')
                    return
                if url.path == '/api/graph':
                    hops = query.get('hops', [''])[0]
                    if hops not in {'1', '2'}:
                        self.error(400, 'error.hops')
                        return
                    payload = snapshot.neighborhood(gid, int(hops))
                else:
                    payload = dict(revision=snapshot.revision, account=snapshot.nodes[gid],
                        edges=snapshot.incident[gid], graph=snapshot.neighborhood(gid, 1),
                        neighbors=[snapshot.nodes[peer] for peer in sorted(snapshot.peers[gid] | {gid}, key=int)],
                        cluster=snapshot.data['clusters'][snapshot.nodes[gid]['cluster_id']])
                self.send(200, json_bytes(payload), 'application/json')
            else:
                name = url.path.removeprefix('/exports/')
                self.send(200, snapshot.exports[name], 'application/json' if name.endswith('.json') else 'text/csv')

    return DashboardServer(result, out_dir, port, Handler)
