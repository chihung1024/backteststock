# Risk Mathematics V1

Status: Phase 2 pure-mathematics contract. This phase does not expose a Refinery API/UI, perform clustering/selection/sizing, or migrate any production consumer.

## Contract identity

```text
RISK_MATH_CONTRACT_VERSION = risk-math-twd-2026-08-09.1
```

Primary implementation:

```text
apps/api/app/quant/
├── covariance.py
├── risk.py
└── correlation.py
```

Input matrices are expected to come from Phase 1 `ResearchDatasetV1` or an explicitly equivalent tested matrix.

## 1. Covariance estimators

### Sample covariance

`sample_covariance()` returns the conventional unbiased sample covariance (`ddof=1`). It is retained as a transparent diagnostic/reference estimator, not the formal default for later optimization.

### Ledoit-Wolf shrinkage

`ledoit_wolf_covariance()` implements the Ledoit-Wolf linear shrinkage estimator using centered maximum-likelihood empirical covariance (`1/n`) and a spherical target:

```text
Σ_LW = (1 - δ) Σ_MLE + δ μ I
μ    = trace(Σ_MLE) / p
```

The shrinkage coefficient follows the Ledoit-Wolf analytical estimator used by the scikit-learn reference implementation.

**Dependency policy:** scikit-learn is a dev/test-only dependency. Production code does not import it. CI compares the NumPy implementation against `sklearn.covariance.ledoit_wolf` across multiple matrix shapes, including `p > n`, one-feature, and centered-input cases.

Any future change that breaks reference parity requires explicit methodology review/versioning; do not loosen the parity test merely to accept a different estimator.

### EWMA covariance

`ewma_covariance()` is a recency/sensitivity estimator with an **explicit caller-supplied decay**. Phase 2 intentionally does not hard-code a universal RiskMetrics-style decay constant.

For observations ordered oldest→newest:

```text
raw_weight_t = decay^(T-1-t)
weight_t     = raw_weight_t / sum(raw_weight)
```

When `assume_centered=False`, the matrix is centered around its weighted mean before weighted population covariance is computed.

### Annualization

Every covariance estimator accepts a positive explicit `annualization` multiplier. Shrinkage is estimated on the periodic return matrix and is unchanged by subsequent covariance scaling. Later daily-risk displays may use 252; structural weekly analyses must use an explicitly appropriate scale rather than silently applying daily annualization.

## 2. Covariance diagnostics

`covariance_diagnostics()` reports, without silently repairing the input:

- observation count;
- feature count;
- maximum symmetry error;
- numerical tolerance;
- minimum/maximum eigenvalue;
- PSD state within tolerance;
- numerical rank;
- condition number (`inf` for singular/near-singular matrices).

The diagnostic tolerance is **relative to the covariance matrix magnitude**. Small-unit covariance matrices must not inherit an artificial absolute floor of `1.0`; PSD/rank/condition diagnostics are required to remain consistent under positive unit rescaling within floating-point limits.

`estimator_dispersion()` reports scale-normalized pairwise Frobenius distance among covariance estimators so later UI can expose model sensitivity instead of presenting one estimate as exact truth.

## 3. Portfolio risk decomposition

For weights `w` summing to 1 and covariance `Σ`:

```text
variance = w' Σ w
σ_p      = sqrt(variance)
MRC_i    = (Σw)_i / σ_p
RC_i     = w_i * MRC_i
```

For non-zero portfolio volatility, Euler decomposition must satisfy:

```text
sum(RC_i) = σ_p
```

**Signed RC is authoritative.** A hedge/diversifier may have `RC_i < 0`; the sign must remain visible.

When portfolio volatility is numerically zero, MRC/RC are unavailable rather than fabricated as zero vectors.

## 4. Diversification and effective-count diagnostics

### Diversification Ratio

```text
DR = sum(w_i * σ_i) / σ_p
```

Undefined when portfolio volatility is zero.

### Weight-effective holdings

```text
N_weight = 1 / sum(w_i^2)
```

### Gross risk-contribution equivalent holdings

This is deliberately a separate *gross* concentration diagnostic:

```text
p_i       = abs(RC_i) / sum(abs(RC))
N_grossRC = 1 / sum(p_i^2)
```

It must never replace or hide signed RC.

### Effective dimensions

