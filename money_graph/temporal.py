"""Day-level amount allocation, not tracing the identity of money.

Called after input validation. Each account has its own FIFO allocation; a
transfer may be outgoing for one account and incoming for another. Self-links
are excluded. Same-day overlap is a separate, non-additive descriptive measure.
"""
from collections import defaultdict
from datetime import date, timedelta
import math

import pandas as pd


WINDOW_DAYS = 2
MIN_SHARE = 0.8
OBSERVATION_END = date(2026, 7, 31)


def temporal_features(tx: pd.DataFrame) -> dict[int, dict]:
    incoming = defaultdict(lambda: defaultdict(list))
    outgoing = defaultdict(lambda: defaultdict(list))
    for row in tx.itertuples(index=False):
        if row.src == row.dst:
            continue
        day = row.date.date()
        incoming[int(row.dst)][day].append(float(row.sum_kzt))
        outgoing[int(row.src)][day].append(float(row.sum_kzt))
    result = {}
    for gid in sorted(incoming.keys() | outgoing.keys()):
        ins = {day: math.fsum(values) for day, values in incoming[gid].items()}
        outs = {day: math.fsum(values) for day, values in outgoing[gid].items()}
        remaining = dict(ins)
        matches = []
        # Ascending outgoing dates, then earliest eligible incoming date. Daily
        # buckets avoid inventing intraday order or dependence on input row order.
        for out_day in sorted(outs):
            available = outs[out_day]
            for lag in range(WINDOW_DAYS, 0, -1):
                in_day = out_day - timedelta(days=lag)
                amount = min(available, remaining.get(in_day, 0.0))
                if amount > 0:
                    matches.append(dict(in_date=in_day.isoformat(), out_date=out_day.isoformat(),
                                        lag_days=lag, amount_kzt=amount))
                    available -= amount
                    remaining[in_day] -= amount
        matched = math.fsum(m['amount_kzt'] for m in matches)
        total = math.fsum(ins.values())
        same_day = [dict(date=day.isoformat(), amount_kzt=min(ins[day], outs[day]))
                    for day in sorted(ins.keys() & outs.keys())]
        result[gid] = dict(
            incoming_kzt=total, outgoing_kzt=math.fsum(outs.values()),
            matched_kzt=matched,
            matched_day1_kzt=math.fsum(m['amount_kzt'] for m in matches if m['lag_days'] == 1),
            matched_day2_kzt=math.fsum(m['amount_kzt'] for m in matches if m['lag_days'] == 2),
            matched_in_share=min(1.0, matched / total) if total else None,
            same_day_overlap_kzt=math.fsum(m['amount_kzt'] for m in same_day),
            same_day=same_day, matches=matches,
            end_window_incoming_kzt=math.fsum(amount for day, amount in ins.items()
                if day + timedelta(days=WINDOW_DAYS) > OBSERVATION_END))
    return result


def empty_temporal() -> dict:
    return dict(incoming_kzt=0.0, outgoing_kzt=0.0, matched_kzt=0.0,
                matched_day1_kzt=0.0, matched_day2_kzt=0.0, matched_in_share=None,
                same_day_overlap_kzt=0.0, same_day=[], matches=[], end_window_incoming_kzt=0.0)
