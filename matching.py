"""
matching.py - Pair bank transactions with receipts, using plain Python.

Each (transaction, receipt) pair gets a score between 0 and 1 built from:
  - vendor-name similarity  (50% of the score)
  - amount closeness        (30%)
  - date closeness          (20%)  - must be within 4 days, or the score is 0

Then we pick matches "greedily": best-scoring pair first, then the next best
pair that doesn't reuse a transaction or receipt, and so on.
"""

import re
from difflib import SequenceMatcher

MAX_DAYS_APART = 4
DEFAULT_THRESHOLD = 0.7  # correct pairs score ~0.9+, wrong ones under 0.6

# How much each part counts toward the total score. They add up to 1.0.
VENDOR_WEIGHT = 0.5
AMOUNT_WEIGHT = 0.3
DATE_WEIGHT = 0.2

# Banks shorten store names. This maps common short forms to full words,
# so "MAIN ST HDWE" becomes "main street hardware".
# Add to this list whenever you see a new abbreviation in your statements.
ABBREVIATIONS = {
    "st": "street",
    "hdwe": "hardware",
    "hdw": "hardware",
    "prt": "parts",
    "pts": "parts",
    "sup": "supply",
    "supp": "supply",
    "ofc": "office",
    "svc": "service",
    "svcs": "services",
    "mkt": "market",
    "rest": "restaurant",
    "intl": "international",
    "co": "company",
}

# Card processors add prefixes like "SQ *" (Square) or "TST*" (Toast).
PROCESSOR_PREFIX = re.compile(r"^(sq|tst|sp|pp|paypal)\s*\*\s*")


def normalize_name(name):
    """
    Turn a messy name into simple lowercase words.

    Example: "SQ *HARBOR GRILL LAKEVIEW" -> "harbor grill lakeview"
             "MAIN ST HDWE FAIRVIEW"    -> "main street hardware fairview"
    """
    text = name.lower().strip()
    text = PROCESSOR_PREFIX.sub("", text)    # remove "sq *" etc.
    text = re.sub(r"#\s*\d+", " ", text)      # remove store numbers like "#12"
    text = re.sub(r"[^a-z0-9\s]", " ", text)  # replace punctuation with spaces
    words = text.split()
    words = [ABBREVIATIONS.get(word, word) for word in words]
    return " ".join(words)


def word_similarity(a, b):
    """How alike two words are, from 0.0 (nothing alike) to 1.0 (identical)."""
    return SequenceMatcher(None, a, b).ratio()


def vendor_similarity(bank_description, receipt_vendor):
    """
    Score how well a bank description matches a receipt's vendor name (0-1).

    For each word on the RECEIPT we find the closest word in the BANK
    description and average those scores. Going this direction means extra
    bank words (like the city "FAIRVIEW") don't lower the score.
    """
    bank_words = normalize_name(bank_description).split()
    receipt_words = normalize_name(receipt_vendor).split()
    if not bank_words or not receipt_words:
        return 0.0

    total = 0.0
    for r_word in receipt_words:
        best = max(word_similarity(r_word, b_word) for b_word in bank_words)
        total += best
    return total / len(receipt_words)


def amount_score(amount_a, amount_b):
    """
    1.0 when amounts are equal, falling toward 0 as they drift apart.

    Example: 36.84 vs 43.84 -> about 0.84 (still fairly close).
    """
    biggest = max(amount_a, amount_b)
    if biggest == 0:
        return 1.0
    return max(0.0, 1 - abs(amount_a - amount_b) / biggest)


def date_score(date_a, date_b):
    """
    1.0 for the same day, a bit less for each day apart,
    and 0.0 if the dates are more than MAX_DAYS_APART days apart.
    """
    days_apart = abs((date_a - date_b).days)
    if days_apart > MAX_DAYS_APART:
        return 0.0
    return 1 - days_apart / (MAX_DAYS_APART + 1)


def score_pair(transaction, receipt):
    """Combine the three scores for one transaction/receipt pair (0-1)."""
    d_score = date_score(transaction["date"], receipt["date"])
    if d_score == 0:
        # Too far apart in time to be the same purchase.
        return 0.0

    v_score = vendor_similarity(transaction["description"], receipt["vendor"])
    a_score = amount_score(transaction["amount"], receipt["total"])
    return VENDOR_WEIGHT * v_score + AMOUNT_WEIGHT * a_score + DATE_WEIGHT * d_score


def match(transactions, receipts, threshold=DEFAULT_THRESHOLD):
    """
    Pair up transactions and receipts.

    Receipts need a real date object in "date"
    (see receipts.receipt_with_date).

    Returns a dict:
      "matches":                list of {"transaction", "receipt", "score"}
      "unmatched_transactions": transactions with no receipt
      "unmatched_receipts":     receipts with no transaction
    """
    # Step 1: score every possible pair.
    candidates = []
    for t_index, transaction in enumerate(transactions):
        for r_index, receipt in enumerate(receipts):
            score = score_pair(transaction, receipt)
            if score >= threshold:
                candidates.append((score, t_index, r_index))

    # Step 2: best scores first.
    candidates.sort(reverse=True)

    # Step 3: take each pair unless its transaction or receipt is already used.
    used_transactions = set()
    used_receipts = set()
    matches = []
    for score, t_index, r_index in candidates:
        if t_index in used_transactions or r_index in used_receipts:
            continue
        used_transactions.add(t_index)
        used_receipts.add(r_index)
        matches.append({
            "transaction": transactions[t_index],
            "receipt": receipts[r_index],
            "score": round(score, 3),
        })

    # Keep matches in date order so they're easy to read.
    matches.sort(key=lambda m: m["transaction"]["date"])

    return {
        "matches": matches,
        "unmatched_transactions": [
            t for i, t in enumerate(transactions) if i not in used_transactions
        ],
        "unmatched_receipts": [
            r for i, r in enumerate(receipts) if i not in used_receipts
        ],
    }
