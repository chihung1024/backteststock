from __future__ import annotations

from datetime import date

import pytest
from pydantic import ValidationError

from apps.api.app.refinery import RefineryRequest


def test_weight_tolerance_is_proportionally_normalized_to_unit_sum() -> None:
    request = RefineryRequest(
        symbols=["AAA", "BBB"],
        start_date=date(2024, 1, 1),
        end_date=date(2024, 12, 31),
        weights=[
            {"symbol": "AAA", "weight_percent": 49.99},
            {"symbol": "BBB", "weight_percent": 50.0},
        ],
    )

    assert request.weight_input_total_percent == pytest.approx(99.99)
    assert request.weight_vector is not None
    assert sum(request.weight_vector) == pytest.approx(1.0, abs=1e-15)
    assert request.weight_vector[0] / request.weight_vector[1] == pytest.approx(
        49.99 / 50.0,
        rel=1e-15,
    )


def test_weight_total_outside_contract_tolerance_is_rejected() -> None:
    with pytest.raises(ValidationError, match="weights must total 100%"):
        RefineryRequest(
            symbols=["AAA", "BBB"],
            start_date=date(2024, 1, 1),
            end_date=date(2024, 12, 31),
            weights=[
                {"symbol": "AAA", "weight_percent": 49.9},
                {"symbol": "BBB", "weight_percent": 50.0},
            ],
        )


def test_candidate_count_above_resource_limit_is_rejected() -> None:
    with pytest.raises(ValidationError):
        RefineryRequest(
            symbols=[f"SYM{index}" for index in range(101)],
            start_date=date(2024, 1, 1),
            end_date=date(2024, 12, 31),
        )


def test_history_window_above_resource_limit_is_rejected() -> None:
    with pytest.raises(ValidationError, match="requested history exceeds"):
        RefineryRequest(
            symbols=["AAA", "BBB"],
            start_date=date(2000, 1, 1),
            end_date=date(2020, 1, 1),
        )
