from __future__ import annotations

import re
from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    file_path = Path(path)
    text = file_path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{path}: expected one exact match, found {count}")
    file_path.write_text(text.replace(old, new, 1), encoding="utf-8")


def regex_once(path: str, pattern: str, replacement: str) -> None:
    file_path = Path(path)
    text = file_path.read_text(encoding="utf-8")
    updated, count = re.subn(pattern, replacement, text, count=1, flags=re.DOTALL)
    if count != 1:
        raise RuntimeError(f"{path}: expected one regex match, found {count}")
    file_path.write_text(updated, encoding="utf-8")


clustering_path = "apps/api/app/quant/clustering.py"
bootstrap_block = '''def prepare_bootstrap_sample(
    weekly_returns: pd.DataFrame,
    *,
    window: int = PRIMARY_STRUCTURAL_WINDOW_WEEKS,
) -> pd.DataFrame:
    """Return the exact canonical complete-case sample resampled by bootstrap."""

    if not isinstance(window, int) or window < 2:
        raise ValueError("window must be an integer >= 2")
    frame = _numeric_return_frame(weekly_returns)
    return frame.tail(window).replace([np.inf, -np.inf], np.nan).dropna(how="any")


def bootstrap_input_fingerprint(
    weekly_returns: pd.DataFrame,
    *,
    window: int = PRIMARY_STRUCTURAL_WINDOW_WEEKS,
) -> str:
    """Fingerprint only the exact effective sample consumed by bootstrap."""

    return _bootstrap_sample_fingerprint(
        prepare_bootstrap_sample(weekly_returns, window=window)
    )


def _bootstrap_sample_fingerprint(sample: pd.DataFrame) -> str:
    payload = {
        "symbols": [str(column) for column in sample.columns],
        "dates": [pd.Timestamp(value).isoformat() for value in sample.index],
        "values": sample.to_numpy(dtype=float).tolist(),
    }
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def bootstrap_cluster_stability(
    weekly_returns: pd.DataFrame,
    *,
    input_fingerprint: str,
    replicates: int = BOOTSTRAP_REPLICATES,
    block_weeks: int = BOOTSTRAP_BLOCK_WEEKS,
    min_observations: int = 52,
    window: int = PRIMARY_STRUCTURAL_WINDOW_WEEKS,
    cut_distance: float = PRIMARY_FLAT_CUT_DISTANCE,
) -> BootstrapClusterStability:
    """Return deterministic moving-block bootstrap co-cluster probabilities."""

    if not isinstance(input_fingerprint, str) or not input_fingerprint.strip():
        raise ValueError("input_fingerprint must be a non-empty string")
    if not isinstance(replicates, int) or replicates < 1:
        raise ValueError("replicates must be an integer >= 1")
    if not isinstance(block_weeks, int) or block_weeks < 1:
        raise ValueError("block_weeks must be an integer >= 1")
    if not isinstance(window, int) or window < 2:
        raise ValueError("window must be an integer >= 2")

    minimum = _minimum_observations(min_observations)
    clean = prepare_bootstrap_sample(weekly_returns, window=window)
    effective_fingerprint = _bootstrap_sample_fingerprint(clean)
    if input_fingerprint.strip() != effective_fingerprint:
        raise ValueError(
            "input_fingerprint must match the exact effective bootstrap sample"
        )
    symbols = tuple(str(column) for column in clean.columns)
    seed = _bootstrap_seed(
        input_fingerprint=effective_fingerprint,
        replicates=replicates,
        block_weeks=block_weeks,
        window=window,
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


def circular_block_bootstrap_indices('''
regex_once(
    clustering_path,
    r"def bootstrap_cluster_stability\([\s\S]*?\n\ndef circular_block_bootstrap_indices\(",
    bootstrap_block,
)

seed_block = '''def _bootstrap_seed(
    *,
    input_fingerprint: str,
    replicates: int,
    block_weeks: int,
    window: int,
    cut_distance: float,
) -> int:
    payload = {
        "block_weeks": block_weeks,
        "contract_version": REFINERY_CLUSTERING_CONTRACT_VERSION,
        "cut_distance": float(cut_distance),
        "input_fingerprint": input_fingerprint,
        "linkage": PRIMARY_CLUSTER_LINKAGE,
        "replicates": replicates,
        "window": window,
    }
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    return int.from_bytes(hashlib.sha256(encoded).digest()[:8], "big", signed=False)


def _empty_bootstrap_result('''
regex_once(
    clustering_path,
    r"def _bootstrap_seed\([\s\S]*?\n\ndef _empty_bootstrap_result\(",
    seed_block,
)

