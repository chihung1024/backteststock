from __future__ import annotations

from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

import apps.api.app.quant.clustering as clustering_module
import apps.api.app.refinery.phase5_service as phase5_service_module
from apps.api.app.quant.clustering import (
    bootstrap_cluster_stability,
    bootstrap_input_fingerprint,
    prepare_bootstrap_sample,
)
from apps.api.app.refinery.phase5_service import Phase5RefineryService, _BaseRefineryService


def _weekly_fixture(rows: int = 180) -> pd.DataFrame:
    rng = np.random.default_rng(20260811)
    factor_one = rng.normal(0.001, 0.02, size=rows)
    factor_two = rng.normal(0.0005, 0.018, size=rows)
    return pd.DataFrame(
        {
            "AAA": factor_one + rng.normal(0.0, 0.003, size=rows),
            "BBB": 0.9 * factor_one + rng.normal(0.0, 0.004, size=rows),
            "CCC": factor_two + rng.normal(0.0, 0.004, size=rows),
        },
        index=pd.date_range("2022-01-07", periods=rows, freq="W-FRI"),
    )


def _bootstrap(frame: pd.DataFrame, *, window: int = 156, **kwargs: object):
    fingerprint = bootstrap_input_fingerprint(frame, window=window)
    return bootstrap_cluster_stability(
        frame,
        input_fingerprint=fingerprint,
        window=window,
        replicates=int(kwargs.pop("replicates", 20)),
        min_observations=52,
        **kwargs,
    )


def test_effective_sample_is_canonical_and_request_order_invariant() -> None:
    weekly = _weekly_fixture()
    permuted = weekly[["CCC", "AAA", "BBB"]]

    prepared = prepare_bootstrap_sample(permuted, window=156)
    assert list(prepared.columns) == ["AAA", "BBB", "CCC"]
    assert bootstrap_input_fingerprint(weekly, window=156) == (
        bootstrap_input_fingerprint(permuted, window=156)
    )

    original_result = _bootstrap(weekly)
    permuted_result = _bootstrap(permuted)
    assert original_result.seed == permuted_result.seed
    assert original_result.pair_probabilities == permuted_result.pair_probabilities


def test_inside_sample_value_or_date_change_changes_effective_fingerprint() -> None:
    weekly = _weekly_fixture()
    original = bootstrap_input_fingerprint(weekly, window=156)

    changed_value = weekly.copy()
    changed_value.iloc[-1, 0] += 0.01
    assert bootstrap_input_fingerprint(changed_value, window=156) != original

    changed_date = weekly.copy()
    changed_index = changed_date.index.to_list()
    changed_index[-1] = changed_index[-1] + pd.Timedelta(days=1)
    changed_date.index = pd.DatetimeIndex(changed_index)
    assert bootstrap_input_fingerprint(changed_date, window=156) != original


def test_rows_older_than_effective_window_do_not_change_fingerprint_seed_or_output() -> None:
    weekly = _weekly_fixture(rows=180)
    changed = weekly.copy()
    changed.iloc[0, 0] += 10.0

    original_fingerprint = bootstrap_input_fingerprint(weekly, window=156)
    changed_fingerprint = bootstrap_input_fingerprint(changed, window=156)
    assert original_fingerprint == changed_fingerprint

    original = bootstrap_cluster_stability(
        weekly,
        input_fingerprint=original_fingerprint,
        window=156,
        replicates=20,
        min_observations=52,
    )
    modified = bootstrap_cluster_stability(
        changed,
        input_fingerprint=changed_fingerprint,
        window=156,
        replicates=20,
        min_observations=52,
    )
    assert original.seed == modified.seed
    assert original.pair_probabilities == modified.pair_probabilities


def test_values_on_complete_case_excluded_row_do_not_change_effective_fingerprint() -> None:
    first = _weekly_fixture()
    second = first.copy()
    excluded_position = len(first) - 10
    first.iloc[excluded_position, 1] = np.nan
    second.iloc[excluded_position, 1] = np.nan
    second.iloc[excluded_position, 0] += 999.0

    first_sample = prepare_bootstrap_sample(first, window=156)
    second_sample = prepare_bootstrap_sample(second, window=156)
    pd.testing.assert_frame_equal(first_sample, second_sample)
    assert bootstrap_input_fingerprint(first, window=156) == (
        bootstrap_input_fingerprint(second, window=156)
    )


