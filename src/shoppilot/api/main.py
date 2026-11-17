"""ShopPilot API (Module 2)."""
import json
import secrets
import sys
import time
import uuid
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.responses import PlainTextResponse
from google.api_core.exceptions import NotFound
from google.cloud import storage

from shoppilot.config import Settings, get_settings


def log(severity: str, message: str, **fields) -> None:
    """One JSON object per line. Cloud Logging reads 'severity' and 'message' automatically."""
    print(json.dumps({"severity": severity, "message": message, **fields}), file=sys.stdout, flush=True)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    # Create the GCS client ONCE per instance (not per request) -> connection reuse, lower latency.
    app.state.gcs = storage.Client(project=settings.project_id)
    log("INFO", "startup", env=settings.env, bucket=settings.bucket)
    yield
    log("INFO", "shutdown")  # runs on SIGTERM -> graceful shutdown


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
