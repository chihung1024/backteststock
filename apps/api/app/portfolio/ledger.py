"""Path-dependent portfolio ledger on audited daily TWD return components."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Mapping

import numpy as np
import pandas as pd

from apps.api.app.data.history_service import TWDAssetHistory
from apps.api.app.portfolio.models import (
    CashflowTiming,
    CashflowType,
    ExposureMaintenanceMode,
    LedgerEvent,
    LeverageConfig,
    LeverageType,
    PortfolioSpec,
    RebalanceFrequency,
    SimulationConfig,
    WEIGHT_TOLERANCE,
)

PORTFOLIO_LEDGER_CONTRACT_VERSION = "portfolio-ledger-twd-2026-08-27.2"
_EPSILON = 1e-12
_TRADE_SOLVER_TOLERANCE = 1e-10
_TRADE_SOLVER_MAX_ITERATIONS = 64


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


@dataclass(frozen=True, slots=True)
class ExposurePolicy:
    """One ledger exposure policy derived from portfolio weights + legacy config."""

    target_exposures: np.ndarray
    target_asset_mix: np.ndarray
    target_gross_ratio: float
    target_cash_ratio: float
    fixed_debt: bool


@dataclass(slots=True)
class PortfolioLedger:
    # Keep the established constructor prefix stable. Quant fixtures and
    # Walk-Forward OOS construct this shared ledger directly; new exposure
    # diagnostics therefore remain optional and derive from existing truth.
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
    target_asset_mix: dict[str, float] | None = None
    target_gross_exposure_ratio: float | None = None
    target_cash_allocation: float | None = None
    net_exposure: pd.Series | None = None
    gross_exposure_ratio: pd.Series | None = None
    net_exposure_ratio: pd.Series | None = None
    exposure_reset_count: int = 0

    def __post_init__(self) -> None:
        target_gross = (
            float(sum(self.target_allocation.values()))
            if self.target_gross_exposure_ratio is None
            else float(self.target_gross_exposure_ratio)
        )
        self.target_gross_exposure_ratio = target_gross
        if self.target_asset_mix is None:
            if target_gross > _EPSILON:
                self.target_asset_mix = {
                    symbol: float(self.target_allocation.get(symbol, 0.0)) / target_gross
                    for symbol in self.symbols
                }
            else:
                self.target_asset_mix = {symbol: 0.0 for symbol in self.symbols}
        if self.target_cash_allocation is None:
            self.target_cash_allocation = max(1.0 - target_gross, 0.0)

        if self.net_exposure is None:
            self.net_exposure = self.gross_exposure.astype(float).copy().rename(
                "net_exposure"
            )
        if self.gross_exposure_ratio is None:
            self.gross_exposure_ratio = _derive_exposure_ratio(
                self.gross_exposure,
                self.equity,
                "gross_exposure_ratio",
            )
        if self.net_exposure_ratio is None:
            self.net_exposure_ratio = _derive_exposure_ratio(
                self.net_exposure,
                self.equity,
                "net_exposure_ratio",
            )

    @property
    def final_allocation(self) -> dict[str, float]:
        if self.allocation_history.empty:
            return {symbol: 0.0 for symbol in self.symbols}
        row = self.allocation_history.iloc[-1]
        return {symbol: float(row.get(symbol, 0.0)) for symbol in self.symbols}


def _derive_exposure_ratio(
    exposure: pd.Series,
    equity: pd.Series,
    name: str,
) -> pd.Series:
    aligned_exposure = exposure.reindex(equity.index).astype(float)
    aligned_equity = equity.astype(float)
    result = pd.Series(0.0, index=equity.index, dtype=float, name=name)
    valid = aligned_equity > _EPSILON
    result.loc[valid] = aligned_exposure.loc[valid] / aligned_equity.loc[valid]
    return result


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

    Asset weights are equity-relative target exposures. Totals below 1.0 leave
    residual cash; totals above 1.0 create margin-financed gross exposure.
    Market movement alone never changes shares or loan principal. Exposure
    maintenance is an explicit policy: margin-band repair is the default for
    financed portfolios, while daily constant exposure remains opt-in.
    """

    symbols = portfolio.symbols
    weights = np.asarray(portfolio.weights, dtype=float)
    policy = _exposure_policy(weights, config.leverage)
    aligned = align_portfolio_components(histories, symbols)
    index = aligned.total_returns.index
    execution_eligible = _common_execution_eligibility(index, histories, symbols)

    asset_values, debt, cash = _target_state(
        config.initial_amount,
        policy,
        config.leverage,
    )
    initial_liquidation_reason = _liquidation_reason(
        asset_values,
        cash,
        debt,
        config.leverage.maintenance_margin_percent,
    )
    if initial_liquidation_reason is not None:
        raise ValueError(
            "initial portfolio exposure violates liquidation guard: "
            f"{initial_liquidation_reason}"
        )
    cumulative_income_value = 0.0
    transaction_costs = 0.0
    borrowing_costs = 0.0
    rebalance_count = 0
    exposure_reset_count = 0
    liquidated = False
    pending_band_repair: np.ndarray | None = None
    pending_band_signal_date: str | None = None
    events: list[LedgerEvent] = []
    warnings: list[str] = []

    equity_series = pd.Series(index=index, dtype=float, name="equity")
    return_index = pd.Series(1.0, index=index, dtype=float, name="return_index")
    daily_returns = pd.Series(0.0, index=index, dtype=float, name="daily_return")
    external_flows = pd.Series(0.0, index=index, dtype=float, name="external_flow")
    income = pd.Series(0.0, index=index, dtype=float, name="income")
    cumulative_income = pd.Series(
        0.0,
        index=index,
        dtype=float,
        name="cumulative_income",
    )
    cash_series = pd.Series(0.0, index=index, dtype=float, name="cash")
    debt_series = pd.Series(0.0, index=index, dtype=float, name="debt")
    gross_series = pd.Series(0.0, index=index, dtype=float, name="gross_exposure")
    net_series = pd.Series(0.0, index=index, dtype=float, name="net_exposure")
    gross_ratio_series = pd.Series(
        0.0,
        index=index,
        dtype=float,
        name="gross_exposure_ratio",
    )
    net_ratio_series = pd.Series(
        0.0,
        index=index,
        dtype=float,
        name="net_exposure_ratio",
    )
    allocations = pd.DataFrame(0.0, index=index, columns=list(symbols), dtype=float)

    equity_series.iloc[0] = config.initial_amount
    cash_series.iloc[0] = cash
    debt_series.iloc[0] = debt
    _record_exposure_state(
        0,
        asset_values,
        config.initial_amount,
        gross_series,
        net_series,
        gross_ratio_series,
        net_ratio_series,
    )
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
        eligible=execution_eligible,
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
                net_series,
                gross_ratio_series,
                net_ratio_series,
                allocations,
            )
            continue

        calendar_days = _calendar_days_between(index[position - 1], timestamp)

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
                policy,
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

        annual_interest_rate = config.leverage.annual_interest_rate_percent / 100.0
        interest = debt * annual_interest_rate * calendar_days / 365.2425
        if interest > 0.0:
            debt_before_interest = debt
            debt += interest
            borrowing_costs += interest
            events.append(
                LedgerEvent(
                    date=timestamp.date().isoformat(),
                    type="borrowing_interest",
                    details={
                        "amount": interest,
                        "debt_before_interest": debt_before_interest,
                        "debt_after_interest": debt,
                        "calendar_days": calendar_days,
                        "annual_interest_rate_percent": (
                            config.leverage.annual_interest_rate_percent
                        ),
                    },
                )
            )

        end_flow = 0.0
        pre_end_equity = _state_equity(asset_values, cash, debt)
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
                policy,
                config.leverage,
            )
            external_flows.iloc[position] += end_flow
            events.append(_flow_event(timestamp, end_flow, "end", requested, capped))

        liquidation_reason = _liquidation_reason(
            asset_values,
            cash,
            debt,
            config.leverage.maintenance_margin_percent,
        )
        if liquidation_reason is not None:
            asset_values, debt, cash = _liquidate(
                timestamp,
                asset_values,
                debt,
                cash,
                config.leverage.maintenance_margin_percent,
                liquidation_reason,
                events,
                warnings,
            )
            liquidated = True
        else:
            periodic = bool(rebalance_mask[position]) and (
                config.rebalancing.frequency != RebalanceFrequency.NONE
            )
            threshold = False
            if (
                config.rebalancing.threshold_percent is not None
                and execution_eligible[position]
            ):
                threshold = _threshold_breached(
                    asset_values,
                    debt,
                    cash,
                    policy,
                    config.rebalancing.threshold_percent / 100.0,
                )

            if periodic or threshold:
                trigger = (
                    "periodic_and_threshold"
                    if periodic and threshold
                    else ("periodic" if periodic else "threshold")
                )
                gross_before = _gross_exposure(asset_values)
                debt_before = debt
                asset_values, debt, cash, cost, traded_notional = _rebalance(
                    asset_values,
                    debt,
                    cash,
                    policy,
                    config.leverage,
                    config.transaction_cost_bps,
                )
                transaction_costs += cost
                rebalance_count += 1
                pending_band_repair = None
                pending_band_signal_date = None
                events.append(
                    LedgerEvent(
                        date=timestamp.date().isoformat(),
                        type="rebalance",
                        details={
                            "trigger": trigger,
                            "traded_notional": traded_notional,
                            "transaction_cost": cost,
                            "gross_exposure_before": gross_before,
                            "gross_exposure_after": _gross_exposure(asset_values),
                            "target_gross_ratio": policy.target_gross_ratio,
                            "target_cash_ratio": policy.target_cash_ratio,
                            "debt_before": debt_before,
                            "target_debt": debt,
                            "execution_clock": "common_native_market_observation",
                        },
                    )
                )
            else:
                maintenance_mode = config.exposure_maintenance.mode
                financed = (
                    not policy.fixed_debt
                    and policy.target_gross_ratio > 1.0 + WEIGHT_TOLERANCE
                )
                if (
                    financed
                    and maintenance_mode == ExposureMaintenanceMode.DAILY
                    and execution_eligible[position]
                ):
                    gross_before = _gross_exposure(asset_values)
                    debt_before = debt
                    (
                        asset_values,
                        debt,
                        cash,
                        cost,
                        traded_notional,
                    ) = _reset_gross_exposure(
                        asset_values,
                        debt,
                        cash,
                        policy,
                        config.transaction_cost_bps,
                    )
                    transaction_costs += cost
                    if traded_notional > _EPSILON:
                        exposure_reset_count += 1
                        events.append(
                            LedgerEvent(
                                date=timestamp.date().isoformat(),
                                type="exposure_reset",
                                details={
                                    "mode": "daily_constant_exposure",
                                    "target_gross_ratio": policy.target_gross_ratio,
                                    "gross_exposure_before": gross_before,
                                    "gross_exposure_after": _gross_exposure(asset_values),
                                    "debt_before": debt_before,
                                    "debt_after": debt,
                                    "traded_notional": traded_notional,
                                    "transaction_cost": cost,
                                    "asset_allocation_preserved": True,
                                    "execution_clock": "common_native_market_observation",
                                },
                            )
                        )
                elif financed and maintenance_mode == ExposureMaintenanceMode.BAND:
                    if pending_band_repair is not None and execution_eligible[position]:
                        gross_before = _gross_exposure(asset_values)
                        debt_before = debt
                        breached_symbols = [
                            symbol
                            for symbol, breached in zip(
                                symbols, pending_band_repair, strict=True
                            )
                            if breached
                        ]
                        (
                            asset_values,
                            debt,
                            cash,
                            cost,
                            traded_notional,
                        ) = _repair_exposure_band(
                            asset_values,
                            debt,
                            cash,
                            policy,
                            pending_band_repair,
                            config.transaction_cost_bps,
                        )
                        transaction_costs += cost
                        if traded_notional > _EPSILON:
                            exposure_reset_count += 1
                            events.append(
                                LedgerEvent(
                                    date=timestamp.date().isoformat(),
                                    type="exposure_band_repair",
                                    details={
                                        "signal_date": pending_band_signal_date,
                                        "breached_symbols": breached_symbols,
                                        "tolerance_percent": config.exposure_maintenance.tolerance_percent,
                                        "gross_exposure_before": gross_before,
                                        "gross_exposure_after": _gross_exposure(asset_values),
                                        "debt_before": debt_before,
                                        "debt_after": debt,
                                        "traded_notional": traded_notional,
                                        "transaction_cost": cost,
                                        "repair_scope": "breached_assets_only",
                                        "execution_clock": "next_common_native_market_observation",
                                    },
                                )
                            )
                        pending_band_repair = None
                        pending_band_signal_date = None
                    elif pending_band_repair is None:
                        breached, deviations = _exposure_band_breaches(
                            asset_values,
                            debt,
                            cash,
                            policy,
                            config.exposure_maintenance.tolerance_percent / 100.0,
                        )
                        if bool(breached.any()):
                            pending_band_repair = breached
                            pending_band_signal_date = timestamp.date().isoformat()
                            events.append(
                                LedgerEvent(
                                    date=pending_band_signal_date,
                                    type="exposure_band_signal",
                                    details={
                                        "breached_symbols": [
                                            symbol
                                            for symbol, flag in zip(
                                                symbols, breached, strict=True
                                            )
                                            if flag
                                        ],
                                        "relative_deviations": {
                                            symbol: float(deviation)
                                            for symbol, deviation in zip(
                                                symbols, deviations, strict=True
                                            )
                                        },
                                        "tolerance_percent": config.exposure_maintenance.tolerance_percent,
                                        "execution_policy": "next_common_native_market_observation",
                                    },
                                )
                            )

            liquidation_reason = _liquidation_reason(
                asset_values,
                cash,
                debt,
                config.leverage.maintenance_margin_percent,
            )
            if liquidation_reason is not None:
                asset_values, debt, cash = _liquidate(
                    timestamp,
                    asset_values,
                    debt,
                    cash,
                    config.leverage.maintenance_margin_percent,
                    liquidation_reason,
                    events,
                    warnings,
                )
                liquidated = True

        final_equity = _state_equity(asset_values, cash, debt)
        numerator = final_equity - end_flow
        strategy_return = (
            numerator / denominator - 1.0 if denominator > _EPSILON else 0.0
        )
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
        _record_exposure_state(
            position,
            asset_values,
            final_equity,
            gross_series,
            net_series,
            gross_ratio_series,
            net_ratio_series,
        )
        _record_allocations(allocations, position, asset_values)

    warnings = list(dict.fromkeys(warnings))
    return PortfolioLedger(
        name=portfolio.name,
        symbols=symbols,
        target_allocation=portfolio.target_allocation,
        target_asset_mix=portfolio.target_asset_mix,
        target_gross_exposure_ratio=policy.target_gross_ratio,
        target_cash_allocation=policy.target_cash_ratio,
        equity=equity_series,
        return_index=return_index,
        daily_returns=daily_returns,
        external_flows=external_flows,
        income=income,
        cumulative_income=cumulative_income,
        cash=cash_series,
        debt=debt_series,
        gross_exposure=gross_series,
        net_exposure=net_series,
        gross_exposure_ratio=gross_ratio_series,
        net_exposure_ratio=net_ratio_series,
        allocation_history=allocations,
        transaction_costs=transaction_costs,
        borrowing_costs=borrowing_costs,
        rebalance_count=rebalance_count,
        exposure_reset_count=exposure_reset_count,
        events=events,
        warnings=warnings,
        liquidated=liquidated,
    )


