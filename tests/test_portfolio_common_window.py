from __future__ import annotations

import pandas as pd
import pytest

from apps.api.app.portfolio.models import PortfolioSpec, SimulationConfig
from apps.api.app.portfolio.service import (
    COMPARISON_WINDOW_POLICY,
    PortfolioLedgerService,
)
from tests.portfolio_v3_fixtures import make_history


def test_multi_portfolio_service_recomputes_every_result_on_one_common_window() -> None:
    early_index = pd.to_datetime(
        ["2024-01-02", "2024-01-03", "2024-01-04", "2024-01-05"]
    )
    late_index = pd.to_datetime(["2024-01-04", "2024-01-05"])
    histories = {
        "EARLY": make_history("EARLY", early_index, [0.0, 0.50, 0.10, 0.10]),
        "LATE": make_history("LATE", late_index, [0.0, 0.02]),
    }

    batch = PortfolioLedgerService().run(
        (
            PortfolioSpec.from_weights("Early history", {"EARLY": 1.0}),
            PortfolioSpec.from_weights("Late history", {"LATE": 1.0}),
        ),
        histories,
        SimulationConfig(initial_amount=100.0),
    )

    assert batch.failures == ()
    assert [item.metrics.metrics["start"] for item in batch.results] == [
        "2024-01-04",
        "2024-01-04",
    ]
    assert [item.metrics.metrics["end"] for item in batch.results] == [
        "2024-01-05",
        "2024-01-05",
    ]
    # EARLY's +50% and +10% returns before the common start must not leak into
    # the comparison. It is freshly initialized at 100 on 2024-01-04.
    assert batch.results[0].metrics.metrics["final_balance"] == pytest.approx(110.0)
    assert batch.results[1].metrics.metrics["final_balance"] == pytest.approx(102.0)
    assert any(COMPARISON_WINDOW_POLICY in warning for warning in batch.warnings)


def test_single_runnable_portfolio_keeps_its_full_effective_history() -> None:
    index = pd.to_datetime(
        ["2024-01-02", "2024-01-03", "2024-01-04", "2024-01-05"]
    )
    histories = {
        "ONLY": make_history("ONLY", index, [0.0, 0.01, 0.01, 0.01]),
    }

    batch = PortfolioLedgerService().run(
        (PortfolioSpec.from_weights("Only", {"ONLY": 1.0}),),
        histories,
        SimulationConfig(initial_amount=100.0),
    )

    assert batch.failures == ()
    assert batch.results[0].metrics.metrics["start"] == "2024-01-02"
    assert batch.results[0].metrics.metrics["end"] == "2024-01-05"
    assert not any(COMPARISON_WINDOW_POLICY in warning for warning in batch.warnings)


def test_no_common_window_fails_all_otherwise_runnable_portfolios_explicitly() -> None:
    histories = {
        "EARLY": make_history(
            "EARLY",
            pd.to_datetime(["2024-01-02", "2024-01-03"]),
            [0.0, 0.01],
        ),
        "LATE": make_history(
            "LATE",
            pd.to_datetime(["2024-01-04", "2024-01-05"]),
            [0.0, 0.01],
        ),
    }

    batch = PortfolioLedgerService().run(
        (
            PortfolioSpec.from_weights("Early", {"EARLY": 1.0}),
            PortfolioSpec.from_weights("Late", {"LATE": 1.0}),
        ),
        histories,
        SimulationConfig(initial_amount=100.0),
    )

    assert batch.results == ()
    assert [failure.name for failure in batch.failures] == ["Early", "Late"]
    assert all(failure.stage == "comparison_window" for failure in batch.failures)
    assert all(failure.retryable is False for failure in batch.failures)
    assert any("common effective window" in warning for warning in batch.warnings)


def test_common_window_boundaries_are_explicit_even_across_different_calendars() -> None:
    histories = {
        "A": make_history(
            "A",
            pd.to_datetime(["2024-01-02", "2024-01-04", "2024-01-05"]),
            [0.0, 0.03, 0.01],
        ),
        "B": make_history(
            "B",
            pd.to_datetime(["2024-01-03", "2024-01-04", "2024-01-06"]),
            [0.0, 0.02, 0.01],
        ),
    }

    batch = PortfolioLedgerService().run(
        (
            PortfolioSpec.from_weights("A", {"A": 1.0}),
            PortfolioSpec.from_weights("B", {"B": 1.0}),
        ),
        histories,
        SimulationConfig(initial_amount=100.0),
    )

    assert batch.failures == ()
    assert {item.metrics.metrics["start"] for item in batch.results} == {"2024-01-03"}
    assert {item.metrics.metrics["end"] for item in batch.results} == {"2024-01-05"}
