from __future__ import annotations

import math

import numpy as np
import pandas as pd
import pytest
from scipy.cluster.hierarchy import linkage as scipy_linkage
from scipy.spatial.distance import squareform

from apps.api.app.quant.clustering import (
    PRIMARY_CLUSTER_LINKAGE,
    PRIMARY_FLAT_CUT_DISTANCE,
    SENSITIVITY_CLUSTER_LINKAGE,
    bootstrap_cluster_stability,
    bootstrap_input_fingerprint,
    circular_block_bootstrap_indices,
    correlation_distance_matrix,
    hierarchical_clustering,
    multi_window_cluster_stability,
)


def _correlation_fixture() -> pd.DataFrame:
    return pd.DataFrame(
        [
            [1.0, 0.90, 0.20, 0.15],
            [0.90, 1.0, 0.25, 0.10],
            [0.20, 0.25, 1.0, 0.82],
            [0.15, 0.10, 0.82, 1.0],
        ],
        index=["AAA", "BBB", "CCC", "DDD"],
        columns=["AAA", "BBB", "CCC", "DDD"],
    )


def _weekly_fixture(rows: int = 180) -> pd.DataFrame:
    rng = np.random.default_rng(20260810)
    factor_one = rng.normal(0.001, 0.025, size=rows)
    factor_two = rng.normal(0.0005, 0.022, size=rows)
    return pd.DataFrame(
        {
            "AAA": factor_one + rng.normal(0.0, 0.004, size=rows),
            "BBB": 0.92 * factor_one + rng.normal(0.0, 0.005, size=rows),
            "CCC": factor_two + rng.normal(0.0, 0.005, size=rows),
            "DDD": 0.88 * factor_two + rng.normal(0.0, 0.006, size=rows),
        },
        index=pd.date_range("2023-01-06", periods=rows, freq="W-FRI"),
    )


def test_correlation_distance_has_required_bounds_and_known_extremes() -> None:
    correlation = pd.DataFrame(
        [[1.0, 1.0, -1.0], [1.0, 1.0, -1.0], [-1.0, -1.0, 1.0]],
        index=["AAA", "BBB", "CCC"],
        columns=["AAA", "BBB", "CCC"],
    )
    distance = correlation_distance_matrix(correlation)

    assert list(distance.columns) == ["AAA", "BBB", "CCC"]
    np.testing.assert_allclose(distance.to_numpy(), distance.to_numpy().T)
    np.testing.assert_allclose(np.diag(distance), np.zeros(3))
    assert float(distance.to_numpy().min()) >= 0.0
    assert float(distance.to_numpy().max()) <= 1.0
    assert distance.loc["AAA", "BBB"] == pytest.approx(0.0)
    assert distance.loc["AAA", "CCC"] == pytest.approx(1.0)


def test_identity_correlation_has_sqrt_half_off_diagonal_distance() -> None:
    correlation = pd.DataFrame(
        np.eye(4), index=list("ABCD"), columns=list("ABCD")
    )
    distance = correlation_distance_matrix(correlation)

    expected = math.sqrt(0.5)
    for row in range(4):
        for column in range(4):
            if row != column:
                assert distance.iat[row, column] == pytest.approx(expected)


def test_average_and_complete_linkage_match_direct_scipy_reference() -> None:
    correlation = _correlation_fixture()
    distance = correlation_distance_matrix(correlation)
    condensed = squareform(distance.to_numpy(dtype=float), checks=False)

    for method in (PRIMARY_CLUSTER_LINKAGE, SENSITIVITY_CLUSTER_LINKAGE):
        expected = scipy_linkage(condensed, method=method, optimal_ordering=False)
        actual = hierarchical_clustering(correlation, method=method)
        np.testing.assert_allclose(actual.linkage_matrix, expected, rtol=0.0, atol=1e-15)


def test_hierarchy_is_invariant_to_request_order_after_canonical_labelling() -> None:
    correlation = _correlation_fixture()
    permutation = ["DDD", "BBB", "AAA", "CCC"]
    permuted = correlation.loc[permutation, permutation]

    original = hierarchical_clustering(correlation)
    reordered = hierarchical_clustering(permuted)

    assert original.symbols == reordered.symbols == ("AAA", "BBB", "CCC", "DDD")
    np.testing.assert_allclose(original.linkage_matrix, reordered.linkage_matrix)
    assert original.clusters == reordered.clusters
    assert original.cluster_by_symbol == reordered.cluster_by_symbol


def test_perfect_duplicates_cluster_together_at_primary_cut() -> None:
    correlation = pd.DataFrame(
        [[1.0, 1.0, 0.1], [1.0, 1.0, 0.1], [0.1, 0.1, 1.0]],
        index=["AAA", "BBB", "CCC"],
        columns=["AAA", "BBB", "CCC"],
    )
    result = hierarchical_clustering(
        correlation,
        method=PRIMARY_CLUSTER_LINKAGE,
        cut_distance=PRIMARY_FLAT_CUT_DISTANCE,
    )

    assert result.cluster_by_symbol["AAA"] == result.cluster_by_symbol["BBB"]
    assert result.cluster_by_symbol["AAA"] != result.cluster_by_symbol["CCC"]


