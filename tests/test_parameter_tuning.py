from __future__ import annotations

import pytest

from apps.api.app.research.parameter_tuning import (
    CandidateTuningSummary,
    rank_candidate_summaries,
)


def _summary(
    parameter_hash: str,
    *,
    sortino: float | None,
    max_drawdown: float | None,
    cagr: float | None,
    transaction_costs: float | None,
    status: str = "eligible",
) -> CandidateTuningSummary:
    return CandidateTuningSummary(
        parameter_hash=parameter_hash,
        parameters={"parameter": parameter_hash},
        status=status,
        completed_fold_count=4,
        failed_fold=None if status == "eligible" else "fold-2",
        failure_reason=None if status == "eligible" else "synthetic failure",
        sortino=sortino,
        max_drawdown=max_drawdown,
        cagr=cagr,
        transaction_costs=transaction_costs,
        inner_oos_identity=(f"oos-{parameter_hash}" if status == "eligible" else None),
        decision_hashes=("d1", "d2", "d3", "d4"),
        evaluation_dataset_hashes=("e1", "e2", "e3", "e4"),
    )


def test_ranking_uses_sortino_then_drawdown_then_cagr_then_cost() -> None:
    summaries = (
        _summary("d", sortino=1.1, max_drawdown=-0.10, cagr=0.20, transaction_costs=10.0),
        _summary("c", sortino=1.1, max_drawdown=-0.10, cagr=0.20, transaction_costs=5.0),
        _summary("b", sortino=1.1, max_drawdown=-0.10, cagr=0.22, transaction_costs=20.0),
        _summary("a", sortino=1.1, max_drawdown=-0.08, cagr=0.18, transaction_costs=30.0),
        _summary("z", sortino=1.2, max_drawdown=-0.20, cagr=0.10, transaction_costs=50.0),
    )

    ranked = rank_candidate_summaries(summaries)

    assert [item.parameter_hash for item in ranked] == ["z", "a", "b", "c", "d"]


def test_parameter_hash_is_final_deterministic_tie_break() -> None:
    summaries = (
        _summary("bbb", sortino=1.0, max_drawdown=-0.1, cagr=0.2, transaction_costs=5.0),
        _summary("aaa", sortino=1.0, max_drawdown=-0.1, cagr=0.2, transaction_costs=5.0),
    )

    ranked = rank_candidate_summaries(summaries)

    assert [item.parameter_hash for item in ranked] == ["aaa", "bbb"]


def test_failed_candidates_are_not_eligible_for_ranking() -> None:
    summaries = (
        _summary(
            "failed-high",
            sortino=99.0,
            max_drawdown=-0.01,
            cagr=9.0,
            transaction_costs=0.0,
            status="failed",
        ),
        _summary("eligible", sortino=0.8, max_drawdown=-0.2, cagr=0.1, transaction_costs=4.0),
    )

    ranked = rank_candidate_summaries(summaries)

    assert [item.parameter_hash for item in ranked] == ["eligible"]


def test_unavailable_primary_metric_cannot_be_ranked_as_zero() -> None:
    summaries = (
        _summary("bad", sortino=None, max_drawdown=-0.1, cagr=0.2, transaction_costs=1.0),
    )
    with pytest.raises(ValueError, match="unavailable sortino"):
        rank_candidate_summaries(summaries)


def test_all_failed_candidates_fail_closed() -> None:
    summaries = (
        _summary(
            "failed",
            sortino=None,
            max_drawdown=None,
            cagr=None,
            transaction_costs=None,
            status="failed",
        ),
    )
    with pytest.raises(ValueError, match="no eligible candidate"):
        rank_candidate_summaries(summaries)
