from __future__ import annotations

import re
from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    file_path = Path(path)
    text = file_path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{path}: expected one exact match, found {count}")
    file_path.write_text(text.replace(old, new, 1), encoding="utf-8")


def regex_once(path: str, pattern: str, replacement: str) -> None:
    file_path = Path(path)
    text = file_path.read_text(encoding="utf-8")
    updated, count = re.subn(pattern, replacement, text, count=1, flags=re.DOTALL)
    if count != 1:
        raise RuntimeError(f"{path}: expected one regex match, found {count}")
    file_path.write_text(updated, encoding="utf-8")


factors_path = Path("apps/api/app/quant/factors.py")
old_factors = factors_path.read_text(encoding="utf-8")
for required in (
    'DEFAULT_FACTOR_MIN_MONTHS = 36',
    'def fit_us_factor_exposure(',
    'def factor_implied_relationship(',
    'def _monthly_compounded(',
):
    if required not in old_factors:
        raise RuntimeError(f"factors.py missing expected baseline token: {required}")

new_factors = '''"""Pure factor-exposure and factor-implied relationship diagnostics."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Mapping

import numpy as np
import pandas as pd

US_FACTOR_COLUMNS = ("MKT_RF", "SMB", "HML", "RMW", "CMA", "MOM")
RISK_FREE_COLUMN = "RF"
DEFAULT_FACTOR_MIN_MONTHS = 36
FACTOR_MONTHLY_RETURN_POLICY = "boundary-month-exclusion-v1"
_VARIANCE_EPSILON = 1e-15


@dataclass(frozen=True, slots=True)
class FactorExposure:
    status: str
    observations: int
    start: str | None
    end: str | None
    intercept_monthly: float | None
    r_squared: float | None
    betas: dict[str, float] | None


@dataclass(frozen=True, slots=True)
class FactorImpliedRelationship:
    status: str
    symbols: tuple[str, ...]
    observations: int
    start: str | None
    end: str | None
    sample_fingerprint_sha256: str | None
    covariance: pd.DataFrame | None
    correlation: pd.DataFrame | None


def boundary_safe_monthly_returns(native_daily_returns: pd.Series) -> pd.Series:
    """Compound only interior represented calendar months.

    The first represented month cannot prove a full holding-period month because
    the pre-window close is unavailable. The last represented month can also be
    partial. V1 therefore excludes both boundaries without pretending to own an
    exchange-specific complete-month calendar.
    """

    values = _normalized_daily_returns(native_daily_returns)
    if values.empty:
        return pd.Series(dtype=float, name="asset_return")
    periods = values.index.to_period("M")
    compounded = ((1.0 + values).groupby(periods).prod() - 1.0).astype(float)
    if len(compounded) <= 2:
        return pd.Series(dtype=float, name="asset_return")
    interior = compounded.iloc[1:-1].copy()
    interior.index = interior.index.to_timestamp("M")
    return interior.rename("asset_return")


def fit_us_factor_exposure(
    native_daily_returns: pd.Series,
    factors: pd.DataFrame,
    *,
    min_observations: int = DEFAULT_FACTOR_MIN_MONTHS,
) -> FactorExposure:
    """Regress boundary-safe monthly native excess return on U.S. factors."""

    if not isinstance(native_daily_returns, pd.Series):
        raise TypeError("native_daily_returns must be a pandas Series")
    if not isinstance(min_observations, int) or min_observations < 2:
        raise ValueError("min_observations must be an integer >= 2")
    monthly = boundary_safe_monthly_returns(native_daily_returns)
    return _fit_factor_exposure_from_monthly(
        monthly,
        _factor_frame(factors),
        min_observations=min_observations,
    )


def factor_implied_relationship(
    native_daily_returns: Mapping[str, pd.Series],
    factors: pd.DataFrame,
    *,
    min_observations: int = DEFAULT_FACTOR_MIN_MONTHS,
) -> FactorImpliedRelationship:
    """Refit all relationship betas and factor covariance on one common sample."""

    if not isinstance(native_daily_returns, Mapping):
        raise TypeError("native_daily_returns must be a mapping of symbol to Series")
    if not isinstance(min_observations, int) or min_observations < 2:
        raise ValueError("min_observations must be an integer >= 2")

    factor_frame = _factor_frame(factors)
    monthly_by_symbol: dict[str, pd.Series] = {}
    individual: dict[str, FactorExposure] = {}
    for raw_symbol, returns in native_daily_returns.items():
        symbol = str(raw_symbol)
        if symbol in monthly_by_symbol:
            raise ValueError("factor relationship symbols must remain unique after normalization")
        monthly = boundary_safe_monthly_returns(returns)
        monthly_by_symbol[symbol] = monthly
        individual[symbol] = _fit_factor_exposure_from_monthly(
            monthly,
            factor_frame,
            min_observations=min_observations,
        )

    symbols = tuple(
        sorted(
            symbol
            for symbol, exposure in individual.items()
            if exposure.status == "ok" and exposure.betas is not None
        )
    )
    if len(symbols) < 2:
        return _empty_relationship("insufficient_assets", symbols)

    common = factor_frame.copy()
    for symbol in symbols:
        common = common.join(
            monthly_by_symbol[symbol].rename(_asset_column(symbol)),
            how="inner",
        )
    common = common.replace([np.inf, -np.inf], np.nan).dropna()
    observations = len(common)
    start = common.index[0].date().isoformat() if observations else None
    end = common.index[-1].date().isoformat() if observations else None
    fingerprint = _frame_fingerprint(common) if observations else None
    if observations < min_observations:
        return FactorImpliedRelationship(
            status="insufficient_common_observations",
            symbols=symbols,
            observations=observations,
            start=start,
            end=end,
            sample_fingerprint_sha256=fingerprint,
            covariance=None,
            correlation=None,
        )

    relationship_betas: dict[str, dict[str, float]] = {}
    common_factors = common[list((*US_FACTOR_COLUMNS, RISK_FREE_COLUMN))]
    for symbol in symbols:
        refit = _fit_factor_exposure_from_monthly(
            common[_asset_column(symbol)].rename("asset_return"),
            common_factors,
            min_observations=min_observations,
        )
        if refit.status != "ok" or refit.betas is None:
            return FactorImpliedRelationship(
                status=f"common_refit_{refit.status}",
                symbols=symbols,
                observations=observations,
                start=start,
                end=end,
                sample_fingerprint_sha256=fingerprint,
                covariance=None,
                correlation=None,
            )
        relationship_betas[symbol] = refit.betas

    factor_values = common[list(US_FACTOR_COLUMNS)].to_numpy(dtype=float)
    factor_covariance = np.cov(factor_values, rowvar=False, ddof=1)
    beta_matrix = np.asarray(
        [
            [float(relationship_betas[symbol][name]) for name in US_FACTOR_COLUMNS]
            for symbol in symbols
        ],
        dtype=float,
    )
    systematic_covariance = beta_matrix @ factor_covariance @ beta_matrix.T
    variances = np.diag(systematic_covariance)
    if (
        not np.isfinite(systematic_covariance).all()
        or bool((variances <= _VARIANCE_EPSILON).any())
    ):
        return FactorImpliedRelationship(
            status="degenerate_systematic_variance",
            symbols=symbols,
            observations=observations,
            start=start,
            end=end,
            sample_fingerprint_sha256=fingerprint,
            covariance=None,
            correlation=None,
        )

    scale = np.sqrt(variances)
    correlation = systematic_covariance / np.outer(scale, scale)
    correlation = np.clip(correlation, -1.0, 1.0)
    np.fill_diagonal(correlation, 1.0)
    return FactorImpliedRelationship(
        status="ok",
        symbols=symbols,
        observations=observations,
        start=start,
        end=end,
        sample_fingerprint_sha256=fingerprint,
        covariance=pd.DataFrame(
            systematic_covariance,
            index=symbols,
            columns=symbols,
        ),
        correlation=pd.DataFrame(correlation, index=symbols, columns=symbols),
    )


def _fit_factor_exposure_from_monthly(
    monthly: pd.Series,
    factor_frame: pd.DataFrame,
    *,
    min_observations: int,
) -> FactorExposure:
    joined = factor_frame.join(monthly.rename("asset_return"), how="inner").replace(
        [np.inf, -np.inf], np.nan
    ).dropna()
    observations = len(joined)
    start = joined.index[0].date().isoformat() if observations else None
    end = joined.index[-1].date().isoformat() if observations else None
    if observations < min_observations:
        return FactorExposure(
            status="insufficient_observations",
            observations=observations,
            start=start,
            end=end,
            intercept_monthly=None,
            r_squared=None,
            betas=None,
        )

    y = (
        joined["asset_return"].to_numpy(dtype=float)
        - joined[RISK_FREE_COLUMN].to_numpy(dtype=float)
    )
    denominator = float(np.sum((y - y.mean()) ** 2))
    if denominator <= _VARIANCE_EPSILON:
        return FactorExposure(
            status="degenerate_target",
            observations=observations,
            start=start,
            end=end,
            intercept_monthly=None,
            r_squared=None,
            betas=None,
        )

    x = joined[list(US_FACTOR_COLUMNS)].to_numpy(dtype=float)
    design = np.column_stack([np.ones(observations), x])
    coefficients, *_ = np.linalg.lstsq(design, y, rcond=None)
    predicted = design @ coefficients
    residual = y - predicted
    r_squared = 1.0 - float(np.sum(residual**2) / denominator)
    return FactorExposure(
        status="ok",
        observations=observations,
        start=start,
        end=end,
        intercept_monthly=float(coefficients[0]),
        r_squared=r_squared,
        betas={
            name: float(value)
            for name, value in zip(
                US_FACTOR_COLUMNS,
                coefficients[1:],
                strict=True,
            )
        },
    )


def _normalized_daily_returns(returns: pd.Series) -> pd.Series:
    if not isinstance(returns, pd.Series):
        raise TypeError("native_daily_returns must be a pandas Series")
    values = pd.to_numeric(returns, errors="coerce").replace(
        [np.inf, -np.inf], np.nan
    ).dropna()
    if values.empty:
        return pd.Series(dtype=float, name="return")
    index = pd.DatetimeIndex(pd.to_datetime(values.index))
    if index.tz is not None:
        index = index.tz_convert(None)
    values = pd.Series(values.to_numpy(dtype=float), index=index, name="return")
    return values[~values.index.duplicated(keep="last")].sort_index()


def _factor_frame(factors: pd.DataFrame) -> pd.DataFrame:
    if not isinstance(factors, pd.DataFrame):
        raise TypeError("factors must be a pandas DataFrame")
    frame = factors.copy()
    frame.columns = [
        str(column).strip().replace("Mkt-RF", "MKT_RF")
        for column in frame.columns
    ]
    missing = [
        column
        for column in (*US_FACTOR_COLUMNS, RISK_FREE_COLUMN)
        if column not in frame.columns
    ]
    if missing:
        raise ValueError("factor dataset missing required columns: " + ", ".join(missing))
    index = pd.DatetimeIndex(pd.to_datetime(frame.index))
    if index.tz is not None:
        index = index.tz_convert(None)
    frame.index = index.to_period("M").to_timestamp("M")
    frame = frame[list((*US_FACTOR_COLUMNS, RISK_FREE_COLUMN))]
    frame = frame.apply(pd.to_numeric, errors="coerce").replace(
        [np.inf, -np.inf], np.nan
    ).dropna()
    return frame[~frame.index.duplicated(keep="last")].sort_index().astype(float)


def _asset_column(symbol: str) -> str:
    return f"asset::{symbol}"


def _frame_fingerprint(frame: pd.DataFrame) -> str:
    payload = {
        "columns": [str(column) for column in frame.columns],
        "dates": [pd.Timestamp(value).isoformat() for value in frame.index],
        "values": frame.to_numpy(dtype=float).tolist(),
    }
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _empty_relationship(status: str, symbols: tuple[str, ...]) -> FactorImpliedRelationship:
    return FactorImpliedRelationship(
        status=status,
        symbols=symbols,
        observations=0,
        start=None,
        end=None,
        sample_fingerprint_sha256=None,
        covariance=None,
        correlation=None,
    )
'''
factors_path.write_text(new_factors, encoding="utf-8")

