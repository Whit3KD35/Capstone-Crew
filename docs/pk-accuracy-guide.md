# PK Accuracy Guide

## What To Measure

Use concentration prediction error metrics, not generic classification accuracy.

- `P20`: percent of predictions within +/-20% of observed concentration
- `P30`: percent of predictions within +/-30% of observed concentration
- `MAE`: mean absolute error
- `RMSE`: root mean square error
- `MPE`: mean percentage error (bias)
- `MAPE`: mean absolute percentage error

## Suggested Goal

Set a drug-specific target, for example:

- Primary: `P30 >= 96%`
- Secondary: `MAPE <= 20%`

Only claim this on a locked holdout dataset.

## Data Requirements

Each row should contain:

- patient identifier (de-identified)
- medication name
- dose amount, dose time, route
- sampling time
- observed concentration and units
- patient covariates (weight, renal function, age, sex)

## Current API Support

- `POST /pk/accuracy-metrics`
  - input: observed and predicted concentration arrays
  - output: `P20`, `P30`, `MAE`, `RMSE`, `MPE`, `MAPE`

- `POST /pk/therapeutic-window`
  - supports custom policy targets:
    - `target_max_pct_below`
    - `target_max_pct_above`
    - `target_min_pct_within`

## Practical Workflow

1. Build an observed concentration-time dataset for one drug first.
2. Simulate predictions with the same sampling timestamps.
3. Compute accuracy metrics using `/pk/accuracy-metrics`.
4. Tune model parameters and targets.
5. Re-run on holdout set and document final metrics.
