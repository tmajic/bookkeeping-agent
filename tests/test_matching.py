"""Tests for matching.py."""

from datetime import date

from matching import date_score, match, normalize_name, score_pair, vendor_similarity


def test_normalize_name_expands_abbreviations():
    assert normalize_name("MAIN ST HDWE FAIRVIEW") == "main street hardware fairview"
    assert normalize_name("SQ *HARBOR GRILL LAKEVIEW") == "harbor grill lakeview"
    assert normalize_name("NORTHGATE FUEL #12 FAIRVIEW") == "northgate fuel fairview"


def test_abbreviated_bank_name_prefers_the_right_vendor():
    bank = "MAIN ST HDWE FAIRVIEW"
    right = vendor_similarity(bank, "Main Street Hardware")
    for other in ["Summit Office Supply", "Harbor Grill", "Precision Auto Parts"]:
        assert right > vendor_similarity(bank, other)
    assert right > 0.9


def test_date_window():
    assert date_score(date(2026, 10, 1), date(2026, 10, 1)) == 1.0
    assert date_score(date(2026, 10, 1), date(2026, 10, 5)) > 0  # 4 days: OK
    assert date_score(date(2026, 10, 1), date(2026, 10, 6)) == 0  # 5 days: too far


def test_pair_more_than_4_days_apart_scores_zero():
    t = {"date": date(2026, 10, 1), "description": "HARBOR GRILL", "amount": 10.0}
    r = {"date": date(2026, 10, 6), "vendor": "Harbor Grill", "total": 10.0}
    assert score_pair(t, r) == 0


def test_every_receipt_matches_the_right_charge(transactions, receipts):
    result = match(transactions, receipts)
    assert len(result["matches"]) == 5
    assert result["unmatched_receipts"] == []

    # receipt file -> the bank date it was matched to
    pairs = {m["receipt"]["file"]: m["transaction"] for m in result["matches"]}
    assert pairs["01-northgate-fuel.jpg"]["description"].startswith("NORTHGATE")
    # Main Street matches the FIRST charge (10/03), not the duplicate.
    assert pairs["02-main-street-hardware.jpg"]["date"] == date(2026, 10, 3)
    # Bank posted these one day after the receipt date; still matched.
    assert pairs["03-precision-auto.jpg"]["date"] == date(2026, 10, 7)
    assert pairs["04-harbor-grill.jpg"]["date"] == date(2026, 10, 9)
    assert pairs["05-summit-office.jpg"]["description"].startswith("SUMMIT")


def test_unmatched_charges(transactions, receipts):
    result = match(transactions, receipts)
    leftover = {(t["description"], t["date"]) for t in result["unmatched_transactions"]}
    assert leftover == {
        ("MAIN ST HDWE FAIRVIEW", date(2026, 10, 4)),
        ("BRIGHTLINE PRINT & SIGN", date(2026, 10, 16)),
    }
