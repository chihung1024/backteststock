from __future__ import annotations

from datetime import date

import pandas as pd

from apps.api.app.data.fx_provider import FXDownloadError, FXLevels
from apps.api.app.data.history_service import TWDHistoryService


def _prices(values: list[float], dates: list[str]) -> pd.Series:
    result = pd.Series(values, index=pd.to_datetime(dates), dtype=float)
    result.attrs["corporate_action_audit"] = {"status": "verified_standard_actions"}
    return result


class FakeFXProvider:
    def __init__(self, currencies: dict[str, str], rates: dict[str, pd.Series]) -> None:
        self.currencies = currencies
        self.rates = rates

    def quote_currency(self, symbol: str) -> str:
        value = self.currencies[symbol]
        if value == "ERROR":
            raise FXDownloadError(f"quote currency unavailable for {symbol}")
        return value

    def fx_to_twd(self, currency: str, _start: date, _end: date) -> FXLevels:
        levels = self.rates.get(currency)
        if levels is None:
            raise FXDownloadError(f"FX unavailable for {currency}/TWD")
        return FXLevels(
            source_currency=currency,
            target_currency="TWD",
            levels=levels,
            method="direct",
            tickers=(f"{currency}TWD=X",),
            correction_count=0,
            unresolved_count=0,
            material_transition_count=0,
        )


def test_partial_histories_preserve_successes_and_input_order(monkeypatch) -> None:
    good = _prices([100.0, 101.0], ["2025-01-02", "2025-01-03"])
    taiwan = _prices([500.0, 510.0], ["2025-01-02", "2025-01-03"])
    fx = _prices([30.0, 30.2], ["2025-01-02", "2025-01-03"])
    monkeypatch.setattr(
        "apps.api.app.data.history_service.download_prices_finitely",
        lambda *_args: ({"GOOD": good, "2330.TW": taiwan}, ["BAD"]),
    )
    service = TWDHistoryService(
        fx_provider=FakeFXProvider(
            {"GOOD": "USD", "2330.TW": "TWD"},
            {"USD": fx},
        )
    )

    result = service.histories_partial(
        ["good", "bad", "2330", "GOOD"], date(2025, 1, 2), date(2025, 1, 3)
    )

    assert result.requested == ("GOOD", "BAD", "2330.TW")
    assert set(result.histories) == {"GOOD", "2330.TW"}
    assert result.histories["GOOD"].adjusted_close_twd.tolist() == [3000.0, 3050.2]
    assert result.histories["2330.TW"].adjusted_close_twd.tolist() == [500.0, 510.0]
    assert result.histories["GOOD"].corporate_action_audit == {
        "status": "verified_standard_actions"
    }
    assert result.failures["BAD"].stage == "download"
    assert result.is_complete is False


def test_currency_failure_does_not_erase_other_symbols(monkeypatch) -> None:
    good = _prices([100.0, 101.0], ["2025-01-02", "2025-01-03"])
    bad = _prices([20.0, 21.0], ["2025-01-02", "2025-01-03"])
    fx = _prices([30.0, 30.1], ["2025-01-02", "2025-01-03"])
    monkeypatch.setattr(
        "apps.api.app.data.history_service.download_prices_finitely",
        lambda *_args: ({"GOOD": good, "BAD": bad}, []),
    )
    service = TWDHistoryService(
        fx_provider=FakeFXProvider({"GOOD": "USD", "BAD": "ERROR"}, {"USD": fx})
    )

    result = service.histories_partial(["GOOD", "BAD"], date(2025, 1, 2), date(2025, 1, 3))

    assert set(result.histories) == {"GOOD"}
    assert result.failures["BAD"].stage == "currency"
    assert result.failures["BAD"].retryable is True


def test_one_fx_group_failure_does_not_erase_twd_group(monkeypatch) -> None:
    usd = _prices([100.0, 101.0], ["2025-01-02", "2025-01-03"])
    twd = _prices([500.0, 510.0], ["2025-01-02", "2025-01-03"])
    monkeypatch.setattr(
        "apps.api.app.data.history_service.download_prices_finitely",
        lambda *_args: ({"USD": usd, "TWD": twd}, []),
    )
    service = TWDHistoryService(
        fx_provider=FakeFXProvider({"USD": "USD", "TWD": "TWD"}, {})
    )

    result = service.histories_partial(["USD", "TWD"], date(2025, 1, 2), date(2025, 1, 3))

    assert set(result.histories) == {"TWD"}
    assert result.failures["USD"].stage == "fx"
    assert result.failures["USD"].retryable is True


def test_service_preserves_fx_only_valuation_day(monkeypatch) -> None:
    native = _prices([100.0, 100.0], ["2025-01-02", "2025-01-06"])
    fx = _prices([30.0, 30.2, 30.3], ["2025-01-02", "2025-01-03", "2025-01-06"])
    monkeypatch.setattr(
        "apps.api.app.data.history_service.download_prices_finitely",
        lambda *_args: ({"GOOD": native}, []),
    )
    service = TWDHistoryService(
        fx_provider=FakeFXProvider({"GOOD": "USD"}, {"USD": fx})
    )

    result = service.histories_partial(["GOOD"], date(2025, 1, 2), date(2025, 1, 6))

    history = result.histories["GOOD"]
    assert history.adjusted_close_twd.tolist() == [3000.0, 3020.0, 3030.0]
    assert history.daily_returns.iloc[1] == 30.2 / 30.0 - 1.0


def test_whole_download_failure_is_an_explicit_failure_for_every_symbol(monkeypatch) -> None:
    def fail(*_args):
        raise RuntimeError("upstream unavailable")

    monkeypatch.setattr("apps.api.app.data.history_service.download_prices_finitely", fail)
    service = TWDHistoryService(fx_provider=FakeFXProvider({}, {}))

    result = service.histories_partial(["GOOD", "BAD"], date(2025, 1, 2), date(2025, 1, 3))

    assert result.histories == {}
    assert set(result.failures) == {"GOOD", "BAD"}
    assert all(failure.stage == "download" for failure in result.failures.values())
