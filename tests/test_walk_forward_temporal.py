from dataclasses import FrozenInstanceError
from datetime import date

import pytest

from apps.api.app.research.walk_forward import (
    DECISION_TIMING_AFTER_CLOSE,
    ResolvedPITUniverse,
    WalkForwardPeriod,
    create_decision_snapshot,
    validate_period_schedule,
)


def _period(**overrides):
    values = {
        "period_id": "2025-Q1",
        "training_start": date(2022, 1, 1),
        "training_end": date(2024, 12, 31),
        "decision_date": date(2024, 12, 31),
        "evaluation_start": date(2025, 1, 1),
        "evaluation_end": date(2025, 3, 31),
    }
    values.update(overrides)
    return WalkForwardPeriod(**values)


def _universe(**overrides):
    values = {
        "universe_id": "sp500",
        "requested_as_of": date(2024, 12, 31),
        "source_as_of": date(2024, 12, 30),
        "evidence_available_as_of": date(2024, 12, 30),
        "version": "sp500-2024-12-30",
        "checksum": "abc123",
        "members": ("AAPL", "MSFT", "NVDA"),
        "membership_policy": "latest-causal-v1",
        "membership_authoritative": True,
        "source_label": "official",
        "source_is_proxy": False,
    }
    values.update(overrides)
    return ResolvedPITUniverse(**values)


def _snapshot(**overrides):
    values = {
        "period": _period(),
        "pit_universe": _universe(),
        "training_dataset_hash": "dataset-123",
        "training_effective_start": date(2022, 1, 3),
        "training_effective_end": date(2024, 12, 31),
        "selector_contract_version": "selector-test-v1",
        "selector_rule": "top-two",
        "selector_parameters": {"lookback": 252, "nested": {"enabled": True}},
        "eligible_candidates": ("AAPL", "MSFT", "NVDA"),
        "selected_constituents": ("AAPL", "MSFT"),
        "weights": (0.5, 0.5),
    }
    values.update(overrides)
    return create_decision_snapshot(**values)


def test_period_enforces_train_decision_oos_firewall():
    period = _period()
    assert period.training_end <= period.decision_date < period.evaluation_start
    assert period.decision_timing == DECISION_TIMING_AFTER_CLOSE

    with pytest.raises(ValueError, match="training data"):
        _period(training_end=date(2025, 1, 1))
    with pytest.raises(ValueError, match="strictly after"):
        _period(evaluation_start=date(2024, 12, 31))


def test_pit_evidence_must_be_causally_available_by_decision():
    with pytest.raises(ValueError, match="source_as_of"):
        _universe(source_as_of=date(2025, 1, 1))
    with pytest.raises(ValueError, match="predate"):
        _universe(evidence_available_as_of=date(2024, 12, 29))
    with pytest.raises(ValueError, match="evidence"):
        _universe(evidence_available_as_of=date(2025, 1, 1))
    with pytest.raises(ValueError, match="proxy"):
        _universe(membership_authoritative=True, source_is_proxy=True)


def test_pit_membership_and_decision_symbols_are_not_silently_rewritten():
    with pytest.raises(ValueError, match="canonical symbols"):
        _universe(members=("aapl", "MSFT", "NVDA"))
    with pytest.raises(ValueError, match="canonical symbols"):
        _snapshot(eligible_candidates=("AAPL", "msft", "NVDA"))


def test_decision_rejects_training_data_after_training_boundary():
    with pytest.raises(ValueError, match="training_end"):
        _snapshot(training_effective_end=date(2025, 1, 1))


def test_decision_requires_pit_snapshot_for_exact_decision_date():
    universe = _universe(requested_as_of=date(2024, 12, 30))
    with pytest.raises(ValueError, match="decision_date"):
        _snapshot(pit_universe=universe)


