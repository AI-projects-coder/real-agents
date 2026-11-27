from unittest.mock import MagicMock

import pytest
from google.genai import types

from shoppilot.agent import loop, tools
from shoppilot.config import get_settings


@pytest.fixture(autouse=True)
def env(monkeypatch):
    monkeypatch.setenv("PROJECT_ID", "test-project")
    get_settings.cache_clear()
    tools._db.cache_clear()
    monkeypatch.setattr(tools, "_db", lambda: MagicMock())  # fake Firestore
    yield
    get_settings.cache_clear()


# ---- business rules live in code ----
def test_big_refund_needs_manager_approval():
    r = tools.create_refund_request("51877", "screen cracked")
    assert r["status"] == "pending_manager_approval"
    assert r["amount_inr"] == 64999  # amount from the order system, not the model


def test_small_refund_is_approved():
    assert tools.create_refund_request("#48213", "kettle broken")["status"] == "approved"


def test_refund_outside_window_is_rejected():
    assert tools.create_refund_request("39002", "stopped working")["refund_allowed"] is False


def test_refund_before_delivery_is_rejected():
    assert tools.create_refund_request("60415", "changed my mind")["refund_allowed"] is False


# ---- tool errors are returned, not raised ----
def test_unknown_tool_and_bad_args_become_errors():
    assert "error" in tools.execute("delete_database", {})
    assert "error" in tools.execute("get_order", {"wrong_arg": 1})


# ---- the loop, with a FAKE model ----
def _response(calls=None, text=None):
    r = MagicMock()
    r.function_calls = calls
    r.text = text
    parts = [types.Part(function_call=c) for c in calls] if calls else [types.Part.from_text(text=text)]
    r.candidates = [MagicMock(content=types.Content(role="model", parts=parts))]
    r.usage_metadata = MagicMock(prompt_token_count=100, candidates_token_count=10)
    return r


def test_loop_calls_tool_then_answers(monkeypatch):
    call = types.FunctionCall(name="get_order", args={"order_id": "48213"})
    fake = MagicMock()
    fake.models.generate_content.side_effect = [_response(calls=[call]), _response(text="Order 48213 was delivered.")]
    monkeypatch.setattr(loop, "client", lambda: fake)

    history = []
    answer = loop.run_turn(history, "Where is order 48213?", verbose=False)
    assert answer == "Order 48213 was delivered."
    assert len(history) == 4  # user -> model(tool call) -> tool result -> model(answer)


def test_loop_stops_at_step_limit(monkeypatch):
    call = types.FunctionCall(name="get_order", args={"order_id": "48213"})
    fake = MagicMock()
    fake.models.generate_content.side_effect = [_response(calls=[call]) for _ in range(loop.MAX_STEPS)]
    monkeypatch.setattr(loop, "client", lambda: fake)

    answer = loop.run_turn([], "loop forever please", verbose=False)
    assert "human agent" in answer
    assert fake.models.generate_content.call_count == loop.MAX_STEPS

def test_model_failure_rolls_back_turn(monkeypatch):
    from google.genai import errors
    fake = MagicMock()
    fake.models.generate_content.side_effect = errors.ServerError(504, {"error": {"message": "deadline", "status": "DEADLINE_EXCEEDED"}})
    monkeypatch.setattr(loop, "client", lambda: fake)

    history = [types.Content(role="user", parts=[types.Part.from_text(text="earlier turn")])]
    answer = loop.run_turn(history, "hello", verbose=False)
    assert "try again" in answer
    assert len(history) == 1  # the failed turn was removed; earlier memory is kept