def _exposure_policy(
    weights: np.ndarray,
    leverage: LeverageConfig,
) -> ExposurePolicy:
    input_gross = float(weights.sum())
    if (
        abs(input_gross - 1.0) > WEIGHT_TOLERANCE
        and leverage.type != LeverageType.NONE
    ):
        raise ValueError(
            "weight-defined cash/leverage exposure cannot be combined with "
            "explicit fixed-ratio or fixed-debt leverage"
        )

    if leverage.type == LeverageType.FIXED_RATIO:
        target_exposures = weights * leverage.ratio
    else:
        target_exposures = weights.copy()

    target_gross = float(target_exposures.sum())
    target_mix = target_exposures / target_gross
    target_cash = (
        max(1.0 - target_gross, 0.0)
        if leverage.type != LeverageType.FIXED_DEBT
        else 0.0
    )
    return ExposurePolicy(
        target_exposures=target_exposures,
        target_asset_mix=target_mix,
        target_gross_ratio=target_gross,
        target_cash_ratio=target_cash,
        fixed_debt=leverage.type == LeverageType.FIXED_DEBT,
    )


def _target_state(
    equity: float,
    policy: ExposurePolicy,
    leverage: LeverageConfig,
) -> tuple[np.ndarray, float, float]:
    equity = max(float(equity), 0.0)
    if policy.fixed_debt:
        debt = leverage.debt_amount
        gross = max(equity + debt, 0.0)
        return policy.target_asset_mix * gross, debt, 0.0

    assets = policy.target_exposures * equity
    if policy.target_gross_ratio <= 1.0 + WEIGHT_TOLERANCE:
        return assets, 0.0, policy.target_cash_ratio * equity
    debt = max((policy.target_gross_ratio - 1.0) * equity, 0.0)
    return assets, debt, 0.0


