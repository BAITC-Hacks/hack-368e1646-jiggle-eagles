"""Read-only investigation tools with explicit pagination and snapshot identity."""
from copy import deepcopy

from .contracts import DECISION, HASH, ID, LIMIT, OFFSET, ReviewError, digest, encode, obj, validate
from .evidence import EvidenceIndex

TOOL_VERSION = 1
DEFINITIONS = {
    'record_decision': ('Save one supported decision after follow-up checks. Do this as each candidate is resolved so a limited review retains useful results. This does not mark human follow-up or create a brief.', DECISION),
    'analysis_context': ('Get frozen method settings, scope, capabilities and discovery coverage before drawing conclusions.', obj()),
    'list_candidates': ('Page the diverse candidate shortlist. Found and shortlisted counts differ; unexamined candidates remain unknown.', obj(offset=OFFSET, limit=LIMIT)),
    'inspect_account': ('Inspect measured incoming/outgoing activity, collection depth and seed status. Boundary absence cannot establish a terminal recipient.', obj(gid=ID)),
    'inspect_community': ('Inspect a saved community and page its members. Communities are method-dependent structural groupings.', obj(cluster_id=dict(type='integer', minimum=0), offset=OFFSET, limit=LIMIT)),
    'connections': ('Page directed connections for an account. Check outgoing or both directions before suggesting follow-up; omitted links are not absent.',
        obj(gid=ID, direction=dict(type='string', enum=['incoming', 'outgoing', 'both']), offset=OFFSET, limit=LIMIT)),
    'daily_activity': ('Page saved daily directed aggregates incident to an account. Date order is day-level only; never infer the same funds passed onward.', obj(gid=ID, offset=OFFSET, limit=LIMIT)),
    'supporting_evidence': ('Retrieve one exact evidence record to cite its measurement name, value and unit. Only retrieved evidence may support a final finding.', obj(evidence_id=HASH)),
}
TOOL_SCHEMAS = [dict(type='function', name=name, description=description, parameters=schema, strict=True)
                for name, (description, schema) in DEFINITIONS.items()]


def page(items: list, offset: int, limit: int) -> tuple[list, dict]:
    selected = items[offset:offset + limit]
    return selected, dict(total=len(items), returned=len(selected), omitted=len(items) - len(selected),
                          offset=offset, next_offset=offset + len(selected) if offset + len(selected) < len(items) else None)


