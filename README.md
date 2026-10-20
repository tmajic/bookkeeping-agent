# Bookkeeping Agent

An AI bookkeeping agent for small businesses.

Matches bank charges to receipt photos, flags problems, then lets an AI agent
categorize expenses and draft emails to vendors.

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env      # then put your Muse Spark key, base URL and model in .env
```

`.env` is in `.gitignore`, so your API key won't be committed.

## Run

```bash
streamlit run app.py      # open the page, upload samples/bank.csv and samples/receipts/*.jpg
pytest -v                 # run the tests (no API calls, no key needed)
```

## Results on the sample data

Using Muse Spark on the files in `samples/`:

- All 5 receipts are read correctly (vendor, date and total match `samples/ANSWER_KEY.md`).
- All 3 planted problems are caught: a duplicate Main St Hardware charge, a $7.00
  tip mismatch at Harbor Grill, and a missing Brightline Print & Sign receipt.
  The $2,400 deposit is correctly skipped.
- The agent finishes in 3-4 of its 10 steps for about $0.02.
- Reading the 5 receipts costs about $0.015 the first time. After that the results
  come from the cache and are free.

## Screenshots

**Matches and issues:** every receipt is paired with its bank charge, and the 3 problems are flagged.

![Matches and issues](docs/matches-and-issues.png)

**Categories and drafted emails:** the duplicate charge is held instead of being counted as an expense.

![Categories and drafted emails](docs/categories-and-emails.png)

**Agent run:** steps used, tokens and estimated cost.

![Agent run](docs/agent-run.png)

## How it works

| Step | File | Who does it |
|---|---|---|
| 1. Read the bank CSV, skip deposits | `bank.py` | Python |
| 2. Read each receipt photo (vendor, date, total) | `receipts.py` | Muse Spark model, cached by image hash in `receipt_cache.json` |
| 3. Score every charge/receipt pair and pick the best matches | `matching.py` | Python (difflib) |
| 4. Find missing receipts, amount mismatches, duplicates | `issues.py` | Python |
| 5. Categorize expenses and draft vendor emails | `agent.py` | Model chooses tools, Python runs them |
| 6. Show everything on a web page | `app.py` | Streamlit |

**Matching score** = 50% vendor-name similarity + 30% amount closeness + 20% date
closeness. Pairs more than 4 days apart score 0. Pairs need a score of at least
0.7 to match. Bank abbreviations like `HDWE` are expanded using the
`ABBREVIATIONS` table in `matching.py`. Add new ones there when you see them.

**Agent loop**: the model can call `get_unresolved_items`, `categorize_expense`,
`draft_vendor_email` and `finish`. It runs for at most 10 steps. Token usage is
added up after each step, and the cost is estimated at $1.25 per million input
tokens and $4.25 per million output tokens.

**Tests** use the correct receipt values from `samples/ANSWER_KEY.md` and a
`FakeModelClient` (`tests/fake_client.py`) that plays back scripted replies. That
way the agent loop is tested without calling the API.
