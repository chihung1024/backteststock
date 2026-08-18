from __future__ import annotations

import json
import os
import platform
import sys
import time
import traceback
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

from apps.api.app.data.history_service import PartialTWDHistories, TWDAssetHistory
from apps.api.app.data.twd_valuation import TWDValuation
from apps.api.app.portfolio.models import SimulationConfig
from apps.api.app.research.dataset import build_research_dataset
from apps.api.app.research.parameter_optimization import (
    InnerValidationSpec,
    ParameterSearchSpace,
    TuningBudget,
    build_parameter_search_plan,
)
from apps.api.app.research.parameter_tuning import run_inner_parameter_tuning
from apps.api.app.research.walk_forward import ConfiguredResearchUniverse, WalkForwardPeriod
from apps.api.app.research.walk_forward_job import (
    MAX_INNER_FOLDS,
    MAX_PARAMETER_CANDIDATES,
    MAX_TUNING_EVALUATIONS_PER_JOB,
)

RISKY = ("AAA", "BBB", "CCC", "DDD", "EEE", "FFF")
DEFENSIVE = ("BND",)
MEMBERS = (*RISKY, *DEFENSIVE)
ALLOCATIONS = ("equal", "inverse_volatility", "risk_parity_erc")
OUTPUT = Path("parameter-tuning-capacity.json")


def _history(symbol: str, dates: pd.DatetimeIndex, daily: np.ndarray) -> TWDAssetHistory:
    levels = pd.Series(100.0 * np.cumprod(1.0 + daily), index=dates, dtype=float)
    fx = pd.Series(1.0, index=dates, dtype=float)
    return TWDAssetHistory(
        symbol=symbol,
        quote_currency="TWD",
        valuation=TWDValuation(
            source_currency="TWD",
            native_adjusted_close=levels.rename("native_adjusted_close"),
            fx_to_twd=fx.rename("fx_to_twd"),
            adjusted_close_twd=levels.rename("adjusted_close_twd"),
            daily_returns=levels.pct_change(fill_method=None).fillna(0.0).rename("daily_return"),
        ),
        corporate_action_audit={"status": "verified_standard_actions"},
        fx_audit={"method": "identity", "tickers": []},
        raw_quote_currency="TWD",
        native_price_scale=1.0,
    )


def _dataset():
    dates = pd.bdate_range("2021-01-29", "2025-12-31")
    phase = np.arange(len(dates), dtype=float)
    daily = {
        "AAA": 0.00080 + 0.0100 * np.sin(phase / 8.0),
        "BBB": 0.00072 + 0.0092 * np.cos(phase / 10.0),
        "CCC": 0.00064 + 0.0087 * np.sin(phase / 12.0 + 0.5),
        "DDD": 0.00056 + 0.0081 * np.cos(phase / 14.0 + 0.8),
        "EEE": 0.00048 + 0.0076 * np.sin(phase / 16.0 + 1.1),
        "FFF": 0.00040 + 0.0070 * np.cos(phase / 18.0 + 1.4),
        "BND": 0.00014 + 0.0022 * np.sin(phase / 21.0 + 0.3),
    }
    histories = {symbol: _history(symbol, dates, daily[symbol]) for symbol in MEMBERS}
    return build_research_dataset(
        PartialTWDHistories(requested=MEMBERS, histories=histories, failures={}),
        start=date(2021, 1, 29),
        end=date(2025, 12, 31),
    )


def _outer_period() -> WalkForwardPeriod:
    return WalkForwardPeriod(
        period_id="capacity-outer-2025-12",
        training_start=date(2021, 1, 29),
        training_end=date(2025, 12, 31),
        decision_date=date(2025, 12, 31),
        evaluation_start=date(2026, 1, 1),
        evaluation_end=date(2026, 1, 30),
    )


def _space(candidate_count: int) -> ParameterSearchSpace:
    dimensions = {
        12: ((6, 12), (1, 3), (0.0,)),
        24: ((6, 12), (1, 3), (0.0, 0.03)),
        48: ((3, 6, 9, 12), (1, 3), (0.0, 0.03)),
    }
    lookbacks, top_k, thresholds = dimensions[candidate_count]
    space = ParameterSearchSpace(
        lookback_months=lookbacks,
        top_k=top_k,
        absolute_thresholds=thresholds,
        allocation_methods=ALLOCATIONS,
    )
    if space.candidate_count != candidate_count:
        raise AssertionError(f"expected {candidate_count} candidates, got {space.candidate_count}")
    return space