def _apply_external_flow(
    asset_values: np.ndarray,
    debt: float,
    cash: float,
    flow: float,
    policy: ExposurePolicy,
    leverage: LeverageConfig,
) -> tuple[np.ndarray, float, float]:
    if abs(flow) <= _EPSILON:
        return asset_values, debt, cash

    if flow > 0.0:
        if policy.fixed_debt:
            asset_values += policy.target_asset_mix * flow
        else:
            asset_values += policy.target_exposures * flow
            if policy.target_gross_ratio <= 1.0 + WEIGHT_TOLERANCE:
                cash += policy.target_cash_ratio * flow
            else:
                debt += (policy.target_gross_ratio - 1.0) * flow
        return asset_values, debt, cash

    withdrawal = -flow
    from_cash = min(max(cash, 0.0), withdrawal)
    cash -= from_cash
    remaining = withdrawal - from_cash
    if remaining <= _EPSILON:
        return asset_values, debt, cash

    equity = _state_equity(asset_values, cash, debt)
    if equity <= _EPSILON:
        return np.zeros_like(asset_values), 0.0, 0.0

    if (
        not policy.fixed_debt
        and policy.target_gross_ratio > 1.0 + WEIGHT_TOLERANCE
    ):
        fraction = min(remaining / equity, 1.0)
        asset_values *= 1.0 - fraction
        debt *= 1.0 - fraction
        return asset_values, debt, cash

    gross = _gross_exposure(asset_values)
    if gross > _EPSILON:
        asset_values *= max(1.0 - remaining / gross, 0.0)
    return asset_values, debt, cash


