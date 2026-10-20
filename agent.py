"""
agent.py - A small AI agent that tidies up after reconciliation.

How a "tool-calling loop" works:
  1. We send the model a list of messages plus a list of TOOLS it may use.
  2. The model replies either with text, or with a request to call a tool
     (for example: categorize_expense(transaction_id="t1", category="Fuel")).
  3. Our Python code runs that tool and sends the result back to the model.
  4. Repeat until the model calls `finish`, or we hit MAX_STEPS.

The model decides WHAT to do. Python does the actual work, checks the
inputs, and keeps all the records. The model never does math here.
"""

import json

MAX_STEPS = 10

# Muse Spark prices, in US dollars per ONE MILLION tokens.
INPUT_PRICE_PER_MILLION = 1.25
OUTPUT_PRICE_PER_MILLION = 4.25

CATEGORIES = [
    "Fuel",
    "Materials & Supplies",
    "Vehicle & Repairs",
    "Meals",
    "Office",
    "Marketing & Printing",
    "Other",
]

SYSTEM_PROMPT = f"""You are a bookkeeping assistant for a small business.
Bank charges have already been matched to receipts by a program.
Your job:
1. Call get_unresolved_items to see open issues and uncategorized expenses.
2. Call categorize_expense once for EVERY uncategorized expense.
   Allowed categories: {", ".join(CATEGORIES)}.
3. Call draft_vendor_email once for EVERY open issue. Write a short, polite
   email to the vendor asking them to fix or explain the problem
   (for example: refund a duplicate charge, send a copy of a missing
   receipt, or confirm a tip that was added).
4. Call finish with a one or two sentence summary.
You have at most {MAX_STEPS} turns, so call several tools at once when you can.
Use the exact ids you are given. Do not invent amounts; copy them from the data."""

