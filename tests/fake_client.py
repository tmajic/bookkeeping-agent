"""
fake_client.py - A pretend model client for tests.

It has the same shape as the real OpenAI client
(client.chat.completions.create(...)) but instead of calling an API it
hands back replies we wrote in advance. That lets us test the agent loop
for free, offline, and with predictable results.
"""

import json
from types import SimpleNamespace


def tool_call(call_id, name, **arguments):
    """Build one fake tool call, like the model asking to run a tool."""
    return SimpleNamespace(
        id=call_id,
        type="function",
        function=SimpleNamespace(name=name, arguments=json.dumps(arguments)),
    )


def fake_response(tool_calls=None, content=None, prompt_tokens=100,
                  completion_tokens=20):
    """Build one fake model response with token usage."""
    message = SimpleNamespace(content=content, tool_calls=tool_calls)
    return SimpleNamespace(
        choices=[SimpleNamespace(message=message)],
        usage=SimpleNamespace(prompt_tokens=prompt_tokens,
                              completion_tokens=completion_tokens),
    )


class FakeModelClient:
    """
    Replays a list of prepared responses, one per call.

    If it runs out, it keeps repeating the last response (handy for
    testing the step limit). Every request is saved in `self.requests`
    so tests can look at what was sent.
    """

    def __init__(self, responses):
        self.responses = list(responses)
        self.requests = []
        # Make `client.chat.completions.create` work like the real thing.
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, **kwargs):
        self.requests.append(kwargs)
        index = min(len(self.requests) - 1, len(self.responses) - 1)
        return self.responses[index]
