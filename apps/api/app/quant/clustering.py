"""Deterministic correlation-distance clustering and stability primitives."""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from itertools import combinations
from typing import Iterable

import numpy as np
import pandas as pd
from scipy.cluster.hierarchy import fcluster, linkage as scipy_linkage
from scipy.spatial.distance import squareform

REFINERY_CLUSTERING_CONTRACT_VERSION = "refinery-clustering-twd-2026-08-10.1"
PRIMARY_CLUSTER_LINKAGE = "average"
SENSITIVITY_CLUSTER_LINKAGE = "complete"
PRIMARY_FLAT_CUT_DISTANCE = 0.50
BOOTSTRAP_REPLICATES = 200
BOOTSTRAP_BLOCK_WEEKS = 4
STABILITY_WINDOWS_WEEKS = (52, 104, 156)
PRIMARY_STRUCTURAL_WINDOW_WEEKS = 156
_ALLOWED_LINKAGES = frozenset({PRIMARY_CLUSTER_LINKAGE, SENSITIVITY_CLUSTER_LINKAGE})
_CORRELATION_TOLERANCE = 1e-10
_VARIANCE_EPSILON = 1e-15


@dataclass(frozen=True, slots=True)
class ClusterGroup:
    cluster_id: str
    members: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class LinkageMerge:
    node_id: str
    left: str
    right: str
    distance: float
    count: int


@dataclass(frozen=True, slots=True)
class ClusterHierarchy:
    method: str
    cut_distance: float
    symbols: tuple[str, ...]
    linkage_matrix: np.ndarray
    merges: tuple[LinkageMerge, ...]
    clusters: tuple[ClusterGroup, ...]
    cluster_by_symbol: dict[str, str]


@dataclass(frozen=True, slots=True)
class WindowClusterResult:
    window_weeks: int
    status: str
    input_observations: int
    observations: int
    hierarchy: ClusterHierarchy | None


@dataclass(frozen=True, slots=True)
class PairWindowAgreement:
    symbol_a: str
    symbol_b: str
    available_windows: int
    same_cluster_windows: int
    agreement: float | None


@dataclass(frozen=True, slots=True)
class MultiWindowClusterStability:
    symbols: tuple[str, ...]
    windows: tuple[WindowClusterResult, ...]
    pair_agreements: tuple[PairWindowAgreement, ...]


@dataclass(frozen=True, slots=True)
class PairBootstrapProbability:
    symbol_a: str
    symbol_b: str
    probability: float | None


@dataclass(frozen=True, slots=True)
class BootstrapClusterStability:
    status: str
    symbols: tuple[str, ...]
    requested_replicates: int
    usable_replicates: int
    unusable_replicates: int
    block_weeks: int
    observations: int
    seed: int
    pair_probabilities: tuple[PairBootstrapProbability, ...]


def correlation_distance_matrix(correlation: pd.DataFrame) -> pd.DataFrame:
    """Convert a labelled Pearson correlation matrix to canonical distance."""

    matrix = _canonical_correlation(correlation)
    values = matrix.to_numpy(dtype=float, copy=True)
    values = np.clip(values, -1.0, 1.0)
    distances = np.sqrt(np.maximum((1.0 - values) / 2.0, 0.0))
    np.fill_diagonal(distances, 0.0)
    return pd.DataFrame(distances, index=matrix.index, columns=matrix.columns)


def hierarchical_clustering(
    correlation: pd.DataFrame,
    *,
    method: str = PRIMARY_CLUSTER_LINKAGE,
    cut_distance: float = PRIMARY_FLAT_CUT_DISTANCE,
) -> ClusterHierarchy:
    """Build a deterministic labelled hierarchy from a correlation matrix."""

    if method not in _ALLOWED_LINKAGES:
        raise ValueError(
            "clustering method must be one of: " + ", ".join(sorted(_ALLOWED_LINKAGES))
        )
    if not math.isfinite(cut_distance) or not 0.0 <= cut_distance <= 1.0:
        raise ValueError("cut_distance must be finite and between 0 and 1")

    distance = correlation_distance_matrix(correlation)
    symbols = tuple(str(symbol) for symbol in distance.columns)
    condensed = squareform(distance.to_numpy(dtype=float), checks=False)
    linkage_matrix = scipy_linkage(condensed, method=method, optimal_ordering=False)
    raw_labels = fcluster(linkage_matrix, t=cut_distance, criterion="distance")
    clusters, cluster_by_symbol = _canonical_clusters(symbols, raw_labels)
    merges = _labelled_merges(symbols, linkage_matrix)
    return ClusterHierarchy(
        method=method,
        cut_distance=float(cut_distance),
        symbols=symbols,
        linkage_matrix=np.asarray(linkage_matrix, dtype=float),
        merges=merges,
        clusters=clusters,
        cluster_by_symbol=cluster_by_symbol,
    )


