# Optimizer implementation status

This branch implements the agreed MVP end to end:

- strict training-only candidate selection from the source scan universe;
- 20-stock candidate pool and 10-stock equal-weight portfolios;
- relative ±20% weight bands with next-common-close execution;
- 184,756-combination proxy pass and 30,000 deep-search budget;
- deterministic multi-start, one-swap and limited two-swap search;
- 300 Python exact verifications with 70/30 training/out-of-sample split;
- transaction costs, turnover and rebalance event output;
- signed compressed data snapshot reused by search and verification;
- objective champions, exact-result table, Pareto chart and audit exports.

The optimizer does not create a persistent daily-price database and does not weaken Adjusted Close, repair or corporate-action audit requirements.

Final hardening guarantees exact unique budget contributions, explicit little-endian mask hashing, and a 3 MiB optimizer-only edge request ceiling compatible with the 2 MiB compressed snapshot ceiling.