def test_bootstrap_rejects_fingerprint_that_does_not_match_effective_sample() -> None:
    weekly = _weekly_fixture()
    with pytest.raises(ValueError, match="must match the exact effective bootstrap sample"):
        bootstrap_cluster_stability(
            weekly,
            input_fingerprint="not-the-effective-sample",
            replicates=5,
            min_observations=52,
        )


def test_methodology_parameters_and_contract_version_are_seed_material(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    weekly = _weekly_fixture(rows=100)
    fingerprint = bootstrap_input_fingerprint(weekly, window=156)

    baseline = bootstrap_cluster_stability(
        weekly,
        input_fingerprint=fingerprint,
        window=156,
        replicates=5,
        block_weeks=4,
        min_observations=52,
        cut_distance=0.50,
    )
    changed_replicates = bootstrap_cluster_stability(
        weekly,
        input_fingerprint=fingerprint,
        window=156,
        replicates=6,
        block_weeks=4,
        min_observations=52,
        cut_distance=0.50,
    )
    changed_block = bootstrap_cluster_stability(
        weekly,
        input_fingerprint=fingerprint,
        window=156,
        replicates=5,
        block_weeks=5,
        min_observations=52,
        cut_distance=0.50,
    )
    changed_cut = bootstrap_cluster_stability(
        weekly,
        input_fingerprint=fingerprint,
        window=156,
        replicates=5,
        block_weeks=4,
        min_observations=52,
        cut_distance=0.49,
    )
    # Both windows contain the same 100-row effective sample, so this isolates
    # the explicit window policy in seed material from the sample fingerprint.
    changed_window = bootstrap_cluster_stability(
        weekly,
        input_fingerprint=fingerprint,
        window=100,
        replicates=5,
        block_weeks=4,
        min_observations=52,
        cut_distance=0.50,
    )

    monkeypatch.setattr(
        clustering_module,
        "REFINERY_CLUSTERING_CONTRACT_VERSION",
        "refinery-clustering-test-contract-change",
    )
    changed_contract = bootstrap_cluster_stability(
        weekly,
        input_fingerprint=fingerprint,
        window=156,
        replicates=5,
        block_weeks=4,
        min_observations=52,
        cut_distance=0.50,
    )

    assert len(
        {
            baseline.seed,
            changed_replicates.seed,
            changed_block.seed,
            changed_cut.seed,
            changed_window.seed,
            changed_contract.seed,
        }
    ) == 6


def test_phase5_service_keeps_research_dataset_identity_separate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    weekly = _weekly_fixture()
    candidate_dataset = SimpleNamespace(dataset_hash="research-dataset-hash-stays-intact")
    prepared = SimpleNamespace(
        weekly_returns=weekly,
        candidate_dataset=candidate_dataset,
    )
    captured: dict[str, object] = {}

    monkeypatch.setattr(
        _BaseRefineryService,
        "_analysis_payload",
        lambda self, value: {
            "correlations": {
                "structural_weekly": {
                    "status": "unavailable_test_fixture",
                    "input_observations": 0,
                    "observations": 0,
                    "dropped_observations": 0,
                    "condition": "unavailable",
                    "threshold": None,
                    "window": None,
                    "matrix": None,
                }
            }
        },
    )

    def fake_relationships(**kwargs: object) -> dict[str, object]:
        captured.update(kwargs)
        return {
            "clustering": {
                "bootstrap_input_fingerprint_sha256": kwargs[
                    "bootstrap_input_fingerprint"
                ]
            }
        }

    monkeypatch.setattr(
        phase5_service_module,
        "build_phase5_relationships",
        fake_relationships,
    )
    service = Phase5RefineryService(factor_provider=object())  # type: ignore[arg-type]
    payload = service._analysis_payload(prepared)

    assert captured["candidate_dataset"] is candidate_dataset
    assert candidate_dataset.dataset_hash == "research-dataset-hash-stays-intact"
    expected_fingerprint = bootstrap_input_fingerprint(weekly, window=156)
    assert captured["bootstrap_input_fingerprint"] == expected_fingerprint
    assert payload["clustering"]["bootstrap_input_fingerprint_sha256"] == (
        expected_fingerprint
    )
    assert expected_fingerprint != candidate_dataset.dataset_hash