def multi_window_cluster_stability(
    weekly_returns: pd.DataFrame,
    *,
    windows: Iterable[int] = STABILITY_WINDOWS_WEEKS,
    min_observations: int = 52,
    cut_distance: float = PRIMARY_FLAT_CUT_DISTANCE,
) -> MultiWindowClusterStability:
    """Measure average-linkage flat-cluster agreement across trailing windows."""

    frame = _numeric_return_frame(weekly_returns)
    minimum = _minimum_observations(min_observations)
    requested_windows = tuple(int(window) for window in windows)
    if not requested_windows or any(window < 2 for window in requested_windows):
        raise ValueError("stability windows must contain integers >= 2")
    if len(set(requested_windows)) != len(requested_windows):
        raise ValueError("stability windows must be unique")

    results: list[WindowClusterResult] = []
    for window in requested_windows:
        input_observations = min(len(frame), window)
        sample = frame.tail(window).replace([np.inf, -np.inf], np.nan).dropna(how="any")
        if len(frame) < window:
            results.append(
                WindowClusterResult(
                    window_weeks=window,
                    status="insufficient_window",
                    input_observations=input_observations,
                    observations=len(sample),
                    hierarchy=None,
                )
            )
            continue
        if len(sample) < minimum:
            results.append(
                WindowClusterResult(
                    window_weeks=window,
                    status="insufficient_observations",
                    input_observations=input_observations,
                    observations=len(sample),
                    hierarchy=None,
                )
            )
            continue
        if _has_degenerate_variance(sample):
            results.append(
                WindowClusterResult(
                    window_weeks=window,
                    status="degenerate_variance",
                    input_observations=input_observations,
                    observations=len(sample),
                    hierarchy=None,
                )
            )
            continue
        hierarchy = hierarchical_clustering(
            _correlation_from_clean_frame(sample),
            method=PRIMARY_CLUSTER_LINKAGE,
            cut_distance=cut_distance,
        )
        results.append(
            WindowClusterResult(
                window_weeks=window,
                status="ok",
                input_observations=input_observations,
                observations=len(sample),
                hierarchy=hierarchy,
            )
        )

    symbols = tuple(str(column) for column in frame.columns)
    available = [
        result for result in results if result.status == "ok" and result.hierarchy is not None
    ]
    agreements: list[PairWindowAgreement] = []
    for symbol_a, symbol_b in combinations(symbols, 2):
        same = sum(
            1
            for result in available
            if result.hierarchy is not None
            and result.hierarchy.cluster_by_symbol[symbol_a]
            == result.hierarchy.cluster_by_symbol[symbol_b]
        )
        agreements.append(
            PairWindowAgreement(
                symbol_a=symbol_a,
                symbol_b=symbol_b,
                available_windows=len(available),
                same_cluster_windows=same,
                agreement=(float(same / len(available)) if len(available) >= 2 else None),
            )
        )
    return MultiWindowClusterStability(
        symbols=symbols,
        windows=tuple(results),
        pair_agreements=tuple(agreements),
    )