replace_once(
    "apps/api/app/quant/__init__.py",
    "    DEFAULT_FACTOR_MIN_MONTHS,\n    RISK_FREE_COLUMN,",
    "    DEFAULT_FACTOR_MIN_MONTHS,\n    FACTOR_MONTHLY_RETURN_POLICY,\n    RISK_FREE_COLUMN,",
)
replace_once(
    "apps/api/app/quant/__init__.py",
    "    FactorImpliedRelationship,\n    factor_implied_relationship,",
    "    FactorImpliedRelationship,\n    boundary_safe_monthly_returns,\n    factor_implied_relationship,",
)
replace_once(
    "apps/api/app/quant/__init__.py",
    '    "DEFAULT_FACTOR_MIN_MONTHS",\n    "CorrelationResult",',
    '    "DEFAULT_FACTOR_MIN_MONTHS",\n    "FACTOR_MONTHLY_RETURN_POLICY",\n    "CorrelationResult",',
)
replace_once(
    "apps/api/app/quant/__init__.py",
    '    "circular_block_bootstrap_indices",\n    "factor_implied_relationship",',
    '    "circular_block_bootstrap_indices",\n    "boundary_safe_monthly_returns",\n    "factor_implied_relationship",',
)

relationships = "apps/api/app/refinery/relationships.py"
replace_once(
    relationships,
    "    DEFAULT_FACTOR_MIN_MONTHS,\n    PRIMARY_CLUSTER_LINKAGE,",
    "    DEFAULT_FACTOR_MIN_MONTHS,\n    FACTOR_MONTHLY_RETURN_POLICY,\n    PRIMARY_CLUSTER_LINKAGE,",
)
replace_once(
    relationships,
    '                "quote_currency": quote_currency or None,\n                "observations": 0,',
    '                "quote_currency": quote_currency or None,\n                "monthly_return_policy": FACTOR_MONTHLY_RETURN_POLICY,\n                "observations": 0,',
)
replace_once(
    relationships,
    '                "quote_currency": quote_currency,\n                "observations": 0,',
    '                "quote_currency": quote_currency,\n                "monthly_return_policy": FACTOR_MONTHLY_RETURN_POLICY,\n                "observations": 0,',
)
replace_once(
    relationships,
    '        "return_currency": "native_quote_currency",\n        "minimum_monthly_observations": DEFAULT_FACTOR_MIN_MONTHS,',
    '        "return_currency": "native_quote_currency",\n        "monthly_return_policy": FACTOR_MONTHLY_RETURN_POLICY,\n        "minimum_monthly_observations": DEFAULT_FACTOR_MIN_MONTHS,',
)
replace_once(
    relationships,
    '                "quote_currency": "USD",\n                "observations": 0,',
    '                "quote_currency": "USD",\n                "monthly_return_policy": FACTOR_MONTHLY_RETURN_POLICY,\n                "observations": 0,',
)
replace_once(
    relationships,
    '            "quote_currency": "USD",\n            "observations": exposure.observations,',
    '            "quote_currency": "USD",\n            "monthly_return_policy": FACTOR_MONTHLY_RETURN_POLICY,\n            "observations": exposure.observations,',
)
replace_once(
    relationships,
    "    relation = factor_implied_relationship(exposures, factors)",
    '''    relation = factor_implied_relationship(
        {symbol: dataset.native_returns[symbol] for symbol in eligible},
        factors,
        min_observations=DEFAULT_FACTOR_MIN_MONTHS,
    )''',
)
old_relationship_payload = '''    if relation.status == "ok" and relation.correlation is not None:
        relationship_payload = {
            "status": relation.status,
            "factor_observations": relation.factor_observations,
            "matrix": _matrix_payload(relation.correlation),
        }
    elif relation.symbols:
        relationship_payload = {
            "status": relation.status,
            "factor_observations": relation.factor_observations,
            "matrix": None,
        }'''
