from __future__ import annotations

from datetime import date

import pytest

from apps.api.app.research.pit_client import PITResolverError, parse_pit_universe_payload


def _payload(*, authoritative: bool = True, is_proxy: bool = False) -> dict:
    return {
        "data": {
            "id": "soxx",
            "version": "2024-04-30-pit",
            "members": [
                {"ticker": "AAA", "sourceTicker": "AAA"},
                {"ticker": "BBB", "sourceTicker": "BBB"},
            ],
            "sourceAsOf": "2024-04-30",
            "fetchedAt": "2024-04-30T12:00:00Z",
            "evidenceAvailableAsOf": "2024-04-30",
            "checksum": "abc123",
            "requestedAsOf": "2024-04-30",
            "selectionMode": "point_in_time_last_causally_available",
            "pointInTime": True,
            "membershipCausal": True,
            "membershipAuthoritative": authoritative,
            "membershipPolicy": "latest-causally-available-observation-on-or-before-max-10d-v2",
            "source": {
                "label": "Fixture source",
                "url": "https://example.com/source",
                "isProxy": is_proxy,
            },
        }
    }


def test_pit_client_preserves_exact_worker_provenance():
    resolved = parse_pit_universe_payload(
        _payload(),
        expected_universe_id="soxx",
        expected_requested_as_of=date(2024, 4, 30),
    )

    assert resolved.universe_id == "soxx"
    assert resolved.requested_as_of == date(2024, 4, 30)
    assert resolved.source_as_of == date(2024, 4, 30)
    assert resolved.evidence_available_as_of == date(2024, 4, 30)
    assert resolved.fetched_at == "2024-04-30T12:00:00Z"
    assert resolved.members == ("AAA", "BBB")
    assert resolved.membership_authoritative is True
    assert resolved.source_is_proxy is False


def test_pit_client_rejects_noncausal_or_wrong_date_payloads():
    noncausal = _payload()
    noncausal["data"]["membershipCausal"] = False
    with pytest.raises(PITResolverError, match="not causally point-in-time"):
        parse_pit_universe_payload(
            noncausal,
            expected_universe_id="soxx",
            expected_requested_as_of=date(2024, 4, 30),
        )

    with pytest.raises(PITResolverError, match="different research date"):
        parse_pit_universe_payload(
            _payload(),
            expected_universe_id="soxx",
            expected_requested_as_of=date(2024, 4, 29),
        )


def test_pit_client_preserves_proxy_truth_instead_of_promoting_authority():
    resolved = parse_pit_universe_payload(
        _payload(authoritative=False, is_proxy=True),
        expected_universe_id="soxx",
        expected_requested_as_of=date(2024, 4, 30),
    )
    assert resolved.membership_authoritative is False
    assert resolved.source_is_proxy is True
