"""Hand-checkable synthetic cases and a scripted external-provider double."""
from datetime import date
from copy import deepcopy
import json

import pandas as pd

BASE = 9007199254740993


def case(boundary=False, onward=True, many=False):
    size = 90 if many else 16
    nodes = pd.DataFrame(dict(gid=[BASE + i for i in range(size)], depth=[0] + [1] * (size - 1), is_seed=[True] + [False] * (size - 1)))
    nodes.loc[3, 'depth'] = 4 if boundary else 1
    rows = [(i, 3, day, 5000.) for i in (0, 1, 2) for day in (1, 2)]
    rows += [(i, 9, 10, 10000.) for i in (6, 7, 8)]
    if onward:
        rows += [(3, 4, 3, 15000.), (4, 5, 4, 15000.)]
    if many:
        rows += [(i, 3, 11, 5000.) for i in range(16, size)]
    tx = pd.DataFrame([dict(src=BASE + a, dst=BASE + b, date=date(2026, 7, day), sum_kzt=amount) for a, b, day, amount in rows])
    edges = tx.groupby(['src', 'dst'], as_index=False).agg(sum_kzt=('sum_kzt', 'sum'), n_tx=('sum_kzt', 'size'))
    edges['depth'] = 1
    return nodes, edges, tx


class ScriptedProvider:
    """Exercises the API loop only; never presented as evidence of model quality."""
    def __init__(self):
        self.stage = 0
        self.candidate = None
        self.account = None
        self.outgoing = None
        self.requests = []

    def __call__(self, payload, timeout):
        self.requests.append(deepcopy(payload))
        latest = next((json.loads(item['output']) for item in reversed(payload['input']) if item.get('type') == 'function_call_output'), None)
        stage = self.stage
        self.stage += 1
        if stage == 0:
            name, args = 'analysis_context', {}
        elif stage == 1:
            name, args = 'list_candidates', {'offset': 0, 'limit': 100}
        elif stage == 2:
            self.candidate = next(c for c in latest['data'] if c['pattern'] == 'shared_recipient')
            name, args = 'inspect_account', {'gid': self.candidate['center']}
        elif stage == 3:
            self.account = latest['evidence'][0]
            name, args = 'connections', {'gid': self.candidate['center'], 'direction': 'outgoing', 'offset': 0, 'limit': 20}
        elif stage == 4:
            self.outgoing = latest['data']['connections']
            name, args = 'daily_activity', {'gid': self.candidate['center'], 'offset': 0, 'limit': 20}
        elif stage == 5:
            name, args = 'inspect_account', {'gid': self.outgoing[0]['dst'] if self.outgoing else self.candidate['center']}
        elif stage == 6:
            name, args = 'record_decision', self.decision()
        else:
            return dict(id='response-final', model=payload['model'], status='completed', usage=dict(input_tokens=100, output_tokens=100),
                output=[dict(type='message', role='assistant', content=[dict(type='output_text', text='{"decisions":[]}')])])
        return dict(id='response-' + str(stage), model=payload['model'], status='completed', usage=dict(input_tokens=100, output_tokens=100),
            output=[dict(type='reasoning', id='reason-' + str(stage), summary=[]),
                    dict(type='function_call', call_id='call-' + str(stage), name=name, arguments=json.dumps(args))])

    def decision(self):
        ref = self.account['evidence_id']
        boundary = self.account['measurements']['boundary']['value'] == 1
        return dict(candidate_id=self.candidate['candidate_id'], disposition='insufficient_evidence' if boundary else 'investigate',
            title='Shared recipient needs context',
            reason='Collection stopped at this account; missing onward activity cannot establish retention.' if boundary else 'Shared receipts and observed onward activity warrant checking the transaction purpose.',
            next_step='Obtain activity beyond the collection boundary.' if boundary else 'Inspect the purpose of the observed onward transfers.',
            findings=[dict(evidence_id=ref, measurement='in_deg', **self.account['measurements']['in_deg'])],
            graph_selection=[self.candidate['center']] + ([self.outgoing[0]['dst']] if self.outgoing else []))
