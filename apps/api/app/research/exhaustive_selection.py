"""Walk-forward adapter for the existing Exhaustive JavaScript authority.

The numerical optimizer remains ``public/exhaustive-optimizer-core.js``.  This
module validates causal Training evidence, invokes a narrow Node bridge around
that authority, and maps the authoritative winner into the Batch 4A-2
``SelectionEngine`` result without reproducing simulation or ranking formulas in
Python.
"""

from __future__ import annotations

import json
import math
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, ClassVar, Mapping, Protocol

import numpy as np

from api import exhaustive_optimizer
from apps.api.app.research.dataset import ResearchDataset
from apps.api.app.research.selection import SelectionContext, SelectionResult

WALK_FORWARD_EXHAUSTIVE_ADAPTER_VERSION = (
    "walk-forward-exhaustive-adapter-2026-08-15.1"
)
EXHAUSTIVE_SELECTION_RULE = "existing-exhaustive-optimized-score-v1"
EXHAUSTIVE_SELECTION_BRIDGE_PATH = "scripts/exhaustive_selection_authority.mjs"
EXHAUSTIVE_RANKING_FIELD = "optimized_score"
EXHAUSTIVE_RANKING_DIRECTION = "desc"
EXHAUSTIVE_RANKING_TIE_BREAK = "smaller-combination-rank"
MAX_TRANSACTION_COST_BPS = 1000.0
ALLOWED_REBALANCE_MODES = frozenset(
    {"band", "monthly", "quarterly", "annually", "never"}
)


class ExhaustiveAuthorityRunner(Protocol):
    """Execution boundary for the existing JavaScript numerical authority."""

    def identity(self) -> Mapping[str, str]:
        ...

    def select_best(self, payload: Mapping[str, Any]) -> Mapping[str, Any]:
        ...