For non-negative eigenvalues `λ_k` of a PSD correlation/covariance matrix:

```text
p_k = λ_k / sum(λ)
entropy effective rank = exp(-sum(p_k log p_k))
participation ratio    = (sum λ)^2 / sum(λ^2)
```

Both are reported because they summarize concentration differently. Neither is labelled as a definitive "number of independent bets".

A matrix of perfect duplicate assets has effective dimension ~1; identity correlation has full dimension equal to asset count. Effective-dimension results are also required to be invariant to positive matrix rescaling within floating-point limits.

## 5. Correlation policy

Phase 2 separates time horizons rather than forcing one daily matrix to answer every question.

Initial lookback constants:

```text
TACTICAL_DAILY_WINDOW    = 63
MEDIUM_DAILY_WINDOW      = 252
STRUCTURAL_WEEKLY_WINDOW = 156
```

These are analysis lookbacks, not claims that a particular sample size is statistically sufficient.

`multi_horizon_correlations()` therefore requires callers to provide minimum-observation guards explicitly for tactical, medium, and structural views.

The structural input is Phase 1's synchronized weekly TWD return matrix using the last actual observation date in each W-FRI period. It is intentionally distinct from daily investor-NAV risk.

## 6. Complete-case/sample evidence

Correlation functions report:

- input observations;
- effective observations;
- dropped observations;
- requested window;
- condition;
- stress threshold when applicable;
- status.

For unconditional correlation, `input_observations` is the requested/windowed candidate row count before asset complete-case filtering. For downside/stress correlation, it is the number of rows that are **eligible under the benchmark condition** after benchmark alignment/finite-value validation but before asset complete-case filtering. `dropped_observations` therefore counts invalid/missing asset rows inside the eligible conditional sample; rows that simply do not satisfy the downside/stress condition are not mislabelled as dropped data.

The internal benchmark alignment uses a collision-proof temporary label, so an asset column named like an implementation-reserved benchmark field cannot corrupt conditional correlation.

Correlation functions do not silently emit a matrix when sample evidence is inadequate.

Statuses include:

- `ok`
- `insufficient_observations`
- `degenerate_variance`

Minimum observations are caller policy, not a hidden constant in the pure math layer.

## 7. Downside and stress correlation

### Downside

`downside_correlation()` conditions on aligned benchmark return `< 0`.

### Stress

`stress_correlation()` computes the benchmark lower-tail threshold from aligned finite benchmark observations and selects returns `<= threshold` for an explicit quantile in `(0, 0.5)`.

If the selected conditional sample is smaller than the caller-supplied minimum, status is `insufficient_observations` and `matrix=None`. The system must not output false decimal precision from a tiny tail sample.

## 8. Required Phase 2 invariants

Tests must enforce:

1. Ledoit-Wolf NumPy implementation matches scikit-learn reference covariance and shrinkage.
2. The golden fixture itself is independently anchored to NumPy sample covariance and scikit-learn Ledoit-Wolf reference values.
3. Covariance diagnostics expose singularity/PSD/symmetry rather than hiding it.
4. Covariance diagnostics and effective dimensions preserve their classification under positive unit rescaling within floating-point limits.
5. `sum(RC) == portfolio volatility` for non-zero-volatility portfolios.
6. Asset-order permutation leaves portfolio risk unchanged and only permutes per-asset RC.
7. Negative signed hedge RC remains negative.
8. Perfect duplicate assets do not manufacture effective risk dimensions.
9. Identity correlation has full effective dimension.
10. Conditional correlation fails closed when samples are insufficient.
11. Conditional sample accounting distinguishes condition-ineligible rows from actual incomplete-data drops.
12. Complete-case drops are explicitly counted.
13. Golden fixture results remain stable unless the methodology contract is intentionally versioned.

## 9. Explicit non-goals

- No public Refinery endpoint.
- No Refinery UI.
- No clustering or redundancy classification.
- No factor-overlap engine.
- No Leave-One-Out/Add-One/Replace-One.
- No selection or sizing.
- No HRP/ERC/minimum-variance portfolio optimizer.
- No Exhaustive migration or integration.
- No OOS/walk-forward recommendation claim.

Phase 3 may consume these primitives only after Phase 2 passes reference parity, invariants, full regression checks, independent review, backup verification, and closeout.
