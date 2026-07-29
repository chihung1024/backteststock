import pytest

from scripts import update_universes as updater


def source_definition(**overrides):
    values = {
        "id": "test",
        "name": "Test Universe",
        "source_label": "Fixture",
        "source_url": "https://example.com/holdings",
        "adapter": "ishares_csv",
        "min_members": 2,
        "max_members": 3,
        "max_count_change_ratio": 0.2,
        "max_membership_churn_ratio": 0.2,
    }
    values.update(overrides)
    return updater.SourceDefinition(**values)


def test_parse_ishares_csv_filters_non_equity_and_normalizes_aliases():
    payload = """Example ETF
Fund Holdings as of,"Jul 28, 2026"
Ticker,Name,Sector,Asset Class,Market Value,Weight (%)
"BRKB","BERKSHIRE HATHAWAY","Financials","Equity","1000","6.5"
"AAPL","APPLE INC","Information Technology","Equity","900","5.5"
"USD","USD CASH","Cash and/or Derivatives","Cash","10","0.1"
"""
    source_as_of, members = updater.parse_ishares_csv(payload)
    assert source_as_of == "2026-07-28"
    assert [member.ticker for member in members] == ["BRK-B", "AAPL"]
    assert members[0].source_ticker == "BRKB"
    assert members[0].weight == 6.5


def test_parse_nasdaq_json_uses_official_nested_rows():
    payload = {
        "data": {
            "date": "Jul 28, 2026",
            "data": {
                "rows": [
                    {
                        "symbol": "MSFT",
                        "companyName": "Microsoft Corporation",
                        "marketCap": "2,900,000,000,000",
                    },
                    {
                        "symbol": "GOOGL",
                        "companyName": "Alphabet Inc.",
                        "marketCap": "2,000,000,000,000",
                    },
                ]
            },
        }
    }
    source_as_of, members = updater.parse_nasdaq_json(payload)
    assert source_as_of == "2026-07-28"
    assert [member.ticker for member in members] == ["MSFT", "GOOGL"]
    assert members[0].market_value == 2_900_000_000_000


def test_parse_invesco_json_only_keeps_equity_security_types():
    payload = {
        "effectiveBusinessDate": "2026-07-28",
        "holdings": [
            {
                "ticker": "AAPL",
                "issuerName": "Apple Inc",
                "securityTypeCode": "COM",
                "percentageOfTotalNetAssets": 8.1,
                "marketValueBase": 1_000,
            },
            {
                "ticker": "ASML",
                "issuerName": "ASML Holding NV",
                "securityTypeCode": "DRNY",
                "percentageOfTotalNetAssets": 1.2,
                "marketValueBase": 500,
            },
            {
                "ticker": "USD",
                "issuerName": "US Dollar",
                "securityTypeCode": "CURR",
            },
        ],
    }
    source_as_of, members = updater.parse_invesco_json(payload)
    assert source_as_of == "2026-07-28"
    assert [member.ticker for member in members] == ["AAPL", "ASML"]
    assert members[0].weight == 8.1
    assert members[0].market_value == 1_000


def test_fetch_snapshot_uses_invesco_fallback_after_primary_timeout(monkeypatch):
    fallback = updater.SourceEndpoint(
        source_label="Invesco QQQM holdings",
        source_url="https://example.com/qqqm",
        adapter="invesco_json",
        is_proxy=True,
        proxy_note="QQQM proxy",
    )
    source = source_definition(
        adapter="nasdaq_json",
        fallbacks=(fallback,),
    )

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "effectiveBusinessDate": "2026-07-28",
                "holdings": [
                    {
                        "ticker": "AAPL",
                        "issuerName": "Apple Inc",
                        "securityTypeCode": "COM",
                    },
                    {
                        "ticker": "MSFT",
                        "issuerName": "Microsoft Corp",
                        "securityTypeCode": "COM",
                    },
                ],
            }

    class FakeSession:
        def __init__(self):
            self.urls = []

        def get(self, url, timeout):
            self.urls.append((url, timeout))
            if url == source.source_url:
                raise updater.requests.Timeout("primary timeout")
            return FakeResponse()

    monkeypatch.setattr(updater, "validate_source_date", lambda *_args: None)
    session = FakeSession()
    snapshot = updater.fetch_snapshot(session, source)

    assert [url for url, _timeout in session.urls] == [
        source.source_url,
        fallback.source_url,
    ]
    assert snapshot.effective_source == fallback
    assert snapshot.effective_source.is_proxy is True
    assert [member.ticker for member in snapshot.members] == ["AAPL", "MSFT"]
    assert updater.snapshot_report(snapshot, False, None)["fallbackUsed"] is True


def test_validation_rejects_suspicious_member_count_change():
    members = (
        updater.Member("AAA", "AAA"),
        updater.Member("BBB", "BBB"),
    )
    with pytest.raises(updater.UniverseUpdateError, match="changed"):
        updater.validate_snapshot(
            source_definition(max_count_change_ratio=0.1),
            members,
            previous_member_count=3,
        )


def test_checksum_only_depends_on_normalized_membership():
    first = (
        updater.Member("AAA", "AAA", company_name="Old Name", weight=10),
        updater.Member("BBB", "BBB", company_name="Second", weight=20),
    )
    second = (
        updater.Member("AAA", "AAA", company_name="New Name", weight=99),
        updater.Member("BBB", "BBB", company_name="Second", weight=1),
    )
    assert updater.checksum_members(first) == updater.checksum_members(second)


def test_validation_rejects_same_size_but_unrelated_membership():
    members = (
        updater.Member("XXX", "XXX"),
        updater.Member("YYY", "YYY"),
    )
    with pytest.raises(updater.UniverseUpdateError, match="churn"):
        updater.validate_snapshot(
            source_definition(max_membership_churn_ratio=0.1),
            members,
            previous_member_count=2,
            previous_members={"AAA", "BBB"},
        )


def test_source_date_rejects_stale_snapshot():
    with pytest.raises(updater.UniverseUpdateError, match="stale"):
        updater.validate_source_date("test", "2000-01-01")