new_relationship_payload = '''    if relation.status == "ok" and relation.correlation is not None:
        relationship_payload = {
            "status": relation.status,
            "observations": relation.observations,
            "start": relation.start,
            "end": relation.end,
            "sample_fingerprint_sha256": relation.sample_fingerprint_sha256,
            "matrix": _matrix_payload(relation.correlation),
        }
    elif relation.symbols:
        relationship_payload = {
            "status": relation.status,
            "observations": relation.observations,
            "start": relation.start,
            "end": relation.end,
            "sample_fingerprint_sha256": relation.sample_fingerprint_sha256,
            "matrix": None,
        }'''
replace_once(relationships, old_relationship_payload, new_relationship_payload)

replace_once(
    "apps/portfolio-web/src/refineryTypes.ts",
    "  quote_currency: string | null;\n  observations: number;",
    "  quote_currency: string | null;\n  monthly_return_policy: string;\n  observations: number;",
)
replace_once(
    "apps/portfolio-web/src/refineryTypes.ts",
    "  return_currency: string;\n  minimum_monthly_observations: number;",
    "  return_currency: string;\n  monthly_return_policy: string;\n  minimum_monthly_observations: number;",
)
replace_once(
    "apps/portfolio-web/src/refineryTypes.ts",
    '''  systematic_relationship: {
    status: string;
    factor_observations: number;
    matrix: RefineryCorrelationMatrix | null;
  } | null;''',
    '''  systematic_relationship: {
    status: string;
    observations: number;
    start: string | null;
    end: string | null;
    sample_fingerprint_sha256: string | null;
    matrix: RefineryCorrelationMatrix | null;
  } | null;''',
)

