# Validation and agent guardrails

## Before analysis

Complete per important column/channel; mark unsupported fields **unknown** and identify affected calculations.

- [ ] Physical quantity, unit and scale multiplier established.
- [ ] Meter/sensor identity, scope, hierarchy, phase and gross/net direction established.
- [ ] Instantaneous, averaged, maximum, interval or cumulative measurement established.
- [ ] Measurement timestamp versus ingestion time; interval start/end semantics established.
- [ ] Timezone/offset and ambiguous local-time handling established.
- [ ] Sampling/reporting frequency, actual durations and aggregation method established; rolling-window overlap checked.
- [ ] Missing-value/zero semantics, quality flags, duplicates and revision policy checked.
- [ ] Sign convention, counter continuity, resets, replacements and rollovers checked.
- [ ] Requested-period coverage, calendar boundaries and partial intervals checked.
- [ ] Operating context, production, occupancy, weather and relevant schedules established where available.
- [ ] Objective, forecast horizon and information available at prediction time specified.

Record beside the analysis:

```text
column/channel + scope:
quantity + unit + multiplier + sign:
measurement type + aggregation:
timestamp meaning + timezone + duration/cadence:
quality + missing/zero rules + counter continuity:
context + metadata evidence:
unknowns/assumptions + affected outputs:
decision: supported calculation / conditional estimate / insufficient data
```

## Hard guardrails

- **NEVER fabricate** requirements, tariffs, emissions factors, units, equipment characteristics, meter semantics, missing-value meanings or operating schedules.
- **NEVER silently resolve ambiguity** or relabel kW as kWh. Record assumptions and their consequences; unsupported calculations remain unresolved or explicitly conditional.
- **NEVER sum cumulative meter readings to calculate consumption.** Use validated differences for energy counters.
- **ALWAYS preserve units and provenance**, distinguishing measured values, derived values, estimates and assumptions.

## Conditional analytical rules

| Situation | Rule |
| --- | --- |
| Instantaneous kW multiplied by nominal interval | Label the estimate and hold/interpolation assumption; exact energy is unsupported. |
| Aggregate-meter anomaly | Investigate quality/context; neither anomaly nor aggregate load proves a fault or specific equipment failure. |
| Period comparison | Consider relevant operating conditions, duration and coverage before interpreting changes. |
| Time-series splitting | Use chronological evaluation for forecasting; random splitting is invalid when it leaks future information. |
| Zeros, negatives or outliers | Preserve raw values; change/exclude only under a documented, justified policy. |
| Arithmetic or unit conversion | Prefer deterministic code/calculators over LLM arithmetic; verify numeric examples. |
| Missing semantics | Describe observations; request evidence or present conditional alternatives. |

## Calculation coverage checklist

Check these [entries](calculations.md) when editing:

- [ ] C1: interval-average kW to kWh.
- [ ] C2: daily, weekly and monthly totals.
- [ ] C3: kWh ↔ MWh.
- [ ] C4: cumulative energy differences.
- [ ] C5: rectangular and trapezoidal integration.
- [ ] C6: average power.
- [ ] C7: peak power.
- [ ] C8: kWh/unit-produced and kWh/tonne.
- [ ] C9: baseline-based estimated savings.

## Six-area consistency review

- [ ] **kW versus kWh:** dimensions, conversions and output labels agree.
- [ ] **Instantaneous versus interval-average:** exact multiplication requires the matching average; integration assumptions are explicit.
- [ ] **Cumulative versus interval energy:** difference versus sum; reset and scope handling agree.
- [ ] **Time aggregation:** actual durations, timezones, boundaries, weighting, gaps and overlaps agree.
- [ ] **Baselines:** comparable conditions, adjustments and estimated savings agree.
- [ ] **Leakage:** splits, features, preprocessing and prediction-time availability agree.

Recalculate examples, check links and inspect the documentation diff. These reusable checklists do not certify an unseen dataset.
