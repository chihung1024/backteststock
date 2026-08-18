from __future__ import annotations

from datetime import date

import pytest

from apps.api.app.research.parameter_optimization import (
    PARAMETER_OPTIMIZATION_INNER_FOLD_POLICY,
    InnerValidationSpec,
    ParameterSearchSpace,
    TuningBudget,
    build_inner_fold_schedule,
    build_parameter_search_plan,
    enumerate_parameter_candidates,
)
from apps.api.app.research.walk_forward import WalkForwardPeriod


def _outer_period() -> WalkForwardPeriod:
    return WalkForwardPeriod(
        period_id="outer-2025-12",
        training_start=date(2023, 1, 1),
        training_end=date(2025, 12, 31),
        decision_date=date(2025, 12, 31),
        evaluation_start=date(2026, 1, 1),
        evaluation_end=date(2026, 1, 31),
    )


def test_search_space_is_order_and_duplicate_invariant() -> None:
    first = ParameterSearchSpace(
        lookback_months=(12, 6, 12),
        top_k=(2, 1, 2),
        absolute_thresholds=(0.0, -0.0, 0.05),
        allocation_methods=(
            "risk_parity_erc",
            "equal",
            "inverse_volatility",
            "equal",
        ),
    )
    second = ParameterSearchSpace(
        lookback_months=(6, 12),
        top_k=(1, 2),
        absolute_thresholds=(0.05, 0.0),
        allocation_methods=("inverse_volatility", "risk_parity_erc", "equal"),
    )

    assert first.lookback_months == (6, 12)
    assert first.top_k == (1, 2)
    assert first.absolute_thresholds == (0.0, 0.05)
    assert first.allocation_methods == (
        "equal",
        "inverse_volatility",
        "risk_parity_erc",
    )
    assert first.candidate_count == 24
    assert first.search_space_hash == second.search_space_hash
    assert first.export_payload() == second.export_payload()


def test_candidate_enumeration_is_canonical_and_hash_stable() -> None:
    search = ParameterSearchSpace(
        lookback_months=(12, 6),
        top_k=(2, 1),
        absolute_thresholds=(0.0,),
        allocation_methods=("risk_parity_erc", "equal"),
    )
    candidates = enumerate_parameter_candidates(search, risky_symbol_count=3)

    tuples = [
        (
            item.lookback_months,
            item.top_k,
            item.absolute_threshold,
            item.allocation_method,
        )
        for item in candidates
    ]
    assert tuples == [
        (6, 1, 0.0, "equal"),
        (6, 1, 0.0, "risk_parity_erc"),
        (6, 2, 0.0, "equal"),
        (6, 2, 0.0, "risk_parity_erc"),
        (12, 1, 0.0, "equal"),
        (12, 1, 0.0, "risk_parity_erc"),
        (12, 2, 0.0, "equal"),
        (12, 2, 0.0, "risk_parity_erc"),
    ]
    assert len({item.parameter_hash for item in candidates}) == len(candidates)
    assert candidates[0].export_payload()["parameterHash"] == candidates[0].parameter_hash


def test_top_k_is_checked_against_fixed_risky_universe() -> None:
    search = ParameterSearchSpace(
        lookback_months=(12,),
        top_k=(1, 4),
        absolute_thresholds=(0.0,),
        allocation_methods=("equal",),
    )
    with pytest.raises(ValueError, match="fixed risky universe size"):
        enumerate_parameter_candidates(search, risky_symbol_count=3)


