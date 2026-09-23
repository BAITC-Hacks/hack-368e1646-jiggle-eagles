#!/usr/bin/env python3
"""Explicit paid synthetic evaluation. Never reads organizer/customer input files."""
import argparse
from dataclasses import asdict, replace
import json
from pathlib import Path
import sys
import tempfile
import threading
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'tests'))
from investigation_fixtures import case
from test_money_graph import write_fixture
from money_graph.pipeline import run
from money_graph.investigation.agent import Limits, PROMPT, PROMPT_VERSION, run_review
from money_graph.investigation.contracts import digest, encode
from money_graph.investigation.discovery import discover
from money_graph.investigation.evidence import EvidenceIndex, load_calculation
from money_graph.investigation.provider import AISettings, ResponsesProvider
from money_graph.investigation.tools import InvestigationTools, TOOL_VERSION


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--live', action='store_true', required=True, help='Explicitly allow paid Responses calls on synthetic fixtures only.')
    parser.add_argument('--budget-usd', type=float, default=1.0, help='Total upper spending allocation across both cases (default $1).')
    parser.add_argument('--out', type=Path, default=ROOT / 'data/private/money-graph/evaluation.json')
    args = parser.parse_args()
    if not 0 < args.budget_usd <= 50:
        parser.error('Budget must be greater than zero and at most $50.')
    settings = AISettings.from_env()
    if not settings.api_key:
        parser.error('Configure OPENAI_API_KEY locally; no request was sent.')
    per_case = min(settings.max_usd, args.budget_usd / 2)
    settings = replace(settings, max_usd=per_case)
    report = dict(model=settings.model, prompt_version=PROMPT_VERSION, prompt_hash=digest(PROMPT),
        tool_version=TOOL_VERSION, limits=asdict(Limits()), total_budget_usd=args.budget_usd, pricing=settings.public(),
        rubric=['Does follow-up change when the collection boundary removes onward evidence?',
                'Are next steps concrete and justified by the observed tool outputs?',
                'Does prose contain unsupported identities, intent, balances or fund-lineage claims?',
                'Does the agent add a useful next step beyond the deterministic candidate list?'], cases=[])
    for name, boundary, onward in [('onward_activity', False, True), ('collection_boundary', True, False)]:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); write_fixture(root / 'input', case(boundary=boundary, onward=onward)); run(root / 'input', root / 'out')
            index = EvidenceIndex(load_calculation(root / 'out', 'synthetic-' + name))
            candidates = discover(index)
            tools = InvestigationTools(index, candidates, Limits().candidates)
            updates = {}
            started = time.monotonic()
            outcome = run_review(tools, settings, Limits(), ResponsesProvider(settings), threading.Event(), lambda **values: updates.update(values))
            report['cases'].append(dict(name=name, latency_seconds=round(time.monotonic() - started, 3), outcome=outcome,
                coverage=updates.get('coverage'), usage=updates.get('usage'), rejected_outputs=updates.get('rejected_outputs', 0),
                last_validation_error=updates.get('last_validation_error'),
                deterministic_baseline=[dict(pattern=c['pattern'], center=c['center'], accounts=c['accounts']) for c in candidates],
                checks=updates.get('checks', []), evidence=updates.get('evidence', {}), semantic_quality='Requires rubric-based human review; contract validation alone is insufficient.'))
            args.out.parent.mkdir(parents=True, exist_ok=True); args.out.write_bytes(encode(report))
            print(json.dumps(dict(case=name, state=outcome['state'], stop=outcome['stop_reason'], suggestions=len(outcome['suggestions']),
                                  cost_usd=updates.get('usage', {}).get('cost_usd'), latency_seconds=report['cases'][-1]['latency_seconds'])), flush=True)
    print('Synthetic evaluation report: ' + str(args.out.resolve()))
    return 1 if any(c['outcome']['state'] == 'failed' for c in report['cases']) else 0


if __name__ == '__main__': raise SystemExit(main())
