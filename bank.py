"""
bank.py - Read a bank statement CSV into a list of simple dictionaries.

The CSV is expected to have three columns: date, description, amount.
Money going OUT of the account is negative (an expense).
Money coming IN is positive (a deposit) and is skipped, because
deposits don't need receipts.
"""

import csv
import io
from datetime import date


def load_bank_csv(path_or_file):
    """
    Load expenses from a bank CSV.

    `path_or_file` can be either:
      - a file path like "samples/bank.csv", or
      - an uploaded file object (for example from Streamlit).

    Returns a list of dicts like:
      {"id": "t1", "date": date(2026, 10, 2),
       "description": "NORTHGATE FUEL #12 FAIRVIEW", "amount": 53.56}

    Amounts are returned as POSITIVE numbers so the rest of the code
    can compare them directly with receipt totals.
    """
    # Get the CSV text, whether we were given a path or a file object.
    if hasattr(path_or_file, "read"):
        raw = path_or_file.read()
        # Uploaded files give us bytes; turn them into text.
        text = raw.decode("utf-8-sig") if isinstance(raw, bytes) else raw
    else:
        with open(path_or_file, encoding="utf-8-sig") as f:
            text = f.read()

    transactions = []
    reader = csv.DictReader(io.StringIO(text))
    for row in reader:
        amount = float(row["amount"])

        # Positive amounts are deposits (income). We only care about expenses.
        if amount > 0:
            continue

        transactions.append({
            # A short id so other parts of the program (and the agent)
            # can refer to this exact transaction.
            "id": f"t{len(transactions) + 1}",
            # date.fromisoformat turns "2026-10-02" into a real date object,
            # which lets us subtract dates later.
            "date": date.fromisoformat(row["date"].strip()),
            "description": row["description"].strip(),
            # abs() turns -53.56 into 53.56. round() avoids tiny float noise.
            "amount": round(abs(amount), 2),
        })

    return transactions