def test_ward_and_materially_invalid_correlation_inputs_fail_closed() -> None:
    with pytest.raises(ValueError, match="clustering method"):
        hierarchical_clustering(_correlation_fixture(), method="ward")

    asymmetric = _correlation_fixture()
    asymmetric.loc["AAA", "BBB"] = 0.5
    with pytest.raises(ValueError, match="symmetric"):
        correlation_distance_matrix(asymmetric)

    bad_diagonal = _correlation_fixture()
    bad_diagonal.loc["AAA", "AAA"] = 0.8
    with pytest.raises(ValueError, match="diagonal"):
        correlation_distance_matrix(bad_diagonal)

    out_of_range = _correlation_fixture()
    out_of_range.loc["AAA", "BBB"] = 1.2
    out_of_range.loc["BBB", "AAA"] = 1.2
    with pytest.raises(ValueError, match="within"):
        correlation_distance_matrix(out_of_range)


def test_multi_window_stability_excludes_unavailable_windows_from_denominator() -> None:
    weekly = _weekly_fixture(rows=110)
    result = multi_window_cluster_stability(
        weekly,
        windows=(52, 104, 156),
        min_observations=52,
    )

    assert [window.status for window in result.windows] == [
        "ok",
        "ok",
        "insufficient_window",
    ]
    assert result.windows[-1].hierarchy is None
    assert result.pair_agreements
    assert all(pair.available_windows == 2 for pair in result.pair_agreements)
    assert all(pair.agreement is not None for pair in result.pair_agreements)


def test_circular_block_indices_preserve_contiguous_blocks_and_are_reusable_jointly() -> None:
    rng = np.random.default_rng(17)
    indices = circular_block_bootstrap_indices(10, block_length=4, rng=rng)

    assert indices.shape == (10,)
    assert ((indices >= 0) & (indices < 10)).all()
    for start in range(0, 8, 4):
        block = indices[start : start + 4]
        np.testing.assert_array_equal(block, (block[0] + np.arange(len(block))) % 10)

    frame = pd.DataFrame({"AAA": np.arange(10), "BBB": np.arange(10) + 1000})
    sampled = frame.iloc[indices].reset_index(drop=True)
    np.testing.assert_array_equal(
        sampled["BBB"].to_numpy() - sampled["AAA"].to_numpy(),
        np.full(10, 1000),
    )


def test_bootstrap_stability_is_deterministic_for_same_dataset_contract() -> None:
    weekly = _weekly_fixture(rows=120)
    fingerprint = bootstrap_input_fingerprint(weekly)
    first = bootstrap_cluster_stability(
        weekly,
        input_fingerprint=fingerprint,
        replicates=30,
        block_weeks=4,
        min_observations=52,
    )
    second = bootstrap_cluster_stability(
        weekly,
        input_fingerprint=fingerprint,
        replicates=30,
        block_weeks=4,
        min_observations=52,
    )

    assert first.status == second.status == "ok"
    assert first.seed == second.seed
    assert first.requested_replicates == second.requested_replicates == 30
    assert first.usable_replicates == second.usable_replicates
    assert first.unusable_replicates == second.unusable_replicates
    assert first.pair_probabilities == second.pair_probabilities
    assert first.usable_replicates + first.unusable_replicates == 30
    for pair in first.pair_probabilities:
        assert pair.probability is not None
        assert 0.0 <= pair.probability <= 1.0


def test_bootstrap_counts_degenerate_replicates_as_unusable_not_success() -> None:
    weekly = pd.DataFrame(
        {
            "AAA": np.ones(80),
            "BBB": np.linspace(-0.02, 0.02, 80),
        },
        index=pd.date_range("2024-01-05", periods=80, freq="W-FRI"),
    )
    result = bootstrap_cluster_stability(
        weekly,
        input_fingerprint=bootstrap_input_fingerprint(weekly),
        replicates=12,
        min_observations=52,
    )

    assert result.status == "degenerate_variance"
    assert result.usable_replicates == 0
    assert result.unusable_replicates == 12
    assert all(pair.probability is None for pair in result.pair_probabilities)


def test_bootstrap_effective_input_change_changes_deterministic_seed() -> None:
    first_weekly = _weekly_fixture(rows=90)
    second_weekly = first_weekly.copy()
    second_weekly.iloc[-1, 0] += 0.01
    first_fingerprint = bootstrap_input_fingerprint(first_weekly)
    second_fingerprint = bootstrap_input_fingerprint(second_weekly)

    first = bootstrap_cluster_stability(
        first_weekly,
        input_fingerprint=first_fingerprint,
        replicates=5,
        min_observations=52,
    )
    second = bootstrap_cluster_stability(
        second_weekly,
        input_fingerprint=second_fingerprint,
        replicates=5,
        min_observations=52,
    )

    assert first_fingerprint != second_fingerprint
    assert first.seed != second.seed
