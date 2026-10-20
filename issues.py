"""
issues.py - Find problems after matching.

Three kinds of issues:
  - "amount_mismatch":  a receipt matched a charge, but the amounts differ
                        (often a tip added after signing).
  - "duplicate_charge": a charge with no receipt that looks like a repeat of
                        another charge (same amount, same vendor, close date).
  - "missing_receipt":  any other charge with no receipt.
"""

from matching import MAX_DAYS_APART, vendor_similarity

# Differences smaller than one cent are just rounding, not a real mismatch.
AMOUNT_TOLERANCE = 0.01
# How alike two bank descriptions must be to count as the "same vendor".
SAME_VENDOR_SIMILARITY = 0.8


def looks_like_duplicate(transaction, other):
    """True if `other` looks like the same charge as `transaction`."""
    same_amount = abs(transaction["amount"] - other["amount"]) < AMOUNT_TOLERANCE
    days_apart = abs((transaction["date"] - other["date"]).days)
    same_vendor = vendor_similarity(
        transaction["description"], other["description"]
    ) >= SAME_VENDOR_SIMILARITY
    return same_amount and same_vendor and days_apart <= MAX_DAYS_APART


def find_issues(match_result, transactions):
    """
    Look through the output of matching.match() and list the problems.

    `transactions` is the full list from load_bank_csv(), used to look for
    duplicates.

    Returns a list of dicts, each with an "id", a "type", the
    "transaction" involved, and a plain-English "message".
    """
    issues = []

    def add_issue(issue_type, transaction, message, **extra):
        # Give every issue an id like "i1" so the agent can refer to it.
        issue = {
            "id": f"i{len(issues) + 1}",
            "type": issue_type,
            "transaction": transaction,
            "message": message,
        }
        issue.update(extra)
        issues.append(issue)

    # 1. Amount mismatches: matched, but the numbers don't agree.
    for m in match_result["matches"]:
        charged = m["transaction"]["amount"]
        on_receipt = m["receipt"]["total"]
        difference = round(charged - on_receipt, 2)
        if abs(difference) >= AMOUNT_TOLERANCE:
            reason = " (possible tip added after signing)" if difference > 0 else ""
            add_issue(
                "amount_mismatch",
                m["transaction"],
                f"{m['receipt']['vendor']}: bank charged ${charged:.2f} but the "
                f"receipt says ${on_receipt:.2f}, a difference of "
                f"${difference:.2f}{reason}.",
                receipt=m["receipt"],
                difference=difference,
            )

    # Ids of transactions that DID get a receipt.
    matched_ids = {m["transaction"]["id"] for m in match_result["matches"]}

    # 2 and 3. Charges with no receipt: duplicate, or just missing?
    for t in match_result["unmatched_transactions"]:
        original = None
        for other in transactions:
            if other["id"] == t["id"]:
                continue
            # Only treat `other` as the "original" if it has a receipt or
            # happened earlier. That way, of two identical charges, the
            # later one is the one flagged as the duplicate.
            is_original = other["id"] in matched_ids or other["date"] < t["date"]
            if is_original and looks_like_duplicate(t, other):
                original = other
                break

        if original is not None:
            add_issue(
                "duplicate_charge",
                t,
                f"{t['description']}: ${t['amount']:.2f} on {t['date']} looks "
                f"like a repeat of the same charge on {original['date']}, "
                f"and there is only one receipt.",
                duplicate_of=original,
            )
        else:
            add_issue(
                "missing_receipt",
                t,
                f"{t['description']}: ${t['amount']:.2f} on {t['date']} has "
                f"no matching receipt.",
            )

    return issues
