"""Tests for bank.py."""

from datetime import date


def test_deposit_is_skipped(transactions):
    # 8 rows in the CSV, 1 is the $2,400 deposit, so 7 expenses remain.
    assert len(transactions) == 7
    assert all("DEPOSIT" not in t["description"] for t in transactions)


def test_amounts_are_positive_and_dates_parsed(transactions):
    first = transactions[0]
    assert first["id"] == "t1"
    assert first["date"] == date(2026, 10, 2)
    assert first["amount"] == 53.56
    assert all(t["amount"] > 0 for t in transactions)
