"""Pull worker: consumes ticket events (Module 3A).

Knobs (env vars) to break things on purpose:
  FAIL_RATE=0.5     -> randomly fail 50% of messages (transient errors)
  SLOW_SECONDS=15   -> slow processing (to test crashes mid-work)
"""
import json
import os
import random
import time

from google.cloud import pubsub_v1

from shoppilot.config import get_settings
from shoppilot.tickets import classify_rules as classify

SUBSCRIPTION = os.getenv("SUBSCRIPTION", "ticket-events-learn")
FAIL_RATE = float(os.getenv("FAIL_RATE", "0"))
SLOW_SECONDS = float(os.getenv("SLOW_SECONDS", "0"))

# Idempotency store. In-memory = lost on restart (we'll see why that's a problem). Firestore in 3B.
processed: set[str] = set()


def classify(ticket: dict) -> tuple[str, str]:
    """Rule-based for now. In Module 5 this becomes an LLM call."""
    text = f"{ticket['subject']} {ticket['body']}".lower()
    if "refund" in text:
        return "refund", "high"
    if "cancel" in text:
        return "cancellation", "high"
    if "address" in text:
        return "address_change", "medium"
    return "order_status", "low"


def callback(message: pubsub_v1.subscriber.message.Message) -> None:
    attempt = message.delivery_attempt  # filled in because our subscription has a DLQ policy

    # 1. Parse. Bad JSON will NEVER succeed -> nack -> retried -> DLQ after 5 attempts.
    try:
        ticket = json.loads(message.data)
    except json.JSONDecodeError:
        print(f"☠️  poison message {message.message_id} attempt={attempt} -> nack")
        message.nack()
        return

    # 2. Idempotency: already done? ack and skip.
    event_id = ticket["event_id"]
    if event_id in processed:
        print(f"↩️  duplicate {event_id[:8]} -> already processed, ack")
        message.ack()
        return

    # 3. "Work"
    if SLOW_SECONDS:
        print(f"⏳ working on {ticket['ticket_id']} for {SLOW_SECONDS}s...")
        time.sleep(SLOW_SECONDS)
    if random.random() < FAIL_RATE:
        print(f"💥 transient failure {ticket['ticket_id']} attempt={attempt} -> nack (will retry)")
        message.nack()
        return

    category, priority = classify(ticket)
    processed.add(event_id)
    print(f"✅ {ticket['ticket_id']:8} {category:15} {priority:6} attempt={attempt}")
    message.ack()  # 4. Ack ONLY after the work succeeded


def main() -> None:
    settings = get_settings()
    subscriber = pubsub_v1.SubscriberClient()
    path = subscriber.subscription_path(settings.project_id, SUBSCRIPTION)

    # Flow control = backpressure: hold at most 10 unacked messages at once
    flow = pubsub_v1.types.FlowControl(max_messages=10)
    future = subscriber.subscribe(path, callback=callback, flow_control=flow)
    print(f"👂 listening on {path}  (Ctrl+C to stop)")

    with subscriber:
        try:
            future.result()  # block forever; callbacks run in a background thread pool
        except KeyboardInterrupt:
            future.cancel()  # stop pulling new messages
            future.result()  # wait for in-flight callbacks to finish
            print("👋 stopped")


if __name__ == "__main__":
    main()
