"""
conftest.py - Shared test data. pytest loads this file automatically.

The receipts here are copied from samples/ANSWER_KEY.md, so we can test
matching and issue-finding without calling the AI model.
"""

import os
import sys
from datetime import date

import pytest

# Let the tests import bank.py, matching.py, etc. from the project folder.
PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_DIR)

from bank import load_bank_csv  # noqa: E402

SAMPLE_CSV = os.path.join(PROJECT_DIR, "samples", "bank.csv")


@pytest.fixture
def transactions():
    """The expenses from samples/bank.csv."""
    return load_bank_csv(SAMPLE_CSV)


@pytest.fixture
def receipts():
    """The correct receipt readings, straight from ANSWER_KEY.md."""
    return [
        {"vendor": "Northgate Fuel #12", "date": date(2026, 10, 2), "total": 53.56,
         "file": "01-northgate-fuel.jpg"},
        {"vendor": "Main Street Hardware", "date": date(2026, 10, 3), "total": 129.12,
         "file": "02-main-street-hardware.jpg"},
        {"vendor": "Precision Auto Parts", "date": date(2026, 10, 6), "total": 44.61,
         "file": "03-precision-auto.jpg"},
        {"vendor": "Harbor Grill", "date": date(2026, 10, 8), "total": 36.84,
         "file": "04-harbor-grill.jpg"},
        {"vendor": "Summit Office Supply", "date": date(2026, 10, 10), "total": 23.19,
         "file": "05-summit-office.jpg"},
    ]
