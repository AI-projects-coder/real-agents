"""Ticket worker: receives Pub/Sub PUSH requests (Module 3B).

HTTP 2xx = ack. Anything else = nack -> retry with backoff -> DLQ after 5 attempts.
"""
import base64
import binascii
import datetime as dt
import json
import os
import random
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from google.cloud import firestore, run_v2
from pydantic import BaseModel, Field

from shoppilot.logs import log
from shoppilot.tickets import classify
from fastapi import FastAPI, Header, HTTPException, Request



FAIL_RATE = float(os.getenv("FAIL_RATE", "0"))  # for experiments
MARKER_TTL = dt.timedelta(days=7)
ALLOWED_EXT = (".md", ".txt", ".pdf")
MAX_BYTES = 10 * 1024 * 1024  # 10 MB guardrail
INGEST_JOB = os.getenv("INGEST_JOB", "shoppilot-ingest")
REGION = os.getenv("REGION", "us-central1")



# ---------- The Pub/Sub push envelope ----------
class PubSubMessage(BaseModel):
    data: str = ""
    attributes: dict[str, str] = {}
    message_id: str = Field(alias="messageId")


class PushEnvelope(BaseModel):
    message: PubSubMessage
    subscription: str
    delivery_attempt: int | None = Field(default=None, alias="deliveryAttempt")


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.db = firestore.Client(project=os.environ["PROJECT_ID"])
    app.state.jobs = run_v2.JobsClient()
    log("INFO", "worker startup")
    yield
    log("INFO", "worker shutdown")


app = FastAPI(title="ShopPilot Ticket Worker", lifespan=lifespan)


@app.get("/health")
def health():
    return {"status": "ok"}


@firestore.transactional
def save_once(tx, db, event_id: str, ticket: dict) -> bool:
    """Atomically: if the event wasn't processed, save ticket + marker. Returns False if duplicate."""
    marker_ref = db.collection("processed_events").document(event_id)
    if marker_ref.get(transaction=tx).exists:
        return False
    now = dt.datetime.now(dt.UTC)
    tx.set(db.collection("tickets").document(ticket["ticket_id"]), ticket)
    tx.set(marker_ref, {"ticket_id": ticket["ticket_id"], "processed_at": now, "expire_at": now + MARKER_TTL})
    return True


@app.post("/pubsub/tickets")
def handle_push(envelope: PushEnvelope, request: Request):
    msg, attempt = envelope.message, envelope.delivery_attempt

    # 1. Decode. Broken data will never succeed -> non-2xx -> retries -> DLQ.
    try:
        ticket = json.loads(base64.b64decode(msg.data))
        event_id = ticket["event_id"]
    except (binascii.Error, ValueError, KeyError) as e:
        log("WARNING", "poison message", message_id=msg.message_id, attempt=attempt, error=str(e))
        raise HTTPException(status_code=400, detail="bad message")

    db = request.app.state.db

    # 2. Cheap pre-check: skip the (future, expensive) work for obvious duplicates.
    if db.collection("processed_events").document(event_id).get().exists:
        log("INFO", "duplicate skipped", event_id=event_id, ticket_id=ticket.get("ticket_id"), attempt=attempt)
        return {"status": "duplicate"}

    # 3. Simulated transient failure (experiments only).
    if random.random() < FAIL_RATE:
        log("ERROR", "transient failure (simulated)", ticket_id=ticket.get("ticket_id"), attempt=attempt)
        raise HTTPException(status_code=503, detail="simulated failure")

    # 4. Work + atomic save.
    category, priority = classify(ticket)
    doc = {**ticket, "category": category, "priority": priority, "status": "classified"}
    created = save_once(db.transaction(), db, event_id, doc)

    log(
        "INFO", "ticket processed" if created else "duplicate skipped (race)",
        ticket_id=ticket["ticket_id"], category=category, priority=priority, attempt=attempt,
    )
    return {"status": "ok" if created else "duplicate"}  # 200 -> ack

@app.post("/events/upload")
def on_upload(event: dict, request: Request, ce_id: str | None = Header(default=None)):
    """Eventarc delivers a GCS 'object finalized' CloudEvent. Validate, then start the ingest Job.
    Always return quickly: heavy work happens in the Job, not here."""
    bucket, name = event.get("bucket", ""), event.get("name", "")
    size, generation = int(event.get("size", 0)), str(event.get("generation", ""))

    # 200 = ack. We never want Eventarc to retry files we deliberately skip.
    if not name.startswith("policies/") or not name.lower().endswith(ALLOWED_EXT):
        log("INFO", "upload ignored", object=name, reason="not a policy document", ce_id=ce_id)
        return {"status": "ignored"}
    if size > MAX_BYTES:
        log("WARNING", "upload ignored", object=name, reason="too large", size=size, ce_id=ce_id)
        return {"status": "ignored"}

    env = [
        run_v2.EnvVar(name="SOURCE_BUCKET", value=bucket),
        run_v2.EnvVar(name="SOURCE_OBJECT", value=name),
        run_v2.EnvVar(name="SOURCE_GENERATION", value=generation),
    ]
    overrides = run_v2.RunJobRequest.Overrides(
        container_overrides=[run_v2.RunJobRequest.Overrides.ContainerOverride(env=env)]
    )
    job = f"projects/{os.environ['PROJECT_ID']}/locations/{REGION}/jobs/{INGEST_JOB}"

    # Starts an execution and returns immediately (we don't wait for the job to finish).
    # If this call fails -> 500 -> Eventarc retries the event.
    op = request.app.state.jobs.run_job(request=run_v2.RunJobRequest(name=job, overrides=overrides))
    log("INFO", "ingest job started", object=name, generation=generation,
        operation=op.operation.name, ce_id=ce_id)
    return {"status": "started"}
