# Optimizer Hub Parameter Optimization — Capacity Evidence (2026-08-19)

Status: **Phase 4B-3 release evidence**

This record preserves the empirical runtime evidence used to set the synchronous V1 tuning budget. It is evidence for the release decision, not a second methodology or numerical authority.

## Source identity

- Repository: `chihung1024/backteststock`
- Product quant/API tree measured: `e9ba4296ecc107d11a9b398df89c3cc26a9c0239`
- Isolated benchmark PR: `#176` (`internal-4b3-capacity-benchmark-20260819` → `feat/optimizer-hub-parameter-optimization`), never intended for merge
- Successful parallel benchmark workflow run: `32165862276` (`Internal Parameter Tuning Capacity Benchmark`, run #13)
- Runtime authority exercised: real `run_inner_parameter_tuning`; no mocked tuner, proxy metric or per-candidate market-data fetch
- Dataset regime: the audited synthetic `AAA / BBB / BND` regime already used by `tests/test_parameter_tuning_integration.py`
- Measurement definition: wall time around tuning execution only; dependency installation and CI queue/setup are excluded

The later product-only changes before this evidence record were browser locator assertions, OOS execution-metadata name bounding, and the budget convergence itself; the tuning numerical authority measured here is unchanged.

## Matrix

| Candidates | Inner folds | Planned candidate-fold evaluations | Tuning wall time | Eligible candidates |
| ---: | ---: | ---: | ---: | ---: |
| 2 | 3 | 6 | 1.233596 s | 2 / 2 |
| 12 | 3 | 36 | 10.164710 s | 12 / 12 |
| 12 | 6 | 72 | 18.608883 s | 12 / 12 |
| 24 | 3 | 72 | 20.076092 s | 24 / 24 |
| 24 | 6 | 144 | 21.847702 s | 24 / 24 |
| 48 | 3 | 144 | 39.293456 s | 48 / 48 |
| 48 | 6 | 288 | 78.709000 s | 48 / 48 |

The 48×6 case demonstrates that 288 candidate-fold evaluations complete correctly on the benchmark runner, but ~78.7 seconds is tuning CPU only. It excludes live Training/Evaluation data access, winner refit, outer-period orchestration and final OOS work. Therefore 288 is evidence of technical completability, not the accepted synchronous product ceiling.

## Accepted V1 budget

```text
MAX_PARAMETER_CANDIDATES = 48
MAX_INNER_FOLDS = 6
MAX_TUNING_EVALUATIONS_PER_JOB = 216
```

The global 216 limit is evaluated against the full request workload (`candidateCount × innerFoldCount × outerPeriodCount`) before market-data fetch. It preserves the shipped default `12 × 3 × 6 = 216` while preventing the measured 288-evaluation worst case from becoming an accepted synchronous request.

Raising the 216 ceiling requires new empirical evidence and separate release review. The per-dimension 48-candidate / 6-fold limits do not imply that every Cartesian combination is admissible; the global job budget remains authoritative.

## Benchmark RCA discovered during measurement

Early benchmark attempts failed before producing valid capacity data with `ValueError: portfolio name cannot exceed 60 characters`. Candidate diagnostics proved that inner folds had completed and the failure occurred when the OOS adapter constructed execution-only `PortfolioSpec` segment names by concatenating the nested tuning name with a valid Walk-Forward `period_id`.

The product fix preserves full `period_id` in Decision/audit/request identity and deterministically hash-compacts only an overlong internal segment name. Existing short internal names remain byte-for-byte unchanged. Capacity measurement then used the exact formally tested `outer-2025-12` period identifier so runtime timing remained isolated from that metadata boundary.

## Release interpretation

This benchmark supports only the bounded synchronous V1 decision above. It does not justify queue/distributed-worker infrastructure, broader search dimensions, a higher job budget, or changes to Dual Momentum, Allocation, Portfolio v3, ResearchDataset, metric, or ResearchRun authorities.