def test_decision_identity_is_deterministic_and_deeply_frozen():
    parameters = {"lookback": 252, "nested": {"enabled": True, "values": [1, 2]}}
    first = _snapshot(selector_parameters=parameters)
    second = _snapshot(
        selector_parameters={
            "nested": {"values": [1, 2], "enabled": True},
            "lookback": 252,
        }
    )
    assert first.decision_hash == second.decision_hash
    assert first.export_payload() == second.export_payload()

    parameters["lookback"] = 1
    parameters["nested"]["values"].append(999)
    assert first.export_payload()["selector"]["parameters"]["lookback"] == 252
    assert first.export_payload()["selector"]["parameters"]["nested"]["values"] == [1, 2]

    with pytest.raises(FrozenInstanceError):
        first.training_dataset_hash = "mutated"


def test_selector_parameter_container_types_are_unambiguous_and_json_safe():
    parameters = {
        "pair_list": [["a", 1], ["b", 2]],
        "nested": {"pairs": [["x", True], ["y", False]]},
        "negative_zero": -0.0,
    }
    snapshot = _snapshot(selector_parameters=parameters)
    exported = snapshot.export_payload()["selector"]["parameters"]
    assert exported["pair_list"] == [["a", 1], ["b", 2]]
    assert exported["nested"]["pairs"] == [["x", True], ["y", False]]
    assert exported["negative_zero"] == 0.0

    with pytest.raises(TypeError, match="mapping keys must be strings"):
        _snapshot(selector_parameters={1: "ambiguous"})


def test_selector_parameter_rejects_nonfinite_or_nondeterministic_values():
    with pytest.raises(ValueError, match="non-finite"):
        _snapshot(selector_parameters={"bad": float("nan")})
    with pytest.raises(TypeError, match="unsupported"):
        _snapshot(selector_parameters={"bad": {"unordered"}})


def test_decision_hash_changes_for_material_training_or_selection_changes():
    baseline = _snapshot()
    changed_dataset = _snapshot(training_dataset_hash="dataset-456")
    changed_selection = _snapshot(
        selected_constituents=("AAPL", "NVDA"),
        weights=(0.5, 0.5),
    )
    assert baseline.decision_hash != changed_dataset.decision_hash
    assert baseline.decision_hash != changed_selection.decision_hash


def test_selected_and_eligible_membership_fail_closed():
    with pytest.raises(ValueError, match="subset of eligible"):
        _snapshot(selected_constituents=("AAPL", "TSLA"), weights=(0.5, 0.5))
    with pytest.raises(ValueError, match="exact PIT membership"):
        _snapshot(
            eligible_candidates=("AAPL", "TSLA"),
            selected_constituents=("AAPL",),
            weights=(1.0,),
        )


def test_weights_must_match_selection_and_sum_to_one():
    with pytest.raises(ValueError, match="weight count"):
        _snapshot(weights=(1.0,))
    with pytest.raises(ValueError, match="summing to one"):
        _snapshot(weights=(0.6, 0.5))


def test_schedule_rejects_overlapping_oos_windows_and_rewound_decisions():
    first = _period()
    second = _period(
        period_id="2025-Q2",
        training_start=date(2022, 4, 1),
        training_end=date(2025, 3, 31),
        decision_date=date(2025, 3, 31),
        evaluation_start=date(2025, 4, 1),
        evaluation_end=date(2025, 6, 30),
    )
    assert validate_period_schedule((first, second)) == (first, second)

    overlap = _period(
        period_id="overlap",
        training_start=date(2022, 2, 1),
        training_end=date(2025, 2, 28),
        decision_date=date(2025, 2, 28),
        evaluation_start=date(2025, 3, 1),
        evaluation_end=date(2025, 4, 30),
    )
    with pytest.raises(ValueError, match="must not overlap"):
        validate_period_schedule((first, overlap))

    early_next_decision = _period(
        period_id="early-next-decision",
        training_start=date(2022, 3, 1),
        training_end=date(2025, 3, 15),
        decision_date=date(2025, 3, 15),
        evaluation_start=date(2025, 4, 1),
        evaluation_end=date(2025, 6, 30),
    )
    with pytest.raises(ValueError, match="prior evaluation end"):
        validate_period_schedule((first, early_next_decision))