replace_once(
    "apps/api/app/quant/__init__.py",
    "    bootstrap_cluster_stability,\n    circular_block_bootstrap_indices,",
    "    bootstrap_cluster_stability,\n    bootstrap_input_fingerprint,\n    circular_block_bootstrap_indices,",
)
replace_once(
    "apps/api/app/quant/__init__.py",
    "    multi_window_cluster_stability,\n)",
    "    multi_window_cluster_stability,\n    prepare_bootstrap_sample,\n)",
)
replace_once(
    "apps/api/app/quant/__init__.py",
    '    "bootstrap_cluster_stability",\n    "circular_block_bootstrap_indices",',
    '    "bootstrap_cluster_stability",\n    "bootstrap_input_fingerprint",\n    "prepare_bootstrap_sample",\n    "circular_block_bootstrap_indices",',
)

phase5_path = "apps/api/app/refinery/phase5_service.py"
replace_once(
    phase5_path,
    "import hashlib\nimport json\nfrom dataclasses import replace\nfrom typing import Any, Mapping\n\nimport numpy as np\nimport pandas as pd",
    "from typing import Any, Mapping\n\nimport pandas as pd",
)
replace_once(
    phase5_path,
    "    PRIMARY_FLAT_CUT_DISTANCE,\n    REFINERY_CLUSTERING_CONTRACT_VERSION,",
    "    PRIMARY_FLAT_CUT_DISTANCE,\n    PRIMARY_STRUCTURAL_WINDOW_WEEKS,\n    REFINERY_CLUSTERING_CONTRACT_VERSION,",
)
replace_once(
    phase5_path,
    "    STABILITY_WINDOWS_WEEKS,\n    CorrelationResult,",
    "    STABILITY_WINDOWS_WEEKS,\n    CorrelationResult,\n    bootstrap_input_fingerprint,",
)
replace_once(
    phase5_path,
    '                    "canonical_structural_weekly_fingerprint_sha256"',
    '                    "effective_structural_weekly_sample_fingerprint_sha256"',
)
old_analysis = '''        canonical_seed_fingerprint = _structural_bootstrap_fingerprint(
            prepared.weekly_returns
        )
        phase5_dataset = replace(
            prepared.candidate_dataset,
            dataset_hash=canonical_seed_fingerprint,
        )
        payload.update(
            build_phase5_relationships(
                candidate_dataset=phase5_dataset,
                weekly_returns=prepared.weekly_returns,
                structural_correlation=structural,
                correlation_payloads=payload["correlations"],
                factor_provider=self._factor_provider,
            )
        )
        payload["clustering"]["bootstrap_seed_fingerprint"] = (
            canonical_seed_fingerprint
        )
        return payload'''
new_analysis = '''        bootstrap_fingerprint = bootstrap_input_fingerprint(
            prepared.weekly_returns,
            window=PRIMARY_STRUCTURAL_WINDOW_WEEKS,
        )
        payload.update(
            build_phase5_relationships(
                candidate_dataset=prepared.candidate_dataset,
                weekly_returns=prepared.weekly_returns,
                structural_correlation=structural,
                correlation_payloads=payload["correlations"],
                bootstrap_input_fingerprint=bootstrap_fingerprint,
                factor_provider=self._factor_provider,
            )
        )
        return payload'''
replace_once(phase5_path, old_analysis, new_analysis)
regex_once(
    phase5_path,
    r"\n\ndef _structural_bootstrap_fingerprint\([\s\S]*\Z",
    "\n",
)