def bootstrap_cluster_stability(
    weekly_returns: pd.DataFrame,
    *,
    dataset_hash: str,
    replicates: int = BOOTSTRAP_REPLICATES,
    block_weeks: int = BOOTSTRAP_BLOCK_WEEKS,
    min_observations: int = 52,
    window: int = PRIMARY_STRUCTURAL_WINDOW_WEEKS,
    cut_distance: float = PRIMARY_FLAT_CUT_DISTANCE,
) -> BootstrapClusterStability:
    """Return deterministic moving-block bootstrap co-cluster probabilities."""

    if not isinstance(dataset_hash, str) or not dataset_hash.strip():
        raise ValueError("dataset_hash must be a non-empty string")
    if not isinstance(replicates, int) or replicates < 1:
        raise ValueError("replicates must be an integer >= 1")
    if not isinstance(block_weeks, int) or block_weeks < 1:
        raise ValueError("block_weeks must be an integer >= 1")
    if not isinstance(window, int) or window < 2:
        raise ValueError("window must be an integer >= 2")

    minimum = _minimum_observations(min_observations)
    frame = _numeric_return_frame(weekly_returns).tail(window)
    clean = frame.replace([np.inf, -np.inf], np.nan).dropna(how="any")
    symbols = tuple(str(column) for column in clean.columns)
    seed = _bootstrap_seed(
        dataset_hash=dataset_hash,
        replicates=replicates,
        block_weeks=block_weeks,
        cut_distance=cut_distance,
    )
    pairs = tuple(combinations(symbols, 2))
    if len(clean) < minimum:
        return _empty_bootstrap_result(
            status="insufficient_observations",
            symbols=symbols,
            pairs=pairs,
            replicates=replicates,
            block_weeks=block_weeks,
            observations=len(clean),
            seed=seed,
        )
    if _has_degenerate_variance(clean):
        return _empty_bootstrap_result(
            status="degenerate_variance",
            symbols=symbols,
            pairs=pairs,
            replicates=replicates,
            block_weeks=block_weeks,
            observations=len(clean),
            seed=seed,
        )

    rng = np.random.default_rng(seed)
    counts = {pair: 0 for pair in pairs}
    usable = 0
    for _ in range(replicates):
        indices = circular_block_bootstrap_indices(
            len(clean), block_length=block_weeks, rng=rng
        )
        sampled = clean.iloc[indices].reset_index(drop=True)
        if _has_degenerate_variance(sampled):
            continue
        try:
            hierarchy = hierarchical_clustering(
                _correlation_from_clean_frame(sampled),
                method=PRIMARY_CLUSTER_LINKAGE,
                cut_distance=cut_distance,
            )
        except ValueError:
            continue
        usable += 1
        for pair in pairs:
            if hierarchy.cluster_by_symbol[pair[0]] == hierarchy.cluster_by_symbol[pair[1]]:
                counts[pair] += 1

    probabilities = tuple(
        PairBootstrapProbability(
            symbol_a=symbol_a,
            symbol_b=symbol_b,
            probability=(float(counts[(symbol_a, symbol_b)] / usable) if usable else None),
        )
        for symbol_a, symbol_b in pairs
    )
    return BootstrapClusterStability(
        status="ok" if usable else "no_usable_replicates",
        symbols=symbols,
        requested_replicates=replicates,
        usable_replicates=usable,
        unusable_replicates=replicates - usable,
        block_weeks=block_weeks,
        observations=len(clean),
        seed=seed,
        pair_probabilities=probabilities,
    )


def circular_block_bootstrap_indices(
    observations: int,
    *,
    block_length: int,
    rng: np.random.Generator,
) -> np.ndarray:
    """Draw circular moving-block row positions for one joint multivariate sample."""

    if not isinstance(observations, int) or observations < 1:
        raise ValueError("observations must be an integer >= 1")
    if not isinstance(block_length, int) or block_length < 1:
        raise ValueError("block_length must be an integer >= 1")
    if not isinstance(rng, np.random.Generator):
        raise TypeError("rng must be a numpy.random.Generator")
    blocks = math.ceil(observations / block_length)
    starts = rng.integers(0, observations, size=blocks)
    offsets = np.arange(block_length, dtype=int)
    positions = np.concatenate(
        [(int(start) + offsets) % observations for start in starts]
    )
    return positions[:observations].astype(int, copy=False)


def _canonical_correlation(correlation: pd.DataFrame) -> pd.DataFrame:
    if not isinstance(correlation, pd.DataFrame):
        raise TypeError("correlation must be a pandas DataFrame")
    if correlation.shape[0] != correlation.shape[1] or correlation.shape[0] < 2:
        raise ValueError("correlation must be a square matrix with at least two assets")
    if not correlation.index.is_unique or not correlation.columns.is_unique:
        raise ValueError("correlation labels must be unique")
    index_labels = [str(label) for label in correlation.index]
    column_labels = [str(label) for label in correlation.columns]
    if set(index_labels) != set(column_labels):
        raise ValueError("correlation index and columns must contain the same labels")
    if len(set(index_labels)) != len(index_labels):
        raise ValueError("correlation labels must remain unique after string normalization")

    normalized = correlation.copy()
    normalized.index = index_labels
    normalized.columns = column_labels
    symbols = sorted(index_labels)
    matrix = normalized.loc[symbols, symbols].apply(pd.to_numeric, errors="coerce").astype(float)
    values = matrix.to_numpy(dtype=float)
    if not np.isfinite(values).all():
        raise ValueError("correlation matrix must be finite")
    if np.max(np.abs(values - values.T)) > _CORRELATION_TOLERANCE:
        raise ValueError("correlation matrix must be symmetric")
    diagonal = np.diag(values)
    if np.max(np.abs(diagonal - 1.0)) > _CORRELATION_TOLERANCE:
        raise ValueError("correlation matrix diagonal must equal one")
    if (
        values.min() < -1.0 - _CORRELATION_TOLERANCE
        or values.max() > 1.0 + _CORRELATION_TOLERANCE
    ):
        raise ValueError("correlation entries must be within [-1, 1]")
    return matrix


