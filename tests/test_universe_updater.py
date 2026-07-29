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
