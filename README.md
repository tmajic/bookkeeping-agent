# Receipt Match Agent

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
