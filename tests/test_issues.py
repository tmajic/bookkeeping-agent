"""Tests for issues.py - the 3 planted problems from ANSWER_KEY.md."""

from datetime import date

from issues import find_issues
from matching import match


def get_issues(transactions, receipts):
    return find_issues(match(transactions, receipts), transactions)


def test_exactly_three_issues(transactions, receipts):
    issues = get_issues(transactions, receipts)
    assert sorted(i["type"] for i in issues) == [
        "amount_mismatch", "duplicate_charge", "missing_receipt",
    ]


def test_duplicate_main_street_charge(transactions, receipts):
    issue = next(i for i in get_issues(transactions, receipts)
                 if i["type"] == "duplicate_charge")
    assert issue["transaction"]["description"] == "MAIN ST HDWE FAIRVIEW"
    assert issue["transaction"]["date"] == date(2026, 10, 4)
    assert issue["transaction"]["amount"] == 129.12
    assert issue["duplicate_of"]["date"] == date(2026, 10, 3)


def test_harbor_grill_tip_mismatch(transactions, receipts):
    issue = next(i for i in get_issues(transactions, receipts)
                 if i["type"] == "amount_mismatch")
    assert issue["receipt"]["vendor"] == "Harbor Grill"
    assert issue["transaction"]["amount"] == 43.84
    assert issue["receipt"]["total"] == 36.84
    assert issue["difference"] == 7.00


def test_brightline_missing_receipt(transactions, receipts):
    issue = next(i for i in get_issues(transactions, receipts)
                 if i["type"] == "missing_receipt")
    assert issue["transaction"]["description"] == "BRIGHTLINE PRINT & SIGN"
    assert issue["transaction"]["amount"] == 75.00


def test_deposit_is_not_flagged(transactions, receipts):
    for issue in get_issues(transactions, receipts):
        assert "DEPOSIT" not in issue["transaction"]["description"]


def test_no_issues_when_everything_matches():
    t = [{"id": "t1", "date": date(2026, 10, 1), "description": "HARBOR GRILL",
          "amount": 20.0}]
    r = [{"vendor": "Harbor Grill", "date": date(2026, 10, 1), "total": 20.0}]
    assert find_issues(match(t, r), t) == []
