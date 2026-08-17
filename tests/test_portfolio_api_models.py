from __future__ import annotations

from datetime import date

import pytest
from pydantic import ValidationError

from apps.api.app.portfolio.api_models import PortfolioRequest


def _payload() -> dict:
    return {
        "contract_version": "portfolio-v3",
        "portfolios": [
            {
                "name": "Core",
                "assets": [
                    {"symbol": "2330", "weight": 60},
                    {"symbol": "SPY", "weight": 40},
                ],
            }
        ],
        "benchmark": "spy",
        "start_date": "2020-01-01",
        "end_date": "2024-12-31",
        "initial_amount": 100000,
        "base_currency": "TWD",
    }


def test_request_normalizes_symbols_and_builds_ledger_models() -> None:
    request = PortfolioRequest.model_validate(_payload())

    assert request.portfolios[0].assets[0].symbol == "2330.TW"
    assert request.portfolios[0].assets[1].symbol == "SPY"
    assert request.benchmark == "SPY"
    assert request.requested_symbols == ("2330.TW", "SPY")
    spec = request.to_specs()[0]
    assert spec.symbols == ("2330.TW", "SPY")
    assert spec.weights == pytest.approx((0.6, 0.4))
    assert request.to_simulation_config().initial_amount == 100000


def test_request_rejects_extra_fields_duplicate_symbols_and_excess_gross_exposure() -> None:
    payload = _payload()
    payload["unexpected"] = True
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        PortfolioRequest.model_validate(payload)

    payload = _payload()
    payload["portfolios"][0]["assets"] = [
        {"symbol": "SPY", "weight": 50},
        {"symbol": "spy", "weight": 50},
    ]
    with pytest.raises(ValidationError, match="unique"):
        PortfolioRequest.model_validate(payload)

    payload = _payload()
    payload["portfolios"][0]["assets"] = [
        {"symbol": "SPY", "weight": 450},
        {"symbol": "QQQ", "weight": 60},
    ]
    with pytest.raises(ValidationError, match="cannot exceed 500"):
        PortfolioRequest.model_validate(payload)


def test_request_rejects_future_end_date_and_non_twd_currency() -> None:
    payload = _payload()
    payload["end_date"] = date.today().replace(year=date.today().year + 1).isoformat()
    with pytest.raises(ValidationError, match="future"):
        PortfolioRequest.model_validate(payload)

    payload = _payload()
    payload["base_currency"] = "USD"
    with pytest.raises(ValidationError):
        PortfolioRequest.model_validate(payload)


def test_disabling_ytd_moves_end_to_previous_calendar_year() -> None:
    today = date.today()
    payload = _payload()
    payload["start_date"] = f"{today.year - 3}-01-01"
    payload["end_date"] = today.isoformat()
    payload["include_ytd"] = False
    request = PortfolioRequest.model_validate(payload)

    assert request.effective_end_date() == date(today.year - 1, 12, 31)


def test_request_supports_cashflow_rebalance_leverage_and_analytics() -> None:
    payload = _payload()
    payload.update(
        {
            "cashflow": {
                "type": "fixed",
                "amount": 1000,
                "frequency": "monthly",
                "timing": "beginning",
                "annual_growth_rate_percent": 3,
            },
            "rebalancing": {
                "frequency": "quarterly",
                "threshold_percent": 5,
            },
            "leverage": {
                "type": "fixed_ratio",
                "ratio": 1.5,
                "annual_interest_rate_percent": 4,
                "maintenance_margin_percent": 25,
            },
            "analytics": {
                "factor_analysis": True,
                "style_analysis": True,
                "regime": "market",
                "inflation_adjusted": True,
                "risk_free_rate_percent": 1.5,
            },
        }
    )
    request = PortfolioRequest.model_validate(payload)
    config = request.to_simulation_config()

    assert config.cashflow.amount == 1000
    assert config.rebalancing.threshold_percent == 5
    assert config.leverage.ratio == 1.5
    assert config.risk_free_rate == pytest.approx(0.015)



def test_request_preserves_cash_and_leveraged_weight_totals() -> None:
    cash_payload = _payload()
    cash_payload["portfolios"][0]["assets"] = [
        {"symbol": "SPY", "weight": 80},
    ]
    cash_request = PortfolioRequest.model_validate(cash_payload)
    assert cash_request.to_specs()[0].weights == pytest.approx((0.8,))
    assert cash_request.to_specs()[0].target_cash_allocation == pytest.approx(0.2)

    leveraged_payload = _payload()
    leveraged_payload["portfolios"][0]["assets"] = [
        {"symbol": "SPY", "weight": 75},
        {"symbol": "QQQ", "weight": 75},
    ]
    leveraged_request = PortfolioRequest.model_validate(leveraged_payload)
    spec = leveraged_request.to_specs()[0]
    assert spec.weights == pytest.approx((0.75, 0.75))
    assert spec.target_gross_exposure == pytest.approx(1.5)
    assert spec.target_asset_mix == pytest.approx({"SPY": 0.5, "QQQ": 0.5})


def test_non_100_weights_fail_closed_with_explicit_legacy_leverage() -> None:
    payload = _payload()
    payload["portfolios"][0]["assets"] = [{"symbol": "SPY", "weight": 150}]
    payload["leverage"] = {"type": "fixed_ratio", "ratio": 2.0}
    with pytest.raises(ValidationError, match="non-100% weights already define"):
        PortfolioRequest.model_validate(payload)

    payload = _payload()
    payload["leverage"] = {"type": "fixed_ratio", "ratio": 1.5}
    request = PortfolioRequest.model_validate(payload)
    assert request.to_simulation_config().leverage.ratio == pytest.approx(1.5)
