"""Review lifecycle and persistence. No dependence on the server's active analysis."""
from copy import deepcopy
from dataclasses import asdict, replace
from datetime import datetime, timezone
from pathlib import Path
import re
import threading
import time
import uuid

from .agent import Limits, PROMPT, PROMPT_VERSION, run_review
from .contracts import HASH, ReviewError, digest, obj, validate
from .discovery import DiscoveryConfig, discover
from .evidence import EvidenceIndex, load_calculation
from .provider import AISettings, ResponsesProvider
from .storage import ReviewStore
from .tools import InvestigationTools, TOOL_SCHEMAS, TOOL_VERSION

ACTIVE = {'queued', 'running'}


def now():
    return datetime.now(timezone.utc).isoformat()


class ReviewService:
    def __init__(self, root: Path, settings: AISettings | None = None, provider=None, limits: Limits = Limits(),
                 discovery: DiscoveryConfig = DiscoveryConfig()):
        self.root, self.store = root, ReviewStore(root)
        self.settings_override, self.provider_override = settings, provider
        self.limits, self.discovery = limits, discovery
        self.lock = threading.RLock()
        self.workers: dict[str, tuple[threading.Thread, threading.Event]] = {}
        records, self.damaged = self.store.list('reviews')
        self.records = {r['review_id']: r for r in records}
        for record in self.records.values():
            if record['state'] in ACTIVE:
                record.update(state='interrupted', stop_reason='server_restart', updated_at=now())
                self.store.write('reviews', record['review_id'], record)

    def settings(self):
        return self.settings_override or AISettings.from_env()

    def calculation(self, analysis_id: str):
        if not re.fullmatch(r'startup|[0-9a-f]{32}', analysis_id):
            raise ReviewError('analysis_missing', 404)
        path = self.root if analysis_id == 'startup' else self.root / 'uploads' / analysis_id / 'output'
        if path.is_symlink() or path.parent.is_symlink():
            raise ReviewError('analysis_missing', 404)
        return load_calculation(path, analysis_id)

    def list(self, analysis_id: str):
        snapshot = self.calculation(analysis_id)
        try:
            settings = self.settings()
            availability = dict(enabled=bool(settings.api_key or self.provider_override), **settings.public(),
                                reason=None if settings.api_key or self.provider_override else 'ai_disabled')
        except ReviewError as error:
            availability = dict(enabled=False, reason=error.code)
        with self.lock:
            records = [self.summary(r) for r in self.records.values() if r['analysis_id'] == analysis_id]
        briefs, damaged = self.store.list('briefs')
        return dict(analysis_id=analysis_id, snapshot_id=snapshot['snapshot_id'], availability=availability,
                    capabilities=dict(daily_activity='daily' in snapshot['data']),
                    reviews=sorted(records, key=lambda r: r['created_at'], reverse=True),
                    briefs=[b for b in briefs if b['analysis_id'] == analysis_id], unavailable_count=self.damaged + damaged)

    @staticmethod
    def summary(record):
        return {k: deepcopy(v) for k, v in record.items() if k not in {'checks', 'evidence'}}

    def get(self, analysis_id: str, review_id: str):
        with self.lock:
            record = self.records.get(review_id)
            if record is None or record['analysis_id'] != analysis_id:
                raise ReviewError('record_missing', 404)
            return deepcopy(record)

    def start(self, analysis_id: str, body: object):
        validate(body, obj(snapshot_id=HASH, locale=dict(type='string', enum=['en', 'kk', 'ru'])))
        snapshot = self.calculation(analysis_id)
        if snapshot['snapshot_id'] != body['snapshot_id']:
            raise ReviewError('snapshot_changed', 409)
        settings = self.settings()
        if not settings.api_key and self.provider_override is None:
            raise ReviewError('ai_disabled', 503)
        compatibility = dict(snapshot_id=snapshot['snapshot_id'], discovery=asdict(self.discovery),
            model=settings.model, prompt_version=PROMPT_VERSION, prompt_hash=digest(PROMPT),
            tool_version=TOOL_VERSION, tool_hash=digest(TOOL_SCHEMAS), limits=asdict(self.limits),
            locale=body['locale'], pricing=settings.public())
        key = digest(compatibility)
        with self.lock:
            for record in self.records.values():
                if record['analysis_id'] == analysis_id and record['compatibility_key'] == key and record['state'] == 'completed':
                    return dict(self.get(analysis_id, record['review_id']), reused=True)
            if any(thread.is_alive() for thread, _ in self.workers.values()):
                raise ReviewError('review_busy', 409)
            identifier = uuid.uuid4().hex
            record = dict(review_id=identifier, analysis_id=analysis_id, snapshot_id=snapshot['snapshot_id'],
                compatibility_key=key, provenance=compatibility, state='queued', stop_reason=None,
                created_at=now(), updated_at=now(), coverage={}, usage={}, checks=[], evidence={}, suggestions=[], usage_final=False)
            self.store.write('snapshots', snapshot['snapshot_id'], snapshot)
            self.store.write('reviews', identifier, record)
            self.records[identifier] = record
            cancel = threading.Event()
            worker = threading.Thread(target=self._run, args=(identifier, snapshot, settings, cancel), daemon=True)
            self.workers[identifier] = worker, cancel
            try:
                worker.start()
            except RuntimeError as error:
                record.update(state='failed', stop_reason='worker_start')
                self.store.write('reviews', identifier, record)
                raise ReviewError('worker_start', 503) from error
            return deepcopy(record)

    def _run(self, identifier, snapshot, settings, cancelled):
        started = time.monotonic()
        def emit(**changes):
            with self.lock:
                record = self.records[identifier]
                if record['state'] in {'cancelled', 'interrupted'}:
                    changes = {k: v for k, v in changes.items() if k in {'usage', 'elapsed_seconds', 'usage_final'}}
                # Preserve human markers when progress refreshes already accepted suggestions.
                marked = {s['suggestion_id']: s['follow_up'] for s in record['suggestions']}
                if 'suggestions' in changes:
                    changes['suggestions'] = [dict(s, follow_up=marked.get(s['suggestion_id'], False)) for s in changes['suggestions']]
                record.update(deepcopy(changes), updated_at=now())
                self.store.write('reviews', identifier, record)
        try:
            index = EvidenceIndex(snapshot)
            candidates = discover(index, self.discovery)
            if time.monotonic() - started >= self.limits.runtime_seconds:
                emit(state='partial', stop_reason='runtime_limit', usage_final=True)
                return
            tools = InvestigationTools(index, candidates, self.limits.candidates)
            tools.locale = self.records[identifier]['provenance']['locale']
            emit(state='running')
            remaining = replace(self.limits, runtime_seconds=self.limits.runtime_seconds - (time.monotonic() - started))
            outcome = run_review(tools, settings, remaining, self.provider_override or ResponsesProvider(settings), cancelled, emit)
            emit(**outcome, usage_final=True)
        except Exception:
            # Retain an explicit in-memory failure even when the disk itself is unavailable.
            with self.lock:
                record = self.records[identifier]
                if record['state'] != 'cancelled':
                    record.update(state='failed', stop_reason='review_storage_or_runtime', updated_at=now())
                try:
                    self.store.write('reviews', identifier, record)
                except OSError:
                    record['persistence_error'] = True

    def cancel(self, analysis_id: str, review_id: str):
        with self.lock:
            record = self.get(analysis_id, review_id)
            if record['state'] in ACTIVE:
                self.workers[review_id][1].set()
                record.update(state='cancelled', stop_reason='cancelled', updated_at=now())
                self.store.write('reviews', review_id, record)
                self.records[review_id] = record
            return record

    def follow_up(self, analysis_id: str, review_id: str, body: object):
        validate(body, obj(suggestion_id=HASH, marked=dict(type='boolean')))
        with self.lock:
            record = self.get(analysis_id, review_id)
            suggestion = next((s for s in record['suggestions'] if s['suggestion_id'] == body['suggestion_id']), None)
            if suggestion is None:
                raise ReviewError('suggestion_missing', 404)
            suggestion['follow_up'] = body['marked']
            record['updated_at'] = now()
            self.store.write('reviews', review_id, record)
            self.records[review_id] = record
            return record

    def brief(self, analysis_id: str, review_id: str, body: object):
        validate(body, obj(suggestion_id=HASH))
        record = self.get(analysis_id, review_id)
        suggestion = next((s for s in record['suggestions'] if s['suggestion_id'] == body['suggestion_id']), None)
        if suggestion is None:
            raise ReviewError('suggestion_missing', 404)
        brief = dict(brief_id=digest(dict(review_id=review_id, suggestion=suggestion)), analysis_id=analysis_id,
            review_id=review_id, snapshot_id=record['snapshot_id'], created_at=now(), suggestion=suggestion,
            provenance=record['provenance'], usage=record['usage'], coverage=record['coverage'],
            review_state=record['state'], checks=[c for c in record['checks'] if c['check_id'] in suggestion['check_ids']],
            evidence=[record['evidence'][ref] for ref in suggestion['evidence_refs']])
        try:
            return self.store.read('briefs', brief['brief_id'])
        except ReviewError as error:
            if error.status != 404:
                raise
        self.store.write('briefs', brief['brief_id'], brief)
        return brief

    def graph(self, analysis_id: str, review_id: str, suggestion_id: str):
        record = self.get(analysis_id, review_id)
        suggestion = next((s for s in record['suggestions'] if s['suggestion_id'] == suggestion_id), None)
        if suggestion is None:
            raise ReviewError('suggestion_missing', 404)
        snapshot = self.store.read('snapshots', record['snapshot_id'])
        data = snapshot['data']
        selected = set(suggestion['graph_selection'])
        nodes = [n for n in data['nodes'] if n['gid'] in selected]
        center = next(n for n in nodes if n['gid'] == suggestion['center'])
        edges = [e for e in data['edges'] if e['src'] in selected and e['dst'] in selected]
        cluster = next(c for c in data['clusters'] if c['cluster_id'] == center['cluster_id'])
        return dict(revision=analysis_id, snapshot_id=record['snapshot_id'], account=center, cluster=cluster,
            edges=[e for e in data['edges'] if center['gid'] in (e['src'], e['dst'])],
            graph=dict(center=center['gid'], nodes=nodes, edges=edges, total_nodes=len(selected), omitted_nodes=0,
                       node_limit=50, hops=1, investigation=True),
            methods=data.get('methods', {}), method_catalogs=data.get('method_catalogs', {}), rule_parameters=data.get('rule_parameters', {}))

    def close(self):
        with self.lock:
            for identifier, (_, event) in self.workers.items():
                if self.records[identifier]['state'] in ACTIVE:
                    event.set()
                    self.records[identifier].update(state='interrupted', stop_reason='server_shutdown', updated_at=now())
                    try:
                        self.store.write('reviews', identifier, self.records[identifier])
                    except OSError:
                        self.records[identifier]['persistence_error'] = True
