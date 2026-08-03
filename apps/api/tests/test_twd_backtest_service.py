from __future__ import annotations

from datetime import date

import pandas as pd
import pytest

from apps.api.app.backtest_service import (
    PortfolioSpec,
    TWDPortfolioBacktestService,
    align_twd_price_frame,
    simulate_twd_portfolio,
)
from apps.api.app.data.history_service import (
    HistoryFailure,
    PartialTWDHistories,
    TWDAssetHistory,
)
from apps.api.app.data.twd_valuation import TWDValuation


def _history(
    symbol: str,
    currency: str,
    native: list[float],
    fx: list[float],
    twd: list[float],
    dates: list[str],
) -> TWDAssetHistory:
    index = pd.to_datetime(dates)
    valuation = TWDValuation(
        source_currency=currency,
        native_adjusted_close=pd.Series(native, index=index, dtype=float),
        fx_to_twd=pd.Series(fx, index=index, dtype=float),
        adjusted_close_twd=pd.Series(twd, index=index, dtype=float),
        daily_returns=pd.Series(twd, index=index, dtype=float)
        .pct_change(fill_method=None)
        .fillna(0.0),
    )
    return TWDAssetHistory(
        symbol=symbol,
        quote_currency=currency,
        valuation=valuation,
        corporate_action_audit={"status": "verified_standard_actions"},
    )


class FakeHistoryService:
    def __init__(self, histories: dict[str, TWDAssetHistory], failures=None) -> None:
        self.histories = histories
        self.failures = failures or {}
        self.requests: list[tuple[str, ...]] = []

    def histories_partial(self, symbols, _start, _end) -> PartialTWDHistories:
        requested = tuple(symbols)
        self.requests.append(requested)
        return PartialTWDHistories(
            requested=requested,
            histories={symbol: self.histories[symbol] for symbol in requested if symbol in self.histories},
            failures={symbol: self.failures[symbol] for symbol in requested if symbol in self.failures},
        )


def test_mixed_market_portfolio_and_benchmark_are_calculated_in_twd() -> None:
    usd = _history(
        "USDASSET",
        "USD",
        [100.0, 100.0, 100.0],
        [30.0, 30.2, 30.3],
        [3000.0, 3020.0, 3030.0],
        ["2025-01-02", "2025-01-03", "2025-01-06"],
    )
    taiwan = _history(
        "2330.TW",
        "TWD",
        [500.0, 510.0],
        [1.0, 1.0],
        [500.0, 510.0],
        ["2025-01-02", "2025-01-06"],
    )
    benchmark = _history(
        "SPY",
        "USD",
        [200.0, 200.0, 200.0],
        [30.0, 30.2, 30.3],
        [6000.0, 6040.0, 6060.0],
        ["2025-01-02", "2025-01-03", "2025-01-06"],
    )
    fake = FakeHistoryService({"USDASSET": usd, "2330.TW": taiwan, "SPY": benchmark})
    service = TWDPortfolioBacktestService(history_service=fake)

    result = service.run(
        [
            PortfolioSpec(
                name="mixed",
                tickers=("USDASSET", "2330"),
                weights=(0.5, 0.5),
            )
        ],
        start=date(2025, 1, 2),
        end=date(2025, 1, 6),
        initial_amount=1000.0,
        benchmark="SPY",
    )

    assert fake.requests == [("USDASSET", "2330.TW", "SPY")]
    assert result.failures == []
    portfolio = result.results[0]
    assert portfolio["valuationCurrency"] == "TWD"
    assert portfolio["metadata"]["asset_quote_currencies"] == {
        "USDASSET": "USD",
        "2330.TW": "TWD",
    }
    assert portfolio["assetFxAudits"]["USDASSET"] is None
    assert portfolio["assetNativePriceFingerprints"]["USDASSET"]
    assert portfolio["assetFxPriceFingerprints"]["2330.TW"]
    # 2330.TW is carried from its prior observed close while USDASSET changes
    # solely because USD/TWD moved on the Jan-03 FX-only day.
    assert [point["date"] for point in portfolio["portfolioHistory"]] == [
        "2025-01-02",
        "2025-01-03",
        "2025-01-06",
    ]
    assert [point["value"] for point in portfolio["portfolioHistory"]] == pytest.approx(
        [1000.0, 1003.3333333333334, 1015.0]
    )
    assert result.benchmark is not None
    assert result.benchmark["portfolioHistory"][1]["date"] == "2025-01-03"
    assert result.benchmark["portfolioHistory"][1]["value"] == pytest.approx(
        1006.6666666666666
    )


def test_failed_portfolio_does_not_erase_a_successful_peer() -> None:
    good = _history(
        "GOOD",
        "TWD",
        [100.0, 110.0],
        [1.0, 1.0],
        [100.0, 110.0],
        ["2025-01-02", "2025-01-03"],
    )
    fake = FakeHistoryService(
        {"GOOD": good},
        {
            "BAD": HistoryFailure(
                symbol="BAD",
                stage="fx",
                detail="USD/TWD unavailable",
                retryable=True,
            )
        },
    )
    service = TWDPortfolioBacktestService(history_service=fake)

    result = service.run(
        [
            PortfolioSpec("good", ("GOOD",), (1.0,)),
            PortfolioSpec("bad", ("BAD",), (1.0,)),
        ],
        start=date(2025, 1, 2),
        end=date(2025, 1, 3),
        initial_amount=1000.0,
    )

    assert [item["name"] for item in result.results] == ["good"]
    assert len(result.failures) == 1
    assert result.failures[0].name == "bad"
    assert result.failures[0].retryable is True
    assert result.failures[0].symbols == ("BAD",)


def test_common_calendar_never_backfills_an_unobserved_opening_price() -> None:
    first = _history(
        "FIRST",
        "TWD",
        [100.0, 110.0, 120.0],
        [1.0, 1.0, 1.0],
        [100.0, 110.0, 120.0],
        ["2025-01-02", "2025-01-03", "2025-01-06"],
    )
    later = _history(
        "LATER",
        "TWD",
        [50.0, 55.0],
        [1.0, 1.0],
        [50.0, 55.0],
        ["2025-01-03", "2025-01-06"],
    )

    frame = align_twd_price_frame({"FIRST": first, "LATER": later}, ["FIRST", "LATER"])

    assert frame.index.strftime("%Y-%m-%d").tolist() == ["2025-01-03", "2025-01-06"]
    assert frame["FIRST"].tolist() == [110.0, 120.0]
    assert frame["LATER"].tolist() == [50.0, 55.0]


def test_twd_period_rebalance_uses_the_previous_close_before_new_period() -> None:
    prices = pd.DataFrame(
        {
            "AAA": [100.0, 200.0, 400.0, 400.0],
            "BBB": [100.0, 100.0, 100.0, 100.0],
        },
        index=pd.to_datetime(["2024-01-30", "2024-01-31", "2024-02-01", "2024-02-02"]),
    )

    values = simulate_twd_portfolio(
        prices,
        weights=(0.5, 0.5),
        initial_amount=100.0,
        rebalancing_period="monthly",
    )

    assert values.loc[pd.Timestamp("2024-01-31")] == pytest.approx(150.0)
    assert values.loc[pd.Timestamp("2024-02-01")] == pytest.approx(225.0)