def _numeric_return_frame(returns: pd.DataFrame) -> pd.DataFrame:
    if not isinstance(returns, pd.DataFrame):
        raise TypeError("returns must be a pandas DataFrame")
    if returns.shape[1] < 2:
        raise ValueError("returns must contain at least two asset columns")
    if not returns.columns.is_unique:
        raise ValueError("return columns must be unique")
    labels = [str(column) for column in returns.columns]
    if len(set(labels)) != len(labels):
        raise ValueError("return columns must remain unique after string normalization")
    frame = returns.copy()
    frame.columns = labels
    frame = frame.reindex(columns=sorted(labels))
    return frame.apply(pd.to_numeric, errors="coerce").astype(float)


def _correlation_from_clean_frame(frame: pd.DataFrame) -> pd.DataFrame:
    values = np.corrcoef(frame.to_numpy(dtype=float), rowvar=False)
    return pd.DataFrame(values, index=frame.columns, columns=frame.columns)


def _has_degenerate_variance(frame: pd.DataFrame) -> bool:
    standard_deviation = frame.std(ddof=1)
    return bool(
        standard_deviation.isna().any()
        or (standard_deviation <= _VARIANCE_EPSILON).any()
    )


def _canonical_clusters(
    symbols: tuple[str, ...], raw_labels: np.ndarray
) -> tuple[tuple[ClusterGroup, ...], dict[str, str]]:
    members_by_raw: dict[int, list[str]] = {}
    for symbol, label in zip(symbols, raw_labels, strict=True):
        members_by_raw.setdefault(int(label), []).append(symbol)
    member_sets = sorted(tuple(sorted(members)) for members in members_by_raw.values())
    clusters = tuple(
        ClusterGroup(cluster_id=f"cluster-{position:02d}", members=members)
        for position, members in enumerate(member_sets, start=1)
    )
    cluster_by_symbol = {
        symbol: cluster.cluster_id
        for cluster in clusters
        for symbol in cluster.members
    }
    return clusters, cluster_by_symbol


def _labelled_merges(
    symbols: tuple[str, ...], linkage_matrix: np.ndarray
) -> tuple[LinkageMerge, ...]:
    count = len(symbols)

    def reference(raw_index: float) -> str:
        index = int(raw_index)
        if index < count:
            return symbols[index]
        return f"node-{index - count + 1:03d}"

    return tuple(
        LinkageMerge(
            node_id=f"node-{position:03d}",
            left=reference(row[0]),
            right=reference(row[1]),
            distance=float(row[2]),
            count=int(round(float(row[3]))),
        )
        for position, row in enumerate(linkage_matrix, start=1)
    )


def _bootstrap_seed(
    *, dataset_hash: str, replicates: int, block_weeks: int, cut_distance: float
) -> int:
    payload = {
        "block_weeks": block_weeks,
        "contract_version": REFINERY_CLUSTERING_CONTRACT_VERSION,
        "cut_distance": float(cut_distance),
        "dataset_hash": dataset_hash,
        "linkage": PRIMARY_CLUSTER_LINKAGE,
        "replicates": replicates,
    }
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    return int.from_bytes(hashlib.sha256(encoded).digest()[:8], "big", signed=False)


def _empty_bootstrap_result(
    *,
    status: str,
    symbols: tuple[str, ...],
    pairs: tuple[tuple[str, str], ...],
    replicates: int,
    block_weeks: int,
    observations: int,
    seed: int,
) -> BootstrapClusterStability:
    return BootstrapClusterStability(
        status=status,
        symbols=symbols,
        requested_replicates=replicates,
        usable_replicates=0,
        unusable_replicates=replicates,
        block_weeks=block_weeks,
        observations=observations,
        seed=seed,
        pair_probabilities=tuple(
            PairBootstrapProbability(symbol_a=a, symbol_b=b, probability=None)
            for a, b in pairs
        ),
    )


def _minimum_observations(value: int) -> int:
    if not isinstance(value, int) or value < 2:
        raise ValueError("min_observations must be an integer >= 2")
    return value
