"""Publish fake 'ticket.created' events to Pub/Sub (Module 3A)."""
import argparse
import datetime as dt
import json
import random
import uuid

from google.cloud import pubsub_v1

from shoppilot.config import get_settings

TEMPLATES = [
    ("Where is my order?", "Order #{n} hasn't arrived after 8 days."),
    ("Refund request", "I want a refund for order #{n}, the item arrived damaged."),
    ("Change address", "Please ship order #{n} to my new address."),
    ("Cancel order", "Please cancel order #{n}, I ordered it by mistake."),
]


def make_ticket() -> dict:
    subject, body = random.choice(TEMPLATES)
    n = random.randint(10000, 99999)
    return {
        "event_id": str(uuid.uuid4()),  # unique per EVENT -> used for idempotency
        "ticket_id": f"T-{n}",
        "customer_id": f"C-{random.randint(1, 50)}",
        "subject": subject,
        "body": body.format(n=n),
        "created_at": dt.datetime.now(dt.UTC).isoformat(),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--count", type=int, default=5)
    parser.add_argument("--poison", action="store_true", help="publish broken JSON")
    args = parser.parse_args()

    settings = get_settings()
    publisher = pubsub_v1.PublisherClient()
    topic = publisher.topic_path(settings.project_id, "ticket-events")

    futures = []
    for _ in range(args.count):
        data = b"{this is not valid json" if args.poison else json.dumps(make_ticket()).encode()
        # attributes = small metadata, readable WITHOUT parsing the body (routing, filtering, versioning)
        futures.append(publisher.publish(topic, data, event_type="ticket.created", schema_version="1"))

    # publish() is async and batched; .result() waits for the server to confirm
    for f in futures:
        print("published message id:", f.result())


if __name__ == "__main__":
    main()