@dataclass(frozen=True, slots=True)
class NodeExhaustiveAuthorityRunner:
    """Invoke the existing JS authority through a repository-local Node bridge.

    Batch 4A-3 is internal research infrastructure.  No public API route relies
    on Node being present in the Python production runtime; deployment placement
    remains a Batch 4A-5 concern.
    """

    node_binary: str = "node"
    timeout_seconds: float = 300.0
    script_path: Path | None = None

    def identity(self) -> Mapping[str, str]:
        return self._run({"type": "version"})

    def select_best(self, payload: Mapping[str, Any]) -> Mapping[str, Any]:
        return self._run(dict(payload))

    def _run(self, payload: Mapping[str, Any]) -> Mapping[str, Any]:
        binary = shutil.which(self.node_binary)
        if not binary:
            raise RuntimeError(
                "Node.js is required to execute the existing Exhaustive authority"
            )
        root = Path(__file__).resolve().parents[4]
        script = self.script_path or (root / EXHAUSTIVE_SELECTION_BRIDGE_PATH)
        if not script.is_file():
            raise RuntimeError(f"Exhaustive authority bridge is missing: {script}")
        try:
            completed = subprocess.run(
                [binary, str(script)],
                cwd=root,
                input=json.dumps(payload, allow_nan=False, separators=(",", ":")),
                text=True,
                capture_output=True,
                timeout=float(self.timeout_seconds),
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError("Exhaustive authority bridge timed out") from exc
        if completed.returncode != 0:
            detail = (completed.stderr or completed.stdout or "unknown bridge failure").strip()
            raise RuntimeError(f"Exhaustive authority bridge failed: {detail[:1000]}")
        try:
            decoded = json.loads(completed.stdout)
        except json.JSONDecodeError as exc:
            raise RuntimeError("Exhaustive authority bridge returned invalid JSON") from exc
        if not isinstance(decoded, dict):
            raise RuntimeError("Exhaustive authority bridge must return an object")
        return decoded


@dataclass(frozen=True, slots=True)
class ExhaustiveSelectionEngine:
    """SelectionEngine adapter for the current production Exhaustive authority.

    ``authority_dataset`` is an engine-specific Training evidence artifact that
    contains the exact PIT candidate sequence followed by one benchmark.  It is
    separate from ``SelectionContext.training_dataset`` so the benchmark never
    becomes an eligible constituent.  Its hash and JS authority identity are
    frozen into selector parameters before selection executes.
    """

    authority_dataset: ResearchDataset
    benchmark_symbol: str
    holding_count: int
    rebalance_mode: str = "never"
    band_ratio: float = 0.20
    transaction_cost_bps: float = 0.0
    execution_delay_trading_days: int = 1
    runner: ExhaustiveAuthorityRunner = field(
        default_factory=NodeExhaustiveAuthorityRunner,
        repr=False,
        compare=False,
    )
    authority_version: str = field(init=False)
    bridge_version: str = field(init=False)
    risk_free_rate: float = field(init=False)

    contract_version: ClassVar[str] = WALK_FORWARD_EXHAUSTIVE_ADAPTER_VERSION
    rule: ClassVar[str] = EXHAUSTIVE_SELECTION_RULE

    def __post_init__(self) -> None:
        benchmark = str(self.benchmark_symbol)
        if not benchmark or benchmark != benchmark.strip().upper():
            raise ValueError("benchmark_symbol must already be canonical")
        if not isinstance(self.holding_count, int) or isinstance(self.holding_count, bool):
            raise TypeError("holding_count must be an integer")
        if self.holding_count < 1:
            raise ValueError("holding_count must be positive")
        if self.rebalance_mode not in ALLOWED_REBALANCE_MODES:
            raise ValueError("unsupported Exhaustive rebalance_mode")
        if not math.isfinite(float(self.band_ratio)) or not 0.0 < float(self.band_ratio) < 1.0:
            raise ValueError("band_ratio must be finite and between zero and one")
        if (
            not math.isfinite(float(self.transaction_cost_bps))
            or not 0.0 <= float(self.transaction_cost_bps) <= MAX_TRANSACTION_COST_BPS
        ):
            raise ValueError(
                f"transaction_cost_bps must be between 0 and {MAX_TRANSACTION_COST_BPS:g}"
            )
        if (
            not isinstance(self.execution_delay_trading_days, int)
            or isinstance(self.execution_delay_trading_days, bool)
            or self.execution_delay_trading_days < 0
        ):
            raise ValueError("execution_delay_trading_days must be a non-negative integer")

        configured_risk_free_rate = float(exhaustive_optimizer.legacy.RISK_FREE_RATE)
        if (
            not math.isfinite(configured_risk_free_rate)
            or configured_risk_free_rate <= -1.0
        ):
            raise ValueError(
                "configured production Exhaustive risk-free rate must be finite and greater than -1"
            )
        object.__setattr__(self, "benchmark_symbol", benchmark)
        object.__setattr__(self, "risk_free_rate", configured_risk_free_rate)

        identity = self.runner.identity()
        authority_version = _required_text(
            identity.get("authorityVersion"), label="Exhaustive authority version"
        )
        bridge_version = _required_text(
            identity.get("bridgeVersion"), label="Exhaustive bridge version"
        )
        object.__setattr__(self, "authority_version", authority_version)
        object.__setattr__(self, "bridge_version", bridge_version)

    @property
    def parameters(self) -> Mapping[str, Any]:
        _assert_dataset_identity(self.authority_dataset, label="Exhaustive authority")
        return {
            "quantAuthority": "public/exhaustive-optimizer-core.js",
            "authorityVersion": self.authority_version,
            "bridgeVersion": self.bridge_version,
            "authorityDatasetHash": self.authority_dataset.dataset_hash,
            "benchmarkSymbol": self.benchmark_symbol,
            "holdingCount": self.holding_count,
            "rebalanceMode": self.rebalance_mode,
            "bandRatio": float(self.band_ratio),
            "transactionCostBps": float(self.transaction_cost_bps),
            "executionDelayTradingDays": self.execution_delay_trading_days,
            "riskFreeRate": float(self.risk_free_rate),
            "ranking": {
                "field": EXHAUSTIVE_RANKING_FIELD,
                "direction": EXHAUSTIVE_RANKING_DIRECTION,
                "nonFinite": "negative-infinity",
                "tieBreak": EXHAUSTIVE_RANKING_TIE_BREAK,
            },
            "weighting": "equal",
        }

    def select(self, context: SelectionContext) -> SelectionResult:
        authority_hash = _assert_dataset_identity(
            self.authority_dataset, label="Exhaustive authority"
        )
        candidates, combination_count = self._validate_training_evidence(context)
        payload = self._authority_payload(candidates)
        result = self.runner.select_best(payload)
        _assert_same_dataset_identity(
            self.authority_dataset,
            expected_hash=authority_hash,
            label="Exhaustive authority",
        )

        if result.get("authorityVersion") != self.authority_version:
            raise ValueError("Exhaustive authority version changed during selection")
        if result.get("bridgeVersion") != self.bridge_version:
            raise ValueError("Exhaustive bridge version changed during selection")
        if result.get("datasetHash") != authority_hash:
            raise ValueError("Exhaustive authority result is bound to a different dataset")
        if result.get("combinationCount") != combination_count:
            raise ValueError("Exhaustive authority returned a different combination count")
        ranking = result.get("ranking")
        if not isinstance(ranking, dict) or ranking != self.parameters["ranking"]:
            raise ValueError("Exhaustive authority returned a different ranking contract")

        best_rank = result.get("bestRank")
        if (
            not isinstance(best_rank, int)
            or isinstance(best_rank, bool)
            or best_rank < 0
            or best_rank >= combination_count
        ):
            raise ValueError("Exhaustive authority returned an invalid winning rank")
        selected = result.get("selectedConstituents")
        weights = result.get("weights")
        if not isinstance(selected, list) or not isinstance(weights, list):
            raise TypeError("Exhaustive authority must return constituents and weights arrays")
        selected_tuple = tuple(str(symbol) for symbol in selected)
        weight_tuple = tuple(float(weight) for weight in weights)
        if len(selected_tuple) != self.holding_count or len(weight_tuple) != self.holding_count:
            raise ValueError("Exhaustive authority winner does not match holding_count")
        if len(set(selected_tuple)) != len(selected_tuple):
            raise ValueError("Exhaustive authority winner contains duplicate symbols")
        if not set(selected_tuple).issubset(set(candidates)):
            raise ValueError("Exhaustive authority selected a symbol outside the PIT candidates")
        if (
            not all(math.isfinite(weight) and weight > 0.0 for weight in weight_tuple)
            or not math.isclose(sum(weight_tuple), 1.0, abs_tol=1e-12)
        ):
            raise ValueError("Exhaustive authority returned invalid portfolio weights")
        expected_weight = 1.0 / self.holding_count
        if not all(math.isclose(weight, expected_weight, abs_tol=1e-12) for weight in weight_tuple):
            raise ValueError("existing Exhaustive authority must return equal weights")
        return SelectionResult(
            selected_constituents=selected_tuple,
            weights=weight_tuple,
        )

    def _validate_training_evidence(
        self, context: SelectionContext
    ) -> tuple[tuple[str, ...], int]:
        if context.unavailable_candidates:
            symbols = ", ".join(item.symbol for item in context.unavailable_candidates)
            raise ValueError(
                "existing Exhaustive policy does not silently drop unavailable PIT members: "
                + symbols
            )
        candidates = tuple(context.eligible_candidates)
        if len(candidates) < exhaustive_optimizer.MIN_SOURCE_TICKERS:
            raise ValueError(
                f"Exhaustive selection requires at least {exhaustive_optimizer.MIN_SOURCE_TICKERS} candidates"
            )
        if len(candidates) > exhaustive_optimizer.MAX_SOURCE_TICKERS:
            raise ValueError(
                f"Exhaustive selection supports at most {exhaustive_optimizer.MAX_SOURCE_TICKERS} candidates"
            )
        if self.holding_count > len(candidates):
            raise ValueError("holding_count cannot exceed the eligible PIT candidate count")
        combination_count = math.comb(len(candidates), self.holding_count)
        if combination_count > exhaustive_optimizer.MAX_EXHAUSTIVE_COMBINATIONS:
            raise ValueError(
                "Exhaustive selection combination count exceeds the existing 50M safety ceiling"
            )
        if self.benchmark_symbol in candidates:
            raise ValueError("benchmark cannot be an eligible PIT constituent")

        dataset = self.authority_dataset
        expected_symbols = (*candidates, self.benchmark_symbol)
        if dataset.requested_symbols != expected_symbols:
            raise ValueError(
                "Exhaustive authority dataset must request the exact PIT candidate order followed by benchmark"
            )
        if dataset.resolved_symbols != expected_symbols or dataset.failures:
            raise ValueError("Exhaustive authority dataset must resolve every candidate and benchmark")
        if dataset.requested_start != context.period.training_start:
            raise ValueError("Exhaustive authority requested_start must equal training_start")
        if dataset.requested_end != context.period.training_end:
            raise ValueError("Exhaustive authority requested_end must equal training_end")
        if dataset.effective_start is None or dataset.effective_end is None:
            raise ValueError("Exhaustive authority dataset has no effective observations")
        if dataset.effective_start < context.period.training_start:
            raise ValueError("Exhaustive authority observations start before Training")
        if dataset.effective_end > context.period.training_end:
            raise ValueError("Exhaustive authority observations extend beyond Training")
        if dataset.effective_end > context.period.decision_date:
            raise ValueError("Exhaustive authority observations extend beyond Decision")
        if len(dataset.reference_calendar) < 60 or len(dataset.daily_levels_twd) < 60:
            raise ValueError("existing Exhaustive authority requires at least 60 observations")

        _assert_candidate_history_parity(context.training_dataset, dataset, candidates)
        values = dataset.daily_levels_twd.to_numpy(dtype=float)
        if not np.isfinite(values).all() or (values <= 0.0).any():
            raise ValueError("Exhaustive authority requires finite positive TWD levels")

        common = dataset.daily_levels_twd.copy()
        common.attrs["reference_index"] = dataset.reference_calendar
        common.attrs["availability_masks"] = {
            symbol: np.asarray(dataset.availability_masks[symbol], dtype=bool)
            for symbol in expected_symbols
        }
        try:
            exhaustive_optimizer._strict_full_period_coverage(
                common,
                list(candidates),
                self.benchmark_symbol,
            )
        except exhaustive_optimizer.legacy.ValidationError as exc:
            raise ValueError(str(exc)) from exc

        unverified = [
            symbol
            for symbol in expected_symbols
            if dataset.asset_metadata[symbol]
            .get("corporate_action_audit", {})
            .get("status")
            != "verified_standard_actions"
        ]
        if unverified:
            raise ValueError(
                "Exhaustive authority requires verified standard corporate actions: "
                + ", ".join(unverified)
            )
        return candidates, combination_count

    def _authority_payload(self, candidates: tuple[str, ...]) -> dict[str, Any]:
        dataset = self.authority_dataset
        required = (*candidates, self.benchmark_symbol)
        return {
            "candidateTickers": list(candidates),
            "benchmark": self.benchmark_symbol,
            "dates": [
                timestamp.strftime("%Y-%m-%d")
                for timestamp in dataset.daily_levels_twd.index
            ],
            "prices": {
                symbol: [
                    float(value)
                    for value in dataset.daily_levels_twd[symbol].to_numpy()
                ]
                for symbol in required
            },
            "datasetHash": dataset.dataset_hash,
            "riskFreeRate": float(self.risk_free_rate),
            "settings": {
                "holdingCount": self.holding_count,
                "rebalanceMode": self.rebalance_mode,
                "bandRatio": float(self.band_ratio),
                "transactionCostBps": float(self.transaction_cost_bps),
                "executionDelayTradingDays": self.execution_delay_trading_days,
            },
        }


def _candidate_history_identity(metadata: Mapping[str, Any]) -> dict[str, Any]:
    fingerprints = metadata.get("fingerprints", {})
    return {
        "symbol": metadata.get("symbol"),
        "quote_currency": metadata.get("quote_currency"),
        "raw_quote_currency": metadata.get("raw_quote_currency"),
        "native_price_scale": metadata.get("native_price_scale"),
        "first_twd_date": metadata.get("first_twd_date"),
        "last_twd_date": metadata.get("last_twd_date"),
        "corporate_action_audit": metadata.get("corporate_action_audit"),
        "fx_audit": metadata.get("fx_audit"),
        "return_component_audit": metadata.get("return_component_audit"),
        "native_adjusted_close": fingerprints.get("native_adjusted_close"),
        "fx_to_twd": fingerprints.get("fx_to_twd"),
        "twd_adjusted_close": fingerprints.get("twd_adjusted_close"),
    }


def _assert_candidate_history_parity(
    candidate_dataset: ResearchDataset,
    authority_dataset: ResearchDataset,
    candidates: tuple[str, ...],
) -> None:
    for symbol in candidates:
        if symbol not in candidate_dataset.asset_metadata:
            raise ValueError(f"candidate Training metadata is missing: {symbol}")
        if symbol not in authority_dataset.asset_metadata:
            raise ValueError(f"Exhaustive authority metadata is missing: {symbol}")
        if _candidate_history_identity(candidate_dataset.asset_metadata[symbol]) != (
            _candidate_history_identity(authority_dataset.asset_metadata[symbol])
        ):
            raise ValueError(
                f"Exhaustive authority candidate history differs from Training evidence: {symbol}"
            )


def _assert_dataset_identity(dataset: ResearchDataset, *, label: str) -> str:
    payload = dataset.export_payload()
    dataset_hash = str(dataset.dataset_hash).strip().lower()
    if not dataset_hash or payload.get("datasetHash") != dataset_hash:
        raise ValueError(f"{label} dataset identity is missing or inconsistent")
    return dataset_hash


def _assert_same_dataset_identity(
    dataset: ResearchDataset,
    *,
    expected_hash: str,
    label: str,
) -> None:
    if _assert_dataset_identity(dataset, label=label) != expected_hash:
        raise ValueError(f"{label} dataset identity changed during selection")


def _required_text(value: Any, *, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must be a non-empty string")
    return value.strip()
