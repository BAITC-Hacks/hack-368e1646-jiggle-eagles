# Energy references

Task-neutral decision aids for AI coding agents, not official task requirements or a comprehensive guide to энергетика. Numeric examples are hypothetical; establish actual semantics from dataset documentation.

## Start here: one minute

1. **Identify measurement type:** power sample, average power, interval energy or cumulative energy?
2. **Confirm units, time and scope:** scale, interval boundaries, timezone, meter/channel and direction.
3. **Check data quality:** gaps, duplicates, resets and coverage using the [validation checklist](validation-and-guardrails.md#before-analysis).
4. **Choose a calculation:** follow the tree, then check its [required inputs](calculations.md).
5. **Record uncertainty:** label measured, derived, estimated or unresolved; retain evidence and assumptions.

## Decision tree

```text
Quantity, unit, scale and meter scope established?
├─ No → inspect metadata/provider documentation; profile data only.
│       Unresolved? Stop dependent calculations or label conditional estimates.
└─ Yes → what does each value represent?
   ├─ Energy (kWh/MWh; normalize units)
   │  ├─ Interval → validate nonoverlapping boundaries → sum energy.
   │  ├─ Cumulative → validate counter continuity → difference readings.
   │  └─ Unknown → unit/shape alone cannot choose between these.
   ├─ Power (kW/MW; normalize units)
   │  ├─ Interval average → confirm duration → power × hours.
   │  ├─ Instantaneous → confirm sample times → estimate by integration.
   │  ├─ Maximum-demand register → establish window; insufficient for energy.
   │  └─ Unknown → timestamp + kW does not identify averaging semantics.
   └─ Other quantity → obtain its definition; do not force these formulas.
Before reporting → check quality, coverage, sign and overlapping meters;
                   state period, units, provenance and uncertainty.
```

## Targeted lookup

| Question | Consult |
| --- | --- |
| What quantity or unit is this? | [Fundamentals](fundamentals.md) |
| What does this meter row mean? | [Meter and time-series semantics](meter-time-series.md) |
| Which formula is valid? | [Calculations C1–C9](calculations.md) |
| How should I compare, detect or forecast? | [Baselines and forecasting](baselines-and-forecasting.md) |
| Am I optimizing energy, money, peak or emissions? | [Objectives](objectives.md) |
| What must I validate or review? | [Validation and guardrails](validation-and-guardrails.md) |
| What is the Russian equivalent? | [Glossary](glossary.md) |
| Where are the supporting sources? | [References](references.md) |
