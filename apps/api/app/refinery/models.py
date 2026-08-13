"""Strict input contract and resource policy for read-only Portfolio Refinery V1."""

from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator
from typing_extensions import Annotated

from apps.api.app.data.history_service import normalize_symbol

REFINERY_API_CONTRACT_VERSION = "refinery-v1"
# The Phase 6 payload is opt-in.  Keep the established V1 schema marker for
# plan-less requests so their serialized P3–P5 response remains byte-for-byte
# compatible at the contract layer.
REFINERY_API_SCHEMA_VERSION = "refinery-v1-2026-08-10.3"
PHASE6_MARGINAL_CONTRACT_VERSION = "refinery-phase6-marginal-v1-2026-08-13.1"

MIN_CANDIDATE_SYMBOLS = 2
MAX_CANDIDATE_SYMBOLS = 100
MAX_EXPERIMENT_OPERATIONS = 12
MAX_EXPERIMENT_UNION_SYMBOLS = 24
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


class RefineryExperimentOperation(BaseModel):
    """One explicit, normalized marginal experiment operation.

    Phase 6 intentionally accepts only user-requested one-symbol operations.
    It never expands a baseline into an implicit Cartesian experiment set.
    """

    model_config = ConfigDict(extra="forbid")

    type: Literal["remove_one", "add_one", "replace_one"]
    remove: TickerSymbol | None = None
    add: TickerSymbol | None = None

    @model_validator(mode="after")
    def validate_operation_shape(self) -> "RefineryExperimentOperation":
        if self.type == "remove_one":
            if self.remove is None or self.add is not None:
                raise ValueError(
                    "remove_one requires remove and does not accept add"
                )
            self.remove = _validated_symbol(self.remove)
        elif self.type == "add_one":
            if self.add is None or self.remove is not None:
                raise ValueError("add_one requires add and does not accept remove")
            self.add = _validated_symbol(self.add)
        else:
            if self.remove is None or self.add is None:
                raise ValueError("replace_one requires both remove and add")
            self.remove = _validated_symbol(self.remove)
            self.add = _validated_symbol(self.add)
        return self

    @property
    def identity(self) -> tuple[str, str | None, str | None]:
        """Stable normalized identity used only for duplicate rejection/IDs."""

        return (self.type, self.remove, self.add)

    def export_payload(self) -> dict[str, str]:
        """Return the minimal normalized operation contract in stable key order."""

        payload = {"type": self.type}
        if self.remove is not None:
            payload["remove"] = self.remove
        if self.add is not None:
            payload["add"] = self.add
        return payload


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
    experiment_plan: list[RefineryExperimentOperation] | None = Field(
        default=None,
        min_length=1,
        max_length=MAX_EXPERIMENT_OPERATIONS,
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

        if self.experiment_plan is not None:
            baseline = set(normalized_symbols)
            seen_operations: set[tuple[str, str | None, str | None]] = set()
            for operation in self.experiment_plan:
                if operation.identity in seen_operations:
                    raise ValueError(
                        "experiment operations must be unique after normalization"
                    )
                seen_operations.add(operation.identity)

                if operation.type == "remove_one":
                    if operation.remove not in baseline:
                        raise ValueError(
                            "remove_one remove symbol must exist in candidate symbols"
                        )
                    if len(normalized_symbols) - 1 < MIN_CANDIDATE_SYMBOLS:
                        raise ValueError(
                            "remove_one must leave at least "
                            f"{MIN_CANDIDATE_SYMBOLS} candidate symbols"
                        )
                elif operation.type == "add_one":
                    if operation.add in baseline:
                        raise ValueError(
                            "add_one add symbol must not already exist in candidate symbols"
                        )
                    if len(normalized_symbols) + 1 > MAX_CANDIDATE_SYMBOLS:
                        raise ValueError(
                            "add_one would exceed the candidate symbol resource limit"
                        )
                else:
                    if operation.remove not in baseline:
                        raise ValueError(
                            "replace_one remove symbol must exist in candidate symbols"
                        )
                    if operation.add in baseline:
                        raise ValueError(
                            "replace_one add symbol must not already exist in candidate symbols"
                        )

            if len(self.experiment_union_symbols) > MAX_EXPERIMENT_UNION_SYMBOLS:
                raise ValueError(
                    "experiment union symbols exceed the "
                    f"{MAX_EXPERIMENT_UNION_SYMBOLS}-symbol resource limit"
                )
        return self

    @property
    def requested_market_symbols(self) -> tuple[str, ...]:
        values = list(self.experiment_union_symbols)
        if self.benchmark is not None and self.benchmark not in values:
            values.append(self.benchmark)
        return tuple(values)

    @property
    def experiment_union_symbols(self) -> tuple[str, ...]:
        """Baseline plus unique external Add/Replace symbols in request order."""

        values = list(self.symbols)
        known = set(values)
        for symbol in self.experiment_external_symbols:
            if symbol not in known:
                values.append(symbol)
                known.add(symbol)
        return tuple(values)

    @property
    def experiment_external_symbols(self) -> tuple[str, ...]:
        """Unique normalized external experiment symbols in operation order."""

        if self.experiment_plan is None:
            return ()
        values: list[str] = []
        known: set[str] = set()
        for operation in self.experiment_plan:
            if operation.add is not None and operation.add not in known:
                values.append(operation.add)
                known.add(operation.add)
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