def _rebalance(
    asset_values: np.ndarray,
    debt: float,
    cash: float,
    policy: ExposurePolicy | np.ndarray,
    leverage: LeverageConfig,
    transaction_cost_bps: float,
) -> tuple[np.ndarray, float, float, float, float]:
    # Walk-Forward OOS already consumes this shared helper with a target
    # weight vector. Adapt that existing call immediately into the same
    # ExposurePolicy rather than creating a second rebalance authority.
    if not isinstance(policy, ExposurePolicy):
        policy = _exposure_policy(np.asarray(policy, dtype=float), leverage)
    equity = _state_equity(asset_values, cash, debt)
    if equity <= _EPSILON:
        return np.zeros_like(asset_values), 0.0, 0.0, 0.0, 0.0

    # Preserve the established 100%-invested / no-leverage transaction-cost
    # contract byte-for-byte in economic ordering.  The exact fixed-point solver
    # below is required only when target cash/debt itself depends on post-trade
    # equity (new weight-defined cash/leverage semantics and legacy leverage).
    if (
        leverage.type == LeverageType.NONE
        and abs(policy.target_gross_ratio - 1.0) <= WEIGHT_TOLERANCE
    ):
        preliminary = policy.target_exposures * equity
        traded_notional = float(np.abs(preliminary - asset_values).sum())
        cost = traded_notional * transaction_cost_bps / 10_000.0
        net_equity = max(equity - cost, 0.0)
        target = policy.target_exposures * net_equity
        return target, 0.0, 0.0, cost, traded_notional

    if policy.fixed_debt:
        preserved_debt = max(float(debt), 0.0)

        def target_builder(net_equity: float) -> tuple[np.ndarray, float, float]:
            target_gross = max(net_equity + preserved_debt, 0.0)
            return policy.target_asset_mix * target_gross, preserved_debt, 0.0
    else:
        def target_builder(net_equity: float) -> tuple[np.ndarray, float, float]:
            return _target_state(net_equity, policy, leverage)

    return _solve_trade_target(
        asset_values,
        equity,
        transaction_cost_bps,
        target_builder,
    )


