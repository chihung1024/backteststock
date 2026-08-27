"""Validated portfolio-ledger input and event models."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Mapping

WEIGHT_TOLERANCE = 1e-8
MAX_PORTFOLIOS = 5
MAX_ASSETS_PER_PORTFOLIO = 20
MAX_TARGET_GROSS_EXPOSURE = 5.0


class CashflowType(StrEnum):
    NONE = "none"
    FIXED = "fixed"
    PERCENT = "percent"


class CashflowFrequency(StrEnum):
    NONE = "none"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    ANNUAL = "annual"


class CashflowTiming(StrEnum):
    BEGINNING = "beginning"
    END = "end"


class RebalanceFrequency(StrEnum):
    NONE = "none"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    SEMIANNUAL = "semiannual"
    ANNUAL = "annual"


class LeverageType(StrEnum):
    NONE = "none"
    FIXED_RATIO = "fixed_ratio"
    FIXED_DEBT = "fixed_debt"


class ExposureMaintenanceMode(StrEnum):
    NONE = "none"
    BAND = "band"
    DAILY = "daily"


@dataclass(frozen=True, slots=True)
class AssetWeight:
    symbol: str
    weight: float

    def __post_init__(self) -> None:
        symbol = _normalize_symbol(self.symbol)
        weight = float(self.weight)
        if not symbol:
            raise ValueError("asset symbol is required")
        if (
            not math.isfinite(weight)
            or weight <= 0.0
            or weight > MAX_TARGET_GROSS_EXPOSURE
        ):
            raise ValueError(
                "asset weight must be a finite fraction in "
                f"(0, {MAX_TARGET_GROSS_EXPOSURE:g}]"
            )
        object.__setattr__(self, "symbol", symbol)
        object.__setattr__(self, "weight", weight)


@dataclass(frozen=True, slots=True)
class PortfolioSpec:
    name: str
    assets: tuple[AssetWeight, ...]

    def __post_init__(self) -> None:
        name = str(self.name or "").strip()
        assets = tuple(self.assets)
        if not name:
            raise ValueError("portfolio name is required")
        if len(name) > 60:
            raise ValueError("portfolio name cannot exceed 60 characters")
        if not 1 <= len(assets) <= MAX_ASSETS_PER_PORTFOLIO:
            raise ValueError(
                f"portfolio must contain 1 to {MAX_ASSETS_PER_PORTFOLIO} assets"
            )
        symbols = [asset.symbol for asset in assets]
        if len(symbols) != len(set(symbols)):
            raise ValueError("portfolio assets must be unique")
        total = sum(asset.weight for asset in assets)
        if (
            not math.isfinite(total)
            or total <= WEIGHT_TOLERANCE
            or total > MAX_TARGET_GROSS_EXPOSURE + WEIGHT_TOLERANCE
        ):
            raise ValueError(
                "portfolio target gross exposure must be in "
                f"(0, {MAX_TARGET_GROSS_EXPOSURE:g}]"
            )
        object.__setattr__(self, "name", name)
        object.__setattr__(self, "assets", assets)

    @classmethod
    def from_weights(cls, name: str, weights: Mapping[str, float]) -> PortfolioSpec:
        return cls(
            name=name,
            assets=tuple(
                AssetWeight(symbol=symbol, weight=weight)
                for symbol, weight in weights.items()
            ),
        )

    @property
    def symbols(self) -> tuple[str, ...]:
        return tuple(asset.symbol for asset in self.assets)

    @property
    def weights(self) -> tuple[float, ...]:
        return tuple(asset.weight for asset in self.assets)

    @property
    def target_gross_exposure(self) -> float:
        return float(sum(self.weights))

    @property
    def target_cash_allocation(self) -> float:
        return max(1.0 - self.target_gross_exposure, 0.0)

    @property
    def target_allocation(self) -> dict[str, float]:
        """Return user-entered equity-relative target exposures."""
        return {asset.symbol: asset.weight for asset in self.assets}

    @property
    def target_asset_mix(self) -> dict[str, float]:
        """Return asset-only composition normalized to 100% of invested gross."""
        gross = self.target_gross_exposure
        return {asset.symbol: asset.weight / gross for asset in self.assets}


@dataclass(frozen=True, slots=True)
class CashflowConfig:
    type: CashflowType = CashflowType.NONE
    amount: float = 0.0
    frequency: CashflowFrequency = CashflowFrequency.NONE
    timing: CashflowTiming = CashflowTiming.END
    annual_growth_rate_percent: float = 0.0

    def __post_init__(self) -> None:
        amount = float(self.amount)
        growth = float(self.annual_growth_rate_percent)
        if not math.isfinite(amount):
            raise ValueError("cashflow amount must be finite")
        if not math.isfinite(growth) or growth <= -100.0 or growth > 1_000.0:
            raise ValueError("cashflow annual growth must be in (-100, 1000]")
        if self.type == CashflowType.NONE:
            if self.frequency != CashflowFrequency.NONE:
                raise ValueError("disabled cashflow must use frequency=none")
        elif self.frequency == CashflowFrequency.NONE:
            raise ValueError("enabled cashflow requires a frequency")
        if self.type == CashflowType.PERCENT and abs(amount) > 1_000.0:
            raise ValueError("percentage cashflow amount is unreasonably large")
        object.__setattr__(self, "amount", amount)
        object.__setattr__(self, "annual_growth_rate_percent", growth)


@dataclass(frozen=True, slots=True)
class RebalanceConfig:
    frequency: RebalanceFrequency = RebalanceFrequency.NONE
    threshold_percent: float | None = None

    def __post_init__(self) -> None:
        threshold = self.threshold_percent
        if threshold is not None:
            threshold = float(threshold)
            if not math.isfinite(threshold) or threshold <= 0.0 or threshold > 100.0:
                raise ValueError("rebalance threshold must be in (0, 100]")
            object.__setattr__(self, "threshold_percent", threshold)


@dataclass(frozen=True, slots=True)
class LeverageConfig:
    type: LeverageType = LeverageType.NONE
    ratio: float = 1.0
    debt_amount: float = 0.0
    annual_interest_rate_percent: float = 0.0
    maintenance_margin_percent: float = 25.0

    def __post_init__(self) -> None:
        ratio = float(self.ratio)
        debt = float(self.debt_amount)
        rate = float(self.annual_interest_rate_percent)
        margin = float(self.maintenance_margin_percent)
        values = (ratio, debt, rate, margin)
        if not all(math.isfinite(value) for value in values):
            raise ValueError("leverage settings must be finite")
        if (
            self.type == LeverageType.FIXED_RATIO
            and not 1.0 < ratio <= MAX_TARGET_GROSS_EXPOSURE
        ):
            raise ValueError(
                "fixed-ratio leverage must be in "
                f"(1, {MAX_TARGET_GROSS_EXPOSURE:g}]"
            )
        if self.type == LeverageType.FIXED_DEBT and debt <= 0.0:
            raise ValueError("fixed debt amount must be positive")
        if debt < 0.0 or rate < 0.0 or rate > 100.0:
            raise ValueError("debt and interest settings are invalid")
        if margin < 0.0 or margin > 100.0:
            raise ValueError("maintenance margin must be in [0, 100]")
        object.__setattr__(self, "ratio", ratio)
        object.__setattr__(self, "debt_amount", debt)
        object.__setattr__(self, "annual_interest_rate_percent", rate)
        object.__setattr__(self, "maintenance_margin_percent", margin)


@dataclass(frozen=True, slots=True)
class ExposureMaintenanceConfig:
    mode: ExposureMaintenanceMode = ExposureMaintenanceMode.BAND
    tolerance_percent: float = 10.0

    def __post_init__(self) -> None:
        tolerance = float(self.tolerance_percent)
        if not math.isfinite(tolerance) or tolerance <= 0.0 or tolerance > 100.0:
            raise ValueError("exposure maintenance tolerance must be in (0, 100]")
        object.__setattr__(self, "tolerance_percent", tolerance)


@dataclass(frozen=True, slots=True)
class SimulationConfig:
    initial_amount: float = 10_000.0
    reinvest_distributions: bool = True
    transaction_cost_bps: float = 0.0
    cashflow: CashflowConfig = field(default_factory=CashflowConfig)
    rebalancing: RebalanceConfig = field(default_factory=RebalanceConfig)
    leverage: LeverageConfig = field(default_factory=LeverageConfig)
    exposure_maintenance: ExposureMaintenanceConfig = field(
        default_factory=ExposureMaintenanceConfig
    )
    risk_free_rate: float = 0.0

    def __post_init__(self) -> None:
        initial = float(self.initial_amount)
        cost = float(self.transaction_cost_bps)
        risk_free = float(self.risk_free_rate)
        if not math.isfinite(initial) or initial <= 0.0:
            raise ValueError("initial amount must be finite and positive")
        if not math.isfinite(cost) or cost < 0.0 or cost > 1_000.0:
            raise ValueError("transaction cost must be in [0, 1000] bps")
        if not math.isfinite(risk_free) or risk_free <= -1.0:
            raise ValueError("risk-free rate must be finite and greater than -1")
        object.__setattr__(self, "initial_amount", initial)
        object.__setattr__(self, "transaction_cost_bps", cost)
        object.__setattr__(self, "risk_free_rate", risk_free)


@dataclass(frozen=True, slots=True)
class LedgerEvent:
    date: str
    type: str
    details: dict[str, Any]


@dataclass(frozen=True, slots=True)
class PortfolioFailure:
    name: str
    stage: str
    detail: str
    symbols: tuple[str, ...]
    retryable: bool = False


def validate_portfolio_batch(portfolios: tuple[PortfolioSpec, ...]) -> None:
    if not 1 <= len(portfolios) <= MAX_PORTFOLIOS:
        raise ValueError(f"a batch must contain 1 to {MAX_PORTFOLIOS} portfolios")
    names = [portfolio.name for portfolio in portfolios]
    if len(names) != len(set(names)):
        raise ValueError("portfolio names must be unique")


def _normalize_symbol(value: str) -> str:
    symbol = str(value or "").strip().upper()
    if symbol.isdigit() and 4 <= len(symbol) <= 6:
        return f"{symbol}.TW"
    return symbol
