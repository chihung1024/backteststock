"""Strict request and response contracts for the self-owned Portfolio v3 API."""

from __future__ import annotations

from datetime import date
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator
from typing_extensions import Annotated

from apps.api.app.portfolio.models import (
    AssetWeight,
    CashflowConfig,
    CashflowFrequency,
    CashflowTiming,
    CashflowType,
    LeverageConfig,
    LeverageType,
    MAX_ASSETS_PER_PORTFOLIO,
    MAX_PORTFOLIOS,
    MAX_TARGET_GROSS_EXPOSURE,
    PortfolioSpec,
    RebalanceConfig,
    RebalanceFrequency,
    SimulationConfig,
    WEIGHT_TOLERANCE,
)

PORTFOLIO_API_CONTRACT_VERSION = "portfolio-v3"
PORTFOLIO_API_SCHEMA_VERSION = "portfolio-v3-2026-08-15.1"

TickerSymbol = Annotated[
    str,
    StringConstraints(strip_whitespace=True, to_upper=True, min_length=1, max_length=32),
]


class RegimeType(StrEnum):
    NONE = "none"
    MARKET = "market"
    VOLATILITY = "volatility"
    INFLATION = "inflation"
    BUSINESS_CYCLE = "business_cycle"


class OutputFrequency(StrEnum):
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"


class AssetAllocationInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    symbol: TickerSymbol
    weight: float = Field(
        gt=0.0, le=MAX_TARGET_GROSS_EXPOSURE * 100.0
    )


class PortfolioDefinitionInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=60)
    assets: list[AssetAllocationInput] = Field(
        min_length=1,
        max_length=MAX_ASSETS_PER_PORTFOLIO,
    )

    @model_validator(mode="after")
    def validate_assets(self) -> PortfolioDefinitionInput:
        symbols = [_normalize_symbol(asset.symbol) for asset in self.assets]
        if len(symbols) != len(set(symbols)):
            raise ValueError("portfolio assets must be unique")
        total = sum(asset.weight for asset in self.assets)
        max_total = (MAX_TARGET_GROSS_EXPOSURE + WEIGHT_TOLERANCE) * 100.0
        if total > max_total:
            raise ValueError(
                "portfolio target gross exposure cannot exceed "
                f"{MAX_TARGET_GROSS_EXPOSURE * 100.0:g}%, received {total:.4f}%"
            )
        for asset, symbol in zip(self.assets, symbols, strict=True):
            asset.symbol = symbol
        self.name = self.name.strip()
        return self

    def to_spec(self) -> PortfolioSpec:
        return PortfolioSpec(
            name=self.name,
            assets=tuple(
                AssetWeight(symbol=asset.symbol, weight=asset.weight / 100.0)
                for asset in self.assets
            ),
        )


class CashflowInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: CashflowType = CashflowType.NONE
    amount: float = 0.0
    frequency: CashflowFrequency = CashflowFrequency.NONE
    timing: CashflowTiming = CashflowTiming.END
    annual_growth_rate_percent: float = Field(default=0.0, gt=-100.0, le=1_000.0)

    def to_config(self) -> CashflowConfig:
        return CashflowConfig(
            type=self.type,
            amount=self.amount,
            frequency=self.frequency,
            timing=self.timing,
            annual_growth_rate_percent=self.annual_growth_rate_percent,
        )


class RebalanceInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    frequency: RebalanceFrequency = RebalanceFrequency.NONE
    threshold_percent: float | None = Field(default=None, gt=0.0, le=100.0)

    def to_config(self) -> RebalanceConfig:
        return RebalanceConfig(
            frequency=self.frequency,
            threshold_percent=self.threshold_percent,
        )


class LeverageInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: LeverageType = LeverageType.NONE
    ratio: float = Field(default=1.0, ge=1.0, le=5.0)
    debt_amount: float = Field(default=0.0, ge=0.0)
    annual_interest_rate_percent: float = Field(default=0.0, ge=0.0, le=100.0)
    maintenance_margin_percent: float = Field(default=25.0, ge=0.0, le=100.0)

    def to_config(self) -> LeverageConfig:
        return LeverageConfig(
            type=self.type,
            ratio=self.ratio,
            debt_amount=self.debt_amount,
            annual_interest_rate_percent=self.annual_interest_rate_percent,
            maintenance_margin_percent=self.maintenance_margin_percent,
        )


class AnalyticsInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    factor_analysis: bool = False
    style_analysis: bool = False
    regime: RegimeType = RegimeType.NONE
    inflation_adjusted: bool = False
    risk_free_rate_percent: float = Field(default=0.0, gt=-100.0, le=100.0)


class PortfolioRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    contract_version: Literal["portfolio-v3"] = PORTFOLIO_API_CONTRACT_VERSION
    portfolios: list[PortfolioDefinitionInput] = Field(
        min_length=1,
        max_length=MAX_PORTFOLIOS,
    )
    benchmark: TickerSymbol | None = None
    start_date: date
    end_date: date
    initial_amount: float = Field(default=100_000.0, gt=0.0, le=1_000_000_000_000.0)
    base_currency: Literal["TWD"] = "TWD"
    include_ytd: bool = True
    reinvest_distributions: bool = True
    transaction_cost_bps: float = Field(default=0.0, ge=0.0, le=1_000.0)
    cashflow: CashflowInput = Field(default_factory=CashflowInput)
    rebalancing: RebalanceInput = Field(default_factory=RebalanceInput)
    leverage: LeverageInput = Field(default_factory=LeverageInput)
    analytics: AnalyticsInput = Field(default_factory=AnalyticsInput)
    output_frequency: OutputFrequency = OutputFrequency.DAILY
    include_events: bool = True
    include_allocation_history: bool = False

    @model_validator(mode="after")
    def validate_request(self) -> PortfolioRequest:
        if self.start_date >= self.end_date:
            raise ValueError("start_date must be before end_date")
        if self.end_date > date.today():
            raise ValueError("end_date cannot be in the future")
        names = [portfolio.name for portfolio in self.portfolios]
        if len(names) != len(set(names)):
            raise ValueError("portfolio names must be unique")
        if self.leverage.type != LeverageType.NONE:
            ambiguous = [
                portfolio.name
                for portfolio in self.portfolios
                if abs(
                    sum(asset.weight for asset in portfolio.assets) / 100.0 - 1.0
                ) > WEIGHT_TOLERANCE
            ]
            if ambiguous:
                raise ValueError(
                    "explicit legacy leverage requires 100% asset weights; "
                    "non-100% weights already define residual cash or gross exposure: "
                    + ", ".join(ambiguous)
                )
        if self.benchmark:
            self.benchmark = _normalize_symbol(self.benchmark)
        return self

    @property
    def requested_symbols(self) -> tuple[str, ...]:
        values: list[str] = []
        seen: set[str] = set()
        for portfolio in self.portfolios:
            for asset in portfolio.assets:
                if asset.symbol not in seen:
                    seen.add(asset.symbol)
                    values.append(asset.symbol)
        if self.benchmark and self.benchmark not in seen:
            values.append(self.benchmark)
        return tuple(values)

    def effective_end_date(self) -> date:
        if self.include_ytd or self.end_date.year < date.today().year:
            return self.end_date
        cutoff = date(date.today().year - 1, 12, 31)
        if self.start_date >= cutoff:
            raise ValueError(
                "disabling year-to-date data leaves no complete calendar year"
            )
        return min(self.end_date, cutoff)

    def to_specs(self) -> tuple[PortfolioSpec, ...]:
        return tuple(portfolio.to_spec() for portfolio in self.portfolios)

    def to_simulation_config(self) -> SimulationConfig:
        return SimulationConfig(
            initial_amount=self.initial_amount,
            reinvest_distributions=self.reinvest_distributions,
            transaction_cost_bps=self.transaction_cost_bps,
            cashflow=self.cashflow.to_config(),
            rebalancing=self.rebalancing.to_config(),
            leverage=self.leverage.to_config(),
            risk_free_rate=self.analytics.risk_free_rate_percent / 100.0,
        )


class AssetSearchResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    symbol: str
    name: str
    exchange: str | None = None
    quote_type: str | None = None
    currency: str | None = None


class AssetPreflightResult(BaseModel):
    model_config = ConfigDict(extra="allow")

    symbol: str
    status: Literal["ready", "failed"]
    stage: str | None = None
    detail: str | None = None
    retryable: bool = False
    quote_currency: str | None = None
    effective_start: str | None = None
    effective_end: str | None = None
    observations: int = 0
    corporate_action_audit: dict[str, Any] | None = None
    fx_audit: dict[str, Any] | None = None
    return_component_audit: dict[str, Any] | None = None
    fingerprints: dict[str, str | None] = Field(default_factory=dict)


class PortfolioPreflightResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    status: Literal["ready", "failed"]
    symbols: list[str]
    missing_symbols: list[str] = Field(default_factory=list)
    effective_start: str | None = None
    effective_end: str | None = None
    observations: int = 0
    detail: str | None = None


class PreflightResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_id: str
    generated_at: str
    contract_version: str
    schema_version: str
    base_currency: Literal["TWD"]
    requested_start: str
    requested_end: str
    effective_end: str
    assets: list[AssetPreflightResult]
    portfolios: list[PortfolioPreflightResult]
    benchmark: AssetPreflightResult | None = None
    analysis_dependencies: list[AssetPreflightResult] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class BacktestResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_id: str
    generated_at: str
    contract_version: str
    schema_version: str
    base_currency: Literal["TWD"]
    requested_start: str
    requested_end: str
    effective_end: str
    results: list[dict[str, Any]]
    failures: list[dict[str, Any]]
    assets: list[AssetPreflightResult]
    benchmark: dict[str, Any] | None = None
    warnings: list[str] = Field(default_factory=list)
    timing: dict[str, float] = Field(default_factory=dict)
    reproducibility: dict[str, Any] = Field(default_factory=dict)


def _normalize_symbol(value: str) -> str:
    symbol = str(value or "").strip().upper()
    if symbol.isdigit() and 4 <= len(symbol) <= 6:
        return f"{symbol}.TW"
    return symbol