def _reset_gross_exposure(
    asset_values: np.ndarray,
    debt: float,
    cash: float,
    policy: ExposurePolicy,
    transaction_cost_bps: float,
) -> tuple[np.ndarray, float, float, float, float]:
    target_ratio = policy.target_gross_ratio
    if abs(target_ratio - 1.0) <= WEIGHT_TOLERANCE or policy.fixed_debt:
        return asset_values, debt, cash, 0.0, 0.0

    equity = _state_equity(asset_values, cash, debt)
    if equity <= _EPSILON:
        return np.zeros_like(asset_values), 0.0, max(equity, 0.0), 0.0, 0.0

    current_gross = _gross_exposure(asset_values)
    if current_gross > _EPSILON:
        current_mix = asset_values / current_gross
    else:
        current_mix = policy.target_asset_mix
    preserved_cash = max(cash, 0.0)

    def target_builder(net_equity: float) -> tuple[np.ndarray, float, float]:
        target_gross = target_ratio * net_equity
        target_assets = current_mix * target_gross
        if target_ratio < 1.0 - WEIGHT_TOLERANCE:
            target_cash = max(net_equity - target_gross, 0.0)
            return target_assets, 0.0, target_cash
        target_debt = target_gross + preserved_cash - net_equity
        return target_assets, max(target_debt, 0.0), preserved_cash

    return _solve_trade_target(
        asset_values,
        equity,
        transaction_cost_bps,
        target_builder,
    )


