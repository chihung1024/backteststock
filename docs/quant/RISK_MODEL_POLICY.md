# Risk Model Policy — Phase 0 Freeze

Status: methodology boundary for future Portfolio Refinery risk work. Phase 0 does not implement covariance, clustering, or sizing.

## 1. Purpose

This policy prevents future risk modules from inventing incompatible return/covariance conventions. Implementation begins in Phase 2 only after Phase 1 ResearchDataset establishes one reproducible input matrix contract.

## 2. Separation of questions

Future Refinery risk analysis must distinguish:

1. **Daily investor risk** — actual daily TWD return experience used for portfolio volatility, component risk contribution, and daily historical tail risk.
2. **Structural relationship** — synchronized lower-frequency TWD returns used to assess persistent correlation, clustering, redundancy, and effective risk dimensions across markets with different trading hours/calendars.
3. **Stress relationship** — conditional/downside samples used only when there are enough observations to support the estimate.

One covariance/correlation matrix must not be forced to answer all three questions.

## 3. Covariance estimator interface planned for Phase 2

The implementation must expose a versioned estimator interface rather than hard-coding one call site.

Required estimators:

- Sample covariance — diagnostic/reference only.
- Ledoit-Wolf shrinkage — intended default formal covariance estimator, subject to reference-parity validation.
- EWMA covariance — sensitivity/recency diagnostic.

No production implementation is added in Phase 0.

## 4. Required covariance diagnostics

Every formal covariance result must carry enough metadata to judge reliability:

- estimator/methodology version;
- effective observations;
- frequency/window;
- symmetry check;
- minimum eigenvalue / PSD check within numerical tolerance;
- condition number or an explicit instability indicator;
- estimator sensitivity/dispersion where multiple estimators are calculated;
- excluded/unavailable symbols reported explicitly rather than silently removed.

## 5. Planned portfolio-risk primitives

Phase 2 is expected to implement and test:

```text
portfolio_volatility = sqrt(w' Σ w)
MRC_i                = (Σw)_i / portfolio_volatility
RC_i                 = w_i * MRC_i
DiversificationRatio = sum(w_i * sigma_i) / portfolio_volatility
```

Signed `RC_i` must remain visible. A hedge with negative risk contribution must not be converted into a positive risk contributor merely to produce an effective-count statistic.

A gross risk-contribution equivalent count may separately use normalized `abs(RC)` and must be labelled as such.

## 6. Effective-dimension policy

Future UI/methodology must distinguish:

- nominal holdings;
- weight-effective holdings;
- gross risk-contribution equivalent holdings;
- correlation effective rank;
- covariance effective rank.

Do not label PCA/eigenvalue participation ratios as a definitive "number of independent bets" without an explicit independent-bet transformation/methodology.

## 7. Correlation horizons planned for Phase 2

The eventual implementation should support, subject to available data:

- tactical daily window (for example 63 observations);
- medium daily window (for example 252 observations);
- structural synchronized weekly window over a materially longer period;
- downside/stress conditional correlation with minimum-observation guards.

Exact defaults become contract values only when Phase 2 is implemented and validated; Phase 0 does not freeze arbitrary thresholds as universal truths.

## 8. Cross-market synchronization rule

Daily TWD portfolio risk may legitimately include FX-only and other-market-open valuation changes under the current TWD calendar contract.

Structural correlation/clustering must separately address non-synchronous market closes. The intended Phase 2 design is a synchronized weekly TWD research return series from Phase 1 ResearchDataset, not naive reuse of a 100-asset daily matrix for every purpose.

## 9. Stress/downside sample rule

Conditional correlation, downside beta, or stress covariance must not be emitted as high-confidence numerical output from trivially small samples.

Phase 2 must define:

- condition/event definition;
- observation count;
- minimum required observations;
- confidence/insufficient-data state.

If the threshold is not met, the result is unavailable/uncertain rather than a fabricated precise number.

## 10. Model-selection and optimizer boundary

Risk models estimate structure/risk. They do not create expected alpha by themselves.

- HRP is a sizing/risk-allocation benchmark, not a stock-selection method.
- Minimum variance is a sizing benchmark, not proof of expected return superiority.
- Unconstrained expected-return Markowitz is not part of the approved V1 path.
- Risk-budget constraints are policy parameters and must be user-visible/versioned when Phase 9 is reached.
- No model may be called superior based solely on the same full-period data used to tune/select it; OOS validation belongs to Phase 7+.

## 11. Implementation dependency order

```text
Phase 0  metric/return authority
   ↓
Phase 1  ResearchDataset / synchronized matrices
   ↓
Phase 2  risk mathematics and estimator validation
   ↓
Phase 3+ API/UI/diagnosis
```

Covariance or clustering code added before the Phase 1 dataset exit gate is a roadmap violation unless the plan is explicitly re-reviewed and amended.