class InvestigationTools:
    def __init__(self, index: EvidenceIndex, candidates: list[dict], candidate_limit: int):
        self.index = index
        self.all_candidates = candidates
        self.candidates = candidates[:candidate_limit]
        self.by_id = {c['candidate_id']: c for c in self.candidates}
        self.seen: dict[str, dict] = {}
        self.checks: list[dict] = []
        self.decisions: dict[str, dict] = {}

    def execute(self, name: str, arguments: object) -> dict:
        if name not in DEFINITIONS:
            raise ReviewError('unknown_tool')
        validate(arguments, DEFINITIONS[name][1])
        index = self.index
        if 'gid' in arguments and arguments['gid'] not in index.nodes:
            raise ReviewError('account_missing', 404)
        refs = []
        coverage = dict(total=1, returned=1, omitted=0, offset=0, next_offset=None)
        if name == 'record_decision':
            accepted = self.validate_decisions([arguments])[0]
            self.decisions[accepted['candidate_id']] = accepted
            data = dict(candidate_id=accepted['candidate_id'], accepted=True)
        elif name == 'analysis_context':
            data = dict(analysis_id=index.snapshot['analysis_id'], profile=index.data['profile'],
                        parameters=index.data['config'], methods=index.data.get('methods', {}),
                        capabilities={'daily_activity': 'daily' in index.data},
                        accounts_scanned=len(index.nodes), candidates_found=len(self.all_candidates),
                        candidates_selected=len(self.candidates), candidates_examined=len(self.examined()))
        elif name == 'list_candidates':
            selected, coverage = page(self.candidates, arguments['offset'], arguments['limit'])
            data = []
            for candidate in selected:
                preview = candidate['accounts'][:20]
                references = candidate['evidence_refs'][:10]
                data.append(dict(candidate_id=candidate['candidate_id'], pattern=candidate['pattern'],
                                 center=candidate['center'], component=candidate['component'],
                                 accounts=preview, omitted_accounts=len(candidate['accounts']) - len(preview),
                                 evidence_refs=references, omitted_evidence=len(candidate['evidence_refs']) - len(references)))
                refs.extend(references[:1])
        elif name == 'inspect_account':
            node = index.nodes[arguments['gid']]
            data = {k: node[k] for k in ('gid', 'cluster_id', 'depth', 'boundary', 'is_seed', 'role', 'role_rule')}
            refs = [index.account_refs[node['gid']]]
        elif name == 'inspect_community':
            cid = arguments['cluster_id']
            if cid not in index.community_refs:
                raise ReviewError('community_missing', 404)
            members = sorted((gid for gid, n in index.nodes.items() if n['cluster_id'] == cid), key=int)
            selected, coverage = page(members, arguments['offset'], arguments['limit'])
            data = dict(cluster_id=cid, members=selected)
            refs = [index.community_refs[cid]]
        elif name == 'connections':
            gid, direction = arguments['gid'], arguments['direction']
            edges = [e for e in index.incident[gid] if direction == 'both' or
                     (direction == 'incoming' and e['dst'] == gid) or (direction == 'outgoing' and e['src'] == gid)]
            selected, coverage = page(edges, arguments['offset'], arguments['limit'])
            refs = [index.edge_refs[e['src'], e['dst']] for e in selected]
            data = dict(gid=gid, direction=direction, connections=selected)
        elif name == 'daily_activity':
            gid = arguments['gid']
            rows = sorted((r for r in index.daily if gid in (r['src'], r['dst'])), key=lambda r: (r['date'], int(r['src']), int(r['dst'])))
            selected, coverage = page(rows, arguments['offset'], arguments['limit'])
            refs = [index.daily_refs[r['src'], r['dst'], r['date']] for r in selected]
            data = dict(gid=gid, available='daily' in index.data, daily=selected)
        else:
            data = dict(evidence_id=arguments['evidence_id'])
            refs = [arguments['evidence_id']]
        records = [index.record(ref) for ref in dict.fromkeys(refs)]
        output = dict(snapshot_id=index.snapshot['snapshot_id'], tool_version=TOOL_VERSION, data=data,
                      evidence=records, coverage=coverage, limitations=list(index.limitations))
        # Validate produced evidence against canonical records before it enters model context.
        self.validate_result(output)
        self.seen.update({r['evidence_id']: r for r in records})
        self.checks.append(dict(check_id=len(self.checks) + 1, tool=name, arguments=deepcopy(arguments), result=deepcopy(output)))
        return output

    def validate_result(self, output: dict) -> None:
        if not isinstance(output, dict) or set(output) != {'snapshot_id', 'tool_version', 'data', 'evidence', 'coverage', 'limitations'}:
            raise ReviewError('invalid_tool_result')
        if (output['snapshot_id'] != self.index.snapshot['snapshot_id'] or type(output['tool_version']) is not int or
                output['tool_version'] != TOOL_VERSION or output['limitations'] != self.index.limitations or
                not isinstance(output['data'], (dict, list)) or not isinstance(output['evidence'], list)):
            raise ReviewError('invalid_tool_result')
        c = output['coverage']
        if not isinstance(c, dict) or set(c) != {'total', 'returned', 'omitted', 'offset', 'next_offset'}:
            raise ReviewError('invalid_tool_result')
        if (any(type(c[k]) is not int or c[k] < 0 for k in ('total', 'returned', 'omitted', 'offset')) or
                c['returned'] + c['omitted'] != c['total']):
            raise ReviewError('invalid_tool_result')
        expected_next = c['offset'] + c['returned'] if c['offset'] + c['returned'] < c['total'] else None
        if c['next_offset'] != expected_next:
            raise ReviewError('invalid_tool_result')
        for record in output['evidence']:
            if not isinstance(record, dict) or record != self.index.records.get(record.get('evidence_id')):
                raise ReviewError('invalid_tool_result')
        if len(encode(output)) > 512 * 1024:
            raise ReviewError('tool_result_limit')

    def examined(self) -> set[str]:
        """Count explicit decisions, not every pattern sharing an inspected center."""
        return set(self.decisions)

    def checked(self) -> set[str]:
        """Minimum evidence checks required before accepting a candidate decision."""
        inspected, connected, daily = set(), set(), set()
        for check in self.checks:
            args = check['arguments']
            if check['tool'] == 'inspect_account':
                inspected.add(args['gid'])
            elif check['tool'] == 'connections' and args['direction'] in {'outgoing', 'both'} and args['offset'] == 0:
                connected.add(args['gid'])
            elif check['tool'] == 'daily_activity' and args['offset'] == 0:
                daily.add(args['gid'])
        return {cid for cid, c in self.by_id.items() if c['center'] in inspected & connected & daily}

    def validate_decisions(self, decisions: list[dict]) -> list[dict]:
        from .contracts import FINAL
        validate({'decisions': decisions}, FINAL)
        result, used = [], set()
        for decision in decisions:
            cid = decision['candidate_id']
            if cid not in self.checked() or cid in used:
                raise ReviewError('unchecked_candidate')
            used.add(cid)
            # Numeric claims belong in structured findings, not uncheckable prose.
            if any(any(char.isdigit() for char in decision[field]) for field in ('title', 'reason', 'next_step')):
                raise ReviewError('unstructured_measurement')
            selection = decision['graph_selection']
            candidate = self.by_id[cid]
            related = set(candidate['accounts'])
            for check in self.checks:
                if check['arguments'].get('gid') == candidate['center']:
                    related.update(g for r in check['result']['evidence'] for g in r['accounts'])
            if len(selection) != len(set(selection)) or candidate['center'] not in selection or not set(selection) <= related:
                raise ReviewError('invalid_graph_selection')
            refs = []
            findings = []
            for finding in decision['findings']:
                ref = finding['evidence_id']
                record = self.seen.get(ref)
                if record is None or not set(record['accounts']) & set(candidate['accounts']):
                    raise ReviewError('invalid_evidence_reference')
                metric = record['measurements'].get(finding['measurement'])
                if metric != {'value': finding['value'], 'unit': finding['unit']}:
                    raise ReviewError('invalid_measurement')
                refs.append(ref)
                findings.append(dict(finding, accounts=record['accounts'], details=record['details']))
            if not set(refs) & set(candidate['evidence_refs']):
                raise ReviewError('missing_candidate_evidence')
            checks = [c['check_id'] for c in self.checks if c['arguments'].get('gid') in related or
                      any(r['evidence_id'] in refs for r in c['result']['evidence'])]
            limitations = list(self.index.limitations)
            if any(c['result']['coverage']['omitted'] for c in self.checks if c['check_id'] in checks):
                limitations.append('Some tool results were paginated; omitted activity was not fully examined.')
            result.append(dict(decision, suggestion_id=digest({'candidate': cid, 'decision': decision}),
                findings=findings, evidence_refs=list(dict.fromkeys(refs)), limitations=limitations,
                check_ids=checks, pattern=candidate['pattern'], center=candidate['center'], follow_up=False))
        return result