def _exposure_band_breaches(
    asset_values: np.ndarray,
    debt: float,
    cash: float,
    policy: ExposurePolicy,
    tolerance: float,
) -> tuple[np.ndarray, np.ndarray]:
    """Return equity-relative exposure breaches and their relative deviations."""

    equity = _state_equity(asset_values, cash, debt)
    deviations = np.zeros_like(policy.target_exposures, dtype=float)
    if equity <= _EPSILON:
        return np.zeros_like(policy.target_exposures, dtype=bool), deviations
    current_exposures = asset_values / equity
    deviations = np.abs(
        current_exposures / policy.target_exposures - 1.0
    )
    breached = deviations + _EPSILON >= tolerance
    return breached.astype(bool), deviations


def _repair_exposure_band(
    asset_values: np.ndarray,
    debt: float,
    cash: float,
    policy: ExposurePolicy,
    breached: np.ndarray,
    transaction_cost_bps: float,
) -> tuple[np.ndarray, float, float, float, float]:
    """Repair only breached equity-relative target exposures back to target."""

    mask = np.asarray(breached, dtype=bool)
    if mask.shape != asset_values.shape:
        raise ValueError("exposure-band repair mask must match portfolio assets")
    if not bool(mask.any()) or policy.fixed_debt:
        return asset_values, debt, cash, 0.0, 0.0
    equity = _state_equity(asset_values, cash, debt)
    if equity <= _EPSILON:
        return np.zeros_like(asset_values), 0.0, max(equity, 0.0), 0.0, 0.0

    current_assets = asset_values.copy()
    preserved_cash = max(cash, 0.0)

    def target_builder(net_equity: float) -> tuple[np.ndarray, float, float]:
        target_assets = current_assets.copy()
        target_assets[mask] = policy.target_exposures[mask] * net_equity
        target_debt = max(float(target_assets.sum()) + preserved_cash - net_equity, 0.0)
        return target_assets, target_debt, preserved_cash

    return _solve_trade_target(
        asset_values,
        equity,
        transaction_cost_bps,
        target_builder,
    )