relationships_path = "apps/api/app/refinery/relationships.py"
replace_once(
    relationships_path,
    "    PRIMARY_FLAT_CUT_DISTANCE,\n    REFINERY_CLUSTERING_CONTRACT_VERSION,",
    "    PRIMARY_FLAT_CUT_DISTANCE,\n    PRIMARY_STRUCTURAL_WINDOW_WEEKS,\n    REFINERY_CLUSTERING_CONTRACT_VERSION,",
)
replace_once(
    relationships_path,
    "    correlation_payloads: Mapping[str, Mapping[str, Any]],\n    factor_provider: FrenchFactorProvider,",
    "    correlation_payloads: Mapping[str, Mapping[str, Any]],\n    bootstrap_input_fingerprint: str,\n    factor_provider: FrenchFactorProvider,",
)
replace_once(
    relationships_path,
    "        structural_correlation=structural_correlation,\n        dataset_hash=candidate_dataset.dataset_hash,",
    "        structural_correlation=structural_correlation,\n        input_fingerprint=bootstrap_input_fingerprint,",
)
replace_once(
    relationships_path,
    "    structural_correlation: CorrelationResult,\n    dataset_hash: str,",
    "    structural_correlation: CorrelationResult,\n    input_fingerprint: str,",
)
replace_once(
    relationships_path,
    '        "bootstrap_block_weeks": BOOTSTRAP_BLOCK_WEEKS,\n    }',
    '        "bootstrap_block_weeks": BOOTSTRAP_BLOCK_WEEKS,\n        "bootstrap_window_weeks": PRIMARY_STRUCTURAL_WINDOW_WEEKS,\n        "bootstrap_input_fingerprint_sha256": input_fingerprint,\n    }',
)
replace_once(
    relationships_path,
    "            weekly_returns,\n            dataset_hash=dataset_hash,\n            replicates=BOOTSTRAP_REPLICATES,",
    "            weekly_returns,\n            input_fingerprint=input_fingerprint,\n            replicates=BOOTSTRAP_REPLICATES,",
)
replace_once(
    relationships_path,
    "            block_weeks=BOOTSTRAP_BLOCK_WEEKS,\n            min_observations=52,\n            cut_distance=PRIMARY_FLAT_CUT_DISTANCE,",
    "            block_weeks=BOOTSTRAP_BLOCK_WEEKS,\n            min_observations=52,\n            window=PRIMARY_STRUCTURAL_WINDOW_WEEKS,\n            cut_distance=PRIMARY_FLAT_CUT_DISTANCE,",
)

replace_once(
    "apps/portfolio-web/src/refineryTypes.ts",
    "  bootstrap_seed_fingerprint?: string;",
    "  bootstrap_window_weeks: number;\n  bootstrap_input_fingerprint_sha256: string;",
)

clustering_test = "tests/test_clustering.py"
replace_once(
    clustering_test,
    "    bootstrap_cluster_stability,\n    circular_block_bootstrap_indices,",
    "    bootstrap_cluster_stability,\n    bootstrap_input_fingerprint,\n    circular_block_bootstrap_indices,",
)
replace_once(
    clustering_test,
    '''    first = bootstrap_cluster_stability(
        weekly,
        dataset_hash="dataset-fixture-abc",
        replicates=30,
        block_weeks=4,
        min_observations=52,
    )
    second = bootstrap_cluster_stability(
        weekly,
        dataset_hash="dataset-fixture-abc",
        replicates=30,
        block_weeks=4,
        min_observations=52,
    )''',
    '''    fingerprint = bootstrap_input_fingerprint(weekly)
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
    )''',
)
replace_once(
    clustering_test,
    '''    result = bootstrap_cluster_stability(
        weekly,
        dataset_hash="degenerate-fixture",
        replicates=12,
        min_observations=52,
    )''',
    '''    result = bootstrap_cluster_stability(
        weekly,
        input_fingerprint=bootstrap_input_fingerprint(weekly),
        replicates=12,
        min_observations=52,
    )''',
)
regex_once(
    clustering_test,
    r"def test_bootstrap_dataset_hash_changes_deterministic_seed\(\) -> None:[\s\S]*\Z",
    '''def test_bootstrap_effective_input_change_changes_deterministic_seed() -> None:
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
''',
)

replace_once(
    "tests/test_refinery_phase5.py",
    '    assert original["clustering"]["bootstrap_seed_fingerprint"] == (\n        permuted["clustering"]["bootstrap_seed_fingerprint"]\n    )',
    '    assert original["clustering"]["bootstrap_input_fingerprint_sha256"] == (\n        permuted["clustering"]["bootstrap_input_fingerprint_sha256"]\n    )',
)

print("P5-CORR-A precise patch applied successfully")
