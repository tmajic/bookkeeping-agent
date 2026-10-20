"""
app.py - A simple web page for reconciling receipts.

Run it with:   streamlit run app.py
"""

import pandas as pd
import streamlit as st

from agent import run_agent
from bank import load_bank_csv
from issues import find_issues
from matching import match
from receipts import get_muse_settings, make_client, read_receipt, receipt_with_date

st.set_page_config(page_title="Bookkeeping Agent", layout="wide")
st.title("Bookkeeping Agent")
st.caption("An AI bookkeeping agent for small businesses.")
st.write("Upload a bank statement CSV and receipt photos, then click **Reconcile**.")

csv_file = st.file_uploader("Bank statement (CSV)", type=["csv"])
image_files = st.file_uploader(
    "Receipt images", type=["jpg", "jpeg", "png"], accept_multiple_files=True
)

if st.button("Reconcile", type="primary", disabled=not (csv_file and image_files)):
    # Check the .env settings before doing any work.
    try:
        _key, _url, model = get_muse_settings()
        client = make_client()
    except RuntimeError as error:
        st.error(str(error))
        st.stop()

    # 1. Read the bank statement.
    transactions = load_bank_csv(csv_file)

    # 2. Read each receipt with the model (cached results are reused).
    receipts = []
    with st.spinner("Reading receipts..."):
        for image in image_files:
            try:
                result = read_receipt(
                    image_bytes=image.getvalue(), filename=image.name,
                    client=client, model=model,
                )
                receipts.append(receipt_with_date(result))
            except Exception as error:
                st.warning(f"Could not read {image.name}: {error}")

    # 3. Match and find issues - plain Python, no AI.
    result = match(transactions, receipts)
    issues = find_issues(result, transactions)

    # 4. Let the agent categorize expenses and draft emails.
    with st.spinner("Agent is categorizing and drafting emails..."):
        agent_result = run_agent(transactions, issues, client=client, model=model)

    # ---- Show the results ----

    st.header("Matches")
    st.dataframe(pd.DataFrame([
        {
            "Bank date": str(m["transaction"]["date"]),
            "Bank description": m["transaction"]["description"],
            "Charged": m["transaction"]["amount"],
            "Receipt": m["receipt"]["file"],
            "Receipt vendor": m["receipt"]["vendor"],
            "Receipt total": m["receipt"]["total"],
            "Score": m["score"],
        }
        for m in result["matches"]
    ]), hide_index=True)
    if result["unmatched_receipts"]:
        names = ", ".join(r["file"] for r in result["unmatched_receipts"])
        st.info(f"Receipts with no matching bank charge: {names}")

    st.header(f"Issues ({len(issues)})")
    if not issues:
        st.success("No problems found.")
    for issue in issues:
        label = issue["type"].replace("_", " ").title()
        st.warning(f"**{label}** - {issue['message']}")

    st.header("Categories")
    st.dataframe(pd.DataFrame([
        {
            "Date": str(t["date"]),
            "Description": t["description"],
            "Amount": t["amount"],
            "Category": agent_result["categories"].get(t["id"], "(not categorized)"),
        }
        for t in transactions
    ]), hide_index=True)

    st.header("Drafted emails")
    if not agent_result["emails"]:
        st.write("No emails drafted.")
    for email in agent_result["emails"]:
        with st.expander(f"{email['vendor']}: {email['subject']}"):
            st.text(email["body"])

    st.header("Agent run")
    if agent_result["summary"]:
        st.write(agent_result["summary"])
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Steps", f"{agent_result['steps']} / 10")
    col2.metric("Input tokens", f"{agent_result['input_tokens']:,}")
    col3.metric("Output tokens", f"{agent_result['output_tokens']:,}")
    col4.metric("Estimated cost", f"${agent_result['cost_usd']:.4f}")
    st.caption(f"Stopped because: {agent_result['stopped_reason']}. "
               "Receipt reading costs are not included in this estimate.")
