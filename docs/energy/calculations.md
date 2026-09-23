# Calculations

Validate [measurement semantics](meter-time-series.md) first. All examples are hypothetical. **Exact** means an exact arithmetic relationship for the specified inputs, not error-free physical measurement. **Estimated** adds a model/assumption. **Insufficient** means required information is unavailable; do not silently select an interpretation.

Carry units through code and output: `kW × h = kWh`; `(kWh/day) × day = kWh`; `kWh / unit-produced = energy intensity`. Convert elapsed seconds to hours before using kW. Use deterministic code/calculators; retain precision until presentation.

## C1: Interval-average power to energy

- **Required inputs:** Confirmed time-average power and corresponding elapsed duration.
- **Formula:** `E_i [kWh] = P_avg,i [kW] × Δt_i [h]`.
- **Example:** `12 kW × (15/60 h) = 3 kWh`.
- **Invalid-use cases:** Instantaneous, maximum or rated power substituted for an average; overlapping averages summed as disjoint energy.
- **Uncertainty:** Exact relationship for the full averaging interval; inherits meter precision. Unknown averaging semantics or duration: insufficient. Allocating part of that energy to a shorter interval requires an assumption.

## C2: Daily, weekly and monthly totals

- **Required inputs:** Compatible interval energies covering the requested calendar/billing boundaries exactly once, with a defined timezone and scope.
- **Formula:** `E_period [kWh] = Σ E_i [kWh]`; convert power or counters before summing.
- **Example:** A complete 24-hour day with 48 half-hour intervals of `2 kWh` totals `96 kWh`. Seven such verified days total `672 kWh`; a specified 30-day month of such days totals `2,880 kWh`.
- **Invalid-use cases:** Assuming every day/month has that length; treating missing intervals as zero; summing cumulative readings; mixing parent and child meters.
- **Uncertainty:** Exact aggregation of covered inputs. Report coverage and observed subtotal for incomplete periods. Extrapolating to a full period or dividing boundary-crossing intervals proportionally is an estimate, not a measured total.

## C3: kWh and MWh

- **Required inputs:** Energy with confirmed unit and scale.
- **Formula:** `E [MWh] = E [kWh] / 1,000`; reverse by multiplying by `1,000`.
- **Example:** `2,500 kWh = 2.5 MWh`; `0.8 MWh = 800 kWh`.
- **Invalid-use cases:** Converting kW to kWh using only a scale factor; applying an already-applied multiplier twice.
- **Uncertainty:** Exact conversion; input precision persists. Unknown unit: insufficient.

## C4: Consumption from cumulative energy

- **Required inputs:** Time-ordered readings from the same register, with consistent units/direction and verified continuity between endpoints.
- **Formula:** `E [kWh] = R_end − R_start`. For one confirmed rollover: `E = (M − R_start) + R_end`, where `M` is the wrap modulus in kWh.
- **Example:** `1,258 − 1,250 = 8 kWh` across the endpoint interval. With known `M = 1,000 kWh` and one wrap, `998 → 3` represents `5 kWh`.
- **Invalid-use cases:** Summing readings; differencing across unexplained resets/replacements; assuming a wrap count; naming a signed net difference “gross consumption.”
- **Uncertainty:** Exact difference for a continuous counter. Missing interior readings do not reveal subperiod use. Unknown resets/wraps: insufficient; even a positive difference does not prove continuity. The first reading alone provides no interval energy.

## C5: Energy estimated from instantaneous power

- **Required inputs:** Ordered samples `P_i` in kW, resolved duplicate times, elapsed `Δt_i = t_(i+1) − t_i` in hours, and an explicit interpolation/gap policy.
- **Formula:** Left rectangular: `E ≈ Σ P_i × Δt_i`, assuming each sample holds until the next. Trapezoidal: `E ≈ Σ ((P_i + P_(i+1))/2) × Δt_i`, assuming linear change between samples. Both sum over consecutive sample pairs.
- **Example:** Samples `4 kW` at `00:00` and `8 kW` at `00:30` give `2 kWh` rectangular or `3 kWh` trapezoidal over that half-hour.
- **Invalid-use cases:** Claiming exact energy from samples alone; using nominal spacing across gaps; bridging long outages without justification; adding a trailing interval beyond the last sample without an extrapolation model.
- **Uncertainty:** Both are estimates unless the assumed between-sample behavior is independently established. Trapezoids are not automatically more accurate for switching loads. Report covered span, gap handling and method; differences between methods are not a confidence interval.

## C6: Average power

- **Required inputs:** Energy and elapsed duration over the same covered scope and period; positive duration.
- **Formula:** `P_avg [kW] = E [kWh] / T [h]`. For disjoint interval averages: `P_avg = Σ(P_i × Δt_i) / ΣΔt_i`.
- **Example:** `2 kW` for `0.25 h` and `4 kW` for `0.75 h` give `3.5 kWh / 1 h = 3.5 kW`.
- **Invalid-use cases:** Unweighted mean of unequal intervals; dividing a partial energy subtotal by a full day's duration.
- **Uncertainty:** Exact for aligned inputs; estimated energy produces estimated average power. Unfilled gaps prevent a full-period average.

## C7: Peak power

- **Required inputs:** Comparable power measurements, their measurement window, direction and analysis period.
- **Formula:** `P_peak [kW] = max(P_i [kW])` for the specified series.
- **Example:** Interval averages `4, 9, 6 kW` yield an observed peak interval-average power of `9 kW`.
- **Invalid-use cases:** Calling this an instantaneous peak or billed demand without evidence; taking `max(kWh)` as kW; adding individual meters' peaks as a coincident site peak.
- **Uncertainty:** Exact maximum of observed values. Gaps and coarse sampling can hide peaks. Billing demand requires tariff-defined windows/rules; different window lengths are not directly comparable.

## C8: Energy intensity

- **Required inputs:** Energy and positive production quantity for aligned periods/scopes, with defined product and denominator unit.
- **Formula:** `I = E / Q`, in `kWh/unit-produced` or `kWh/tonne`.
- **Example:** `600 kWh / 20 tonnes = 30 kWh/tonne`; alternatively `600 kWh / 120 units = 5 kWh/unit`.
- **Invalid-use cases:** Zero production; mismatched boundaries; averaging ratios without denominator weights; equating a changed product mix with improved efficiency.
- **Uncertainty:** Exact ratio of inputs, not proof of causation; estimated allocation adds uncertainty. Compare like operating conditions.

## C9: Baseline-based estimated savings

- **Required inputs:** Baseline energy adjusted to reporting-period conditions, actual energy for the same period/scope, and documented adjustments.
- **Formula:** `S [kWh] = E_baseline,adjusted − E_actual`; `S_percent = 100 × S / E_baseline,adjusted` when baseline is positive.
- **Example:** Adjusted baseline `1,000 kWh`, actual `900 kWh`: estimated savings `100 kWh`, or `10%`.
- **Invalid-use cases:** Treating a raw before/after difference as attributable savings; dividing by a zero baseline; discarding negative savings.
- **Uncertainty:** Estimated counterfactual, even with exact arithmetic. Report baseline error and assumptions; without a defensible baseline, report the observed change only. See [baseline guidance](baselines-and-forecasting.md).

Sources: E1, N1, G1, I1 and B1 in [references](references.md).
