"""Strict input contract and resource policy for read-only Portfolio Refinery V1."""

from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator
from typing_extensions import Annotated

from apps.api.app.data.history_service import normalize_symbol

REFINERY_API_CONTRACT_VERSION = "refinery-v1"
REFINERY_API_SCHEMA_VERSION = "refinery-v1-2026-08-10.3"

MIN_CANDIDATE_SYMBOLS = 2
MAX_CANDIDATE_SYMBOLS = 100
MAX_HISTORY_CALENDAR_DAYS = 15 * 366
MAX_REQUEST_BYTES = 512 * 1024
MAX_RESPONSE_BYTES = 4 * 1024 * 1024
GENERAL_REQUESTS_PER_MINUTE = 20
ANALYZE_REQUESTS_PER_MINUTE = 4
DAILY_COVARIANCE_ANNUALIZATION = 252.0
MIN_DAILY_ANALYSIS_OBSERVATIONS = 60
TACTICAL_MIN_OBSERVATIONS = 40
MEDIUM_MIN_OBSERVATIONS = 120
STRUCTURAL_MIN_OBSERVATIONS = 52
CONDITIONAL_MIN_OBSERVATIONS = 20

TickerSymbol = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=32),
]


class RefineryWeightInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    symbol: TickerSymbol
    weight_percent: float = Field(gt=0.0, le=100.0)


class RefineryRequest(BaseModel):
    """One deterministic diagnostic request; no hidden portfolio assumptions."""

    model_config = ConfigDict(extra="forbid")

    contract_version: Literal["refinery-v1"] = REFINERY_API_CONTRACT_VERSION
    symbols: list[TickerSymbol] = Field(
        min_length=MIN_CANDIDATE_SYMBOLS,
        max_length=MAX_CANDIDATE_SYMBOLS,
    )
    benchmark: TickerSymbol | None = None
    start_date: date
    end_date: date
    weights: list[RefineryWeightInput] | None = Field(
        default=None,
        min_length=MIN_CANDIDATE_SYMBOLS,
        max_length=MAX_CANDIDATE_SYMBOLS,
    )
    ewma_decay: float = Field(default=0.94, gt=0.0, lt=1.0)
    stress_quantile: float = Field(default=0.10, ge=0.05, le=0.25)

    @model_validator(mode="after")
    def validate_request(self) -> "RefineryRequest":
        if self.start_date >= self.end_date:
            raise ValueError("start_date must be before end_date")
        if self.end_date > date.today():
            raise ValueError("end_date cannot be in the future")
        if (self.end_date - self.start_date).days > MAX_HISTORY_CALENDAR_DAYS:
            raise ValueError(
                f"requested history exceeds the {MAX_HISTORY_CALENDAR_DAYS}-day "
                "Refinery V1 resource limit"
            )

        normalized_symbols = [_validated_symbol(value) for value in self.symbols]
        if len(normalized_symbols) != len(set(normalized_symbols)):
            raise ValueError("candidate symbols must be unique after normalization")
        self.symbols = normalized_symbols

        if self.benchmark is not None:
            self.benchmark = _validated_symbol(self.benchmark)

        if self.weights is not None:
            normalized_weights: list[RefineryWeightInput] = []
            seen: set[str] = set()
            by_symbol: dict[str, float] = {}
            for item in self.weights:
                symbol = _validated_symbol(item.symbol)
                if symbol in seen:
                    raise ValueError("weight symbols must be unique after normalization")
                seen.add(symbol)
                by_symbol[symbol] = float(item.weight_percent)
                normalized_weights.append(
                    RefineryWeightInput(
                        symbol=symbol,
                        weight_percent=item.weight_percent,
                    )
                )
            if set(by_symbol) != set(normalized_symbols):
                missing = sorted(set(normalized_symbols) - set(by_symbol))
                extra = sorted(set(by_symbol) - set(normalized_symbols))
                details: list[str] = []
                if missing:
                    details.append("missing " + ", ".join(missing))
                if extra:
                    details.append("unexpected " + ", ".join(extra))
                raise ValueError(
                    "weights must contain every candidate exactly once"
                    + (": " + "; ".join(details) if details else "")
                )
            total = sum(by_symbol.values())
            if abs(total - 100.0) > 0.05:
                raise ValueError(
                    f"weights must total 100%, received {total:.4f}%"
                )
            self.weights = normalized_weights
        return self

    @property
    def requested_market_symbols(self) -> tuple[str, ...]:
        values = list(self.symbols)
        if self.benchmark is not None and self.benchmark not in values:
            values.append(self.benchmark)
        return tuple(values)

    @property
    def weight_input_total_percent(self) -> float | None:
        if self.weights is None:
            return None
        return float(sum(item.weight_percent for item in self.weights))

    @property
    def weight_vector(self) -> tuple[float, ...] | None:
        if self.weights is None:
            return None
        by_symbol = {item.symbol: float(item.weight_percent) for item in self.weights}
        total = sum(by_symbol.values())
        if total <= 0.0:
            raise ValueError("weight total must be positive")
        return tuple(by_symbol[symbol] / total for symbol in self.symbols)


def _validated_symbol(value: str) -> str:
    symbol = normalize_symbol(value)
    if not symbol:
        raise ValueError("symbol must not be empty")
    if len(symbol) > 32:
        raise ValueError("normalized symbol must not exceed 32 characters")
    return symbol
