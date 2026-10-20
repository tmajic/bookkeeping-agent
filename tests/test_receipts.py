"""Tests for receipts.py - parsing and the hash cache (no real API calls)."""

import os

from receipts import parse_model_json, read_receipt
from tests.fake_client import FakeModelClient, fake_response

IMAGE = os.path.join(os.path.dirname(os.path.dirname(__file__)),
                     "samples", "receipts", "04-harbor-grill.jpg")


def test_parse_model_json_strips_code_fence():
    text = '```json\n{"vendor": "X", "date": "2026-10-08", "total": 1}\n```'
    assert parse_model_json(text)["vendor"] == "X"


def test_read_receipt_uses_cache(tmp_path):
    reply = '{"vendor": "Harbor Grill", "date": "2026-10-08", "total": "$36.84"}'
    client = FakeModelClient([fake_response(content=reply)])
    cache_path = tmp_path / "cache.json"

    first = read_receipt(IMAGE, client=client, model="fake", cache_path=cache_path)
    second = read_receipt(IMAGE, client=client, model="fake", cache_path=cache_path)

    assert first == second
    assert first["total"] == 36.84            # "$" removed, turned into a number
    assert first["date"] == "2026-10-08"
    assert len(client.requests) == 1          # second call came from the cache
