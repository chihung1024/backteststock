"""Path-dependent portfolio ledger on audited daily TWD return components."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

import numpy as np
import pandas as pd

from apps.api.app.data.history_service import TWDAssetHistory
from apps.api.app.portfolio.models import (
    CashflowTiming,
    CashflowType,
    LedgerEvent,
    LeverageConfig,
    LeverageType,
    PortfolioSpec,
    RebalanceFrequency,
    SimulationConfig,
)

PORTFOLIO_LEDGER_CONTRACT_VERSION = "portfolio-ledger-twd-2026-08-04.1"
_EPSILON = 1e-12


@dataclass(frozen=True, slots=True)
class AlignedPortfolioComponents:
    total_returns: pd.DataFrame
    price_returns: pd.DataFrame
    distribution_returns: pd.DataFrame

    @property
    def start(self) -> pd.Timestamp:
        return self.total_returns.index[0]

    @property
    def end(self) -> pd.Timestamp:
        return self.total_returns.index[-1]


@dataclass(slots=True)
class PortfolioLedger:
    name: str
    symbols: tuple[str, ...]
    target_allocation: dict[str, float]
    equity: pd.Series
    return_index: pd.Series
    daily_returns: pd.Series
    external_flows: pd.Series
    income: pd.Series
    cumulative_income: pd.Series
    cash: pd.Series
    debt: pd.Series
    gross_exposure: pd.Series
    allocation_history: pd.DataFrame
    transaction_costs: float
    borrowing_costs: float
    rebalance_count: int
    events: list[LedgerEvent]
    warnings: list[str]
    liquidated: bool
    contract_version: str = PORTFOLIO_LEDGER_CONTRACT_VERSION

    @property
    def final_allocation(self) -> dict[str, float]:
        if self.allocation_history.empty:
            return {symbol: 0.0 for symbol in self.symbols}
        row = self.allocation_history.iloc[-1]
        return {symbol: float(row.get(symbol, 0.0)) for symbol in self.symbols}


def align_portfolio_components(
    histories: Mapping[str, TWDAssetHistory],
    symbols: tuple[str, ...],
) -> AlignedPortfolioComponents:
    """Align TWD component returns without inventing pre-observation history."""

    missing = [symbol for symbol in symbols if symbol not in histories]
    if missing:
        raise ValueError("missing TWD histories: " + ", ".join(missing))
    if not symbols:
        raise ValueError("at least one asset is required")

    starts = [histories[symbol].daily_returns.index[0] for symbol in symbols]
    ends = [histories[symbol].daily_returns.index[-1] for symbol in symbols]
    start = max(starts)
    end = min(ends)
    if start >= end:
        raise ValueError("selected assets do not have two overlapping valuation dates")

    calendar = pd.DatetimeIndex([])
    for symbol in symbols:
        calendar = calendar.union(histories[symbol].daily_returns.loc[start:end].index)
    calendar = calendar.sort_values().unique()
    if len(calendar) < 2:
        raise ValueError("selected assets have fewer than two aligned valuation dates")

    def frame(attribute: str) -> pd.DataFrame:
        values = {
            symbol: getattr(histories[symbol], attribute)
            .loc[start:end]
            .reindex(calendar)
            .fillna(0.0)
            for symbol in symbols
        }
        result = pd.DataFrame(values, index=calendar, dtype=float)
        result.iloc[0] = 0.0
        if not np.isfinite(result.to_numpy()).all():
            raise ValueError(f"aligned {attribute} contains non-finite returns")
        return result

    total = frame("daily_returns")
    price = frame("price_returns")
    distribution = frame("distribution_returns")
    residual = (total - price - distribution).abs().to_numpy()
    if residual.size and float(np.max(residual)) > 1e-10:
        raise ValueError("aligned TWD return components do not preserve their identity")
    if bool((distribution < -_EPSILON).any().any()):
        raise ValueError("distribution returns must be non-negative")
    return AlignedPortfolioComponents(
        total_returns=total,
        price_returns=price,
        distribution_returns=distribution,
    )


def simulate_portfolio_ledger(
    portfolio: PortfolioSpec,
    histories: Mapping[str, TWDAssetHistory],
    config: SimulationConfig,
) -> PortfolioLedger:
    """Run one portfolio under the published daily event-order contract.

    For every valuation interval the engine applies: beginning cashflow, market
    and distribution returns, debt interest, end cashflow, close-of-period or
    drift-triggered rebalancing, then maintenance-margin liquidation. External
    flows are removed from the time-weighted daily return at their actual timing.
    """

    symbols = portfolio.symbols
    weights = np.asarray(portfolio.weights, dtype=float)
    aligned = align_portfolio_components(histories, symbols)
    index = aligned.total_returns.index

    asset_values, debt = _target_exposure(config.initial_amount, weights, config.leverage)
    cash = 0.0
    cumulative_income_value = 0.0
    transaction_costs = 0.0
    borrowing_costs = 0.0
    rebalance_count = 0
    liquidated = False
    events: list[LedgerEvent] = []
    warnings: list[str] = []

    equity_series = pd.Series(index=index, dtype=float, name="equity")
    return_index = pd.Series(1.0, index=index, dtype=float, name="return_index")
    daily_returns = pd.Series(0.0, index=index, dtype=float, name="daily_return")
    external_flows = pd.Series(0.0, index=index, dtype=float, name="external_flow")
    income = pd.Series(0.0, index=index, dtype=float, name="income")
    cumulative_income = pd.Series(0.0, index=index, dtype=float, name="cumulative_income")
    cash_series = pd.Series(0.0, index=index, dtype=float, name="cash")
    debt_series = pd.Series(0.0, index=index, dtype=float, name="debt")
    gross_series = pd.Series(0.0, index=index, dtype=float, name="gross_exposure")
    allocations = pd.DataFrame(0.0, index=index, columns=list(symbols), dtype=float)

    equity_series.iloc[0] = config.initial_amount
    debt_series.iloc[0] = debt
    gross_series.iloc[0] = float(asset_values.sum())
    _record_allocations(allocations, 0, asset_values)

    beginning_flow_mask = _period_event_mask(
        index,
        config.cashflow.frequency.value,
        beginning=True,
    )
    end_flow_mask = _period_event_mask(
        index,
        config.cashflow.frequency.value,
        beginning=False,
    )
    rebalance_mask = _period_event_mask(
        index,
        config.rebalancing.frequency.value,
        beginning=False,
    )

    for position in range(1, len(index)):
        timestamp = index[position]
        previous_equity = float(equity_series.iloc[position - 1])
        if liquidated or previous_equity <= _EPSILON:
            _carry_liquidated_state(
                position,
                equity_series,
                return_index,
                cumulative_income,
                cash_series,
                debt_series,
                gross_series,
                allocations,
            )
            continue

        beginning_flow = 0.0
        if (
            config.cashflow.type != CashflowType.NONE
            and config.cashflow.timing == CashflowTiming.BEGINNING
            and beginning_flow_mask[position]
        ):
            requested = _cashflow_amount(config, timestamp, previous_equity, index[0])
            beginning_flow, capped = _cap_withdrawal(requested, previous_equity)
            if capped:
                warnings.append(
                    f"withdrawal on {timestamp.date().isoformat()} was capped at equity"
                )
            asset_values, debt, cash = _apply_external_flow(
                asset_values,
                debt,
                cash,
                beginning_flow,
                weights,
                config.leverage,
            )
            external_flows.iloc[position] += beginning_flow
            events.append(
                _flow_event(timestamp, beginning_flow, "beginning", requested, capped)
            )

        denominator = previous_equity + beginning_flow
        previous_assets = asset_values.copy()
        distribution_vector = aligned.distribution_returns.iloc[position].to_numpy()
        day_income = float(np.dot(previous_assets, distribution_vector))
        day_income = max(day_income, 0.0)
        income.iloc[position] = day_income
        cumulative_income_value += day_income

        chosen = (
            aligned.total_returns.iloc[position].to_numpy()
            if config.reinvest_distributions
            else aligned.price_returns.iloc[position].to_numpy()
        )
        asset_values *= 1.0 + np.nan_to_num(chosen, nan=0.0)
        if not config.reinvest_distributions:
            cash += day_income
            if day_income > _EPSILON:
                events.append(
                    LedgerEvent(
                        date=timestamp.date().isoformat(),
                        type="distribution_cash",
                        details={"amount": day_income},
                    )
                )

        interest = debt * (config.leverage.annual_interest_rate_percent / 100.0) / 365.2425
        if interest > 0.0:
            cash -= interest
            borrowing_costs += interest
            events.append(
                LedgerEvent(
                    date=timestamp.date().isoformat(),
                    type="borrowing_interest",
                    details={"amount": interest, "debt_before_interest": debt},
                )
            )

        end_flow = 0.0
        pre_end_equity = float(asset_values.sum() + cash - debt)
        if (
            config.cashflow.type != CashflowType.NONE
            and config.cashflow.timing == CashflowTiming.END
            and end_flow_mask[position]
        ):
            requested = _cashflow_amount(config, timestamp, pre_end_equity, index[0])
            end_flow, capped = _cap_withdrawal(requested, pre_end_equity)
            if capped:
                warnings.append(
                    f"withdrawal on {timestamp.date().isoformat()} was capped at equity"
                )
            asset_values, debt, cash = _apply_external_flow(
                asset_values,
                debt,
                cash,
                end_flow,
                weights,
                config.leverage,
            )
            external_flows.iloc[position] += end_flow
            events.append(_flow_event(timestamp, end_flow, "end", requested, capped))

        periodic = bool(rebalance_mask[position]) and (
            config.rebalancing.frequency != RebalanceFrequency.NONE
        )
        threshold = False
        if config.rebalancing.threshold_percent is not None:
            threshold = _threshold_breached(
                asset_values,
                weights,
                config.rebalancing.threshold_percent / 100.0,
            )
        if periodic or threshold:
            trigger = "periodic_and_threshold" if periodic and threshold else (
                "periodic" if periodic else "threshold"
            )
            asset_values, debt, cash, cost, traded_notional = _rebalance(
                asset_values,
                debt,
                cash,
                weights,
                config.leverage,
                config.transaction_cost_bps,
            )
            transaction_costs += cost
            rebalance_count += 1
            events.append(
                LedgerEvent(
                    date=timestamp.date().isoformat(),
                    type="rebalance",
                    details={
                        "trigger": trigger,
                        "traded_notional": traded_notional,
                        "transaction_cost": cost,
                        "target_debt": debt,
                    },
                )
            )

        final_equity = float(asset_values.sum() + cash - debt)
        gross = float(asset_values.sum())
        margin_ratio = final_equity / gross * 100.0 if gross > _EPSILON else 100.0
        if (
            config.leverage.type != LeverageType.NONE
            and margin_ratio < config.leverage.maintenance_margin_percent
        ):
            events.append(
                LedgerEvent(
                    date=timestamp.date().isoformat(),
                    type="margin_liquidation",
                    details={
                        "equity": final_equity,
                        "gross_exposure": gross,
                        "debt": debt,
                        "margin_percent": margin_ratio,
                        "maintenance_margin_percent": (
                            config.leverage.maintenance_margin_percent
                        ),
                    },
                )
            )
            warnings.append(
                f"maintenance-margin liquidation on {timestamp.date().isoformat()}"
            )
            final_equity = max(final_equity, 0.0)
            asset_values = np.zeros_like(asset_values)
            debt = 0.0
            cash = final_equity
            gross = 0.0
            liquidated = True

        numerator = final_equity - end_flow
        strategy_return = numerator / denominator - 1.0 if denominator > _EPSILON else 0.0
        if not np.isfinite(strategy_return):
            strategy_return = 0.0
        strategy_return = max(float(strategy_return), -1.0)

        equity_series.iloc[position] = final_equity
        daily_returns.iloc[position] = strategy_return
        return_index.iloc[position] = max(
            float(return_index.iloc[position - 1]) * (1.0 + strategy_return),
            0.0,
        )
        cumulative_income.iloc[position] = cumulative_income_value
        cash_series.iloc[position] = cash
        debt_series.iloc[position] = debt
        gross_series.iloc[position] = gross
        _record_allocations(allocations, position, asset_values)

    warnings = list(dict.fromkeys(warnings))
    return PortfolioLedger(
        name=portfolio.name,
        symbols=symbols,
        target_allocation=portfolio.target_allocation,
        equity=equity_series,
        return_index=return_index,
        daily_returns=daily_returns,
        external_flows=external_flows,
        income=income,
        cumulative_income=cumulative_income,
        cash=cash_series,
        debt=debt_series,
        gross_exposure=gross_series,
        allocation_history=allocations,
        transaction_costs=transaction_costs,
        borrowing_costs=borrowing_costs,
        rebalance_count=rebalance_count,
        events=events,
        warnings=warnings,
        liquidated=liquidated,
    )


def _target_exposure(
    equity: float,
    weights: np.ndarray,
    leverage: LeverageConfig,
) -> tuple[np.ndarray, float]:
    if leverage.type == LeverageType.FIXED_RATIO:
        debt = equity * (leverage.ratio - 1.0)
    elif leverage.type == LeverageType.FIXED_DEBT:
        debt = leverage.debt_amount
    else:
        debt = 0.0
    gross = max(equity + debt, 0.0)
    return weights * gross, debt


def _apply_external_flow(
    asset_values: np.ndarray,
    debt: float,
    cash: float,
    flow: float,
    weights: np.ndarray,
    leverage: LeverageConfig,
) -> tuple[np.ndarray, float, float]:
    if abs(flow) <= _EPSILON:
        return asset_values, debt, cash
    if flow > 0.0:
        if leverage.type == LeverageType.FIXED_RATIO:
            asset_values += weights * flow * leverage.ratio
            debt += flow * (leverage.ratio - 1.0)
        else:
            asset_values += weights * flow
        return asset_values, debt, cash

    withdrawal = -flow
    from_cash = min(max(cash, 0.0), withdrawal)
    cash -= from_cash
    remaining = withdrawal - from_cash
    if remaining <= _EPSILON:
        return asset_values, debt, cash

    equity = float(asset_values.sum() + cash - debt)
    if equity <= _EPSILON:
        return np.zeros_like(asset_values), 0.0, 0.0
    if leverage.type == LeverageType.FIXED_RATIO:
        fraction = min(remaining / equity, 1.0)
        asset_values *= 1.0 - fraction
        debt *= 1.0 - fraction
    else:
        gross = float(asset_values.sum())
        if gross > _EPSILON:
            asset_values *= max(1.0 - remaining / gross, 0.0)
    return asset_values, debt, cash


def _rebalance(
    asset_values: np.ndarray,
    debt: float,
    cash: float,
    weights: np.ndarray,
    leverage: LeverageConfig,
    transaction_cost_bps: float,
) -> tuple[np.ndarray, float, float, float, float]:
    equity = float(asset_values.sum() + cash - debt)
    if equity <= _EPSILON:
        return np.zeros_like(asset_values), 0.0, 0.0, 0.0, 0.0
    preliminary, _ = _target_exposure(equity, weights, leverage)
    traded_notional = float(np.abs(preliminary - asset_values).sum())
    cost = traded_notional * transaction_cost_bps / 10_000.0
    net_equity = max(equity - cost, 0.0)
    target, target_debt = _target_exposure(net_equity, weights, leverage)
    return target, target_debt, 0.0, cost, traded_notional


def _threshold_breached(
    asset_values: np.ndarray,
    target_weights: np.ndarray,
    threshold: float,
) -> bool:
    gross = float(asset_values.sum())
    if gross <= _EPSILON:
        return False
    current = asset_values / gross
    return bool(np.max(np.abs(current - target_weights)) >= threshold)


def _cashflow_amount(
    config: SimulationConfig,
    timestamp: pd.Timestamp,
    equity: float,
    start: pd.Timestamp,
) -> float:
    cashflow = config.cashflow
    years = max(int((timestamp - start).days / 365.2425), 0)
    growth = (1.0 + cashflow.annual_growth_rate_percent / 100.0) ** years
    if cashflow.type == CashflowType.PERCENT:
        return equity * cashflow.amount / 100.0 * growth
    return cashflow.amount * growth


def _cap_withdrawal(requested: float, equity: float) -> tuple[float, bool]:
    if requested >= 0.0:
        return requested, False
    available = max(equity, 0.0)
    actual = -min(-requested, available)
    return actual, actual != requested


def _period_event_mask(
    index: pd.DatetimeIndex,
    frequency: str,
    *,
    beginning: bool,
) -> np.ndarray:
    mask = np.zeros(len(index), dtype=bool)
    if frequency == "none" or len(index) < 2:
        return mask
    if frequency == "monthly":
        keys = index.year * 12 + index.month
    elif frequency == "quarterly":
        keys = index.year * 4 + index.quarter
    elif frequency == "semiannual":
        keys = index.year * 2 + ((index.month - 1) // 6)
    elif frequency == "annual":
        keys = index.year
    else:
        raise ValueError(f"unsupported event frequency: {frequency}")
    if beginning:
        mask[1:] = keys[1:] != keys[:-1]
    else:
        mask[:-1] = keys[:-1] != keys[1:]
    return mask


def _record_allocations(
    frame: pd.DataFrame,
    position: int,
    asset_values: np.ndarray,
) -> None:
    gross = float(asset_values.sum())
    if gross > _EPSILON:
        frame.iloc[position] = asset_values / gross
    else:
        frame.iloc[position] = 0.0


def _flow_event(
    timestamp: pd.Timestamp,
    amount: float,
    timing: str,
    requested: float,
    capped: bool,
) -> LedgerEvent:
    return LedgerEvent(
        date=timestamp.date().isoformat(),
        type="external_cashflow",
        details={
            "amount": amount,
            "requested_amount": requested,
            "timing": timing,
            "capped": capped,
            "direction": "contribution" if amount >= 0.0 else "withdrawal",
        },
    )


def _carry_liquidated_state(
    position: int,
    equity: pd.Series,
    return_index: pd.Series,
    cumulative_income: pd.Series,
    cash: pd.Series,
    debt: pd.Series,
    gross: pd.Series,
    allocations: pd.DataFrame,
) -> None:
    equity.iloc[position] = max(float(equity.iloc[position - 1]), 0.0)
    return_index.iloc[position] = float(return_index.iloc[position - 1])
    cumulative_income.iloc[position] = float(cumulative_income.iloc[position - 1])
    cash.iloc[position] = equity.iloc[position]
    debt.iloc[position] = 0.0
    gross.iloc[position] = 0.0
    allocations.iloc[position] = 0.0
