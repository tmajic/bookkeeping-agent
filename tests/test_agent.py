"""Tests for agent.py using the fake model client (no API calls)."""

import pytest

from agent import estimate_cost, run_agent
from issues import find_issues
from matching import match
from tests.fake_client import FakeModelClient, fake_response, tool_call


@pytest.fixture
def issues(transactions, receipts):
    return find_issues(match(transactions, receipts), transactions)


def test_happy_path(transactions, issues):
    # Script what the "model" does, step by step.
    categorize_calls = [
        tool_call(f"c{t['id']}", "categorize_expense",
                  transaction_id=t["id"], category="Other")
        for t in transactions
    ]
    email_calls = [
        tool_call(f"e{i['id']}", "draft_vendor_email",
                  issue_id=i["id"], subject="Question", body="Hello...")
        for i in issues
    ]
    client = FakeModelClient([
        fake_response([tool_call("a", "get_unresolved_items")]),
        fake_response(categorize_calls),
        fake_response(email_calls),
        fake_response([tool_call("z", "finish", summary="All done.")]),
    ])

    result = run_agent(transactions, issues, client=client, model="fake")

    assert result["stopped_reason"] == "finished"
    assert result["steps"] == 4
    assert len(result["categories"]) == len(transactions)
    assert len(result["emails"]) == 3
    assert result["summary"] == "All done."
    # Each fake response used 100 input and 20 output tokens.
    assert result["input_tokens"] == 400
    assert result["output_tokens"] == 80
    assert result["cost_usd"] == pytest.approx(estimate_cost(400, 80))


def test_stops_after_10_steps(transactions, issues):
    # A "model" that never calls finish.
    client = FakeModelClient([fake_response([tool_call("a", "get_unresolved_items")])])
    result = run_agent(transactions, issues, client=client, model="fake")
    assert result["steps"] == 10
    assert result["stopped_reason"] == "max_steps"
    assert len(client.requests) == 10


def test_invalid_category_is_rejected(transactions, issues):
    client = FakeModelClient([
        fake_response([tool_call("a", "categorize_expense",
                                 transaction_id="t1", category="Pizza")]),
        fake_response([tool_call("z", "finish", summary="done")]),
    ])
    result = run_agent(transactions, issues, client=client, model="fake")
    assert "t1" not in result["categories"]
    # The error was sent back to the model as the tool result.
    tool_messages = [m for m in client.requests[-1]["messages"] if m["role"] == "tool"]
    assert "not allowed" in tool_messages[0]["content"]


def test_cost_math():
    # 1 million input tokens = $1.25, 1 million output tokens = $4.25
    assert estimate_cost(1_000_000, 0) == pytest.approx(1.25)
    assert estimate_cost(0, 1_000_000) == pytest.approx(4.25)
    assert estimate_cost(2000, 500) == pytest.approx(0.0025 + 0.002125)
