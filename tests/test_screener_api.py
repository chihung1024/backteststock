import pytest

from api import screener as api


@pytest.fixture()
def client():
    api.app.config.update(TESTING=True)
    api.DATASET_CACHE.clear()
    return api.app.test_client()


def test_merge_datasets_fills_broad_coverage_and_preserves_richer_fields():
    nasdaq = {
        "data": [
            {
                "ticker": "AAA",
                "companyName": "AAA Nasdaq",
                "sector": "Technology",
                "marketCap": 10_000,
            },
            {
                "ticker": "BBB",
                "companyName": "BBB Nasdaq",
                "sector": "Healthcare",
                "marketCap": 20_000,
            },
        ],
        "asOf": "2026-07-31",
        "warning": "nasdaq warning",
        "source": "Nasdaq",
    }
    gist = {
        "data": [
            {
                "ticker": "AAA",
                "companyName": "AAA Rich",
                "trailingPE": 18,
                "marketCap": None,
            }
        ],
        "asOf": "2026-07-30",
        "warning": None,
        "source": "Gist",
    }

    merged = api.merge_datasets(nasdaq, gist)
    records = {item["ticker"]: item for item in merged["data"]}

    assert set(records) == {"AAA", "BBB"}
    assert records["AAA"]["companyName"] == "AAA Rich"
    assert records["AAA"]["marketCap"] == 10_000
    assert records["AAA"]["trailingPE"] == 18
    assert records["BBB"]["marketCap"] == 20_000


def test_nasdaq_sector_names_match_frontend_taxonomy():
    assert api.normalize_sector("Health Care") == "Healthcare"
    assert api.normalize_sector("Consumer Discretionary") == "Consumer Cyclical"
    assert api.normalize_sector("Consumer Staples") == "Consumer Defensive"
    assert api.normalize_sector("Finance") == "Financial Services"
    assert api.normalize_sector("Telecommunications") == "Communication Services"


def test_russell2000_members_receive_tickers_from_broad_dataset(client, monkeypatch):
    dataset = {
        "data": [
            {
                "ticker": "SMALL1",
                "companyName": "Small One",
                "sector": "Technology",
                "marketCap": 8e9,
            },
            {
                "ticker": "SMALL2",
                "companyName": "Small Two",
                "sector": "Industrials",
                "marketCap": 5e9,
            },
            {
                "ticker": "OTHER",
                "companyName": "Outside Universe",
                "sector": "Technology",
                "marketCap": 20e9,
            },
        ],
        "asOf": "2026-07-31",
        "warnings": ["Nasdaq coverage"],
        "sources": ["Nasdaq official stock screener"],
    }
    monkeypatch.setattr(api, "get_comprehensive_dataset", lambda: dataset)

    response = client.post(
        "/api/v2/screener",
        json={
            "_universe": {
                "id": "russell2000",
                "name": "Russell 2000（IWM holdings 代理）",
                "version": "2026-07-28-test",
                "sourceAsOf": "2026-07-28",
                "proxyNote": "IWM proxy disclosure",
                "members": ["SMALL1", "SMALL2", "MISSING"],
            },
            "universe": "russell2000",
            "sector": "any",
            "filters": {"marketCap": {"min": 1e9}},
            "sort": "marketCap-desc",
            "limit": None,
        },
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert [item["ticker"] for item in payload["candidates"]] == [
        "SMALL1",
        "SMALL2",
    ]
    assert payload["funnel"] == {
        "universeCount": 3,
        "fundamentalsAvailable": 2,
        "sectorMatches": 2,
        "passedFilters": 2,
        "selectedForScan": 2,
    }
    assert payload["fundamentalsSources"] == ["Nasdaq official stock screener"]
    assert any("1 檔" in warning for warning in payload["warnings"])


def test_missing_pe_is_reported_instead_of_silently_empty(client, monkeypatch):
    monkeypatch.setattr(
        api,
        "get_comprehensive_dataset",
        lambda: {
            "data": [{"ticker": "AAA", "marketCap": 2e9}],
            "asOf": "2026-07-31",
            "warnings": [],
            "sources": ["Nasdaq"],
        },
    )

    response = client.post(
        "/api/v2/screener",
        json={
            "_universe": {
                "id": "russell2000",
                "name": "Russell 2000",
                "version": "test-version",
                "members": ["AAA"],
            },
            "filters": {"trailingPE": {"max": 30}},
        },
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["candidates"] == []
    assert any("本益比" in warning for warning in payload["warnings"])


def test_all_tickers_uses_comprehensive_dataset(client, monkeypatch):
    monkeypatch.setattr(
        api,
        "get_comprehensive_dataset",
        lambda: {
            "data": [
                {"ticker": "BBB"},
                {"ticker": "AAA"},
                {"ticker": "BRK.B"},
            ],
            "asOf": "2026-07-31",
            "warnings": [],
            "sources": ["Nasdaq"],
        },
    )

    response = client.get("/api/all-tickers")
    assert response.status_code == 200
    assert response.get_json() == ["AAA", "BBB", "BRK-B"]
