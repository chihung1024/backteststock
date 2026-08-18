"""Continuous Walk-Forward OOS execution on the existing Portfolio v3 ledger authority.

Batch 4A-4 deliberately does not create another portfolio simulator.  Each
Evaluation segment is executed by ``simulate_portfolio_ledger()`` and every
inter-decision target transition delegates to the same Portfolio v3
``_rebalance()`` transaction-cost authority.  Segment state is carried forward
in TWD; period-local NAVs are never normalized and averaged or stitched as if
independent experiments were one investable history.

ResearchDataset v1 exposes total-return TWD levels, not separate cash
distribution components.  This adapter therefore requires reinvested
distributions and forbids external cashflows/leverage.  Those unsupported state
features fail closed instead of being approximated from incomplete research
evidence.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, replace
from typing import Sequence

import numpy as np
import pandas as pd

from apps.api.app.data.history_service import TWDAssetHistory
from apps.api.app.data.return_components import total_only_components
from apps.api.app.data.twd_valuation import TWDValuation
from apps.api.app.portfolio.ledger import (
    PORTFOLIO_LEDGER_CONTRACT_VERSION,
    PortfolioLedger,
    _rebalance,
    simulate_portfolio_ledger,
)
from apps.api.app.portfolio.metrics import PortfolioMetricReport, compute_metric_report
from apps.api.app.portfolio.models import (
    CashflowType,
    LedgerEvent,
    LeverageType,
    PortfolioSpec,
    SimulationConfig,
)
from apps.api.app.research.dataset import ResearchDataset
from apps.api.app.research.selection import validate_evaluation_dataset
from apps.api.app.research.walk_forward import (
    DecisionSnapshot,
    validate_period_schedule,
)

WALK_FORWARD_OOS_LEDGER_CONTRACT_VERSION = "walk-forward-oos-ledger-2026-08-15.1"
WALK_FORWARD_OOS_EXECUTION_POLICY = "target-at-first-effective-oos-close-v1"
WALK_FORWARD_OOS_GAP_POLICY = "carry-last-audited-state-flat-no-invented-return-v1"
WALK_FORWARD_OOS_RETURN_COMPONENT_POLICY = "research-total-return-reinvested-v1"
_EPSILON = 1e-12
_PORTFOLIO_NAME_LIMIT = 60
_SEGMENT_NAME_DIGEST_LENGTH = 12


@dataclass(frozen=True, slots=True)
class WalkForwardEvaluation:
    """One frozen decision paired with its post-decision Evaluation dataset."""

    decision: DecisionSnapshot
    evaluation_dataset: ResearchDataset


@dataclass(frozen=True, slots=True)
class WalkForwardOOSPeriodAudit:
    """Immutable provenance for one segment of the continuous OOS ledger."""

    period_id: str
    decision_hash: str
    evaluation_dataset_hash: str
    requested_start: str
    requested_end: str
    effective_start: str
    effective_end: str
    selected_constituents: tuple[str, ...]
    weights: tuple[float, ...]
    transition_traded_notional: float
    transition_cost: float


@dataclass(frozen=True, slots=True)
class WalkForwardOOSResult:
    """One continuous investable OOS ledger plus existing Portfolio metrics."""

    ledger: PortfolioLedger
    metrics: PortfolioMetricReport
    periods: tuple[WalkForwardOOSPeriodAudit, ...]
    execution_policy: str = WALK_FORWARD_OOS_EXECUTION_POLICY
    gap_policy: str = WALK_FORWARD_OOS_GAP_POLICY
    return_component_policy: str = WALK_FORWARD_OOS_RETURN_COMPONENT_POLICY
    contract_version: str = WALK_FORWARD_OOS_LEDGER_CONTRACT_VERSION


def run_continuous_oos_ledger(
    evaluations: Sequence[WalkForwardEvaluation],
    config: SimulationConfig,
    *,
    name: str = "Walk-Forward OOS",
) -> WalkForwardOOSResult:
    """Execute frozen decisions as one continuous TWD OOS portfolio history.

    Supported v1 state is intentionally narrow and exact:

    - ResearchDataset total returns are treated as reinvested total returns;
    - no external contribution/withdrawal schedule;
    - no leverage/debt state;
    - Portfolio v3 periodic/threshold rebalance and transaction-cost semantics
      remain available inside each Evaluation segment;
    - between Evaluation windows no market return is invented.  The last audited
      equity/allocation state is carried flat until the next segment's first
      effective valuation, where the next frozen target is applied.
    """

    items = tuple(evaluations)
    if not items:
        raise ValueError("at least one Walk-Forward Evaluation segment is required")
    _validate_supported_config(config)

    periods = tuple(item.decision.period for item in items)
    validate_period_schedule(periods)

    validated: list[tuple[WalkForwardEvaluation, ResearchDataset, pd.DataFrame]] = []
    all_symbols: list[str] = []
    seen_symbols: set[str] = set()
    for item in items:
        # export_payload rechecks the immutable decision hash before execution.
        item.decision.export_payload()
        dataset = validate_evaluation_dataset(
            decision=item.decision,
            evaluation_dataset=item.evaluation_dataset,
        )
        levels = _selected_levels(item.decision, dataset)
        validated.append((item, dataset, levels))
        for symbol in item.decision.selected_constituents:
            if symbol not in seen_symbols:
                seen_symbols.add(symbol)
                all_symbols.append(symbol)

    union_symbols = tuple(all_symbols)
    equity_parts: list[pd.Series] = []
    daily_return_parts: list[pd.Series] = []
    external_flow_parts: list[pd.Series] = []
    income_parts: list[pd.Series] = []
    cumulative_income_parts: list[pd.Series] = []
    cash_parts: list[pd.Series] = []
    debt_parts: list[pd.Series] = []
    gross_parts: list[pd.Series] = []
    allocation_parts: list[pd.DataFrame] = []
    events: list[LedgerEvent] = []
    warnings: list[str] = []
    audits: list[WalkForwardOOSPeriodAudit] = []
    total_transaction_costs = 0.0
    total_borrowing_costs = 0.0
    total_rebalance_count = 0
    liquidated = False

    previous_decision: DecisionSnapshot | None = None
    current_initial_amount = float(config.initial_amount)

    for position, (item, dataset, levels) in enumerate(validated):
        decision = item.decision
        transition_traded_notional = 0.0
        transition_cost = 0.0
        transition_return = 0.0

        if position > 0:
            previous_equity = float(equity_parts[-1].iloc[-1])
            previous_gross = float(gross_parts[-1].iloc[-1])
            if previous_equity <= _EPSILON:
                raise ValueError("continuous OOS equity was depleted before the next decision")

            previous_allocation = (
                allocation_parts[-1]
                .iloc[-1]
                .reindex(union_symbols, fill_value=0.0)
                .to_numpy(dtype=float)
            )
            previous_assets = previous_allocation * previous_gross
            target_weights = _union_weight_vector(decision, union_symbols)
            target_assets, target_debt, target_cash, transition_cost, transition_traded_notional = _rebalance(
                previous_assets,
                0.0,
                0.0,
                target_weights,
                config.leverage,
                config.transaction_cost_bps,
            )
            if abs(target_debt) > _EPSILON or abs(target_cash) > _EPSILON:
                raise ValueError("Walk-Forward v1 transition produced unsupported debt/cash state")
            current_initial_amount = float(target_assets.sum())
            if current_initial_amount <= _EPSILON:
                raise ValueError("inter-decision transition depleted continuous OOS equity")
            transition_return = current_initial_amount / previous_equity - 1.0
            total_transaction_costs += float(transition_cost)
            total_rebalance_count += 1
            events.append(
                LedgerEvent(
                    date=levels.index[0].date().isoformat(),
                    type="walk_forward_transition",
                    details={
                        "period_id": decision.period.period_id,
                        "from_decision_hash": (
                            previous_decision.decision_hash if previous_decision else None
                        ),
                        "to_decision_hash": decision.decision_hash,
                        "traded_notional": float(transition_traded_notional),
                        "transaction_cost": float(transition_cost),
                        "execution_policy": WALK_FORWARD_OOS_EXECUTION_POLICY,
                        "gap_policy": WALK_FORWARD_OOS_GAP_POLICY,
                    },
                )
            )

        segment_config = replace(config, initial_amount=current_initial_amount)
        portfolio = PortfolioSpec.from_weights(
            _segment_portfolio_name(name, decision.period.period_id),
            dict(zip(decision.selected_constituents, decision.weights, strict=True)),
        )
        histories = _histories_from_research_levels(levels, dataset)
        segment = simulate_portfolio_ledger(portfolio, histories, segment_config)

        segment_daily_returns = segment.daily_returns.copy()
        if position > 0:
            segment_daily_returns.iloc[0] = transition_return

        equity_parts.append(segment.equity.copy())
        daily_return_parts.append(segment_daily_returns)
        external_flow_parts.append(segment.external_flows.copy())
        income_parts.append(segment.income.copy())
        cumulative_income_parts.append(segment.cumulative_income.copy())
        cash_parts.append(segment.cash.copy())
        debt_parts.append(segment.debt.copy())
        gross_parts.append(segment.gross_exposure.copy())
        allocation_parts.append(
            segment.allocation_history.reindex(columns=union_symbols, fill_value=0.0)
        )
        events.extend(segment.events)
        warnings.extend(segment.warnings)
        total_transaction_costs += float(segment.transaction_costs)
        total_borrowing_costs += float(segment.borrowing_costs)
        total_rebalance_count += int(segment.rebalance_count)
        liquidated = liquidated or bool(segment.liquidated)

        audits.append(
            WalkForwardOOSPeriodAudit(
                period_id=decision.period.period_id,
                decision_hash=decision.decision_hash,
                evaluation_dataset_hash=dataset.dataset_hash,
                requested_start=dataset.requested_start.isoformat(),
                requested_end=dataset.requested_end.isoformat(),
                effective_start=levels.index[0].date().isoformat(),
                effective_end=levels.index[-1].date().isoformat(),
                selected_constituents=decision.selected_constituents,
                weights=decision.weights,
                transition_traded_notional=float(transition_traded_notional),
                transition_cost=float(transition_cost),
            )
        )
        previous_decision = decision
        current_initial_amount = float(segment.equity.iloc[-1])

    equity = _concat_series(equity_parts, "equity")
    daily_returns = _concat_series(daily_return_parts, "daily_return")
    external_flows = _concat_series(external_flow_parts, "external_flow")
    income = _concat_series(income_parts, "income")
    cash = _concat_series(cash_parts, "cash")
    debt = _concat_series(debt_parts, "debt")
    gross = _concat_series(gross_parts, "gross_exposure")
    allocations = pd.concat(allocation_parts).sort_index()
    _require_unique_increasing_index(allocations.index)

    # ResearchDataset total-return mode has no separate income attribution.  Keep
    # this explicit instead of summing period-local counters that each begin at 0.
    cumulative_income = pd.Series(0.0, index=equity.index, name="cumulative_income")
    if any(abs(float(value)) > _EPSILON for value in income.to_numpy(dtype=float)):
        raise ValueError("ResearchDataset total-return OOS mode produced unexpected cash income")

    return_index = (1.0 + daily_returns).cumprod().rename("return_index")
    expected_equity = float(config.initial_amount) * return_index
    if not np.allclose(
        equity.to_numpy(dtype=float),
        expected_equity.to_numpy(dtype=float),
        rtol=1e-10,
        atol=1e-8,
    ):
        raise ValueError("continuous OOS equity and time-weighted return index diverged")

    final_decision = validated[-1][0].decision
    ledger = PortfolioLedger(
        name=name,
        symbols=union_symbols,
        target_allocation=dict(
            zip(final_decision.selected_constituents, final_decision.weights, strict=True)
        ),
        equity=equity,
        return_index=return_index,
        daily_returns=daily_returns,
        external_flows=external_flows,
        income=income,
        cumulative_income=cumulative_income,
        cash=cash,
        debt=debt,
        gross_exposure=gross,
        allocation_history=allocations,
        transaction_costs=total_transaction_costs,
        borrowing_costs=total_borrowing_costs,
        rebalance_count=total_rebalance_count,
        events=events,
        warnings=list(dict.fromkeys(warnings)),
        liquidated=liquidated,
        contract_version=(
            f"{PORTFOLIO_LEDGER_CONTRACT_VERSION}+{WALK_FORWARD_OOS_LEDGER_CONTRACT_VERSION}"
        ),
    )
    metrics = compute_metric_report(ledger, config)
    return WalkForwardOOSResult(
        ledger=ledger,
        metrics=metrics,
        periods=tuple(audits),
    )


def _segment_portfolio_name(name: str, period_id: str) -> str:
    """Bound execution metadata without altering semantic period identity."""

    raw = f"{name}:{period_id}"
    if len(raw) <= _PORTFOLIO_NAME_LIMIT:
        return raw
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:_SEGMENT_NAME_DIGEST_LENGTH]
    prefix_length = _PORTFOLIO_NAME_LIMIT - _SEGMENT_NAME_DIGEST_LENGTH - 1
    return f"{raw[:prefix_length]}:{digest}"


def _validate_supported_config(config: SimulationConfig) -> None:
    if not config.reinvest_distributions:
        raise ValueError(
            "Walk-Forward OOS v1 requires reinvest_distributions=True because "
            "ResearchDataset exposes total-return levels only"
        )
    if config.cashflow.type != CashflowType.NONE:
        raise ValueError("Walk-Forward OOS v1 does not support external cashflows")
    if config.leverage.type != LeverageType.NONE:
        raise ValueError("Walk-Forward OOS v1 does not support leverage/debt state")


def _selected_levels(
    decision: DecisionSnapshot,
    dataset: ResearchDataset,
) -> pd.DataFrame:
    selected = decision.selected_constituents
    if not selected:
        raise ValueError("Walk-Forward decision contains no selected constituents")
    missing = [symbol for symbol in selected if symbol not in dataset.daily_levels_twd.columns]
    if missing:
        raise ValueError("selected OOS levels are missing: " + ", ".join(missing))
    levels = dataset.daily_levels_twd.loc[:, list(selected)].copy()
    if len(levels) < 2:
        raise ValueError("each OOS segment requires at least two effective valuation dates")
    values = levels.to_numpy(dtype=float)
    if not np.isfinite(values).all() or bool((values <= 0.0).any()):
        raise ValueError("selected OOS TWD levels must be finite and positive")
    _require_unique_increasing_index(levels.index)
    return levels


def _histories_from_research_levels(
    levels: pd.DataFrame,
    dataset: ResearchDataset,
) -> dict[str, TWDAssetHistory]:
    histories: dict[str, TWDAssetHistory] = {}
    for symbol in levels.columns:
        series = pd.to_numeric(levels[symbol], errors="coerce").astype(float)
        daily = (
            series.pct_change(fill_method=None)
            .fillna(0.0)
            .rename("daily_return")
        )
        fx = pd.Series(1.0, index=series.index, dtype=float, name="fx_to_twd")
        valuation = TWDValuation(
            source_currency="TWD",
            native_adjusted_close=series.rename("native_adjusted_close"),
            fx_to_twd=fx,
            adjusted_close_twd=series.rename("adjusted_close_twd"),
            daily_returns=daily,
        )
        metadata = dataset.asset_metadata.get(symbol, {})
        corporate_action_audit = metadata.get("corporate_action_audit")
        histories[symbol] = TWDAssetHistory(
            symbol=symbol,
            quote_currency="TWD",
            valuation=valuation,
            corporate_action_audit=(
                dict(corporate_action_audit)
                if isinstance(corporate_action_audit, dict)
                else None
            ),
            fx_audit={"method": "research-dataset-twd-identity"},
            raw_quote_currency="TWD",
            native_price_scale=1.0,
            return_components=total_only_components(series, source_currency="TWD"),
        )
    return histories


def _union_weight_vector(
    decision: DecisionSnapshot,
    union_symbols: tuple[str, ...],
) -> np.ndarray:
    by_symbol = dict(zip(decision.selected_constituents, decision.weights, strict=True))
    vector = np.asarray([by_symbol.get(symbol, 0.0) for symbol in union_symbols], dtype=float)
    if not np.isfinite(vector).all() or bool((vector < 0.0).any()):
        raise ValueError("Walk-Forward target weights must be finite and non-negative")
    if not np.isclose(float(vector.sum()), 1.0, rtol=0.0, atol=1e-10):
        raise ValueError("Walk-Forward target weights must sum to one")
    return vector


def _concat_series(parts: list[pd.Series], name: str) -> pd.Series:
    result = pd.concat(parts).sort_index().astype(float).rename(name)
    _require_unique_increasing_index(result.index)
    if not np.isfinite(result.to_numpy(dtype=float)).all():
        raise ValueError(f"continuous OOS {name} contains non-finite values")
    return result


def _require_unique_increasing_index(index: pd.Index) -> None:
    dates = pd.DatetimeIndex(pd.to_datetime(index))
    if dates.has_duplicates:
        raise ValueError("continuous OOS valuation dates must be unique")
    if not dates.is_monotonic_increasing:
        raise ValueError("continuous OOS valuation dates must increase")
