# Baselines, anomalies and forecasting

## Compare equivalent conditions

A baseline represents expected use under stated conditions. Savings require a counterfactual without intervention; a forecasting benchmark supplies a prediction to beat.

Start with persistence, same hour last week, hour/day-of-week profiles or simple regression. Check weekends, holidays, weather, occupancy, production volume/mix, operating hours and structural changes against actual calendars/schedules.

Lower consumption may reflect less production, closure or milder weather, not better efficiency. Match scope, duration and coverage; adjust relevant conditions for [C9 savings](calculations.md#c9-baseline-based-estimated-savings). [C8 intensity](calculations.md#c8-energy-intensity) requires meaningful denominators.

## Anomalies are investigation candidates

An anomaly is unusual relative to an expectation, not a confirmed fault. Check quality/context first. Identifying equipment failure from aggregate building data requires corroboration: submeters, alarms or inspection. Select thresholds on suitable historical data; without labelled events, detection accuracy remains unverified.

## Evaluate forward in time

Use chronological training, validation for model/threshold selection, then an untouched later test period. Match the forecast horizon; rolling-origin evaluation assesses stability. Add fold gaps when label windows/availability delays require them. Historical input overlap is not itself leakage when available at prediction time.

Leakage examples to check:

- Fitting scalers, imputers or feature selection on the full dataset.
- Centered rolling features or backward filling from future observations.
- Future realized weather/production supplied where only forecasts were available.
- Training labels that extend into evaluation time; tuning repeatedly on test results.
- Random splits that let later observations inform earlier predictions.

Fit learned transformations within training folds. Calendar features may be known ahead; outcomes are not. For irregular data, time-based boundaries avoid unequal-duration row-count splits.

## Basic error metrics

| Metric | Interpretation and limits |
| --- | --- |
| MAE | Mean absolute error; target units, easy to interpret, may hide rare large misses. |
| RMSE | Square root of mean squared error; target units, emphasizes large misses, sensitive to outliers. |
| Mean signed error | Define sign, e.g. prediction minus actual; indicates bias but opposite errors cancel. |
| MAPE | Relative error; undefined mathematically at zero and unstable near zero. Library safeguards differ; avoid for zero-heavy or signed net series. |

Report horizon, units, coverage, aggregation and benchmark performance. Weight unequal durations deliberately; check peak-hour errors separately.

Sources: B1, F1–F3 in [references](references.md).
