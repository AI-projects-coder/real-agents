import base64
import json
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from shoppilot.worker import main as worker


@pytest.fixture
def wclient(monkeypatch):
    monkeypatch.setenv("PROJECT_ID", "test-project")
    monkeypatch.setattr(worker.firestore, "Client", MagicMock())
    with TestClient(worker.app) as c:
        yield c


def envelope(data: bytes) -> dict:
    return {
        "message": {"data": base64.b64encode(data).decode(), "messageId": "m-1"},
        "subscription": "projects/p/subscriptions/s",
        "deliveryAttempt": 1,
    }


def test_poison_message_is_nacked(wclient):
    assert wclient.post("/pubsub/tickets", json=envelope(b"{broken")).status_code == 400


def test_duplicate_is_acked_without_work(wclient):
    db = wclient.app.state.db
    db.collection.return_value.document.return_value.get.return_value.exists = True  # marker exists
    ticket = {"event_id": "e-1", "ticket_id": "T-1", "subject": "Refund", "body": "damaged"}
    r = wclient.post("/pubsub/tickets", json=envelope(json.dumps(ticket).encode()))
    assert r.status_code == 200
    assert r.json() == {"status": "duplicate"}