factor_tests = "tests/test_factor_relationships.py"
replace_once(
    factor_tests,
    "    FactorExposure,\n    factor_implied_relationship,",
    "    boundary_safe_monthly_returns,\n    factor_implied_relationship,",
)
replace_once(
    factor_tests,
    '''    assert result.status == "ok"
    assert result.observations == len(factors)
    assert result.intercept_monthly == pytest.approx(intercept, abs=1e-12)''',
    '''    assert result.status == "ok"
    assert result.observations == len(factors) - 2
    assert result.start == factors.index[1].date().isoformat()
    assert result.end == factors.index[-2].date().isoformat()
    assert result.intercept_monthly == pytest.approx(intercept, abs=1e-12)''',
)
replace_once(
    factor_tests,
    '    assert result.observations == 24',
    '    assert result.observations == 22',
)
regex_once(
    factor_tests,
    r"def test_factor_implied_covariance_and_correlation_match_matrix_formula\(\) -> None:[\s\S]*?\n\ndef test_factor_implied_relationship_excludes_non_ok_exposures_explicitly\(\) -> None:",
    '''def test_factor_implied_covariance_and_correlation_match_matrix_formula() -> None:
    factors = _factor_fixture()
    beta_a = np.array([1.0, 0.2, -0.1, 0.0, 0.1, 0.3])
    beta_b = np.array([0.7, -0.1, 0.4, 0.2, -0.2, 0.1])
    asset_a = pd.Series(
        factors["RF"].to_numpy()
        + factors[list(US_FACTOR_COLUMNS)].to_numpy() @ beta_a,
        index=factors.index,
    )
    asset_b = pd.Series(
        factors["RF"].to_numpy()
        + factors[list(US_FACTOR_COLUMNS)].to_numpy() @ beta_b,
        index=factors.index,
    )

    result = factor_implied_relationship(
        {"BBB": asset_b, "AAA": asset_a},
        factors,
        min_observations=36,
    )

    assert result.status == "ok"
    assert result.symbols == ("AAA", "BBB")
    assert result.observations == len(factors) - 2
    assert result.start == factors.index[1].date().isoformat()
    assert result.end == factors.index[-2].date().isoformat()
    assert result.sample_fingerprint_sha256 is not None
    assert result.covariance is not None
    assert result.correlation is not None
    common_factors = factors.iloc[1:-1]
    sigma_f = np.cov(
        common_factors[list(US_FACTOR_COLUMNS)].to_numpy(),
        rowvar=False,
        ddof=1,
    )
    beta_matrix = np.vstack([beta_a, beta_b])
    expected_covariance = beta_matrix @ sigma_f @ beta_matrix.T
    expected_scale = np.sqrt(np.diag(expected_covariance))
    expected_correlation = expected_covariance / np.outer(expected_scale, expected_scale)

    np.testing.assert_allclose(
        result.covariance.to_numpy(), expected_covariance, rtol=1e-13, atol=1e-15
    )
    np.testing.assert_allclose(
        result.correlation.to_numpy(), expected_correlation, rtol=1e-13, atol=1e-15
    )


def test_factor_implied_relationship_excludes_non_ok_exposures_explicitly() -> None:''',
)
regex_once(
    factor_tests,
    r"def test_factor_implied_relationship_excludes_non_ok_exposures_explicitly\(\) -> None:[\s\S]*\Z",
    '''def test_factor_implied_relationship_excludes_non_ok_exposures_explicitly() -> None:
    factors = _factor_fixture()
    valid = pd.Series(
        factors["RF"].to_numpy() + 0.5 * factors["MKT_RF"].to_numpy(),
        index=factors.index,
    )
    short_factors = factors.iloc[:20]
    unavailable = pd.Series(
        short_factors["RF"].to_numpy()
        + 0.5 * short_factors["MKT_RF"].to_numpy(),
        index=short_factors.index,
    )

    result = factor_implied_relationship(
        {"AAA": valid, "NON_US_OR_SHORT": unavailable},
        factors,
        min_observations=36,
    )

    assert result.status == "insufficient_assets"
    assert result.symbols == ("AAA",)
    assert result.observations == 0
    assert result.sample_fingerprint_sha256 is None
    assert result.covariance is None
    assert result.correlation is None
''',
)

print("P5-CORR-B precise patch applied successfully")
