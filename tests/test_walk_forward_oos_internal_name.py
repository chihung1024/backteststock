from __future__ import annotations

from datetime import date

from apps.api.app.portfolio.models import PortfolioSpec
from apps.api.app.research.oos_ledger import _segment_portfolio_name
from apps.api.app.research.walk_forward import WalkForwardPeriod


def test_short_walk_forward_segment_name_remains_byte_for_byte_unchanged():
    assert (
        _segment_portfolio_name("Walk-Forward OOS", "2024-02-01")
        == "Walk-Forward OOS:2024-02-01"
    )


def test_long_walk_forward_segment_name_is_bounded_deterministically():
    period_id = "period-" + "x" * 96
    first = _segment_portfolio_name("Inner Parameter Tuning:abcdef123456", period_id)
    second = _segment_portfolio_name("Inner Parameter Tuning:abcdef123456", period_id)
    other = _segment_portfolio_name(
        "Inner Parameter Tuning:abcdef123456",
        period_id + "y",
    )

    assert len(first) == 60
    assert first == second
    assert first != other
    PortfolioSpec.from_weights(first, {"AAA": 1.0})


def test_execution_name_compaction_does_not_change_walk_forward_period_identity():
    period_id = "research-period-" + "z" * 96
    period = WalkForwardPeriod(
        period_id=period_id,
        training_start=date(2024, 1, 2),
        training_end=date(2024, 1, 31),
        decision_date=date(2024, 1, 31),
        evaluation_start=date(2024, 2, 1),
        evaluation_end=date(2024, 2, 2),
    )

    internal_name = _segment_portfolio_name(
        "Inner Parameter Tuning:abcdef123456",
        period.period_id,
    )

    assert period.period_id == period_id
    assert period.period_id not in internal_name
    assert len(internal_name) == 60
