# Meter and time-series semantics

## Establish meaning before arithmetic

**A timestamp plus a kW value does NOT by itself prove whether the value is instantaneous or an interval average.** Regular spacing does not resolve this ambiguity.

| Measurement | Meaning | Valid next operation |
| --- | --- | --- |
| Instantaneous power | Sample near one instant; device acquisition window may still be finite | Estimate energy under an explicit between-sample model |
| Interval-average power | Time-average over stated start/end boundaries | Multiply by that interval's hours |
| Interval energy | Energy accumulated within stated boundaries | Sum disjoint intervals for the same scope |
| Cumulative energy | Register total at a reading time | Difference within a continuous counter segment |
| Maximum-demand register | Maximum under a device-defined window/reset policy | Analyze that statistic; cannot reconstruct energy |

“Cumulative” alone does not identify energy: some registers accumulate demand statistics. Confirm quantity, unit, multiplier, channel, phase and aggregation from the schema, manual or provider. Field names and encodings are conventions.

Without metadata, cadence, monotonicity, magnitude and correlations suggest hypotheses only. Report observed gaps, ranges and candidate interpretations. Shape alone cannot establish units, boundaries, sign, scope or missing-value meaning. Leave dependent results unresolved unless a defensible conditional estimate is useful.

## Time boundaries and frequency

Distinguish measurement from ingestion time. Hypothetically, a 15-minute row labelled `10:00` could describe `10:00–10:15` or `09:45–10:00`. Group by actual intervals, not blindly by label dates.

Use an explicit boundary convention, such as `[start, end)`, after interpreting the source. Require positive elapsed durations and check overlaps. A gap between rows does not extend the preceding interval.

Sampling frequency is how often samples are taken; reporting cadence is how often rows arrive; aggregation interval is the span summarized. A value reported every minute could summarize a rolling hour. Summing overlapping windows double counts time.

Regular timestamps do not guarantee complete intervals. With irregular sampling, use actual elapsed times for integration. With interval data, use documented boundaries/durations; the next row's timestamp is not automatically the current interval's end.

## Timezones and calendars

Preserve original timestamps, offsets and the named timezone when available. Normalize unambiguous instants to UTC for ordering/durations; use the required local timezone for calendar totals and operating schedules. Do not silently treat offset-free timestamps as UTC or use the workstation's timezone.

Daylight-saving and historical offset changes can produce repeated or nonexistent local times and days with other than 24 elapsed hours. Resolve them from source evidence. A repeated wall-clock timestamp can denote two distinct instants. Define week start, calendar versus billing month and partial-period handling explicitly.

## Data-quality handling

| Situation | Required handling |
| --- | --- |
| Missing intervals | Report covered versus requested duration. Do not assume gaps are zero. Label imputation and its method. |
| Duplicate timestamps | Check meter/channel, interval and timezone first. For the same logical reading, distinguish retransmission from conflicting revisions; resolve from provenance, not arbitrary averaging. |
| Zero | Could be real inactivity, net balance, rounding or a missing sentinel; use quality flags/documentation. |
| Negative value | Could be export, signed net flow, a correction or invalid data; do not clamp automatically. |
| Counter reset/replacement | Split the series; obtain old final/new initial readings if possible. A downward jump alone does not prove a reset. |
| Counter rollover | Correct only with known modulus and wrap count; otherwise consumption is unresolved. |
| Missing intermediate counter readings | Valid endpoints can establish energy across the whole gap if continuity is established, but not its allocation within the gap. |

An import-only counter normally increases; a signed net counter may decrease. Preserve raw readings and transformation provenance. For partial intervals, proportional allocation assumes uniform power within the interval—even if its full-interval average is known.

Do not add a building meter to its included submeters. Check hierarchy, shared loads and alignment before combining scopes.

Sources: G1 and T1 in [references](references.md). Calculation-specific limits: [C1–C9](calculations.md).
