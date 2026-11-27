from unittest.mock import MagicMock

from shoppilot import tickets
from shoppilot.tickets import TicketClassification

TICKET = {"ticket_id": "T-1", "subject": "Refund request", "body": "Item is broken"}


def test_llm_result_is_used(monkeypatch):
    fake = TicketClassification(category="refund", priority="high", sentiment="negative",
                                summary="Customer wants refund for broken item", needs_human=False)
    usage = MagicMock(prompt_token_count=120, candidates_token_count=40)
    monkeypatch.setattr(tickets, "classify_llm", lambda t: (fake, usage))

    result = tickets.classify(TICKET)
    assert result["classifier"] == "llm"
    assert result["category"] == "refund"
    assert result["tokens_in"] == 120


def test_falls_back_to_rules_when_llm_fails(monkeypatch):
    def boom(t):
        raise TimeoutError("vertex timed out")
    monkeypatch.setattr(tickets, "classify_llm", boom)

    result = tickets.classify(TICKET)
    assert result == {"category": "refund", "priority": "high", "classifier": "rules"}