def _solve_trade_target(
    current_assets: np.ndarray,
    pre_trade_equity: float,
    transaction_cost_bps: float,
    target_builder: Callable[[float], tuple[np.ndarray, float, float]],
) -> tuple[np.ndarray, float, float, float, float]:
    rate = transaction_cost_bps / 10_000.0
    cost = 0.0

    for _ in range(_TRADE_SOLVER_MAX_ITERATIONS):
        net_equity = pre_trade_equity - cost
        if net_equity <= _EPSILON:
            raise ValueError("transaction costs would exhaust portfolio equity")
        target_assets, target_debt, target_cash = target_builder(net_equity)
        traded_notional = float(np.abs(target_assets - current_assets).sum())
        next_cost = traded_notional * rate
        if abs(next_cost - cost) <= _TRADE_SOLVER_TOLERANCE * max(
            pre_trade_equity,
            1.0,
        ):
            cost = next_cost
            net_equity = pre_trade_equity - cost
            target_assets, target_debt, target_cash = target_builder(net_equity)
            traded_notional = float(np.abs(target_assets - current_assets).sum())
            final_cost = traded_notional * rate
            if abs(final_cost - cost) > 10 * _TRADE_SOLVER_TOLERANCE * max(
                pre_trade_equity,
                1.0,
            ):
                cost = final_cost
                continue
            return (
                target_assets,
                float(target_debt),
                float(target_cash),
                float(final_cost),
                traded_notional,
            )
        cost = next_cost

    raise ValueError("portfolio trade-cost solver did not converge")


def _threshold_breached(
    asset_values: np.ndarray,
    debt: float,
    cash: float,
    policy: ExposurePolicy,
    threshold: float,
) -> bool:
    gross = _gross_exposure(asset_values)
    if gross <= _EPSILON:
        return False

    current_mix = asset_values / gross
    return bool(np.max(np.abs(current_mix - policy.target_asset_mix)) >= threshold)


def _liquidation_reason(
    asset_values: np.ndarray,
    cash: float,
    debt: float,
    maintenance_margin_percent: float,
) -> str | None:
    gross = _gross_exposure(asset_values)
    equity = _state_equity(asset_values, cash, debt)
    if equity <= _EPSILON:
        if gross > _EPSILON or debt > _EPSILON:
            return "non_positive_equity"
        return None
    if debt <= _EPSILON or gross <= _EPSILON:
        return None
    margin_ratio = equity / gross * 100.0
    if margin_ratio < maintenance_margin_percent:
        return "maintenance_margin"
    return None


def _liquidate(
    timestamp: pd.Timestamp,
    asset_values: np.ndarray,
    debt: float,
    cash: float,
    maintenance_margin_percent: float,
    reason: str,
    events: list[LedgerEvent],
    warnings: list[str],
) -> tuple[np.ndarray, float, float]:
    equity = _state_equity(asset_values, cash, debt)
    gross = _gross_exposure(asset_values)
    margin_ratio = equity / gross * 100.0 if gross > _EPSILON else 100.0
    events.append(
        LedgerEvent(
            date=timestamp.date().isoformat(),
            type="margin_liquidation",
            details={
                "reason": reason,
                "equity": equity,
                "gross_exposure": gross,
                "debt": debt,
                "margin_percent": margin_ratio,
                "maintenance_margin_percent": maintenance_margin_percent,
            },
        )
    )
    warnings.append(
        f"maintenance-margin liquidation on {timestamp.date().isoformat()} "
        f"({reason})"
    )
    final_equity = max(equity, 0.0)
    return np.zeros_like(asset_values), 0.0, final_equity


