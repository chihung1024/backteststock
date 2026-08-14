from __future__ import annotations

import pytest

from api import index_v2
from apps.api.app.backtest_service import TWDBacktestBatch
from apps.api.app.data.history_service import PartialTWDHistories


@pytest.fixture()
def client():
    index_v2.app.config.update(TESTING=True)
    return index_v2.app.test_client()


def test_production_backtest_explicitly_reports_gross_cost_semantics(
    client, monkeypatch
) -> None:
    class FakeTWDService:
        def run(self, _specs, **_kwargs):
            return TWDBacktestBatch(
                requested=("AAA",),
                results=[
                    {
                        "name": "Portfolio",
                        "metric_start": "2024-01-02",
                        "metric_end": "2024-01-31",
                        "metric_price_observations": 21,
                        "valuationCurrency": "TWD",
                        "portfolioHistory": [],
                    }
                ],
                failures=[],
                benchmark=None,
                benchmark_failure=None,
                histories=PartialTWDHistories(
                    requested=("AAA",), histories={}, failures={}
                ),
            )

    monkeypatch.setattr(index_v2, "twd_backtest_service", FakeTWDService())
    response = client.post(
        "/api/backtest",
        json={
            "initialAmount": 10000,
            "startYear": 2024,
            "startMonth": 1,
            "endYear": 2024,
            "endMonth": 1,
            "rebalancingPeriod": "never",
            "portfolios": [
                {
                    "name": "Portfolio",
                    "tickers": ["AAA"],
                    "weights": [100],
                    "rebalancingPeriod": "never",
                }
            ],
        },
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["returnSemantics"] == {
        "basis": "gross_before_transaction_costs",
        "transactionCostsIncluded": False,
        "transactionCostBps": None,
        "slippageIncluded": False,
        "taxesIncluded": False,
    }
    assert payload["metadata"]["return_semantics"] == (
        "gross_before_transaction_costs"
    )
    assert payload["metadata"]["transaction_costs_included"] is False
    assert payload["metadata"]["transaction_cost_bps"] is None
    assert payload["metadata"]["slippage_included"] is False
    assert payload["metadata"]["taxes_included"] is False
    assert "Gross" in payload["warning"]
    assert "未計交易成本、滑價與稅負" in payload["warning"]