def _plan(candidate_count: int, fold_count: int):
    return build_parameter_search_plan(
        search_space=_space(candidate_count),
        inner_validation=InnerValidationSpec(
            fold_count=fold_count,
            evaluation_months=1,
            step_months=1,
        ),
        risky_symbol_count=len(RISKY),
        outer_period_count=1,
        budget=TuningBudget(
            max_parameter_candidates=MAX_PARAMETER_CANDIDATES,
            max_inner_folds=MAX_INNER_FOLDS,
            max_tuning_evaluations=MAX_TUNING_EVALUATIONS_PER_JOB,
        ),
    )


def _write(report: dict[str, object]) -> None:
    OUTPUT.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    dataset = _dataset()
    outer_period = _outer_period()
    universe = ConfiguredResearchUniverse(MEMBERS)
    config = SimulationConfig(initial_amount=100_000.0, transaction_cost_bps=5.0)
    report: dict[str, object] = {
        "status": "running",
        "workflowSha": os.environ.get("GITHUB_SHA"),
        "productBaseSha": os.environ.get("PRODUCT_SOURCE_SHA"),
        "benchmarkHeadSha": os.environ.get("BENCHMARK_HEAD_SHA"),
        "runnerOs": os.environ.get("RUNNER_OS"),
        "runnerArch": os.environ.get("RUNNER_ARCH"),
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "dataset": {
            "symbols": list(MEMBERS),
            "requestedStart": dataset.requested_start.isoformat(),
            "requestedEnd": dataset.requested_end.isoformat(),
            "datasetHash": dataset.dataset_hash,
        },
        "productionBudget": {
            "maxParameterCandidates": MAX_PARAMETER_CANDIDATES,
            "maxInnerFolds": MAX_INNER_FOLDS,
            "maxTuningEvaluationsPerJob": MAX_TUNING_EVALUATIONS_PER_JOB,
        },
        "cases": [],
    }
    _write(report)

    overall_start = time.perf_counter()
    cases: list[dict[str, object]] = []
    try:
        for candidate_count in (12, 24, 48):
            for fold_count in (3, 6):
                plan = _plan(candidate_count, fold_count)
                planned = candidate_count * fold_count
                started = time.perf_counter()
                tuning = run_inner_parameter_tuning(
                    outer_period=outer_period,
                    outer_training_dataset=dataset,
                    configured_universe=universe,
                    risky_symbols=RISKY,
                    defensive_symbols=DEFENSIVE,
                    search_plan=plan,
                    simulation_config=config,
                )
                elapsed = time.perf_counter() - started
                eligible = sum(item.status == "eligible" for item in tuning.candidates)
                case = {
                    "candidateCount": candidate_count,
                    "innerFoldCount": fold_count,
                    "plannedEvaluations": planned,
                    "elapsedSeconds": round(elapsed, 6),
                    "millisecondsPerEvaluation": round(1000.0 * elapsed / planned, 3),
                    "evaluationsPerSecond": round(planned / elapsed, 3),
                    "eligibleCandidates": eligible,
                    "failedCandidates": len(tuning.candidates) - eligible,
                    "winnerParameterHash": tuning.winner_parameter_hash,
                    "resultHash": tuning.result_hash,
                }
                cases.append(case)
                report["cases"] = cases
                report["elapsedSecondsSoFar"] = round(time.perf_counter() - overall_start, 6)
                _write(report)
                print(json.dumps(case, sort_keys=True), flush=True)
    except Exception as exc:
        report["status"] = "failed"
        report["failureType"] = type(exc).__name__
        report["failureMessage"] = str(exc)
        report["traceback"] = traceback.format_exc()
        report["elapsedSecondsSoFar"] = round(time.perf_counter() - overall_start, 6)
        _write(report)
        raise

    report["status"] = "completed"
    report["totalMeasuredSeconds"] = round(time.perf_counter() - overall_start, 6)
    _write(report)
    print(json.dumps(report, sort_keys=True), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
