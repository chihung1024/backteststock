from __future__ import annotations

from datetime import date

import pandas as pd

from apps.api.app.data.history_service import PartialTWDHistories, TWDAssetHistory
from apps.api.app.data.twd_valuation import TWDValuation
from apps.api.app.portfolio.ledger import simulate_portfolio_ledger
from apps.api.app.portfolio.models import PortfolioSpec, SimulationConfig
from apps.api.app.research.dataset import build_research_dataset
from apps.api.app.research.oos_ledger import WalkForwardEvaluation, run_continuous_oos_ledger
from apps.api.app.research.walk_forward import (
    ResolvedPITUniverse,
    WalkForwardPeriod,
    create_decision_snapshot,
)


def _history(symbol: str, dates: list[str], values: list[float]) -> TWDAssetHistory:
    index = pd.to_datetime(dates)
    native = pd.Series(values, index=index, dtype=float, name="native_adjusted_close")
    fx = pd.Series(1.0, index=index, dtype=float, name="fx_to_twd")
    twd = native.rename("adjusted_close_twd")
    return TWDAssetHistory(
        symbol=symbol,
        quote_currency="TWD",
        valuation=TWDValuation(
            source_currency="TWD",
            native_adjusted_close=native,
            fx_to_twd=fx,
            adjusted_close_twd=twd,
            daily_returns=twd.pct_change(fill_method=None).fillna(0.0).rename("daily_return"),
        ),
        corporate_action_audit={"status": "verified_standard_actions"},
        raw_quote_currency="TWD",
        native_price_scale=1.0,
    )


def _decision(period: WalkForwardPeriod):
    evidence = date(2024, 1, 30) if period.decision_date.month == 1 else date(2024, 2, 1)
    pit = ResolvedPITUniverse(
        universe_id="synthetic",
        requested_as_of=period.decision_date,
        source_as_of=evidence,
        evidence_available_as_of=evidence,
        fetched_at=f"{evidence.isoformat()}T12:00:00Z",
        version=f"synthetic-{evidence.isoformat()}",
        checksum=f"checksum-{period.period_id}",
        members=("AAA",),
        membership_policy="latest-causal-v1",
        membership_authoritative=True,
        source_label="synthetic-official",
        source_url="https://example.test/universe",
        source_is_proxy=False,
    )
    return create_decision_snapshot(
        period=period,
        pit_universe=pit,
        training_dataset_hash=f"training-{period.period_id}",
        training_effective_start=period.training_start,
        training_effective_end=period.training_end,
        selector_contract_version="synthetic-v1",
        selector_rule="hold-AAA",
        selector_parameters={},
        eligible_candidates=("AAA",),
        selected_constituents=("AAA",),
        weights=(1.0,),
    )


def _dataset(period: WalkForwardPeriod, dates: list[str], values: list[float]):
    return build_research_dataset(
        PartialTWDHistories(
            requested=("AAA",),
            histories={"AAA": _history("AAA", dates, values)},
            failures={},
        ),
        start=period.evaluation_start,
        end=period.evaluation_end,
    )


def test_unchanged_target_split_matches_one_portfolio_v3_ledger():
    first = WalkForwardPeriod(
        period_id="first",
        training_start=date(2024, 1, 2),
        training_end=date(2024, 1, 31),
        decision_date=date(2024, 1, 31),
        evaluation_start=date(2024, 2, 1),
        evaluation_end=date(2024, 2, 2),
    )
    second = WalkForwardPeriod(
        period_id="second",
        training_start=date(2024, 1, 2),
        training_end=date(2024, 2, 2),
        decision_date=date(2024, 2, 2),
        evaluation_start=date(2024, 2, 5),
        evaluation_end=date(2024, 2, 6),
    )
    config = SimulationConfig(initial_amount=100.0, transaction_cost_bps=100.0)
    split = run_continuous_oos_ledger(
        (
            WalkForwardEvaluation(_decision(first), _dataset(first, ["2024-02-01", "2024-02-02"], [100.0, 110.0])),
            WalkForwardEvaluation(_decision(second), _dataset(second, ["2024-02-05", "2024-02-06"], [110.0, 121.0])),
        ),
        config,
    ).ledger

    authority = simulate_portfolio_ledger(
        PortfolioSpec.from_weights("AAA", {"AAA": 1.0}),
        {
            "AAA": _history(
                "AAA",
                ["2024-02-01", "2024-02-02", "2024-02-05", "2024-02-06"],
                [100.0, 110.0, 110.0, 121.0],
            )
        },
        config,
    )

    pd.testing.assert_series_equal(split.equity, authority.equity)
    pd.testing.assert_series_equal(split.daily_returns, authority.daily_returns)
    pd.testing.assert_series_equal(split.return_index, authority.return_index)
    assert split.transaction_costs == authority.transaction_costs == 0.0