# Tool descriptions in the OpenAI "function calling" format.
# The model reads these to know which tools exist and what to pass in.
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_unresolved_items",
            "description": "List open issues and expenses that have no category yet.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "categorize_expense",
            "description": "Assign a bookkeeping category to one expense.",
            "parameters": {
                "type": "object",
                "properties": {
                    "transaction_id": {"type": "string", "description": "e.g. t1"},
                    "category": {"type": "string", "enum": CATEGORIES},
                },
                "required": ["transaction_id", "category"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "draft_vendor_email",
            "description": "Draft an email to a vendor about one issue.",
            "parameters": {
                "type": "object",
                "properties": {
                    "issue_id": {"type": "string", "description": "e.g. i1"},
                    "subject": {"type": "string"},
                    "body": {"type": "string"},
                },
                "required": ["issue_id", "subject", "body"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "finish",
            "description": "Call when all work is done.",
            "parameters": {
                "type": "object",
                "properties": {"summary": {"type": "string"}},
                "required": ["summary"],
            },
        },
    },
]


def estimate_cost(input_tokens, output_tokens):
    """Dollar cost of a number of tokens at Muse Spark prices."""
    return (input_tokens / 1_000_000 * INPUT_PRICE_PER_MILLION
            + output_tokens / 1_000_000 * OUTPUT_PRICE_PER_MILLION)


class AgentState:
    """
    Everything the tools read and change while the agent runs.

    Keeping it in one object makes it easy to see (and test) what the
    agent has done so far.
    """

    def __init__(self, transactions, issues):
        # Look-up tables by id, e.g. self.transactions["t1"].
        self.transactions = {t["id"]: t for t in transactions}
        self.issues = {i["id"]: i for i in issues}
        self.categories = {}   # transaction id -> category
        self.emails = {}       # issue id -> {"subject", "body", ...}
        self.finished = False
        self.summary = ""

    # ---- The four tools. Each returns a dict that is sent back to the model.

    def get_unresolved_items(self):
        open_issues = [
            {
                "issue_id": issue["id"],
                "type": issue["type"],
                "description": issue["transaction"]["description"],
                "message": issue["message"],
            }
            for issue in self.issues.values()
            if issue["id"] not in self.emails
        ]
        uncategorized = [
            {
                "transaction_id": t["id"],
                "date": str(t["date"]),
                "description": t["description"],
                "amount": t["amount"],
            }
            for t in self.transactions.values()
            if t["id"] not in self.categories
        ]
        return {"open_issues": open_issues, "uncategorized_expenses": uncategorized}

    def categorize_expense(self, transaction_id, category):
        # Python double-checks the model's choices before saving anything.
        if transaction_id not in self.transactions:
            return {"error": f"Unknown transaction_id '{transaction_id}'."}
        if category not in CATEGORIES:
            return {"error": f"'{category}' is not allowed. Use one of: {CATEGORIES}"}
        self.categories[transaction_id] = category
        return {"ok": True, "transaction_id": transaction_id, "category": category}

    def draft_vendor_email(self, issue_id, subject, body):
        if issue_id not in self.issues:
            return {"error": f"Unknown issue_id '{issue_id}'."}
        issue = self.issues[issue_id]
        self.emails[issue_id] = {
            "issue_id": issue_id,
            "issue_type": issue["type"],
            "vendor": issue["transaction"]["description"],
            "subject": subject,
            "body": body,
        }
        return {"ok": True, "issue_id": issue_id}

    def finish(self, summary):
        self.finished = True
        self.summary = summary
        return {"ok": True}

    def run_tool(self, name, arguments_json):
        """
        Run the tool the model asked for and return its result as a dict.

        Mistakes (unknown tool, bad arguments) become error messages that
        go back to the model, instead of crashing the program.
        """
        tools = {
            "get_unresolved_items": self.get_unresolved_items,
            "categorize_expense": self.categorize_expense,
            "draft_vendor_email": self.draft_vendor_email,
            "finish": self.finish,
        }
        if name not in tools:
            return {"error": f"Unknown tool '{name}'."}
        try:
            arguments = json.loads(arguments_json or "{}")
            return tools[name](**arguments)
        except (json.JSONDecodeError, TypeError) as error:
            return {"error": f"Bad arguments for {name}: {error}"}


def run_agent(transactions, issues, client=None, model=None, max_steps=MAX_STEPS):
    """
    Run the tool-calling loop and return what the agent did.

    `client` is anything with a `client.chat.completions.create(...)` method:
    the real OpenAI-compatible client, or a fake one in tests.

    Returns a dict with categories, emails, summary, steps used,
    token counts, estimated cost and why the loop stopped.
    """
    if client is None:
        from receipts import make_client
        client = make_client()
    if model is None:
        from receipts import get_muse_settings
        model = get_muse_settings()[2]

    state = AgentState(transactions, issues)
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": "Please process this month's statement."},
    ]
    input_tokens = 0
    output_tokens = 0
    steps = 0
    stopped_reason = "max_steps"

    while steps < max_steps:
        steps += 1
        response = client.chat.completions.create(
            model=model, messages=messages, tools=TOOLS
        )

        # Add up tokens so we can show the cost at the end.
        if response.usage is not None:
            input_tokens += response.usage.prompt_tokens
            output_tokens += response.usage.completion_tokens

        reply = response.choices[0].message
        tool_calls = reply.tool_calls or []

        # Save the model's reply in the conversation history.
        messages.append({
            "role": "assistant",
            "content": reply.content,
            "tool_calls": [
                {
                    "id": call.id,
                    "type": "function",
                    "function": {
                        "name": call.function.name,
                        "arguments": call.function.arguments,
                    },
                }
                for call in tool_calls
            ] or None,
        })
        # Some APIs reject "tool_calls": None, so remove it when empty.
        if messages[-1]["tool_calls"] is None:
            del messages[-1]["tool_calls"]

        if not tool_calls:
            # The model answered with plain text instead of using a tool.
            stopped_reason = "no_tool_call"
            break

        # Run each requested tool and send the result back to the model.
        for call in tool_calls:
            result = state.run_tool(call.function.name, call.function.arguments)
            messages.append({
                "role": "tool",
                "tool_call_id": call.id,
                "content": json.dumps(result),
            })

        if state.finished:
            stopped_reason = "finished"
            break

    return {
        "categories": state.categories,
        "emails": list(state.emails.values()),
        "summary": state.summary,
        "steps": steps,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "cost_usd": estimate_cost(input_tokens, output_tokens),
        "stopped_reason": stopped_reason,
    }
