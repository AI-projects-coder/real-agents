"""ShopPilot API (Module 2)."""
import datetime as dt
import json
import secrets
import time
import uuid
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.responses import PlainTextResponse
from google.api_core.exceptions import NotFound
from google.cloud import firestore, pubsub_v1, storage
from pydantic import BaseModel, Field

from shoppilot.config import Settings, get_settings
from shoppilot.logs import log



@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    if not settings.api_key:
        raise RuntimeError("API_KEY is required")  # fail fast, same as before
    # All clients created ONCE per instance
    app.state.gcs = storage.Client(project=settings.project_id)
    app.state.publisher = pubsub_v1.PublisherClient()
    app.state.topic = app.state.publisher.topic_path(settings.project_id, "ticket-events")
    app.state.db = firestore.Client(project=settings.project_id)
    log("INFO", "startup", env=settings.env, bucket=settings.bucket)
    yield
    log("INFO", "shutdown")


app = FastAPI(title="ShopPilot API", lifespan=lifespan)


@app.middleware("http")
async def access_log(request: Request, call_next):
    """Log every request with latency and a request id (for tracing a request across logs)."""
    request_id = request.headers.get("x-request-id", uuid.uuid4().hex[:12])
    start = time.perf_counter()
    response = await call_next(request)
    latency_ms = round((time.perf_counter() - start) * 1000, 1)
    response.headers["x-request-id"] = request_id
    log(
        "INFO", "request",
        method=request.method, path=request.url.path,
        status=response.status_code, latency_ms=latency_ms, request_id=request_id,
    )
    return response


def require_api_key(
    x_api_key: str = Header(default=""),  # reads the "X-API-Key" header
    settings: Settings = Depends(get_settings),
) -> None:
    # compare_digest = constant-time comparison (prevents timing attacks)
    if not secrets.compare_digest(x_api_key, settings.api_key):
        raise HTTPException(status_code=401, detail="invalid or missing API key")


# NOTE: not "/healthz" - Cloud Run reserves some paths ending in "z"!
@app.get("/health")
def health():
    return {"status": "ok", "version": "v3"}



# Plain `def` (not async): the GCS SDK is blocking, so FastAPI runs it in a thread pool.
@app.get("/policies", dependencies=[Depends(require_api_key)])
def list_policies(request: Request, settings: Settings = Depends(get_settings)):
    blobs = request.app.state.gcs.list_blobs(settings.bucket, prefix="policies/")
    return {"policies": [b.name.removeprefix("policies/") for b in blobs if b.name.endswith(".md")]}


@app.get("/policies/{name}", response_class=PlainTextResponse, dependencies=[Depends(require_api_key)])
def get_policy(name: str, request: Request, settings: Settings = Depends(get_settings)):
    blob = request.app.state.gcs.bucket(settings.bucket).blob(f"policies/{name}")
    try:
        return blob.download_as_text()
    except NotFound:
        raise HTTPException(status_code=404, detail=f"policy '{name}' not found")

class TicketIn(BaseModel):
    """Request body. Pydantic validates it -> bad input gets 422 automatically."""
    customer_id: str = Field(min_length=1, max_length=50)
    subject: str = Field(min_length=3, max_length=200)
    body: str = Field(min_length=3, max_length=5000)


@app.post("/tickets", status_code=202, dependencies=[Depends(require_api_key)])
def create_ticket(ticket: TicketIn, request: Request):
    """Accept the ticket, publish an event, return immediately. Workers do the rest."""
    event = {
        "event_id": str(uuid.uuid4()),
        "ticket_id": f"T-{uuid.uuid4().hex[:8]}",
        **ticket.model_dump(),
        "created_at": dt.datetime.now(dt.UTC).isoformat(),
    }
    future = request.app.state.publisher.publish(
        request.app.state.topic,
        json.dumps(event).encode(),
        event_type="ticket.created",
        schema_version="1",
    )
    message_id = future.result(timeout=10)  # wait until Pub/Sub has durably stored it
    log("INFO", "ticket published", ticket_id=event["ticket_id"], message_id=message_id)
    # 202 Accepted = "received, processing later" (not 201 Created: it isn't done yet)
    return {"ticket_id": event["ticket_id"], "status": "received"}


@app.get("/tickets/{ticket_id}", dependencies=[Depends(require_api_key)])
def get_ticket(ticket_id: str, request: Request):
    snap = request.app.state.db.collection("tickets").document(ticket_id).get()
    if not snap.exists:
        # Simplification: unknown IDs also look "processing". The outbox pattern fixes this.
        return {"ticket_id": ticket_id, "status": "processing"}
    return snap.to_dict()