def _state_equity(
    asset_values: np.ndarray,
    cash: float,
    debt: float,
) -> float:
    return float(asset_values.sum() + cash - debt)


def _gross_exposure(asset_values: np.ndarray) -> float:
    return float(np.abs(asset_values).sum())


def _net_exposure(asset_values: np.ndarray) -> float:
    return float(asset_values.sum())


def _record_exposure_state(
    position: int,
    asset_values: np.ndarray,
    equity: float,
    gross: pd.Series,
    net: pd.Series,
    gross_ratio: pd.Series,
    net_ratio: pd.Series,
) -> None:
    gross_value = _gross_exposure(asset_values)
    net_value = _net_exposure(asset_values)
    gross.iloc[position] = gross_value
    net.iloc[position] = net_value
    if equity > _EPSILON:
        gross_ratio.iloc[position] = gross_value / equity
        net_ratio.iloc[position] = net_value / equity
    else:
        gross_ratio.iloc[position] = 0.0
        net_ratio.iloc[position] = 0.0


def _calendar_days_between(previous: pd.Timestamp, current: pd.Timestamp) -> int:
    """Return actual elapsed calendar days for one daily valuation interval."""

    days = (current.date() - previous.date()).days
    if days <= 0:
        raise ValueError("aligned valuation dates must increase by calendar day")
    return days


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


def _common_execution_eligibility(
    index: pd.DatetimeIndex,
    histories: Mapping[str, TWDAssetHistory],
    symbols: tuple[str, ...],
) -> np.ndarray:
    """Return dates where every constituent has a fresh native-market quote.

    TWD valuation remains on the union price/FX calendar.  This mask is used
    only for trade execution.  Legacy/synthetic histories without provenance
    preserve the historical behavior by treating every valuation date as
    executable.
    """

    eligible = np.ones(len(index), dtype=bool)
    for symbol in symbols:
        history = histories.get(symbol)
        native_mask = (
            getattr(history.valuation, "native_observation_mask", None)
            if history is not None
            else None
        )
        if not isinstance(native_mask, pd.Series):
            return np.ones(len(index), dtype=bool)
        observed = (
            native_mask.reindex(index)
            .fillna(False)
            .astype(bool)
            .to_numpy(dtype=bool)
        )
        eligible &= observed
    return eligible


def _period_event_mask(
    index: pd.DatetimeIndex,
    frequency: str,
    *,
    beginning: bool,
    eligible: np.ndarray | None = None,
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

    if eligible is None:
        return mask
    execution = np.asarray(eligible, dtype=bool)
    if execution.shape != mask.shape:
        raise ValueError("execution eligibility mask must match valuation calendar")

    shifted = np.zeros(len(index), dtype=bool)
    positions = np.arange(len(index))
    for event_position in np.flatnonzero(mask):
        same_period = keys == keys[event_position]
        if beginning:
            candidates = positions[
                same_period & execution & (positions >= event_position)
            ]
            if len(candidates):
                shifted[int(candidates[0])] = True
        else:
            candidates = positions[
                same_period & execution & (positions <= event_position)
            ]
            if len(candidates):
                shifted[int(candidates[-1])] = True
    return shifted


def _record_allocations(
    frame: pd.DataFrame,
    position: int,
    asset_values: np.ndarray,
) -> None:
    gross = _gross_exposure(asset_values)
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
    net: pd.Series,
    gross_ratio: pd.Series,
    net_ratio: pd.Series,
    allocations: pd.DataFrame,
) -> None:
    equity.iloc[position] = max(float(equity.iloc[position - 1]), 0.0)
    return_index.iloc[position] = float(return_index.iloc[position - 1])
    cumulative_income.iloc[position] = float(cumulative_income.iloc[position - 1])
    cash.iloc[position] = equity.iloc[position]
    debt.iloc[position] = 0.0
    gross.iloc[position] = 0.0
    net.iloc[position] = 0.0
    gross_ratio.iloc[position] = 0.0
    net_ratio.iloc[position] = 0.0
    allocations.iloc[position] = 0.0
