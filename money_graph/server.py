"""Read-only loopback dashboard; serves only explicit local assets and exports."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import re
from urllib.parse import parse_qs, urlsplit

from .pipeline import Analysis, SCHEMAS, dashboard_data, json_bytes


class DashboardServer(ThreadingHTTPServer):
    daemon_threads = True


def make_server(result: Analysis, out_dir: Path, port: int = 8765) -> DashboardServer:
    data = dashboard_data(result)
    nodes = {n['gid']: n for n in data['nodes']}
    incident: dict[str, list[dict]] = {gid: [] for gid in nodes}
    for edge in data['edges']:
        incident[edge['src']].append(edge)
        if edge['dst'] != edge['src']:
            incident[edge['dst']].append(edge)
    overview = {k: data[k] for k in ['profile', 'config', 'warnings', 'clusters', 'top']}
    static = Path(__file__).parent / 'static'
    assets = {'/': ('index.html', 'text/html'), '/style.css': ('style.css', 'text/css'),
              '/app.js': ('app.js', 'text/javascript')}

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format: str, *args: object) -> None:
            # Avoid logging customer queries/IDs. The UI displays explicit errors.
            return

        def send(self, status: int, body: bytes, content_type: str) -> None:
            self.send_response(status)
            self.send_header('Content-Type', content_type + '; charset=utf-8')
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'")
            self.end_headers()
            self.wfile.write(body)

        def error(self, status: int, message: str) -> None:
            self.send(status, json_bytes({'error': message}), 'application/json')

        def do_GET(self) -> None:
            # Reject nonlocal Host headers (including DNS rebinding origins).
            allowed_hosts = {f'127.0.0.1:{self.server.server_port}', f'localhost:{self.server.server_port}'}
            if self.headers.get('Host') not in allowed_hosts:
                self.error(403, 'Only this loopback host is allowed.')
                return
            url = urlsplit(self.path)
            if url.path == '/api/overview':
                self.send(200, json_bytes(overview), 'application/json')
            elif url.path == '/api/account':
                query = parse_qs(url.query, keep_blank_values=True)
                values = query.get('gid', [])
                if set(query) != {'gid'} or len(values) != 1 or not re.fullmatch(r'-?(0|[1-9][0-9]{0,18})', values[0]):
                    self.error(400, 'Enter an exact decimal client ID (int64).')
                    return
                gid = values[0]
                if not -(2**63) <= int(gid) < 2**63:
                    self.error(400, 'Client ID is outside the int64 range.')
                    return
                if gid not in nodes:
                    self.error(404, 'Client ID was not found in this dataset.')
                    return
                links = incident[gid]
                peers = {e['src'] for e in links} | {e['dst'] for e in links} | {gid}
                self.send(200, json_bytes(dict(account=nodes[gid], edges=links,
                    neighbors=[nodes[g] for g in sorted(peers, key=int)],
                    cluster=data['clusters'][nodes[gid]['cluster_id']])), 'application/json')
            elif url.path in assets:
                filename, content_type = assets[url.path]
                self.send(200, (static / filename).read_bytes(), content_type)
            elif url.path.removeprefix('/exports/') in SCHEMAS and url.path.startswith('/exports/'):
                try:
                    self.send(200, (out_dir / url.path.removeprefix('/exports/')).read_bytes(), 'text/csv')
                except OSError:
                    self.error(503, 'Export unavailable; rerun the pipeline.')
            else:
                self.error(404, 'Resource not found.')

    return DashboardServer(('127.0.0.1', port), Handler)
