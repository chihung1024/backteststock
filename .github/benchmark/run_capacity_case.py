from __future__ import annotations

import json
import os
import time
import traceback
from pathlib import Path

import parameter_tuning_capacity as bench
from apps.api.app.portfolio.models import SimulationConfig
from apps.api.app.research.parameter_tuning import run_inner_parameter_tuning
from apps.api.app.research.walk_forward import ConfiguredResearchUniverse


def _write(output: Path, payload: dict[str, object]) -> None:
    output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(payload, sort_keys=True), flush=True)


def main() -> int:
    candidate_count = int(os.environ["BENCHMARK_CANDIDATES"])
    fold_count = int(os.environ["BENCHMARK_FOLDS"])
    planned = candidate_count * fold_count
    output = Path(f"parameter-tuning-capacity-{candidate_count}-{fold_count}.json")
    dataset = bench._dataset()
    base: dict[str, object] = {
        "productBranch": "feat/optimizer-hub-parameter-optimization",
        "productQuantTreeNote": "benchmark fixture executes the same quant/API tree as product head; later product-only differences are E2E locator assertions",
        "benchmarkHeadSha": os.environ.get("BENCHMARK_HEAD_SHA"),
        "workflowSha": os.environ.get("GITHUB_SHA"),
        "datasetHash": dataset.dataset_hash,
        "candidateCount": candidate_count,
        "innerFoldCount": fold_count,
        "plannedEvaluations": planned,
    }
    started = time.perf_counter()
    try:
        tuning = run_inner_parameter_tuning(
            outer_period=bench._outer_period(),
            outer_training_dataset=dataset,
            configured_universe=ConfiguredResearchUniverse(bench.MEMBERS),
            risky_symbols=bench.RISKY,
            defensive_symbols=bench.DEFENSIVE,
            search_plan=bench._plan(candidate_count, fold_count),
            simulation_config=SimulationConfig(initial_amount=100_000.0, transaction_cost_bps=5.0),
        )
    except Exception as exc:
        elapsed = time.perf_counter() - started
        payload = {
            **base,
            "status": "failed",
            "elapsedSeconds": round(elapsed, 6),
            "millisecondsPerPlannedEvaluation": round(1000.0 * elapsed / planned, 3),
            "failureType": type(exc).__name__,
            "failureMessage": str(exc),
            "traceback": traceback.format_exc(),
        }
        _write(output, payload)
        raise

    elapsed = time.perf_counter() - started
    eligible = sum(item.status == "eligible" for item in tuning.candidates)
    payload = {
        **base,
        "status": "completed",
        "elapsedSeconds": round(elapsed, 6),
        "millisecondsPerEvaluation": round(1000.0 * elapsed / planned, 3),
        "evaluationsPerSecond": round(planned / elapsed, 3),
        "eligibleCandidates": eligible,
        "failedCandidates": len(tuning.candidates) - eligible,
        "winnerParameterHash": tuning.winner_parameter_hash,
        "resultHash": tuning.result_hash,
    }
    _write(output, payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