def test_inner_folds_are_chronological_and_never_touch_outer_oos() -> None:
    schedule = build_inner_fold_schedule(
        outer_period=_outer_period(),
        validation=InnerValidationSpec(
            fold_count=3,
            evaluation_months=1,
            step_months=1,
        ),
        maximum_lookback_months=12,
    )

    assert [period.period_id for period in schedule.periods] == [
        "outer-2025-12:inner:01",
        "outer-2025-12:inner:02",
        "outer-2025-12:inner:03",
    ]
    assert [period.evaluation_end for period in schedule.periods] == [
        date(2025, 10, 31),
        date(2025, 11, 30),
        date(2025, 12, 31),
    ]
    assert schedule.periods[-1].evaluation_start == date(2025, 12, 1)
    assert all(
        period.training_end == period.decision_date for period in schedule.periods
    )
    assert all(
        period.evaluation_start > period.decision_date for period in schedule.periods
    )
    assert all(
        period.evaluation_end <= _outer_period().training_end
        for period in schedule.periods
    )
    assert all(
        period.evaluation_end < _outer_period().evaluation_start
        for period in schedule.periods
    )
    exported = schedule.export_payload()
    assert exported["calendarPolicy"] == PARAMETER_OPTIMIZATION_INNER_FOLD_POLICY
    assert exported["innerFoldScheduleHash"] == schedule.schedule_hash


def test_partial_outer_month_is_reserved_for_full_training_refit() -> None:
    outer = WalkForwardPeriod(
        period_id="outer-mid-month",
        training_start=date(2023, 1, 1),
        training_end=date(2025, 12, 15),
        decision_date=date(2025, 12, 15),
        evaluation_start=date(2025, 12, 16),
        evaluation_end=date(2026, 1, 15),
    )

    schedule = build_inner_fold_schedule(
        outer_period=outer,
        validation=InnerValidationSpec(fold_count=2),
        maximum_lookback_months=12,
    )

    assert [period.evaluation_start for period in schedule.periods] == [
        date(2025, 10, 1),
        date(2025, 11, 1),
    ]
    assert [period.evaluation_end for period in schedule.periods] == [
        date(2025, 10, 31),
        date(2025, 11, 30),
    ]
    assert schedule.periods[-1].evaluation_end < outer.training_end
    assert schedule.periods[-1].evaluation_end < outer.evaluation_start


def test_inner_fold_schedule_fails_when_lookback_does_not_fit() -> None:
    outer = WalkForwardPeriod(
        period_id="short",
        training_start=date(2025, 1, 1),
        training_end=date(2025, 12, 31),
        decision_date=date(2025, 12, 31),
        evaluation_start=date(2026, 1, 1),
        evaluation_end=date(2026, 1, 31),
    )
    with pytest.raises(ValueError, match="cannot support"):
        build_inner_fold_schedule(
            outer_period=outer,
            validation=InnerValidationSpec(fold_count=3),
            maximum_lookback_months=12,
        )


def test_overlapping_inner_oos_policy_is_rejected() -> None:
    with pytest.raises(ValueError, match="do not overlap"):
        InnerValidationSpec(fold_count=3, evaluation_months=2, step_months=1)


def test_budget_preflight_counts_all_outer_candidate_fold_work() -> None:
    search = ParameterSearchSpace(
        lookback_months=(6, 12),
        top_k=(1, 2),
        absolute_thresholds=(0.0,),
        allocation_methods=("equal", "inverse_volatility"),
    )
    validation = InnerValidationSpec(fold_count=4)
    budget = TuningBudget(
        max_parameter_candidates=8,
        max_inner_folds=4,
        max_tuning_evaluations=96,
    )

    plan = build_parameter_search_plan(
        search_space=search,
        inner_validation=validation,
        risky_symbol_count=3,
        outer_period_count=3,
        budget=budget,
    )

    assert search.candidate_count == 8
    assert plan.planned_tuning_evaluations == 96
    assert plan.export_payload()["planHash"] == plan.plan_hash


def test_budget_fails_before_candidate_materialization_scale_expands() -> None:
    search = ParameterSearchSpace(
        lookback_months=(3, 6, 9, 12),
        top_k=(1, 2, 3),
        absolute_thresholds=(-0.05, 0.0, 0.05),
        allocation_methods=("equal", "inverse_volatility", "risk_parity_erc"),
    )
    with pytest.raises(ValueError, match="candidates, exceeding budget"):
        build_parameter_search_plan(
            search_space=search,
            inner_validation=InnerValidationSpec(fold_count=4),
            risky_symbol_count=3,
            outer_period_count=1,
            budget=TuningBudget(
                max_parameter_candidates=100,
                max_inner_folds=6,
                max_tuning_evaluations=1000,
            ),
        )
