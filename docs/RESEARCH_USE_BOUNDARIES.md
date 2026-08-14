# Research-use boundaries

Status: **current product wording and methodology boundary**.

BacktestStock is a research and education tool. Its screens and API metadata must
make the following boundaries visible wherever a user enters a research request or
reads a result. These labels describe what was calculated; they are not a ranking,
signal, recommendation, or promise of future performance.

## Required user-facing labels

### Historical in-sample research

`Historical in-sample research` means that the selected historical period is used
both to calculate the reported evidence and, where applicable, to search, rank, or
compare candidates. It is not walk-forward validation, out-of-sample evidence,
forecasting, or a trading instruction. A result may be numerically reproducible and
still be unsuitable as evidence of future performance.

The label applies to:

- the legacy Scanner and compatibility `/api/backtest` path;
- the full-period Exhaustive search;
- Portfolio v3 historical ledger output; and
- Portfolio Refinery's read-only structural diagnostics.

Portfolio v3 can model path-dependent cash flows, costs, distributions, leverage,
and rebalancing, but those mechanics do not turn a historical period into an
out-of-sample test.

### Current-universe constituents

`Current-universe constituents` means a ticker list or fundamental snapshot sourced
from the current version of a Universe at its published `version` and `sourceAsOf`
date. It is not a point-in-time reconstruction of the constituents that were known
on every historical date in the requested period.

When a current Universe is projected backward, results can contain survivorship,
look-ahead, and delisting bias. The UI must preserve the Universe version/source
date in the visible context or export so a later reader can identify the snapshot
used. A manually entered ticker list is not automatically a point-in-time Universe
either; it should be treated as a user-selected research sample.

### `/api/backtest` Gross return

The compatibility `POST /api/backtest` response uses `return_basis`
`yahoo_adjusted_close_total_return_gross_reinvestment`. Its `total_return` (and the
same metric for the returned benchmark) is a **Gross return** based on the audited
TWD `Yahoo Adj Close` series. Standard distributions are treated as reinvested at
gross amount in that series.

For this endpoint, Gross return does not include transaction costs, slippage,
taxes, dividend withholding, ADR fees, or fund fees. It is not a net executable
return, and it must not be presented as an investment recommendation. The UI label
is `區間總報酬（Gross return）`; consumers should retain the response's
`return_basis`, `return_price_column`, and `dividend_reinvestment_assumption`
metadata when exporting or comparing results.

This wording is specific to the compatibility `/api/backtest` route. Portfolio v3
has a separate ledger contract and must not be described as the legacy endpoint's
Gross return merely because both paths use the shared TWD data authority.

## Required disclaimer

The following meaning must remain visible near the request controls or result
heading:

> Historical in-sample research；若使用目前 Universe，資料屬 Current-universe constituents 快照而非 point-in-time 歷史成分；`/api/backtest` 的區間總報酬為 Gross return。結果僅供研究與教育用途，不構成投資建議或未來績效保證。

The exact punctuation may vary by locale, but the three concepts must not be
removed or hidden behind an optional details panel. A user should be able to see
the boundary before running a request and again when reading the result.

## Related contracts

- [`METRICS_REPRODUCIBILITY.md`](METRICS_REPRODUCIBILITY.md) — price, adjusted total-return, and compatibility API semantics.
- [`UNIVERSE_SCANNER_V2.md`](UNIVERSE_SCANNER_V2.md) — Universe source/version and scanner behavior.
- [`EXHAUSTIVE_OPTIMIZER_V3.md`](EXHAUSTIVE_OPTIMIZER_V3.md) — full-period search boundary.
- [`PORTFOLIO_V3_CONTRACT.md`](PORTFOLIO_V3_CONTRACT.md) — Portfolio ledger/API semantics.
- [`quant/RETURN_SEMANTICS.md`](quant/RETURN_SEMANTICS.md) — historical, sample, and OOS wording.
