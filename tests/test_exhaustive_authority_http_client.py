from __future__ import annotations

import gzip
import json

import pytest

from apps.api.app.research.exhaustive_authority_http import (
    GZIP_THRESHOLD_BYTES,
    MAX_AUTHORITY_JSON_BYTES,
    _encode_payload,
)


def test_authority_client_keeps_small_json_uncompressed():
    body, encoding = _encode_payload({"type": "version"})

    assert encoding is None
    assert json.loads(body) == {"type": "version"}


def test_authority_client_gzips_large_json_without_changing_payload():
    payload = {"values": [123.456789] * (GZIP_THRESHOLD_BYTES // 8)}

    body, encoding = _encode_payload(payload)

    assert encoding == "gzip"
    assert json.loads(gzip.decompress(body)) == payload


def test_authority_client_rejects_nonfinite_json_before_network():
    with pytest.raises(RuntimeError, match="finite JSON"):
        _encode_payload({"value": float("nan")})


def test_authority_client_rejects_decoded_payload_above_safety_ceiling():
    payload = {"value": "x" * MAX_AUTHORITY_JSON_BYTES}

    with pytest.raises(RuntimeError, match="16 MiB decoded safety ceiling"):
        _encode_payload(payload)
