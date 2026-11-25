"""Cloud Run Job: ingest ONE uploaded document (Module 4A).

Input via env vars (set per execution by the dispatcher):
  SOURCE_BUCKET, SOURCE_OBJECT, SOURCE_GENERATION
Exit 0 = success OR permanent failure (recorded). Crash = transient -> the job retries the task.
"""
import datetime as dt
import hashlib
import json
import os
import sys

from google.cloud import firestore, storage

from shoppilot.ingest.chunking import chunk_text
from shoppilot.ingest.extract import extract_text
from shoppilot.logs import log


def doc_id_for(bucket: str, name: str, generation: str) -> str:
    """Same upload -> same id (dedupe). New upload of the same file -> new generation -> new id."""
    return hashlib.sha256(f"{bucket}/{name}#{generation}".encode()).hexdigest()[:24]


def main() -> int:
    project = os.environ["PROJECT_ID"]
    bucket_name = os.environ["SOURCE_BUCKET"]
    object_name = os.environ["SOURCE_OBJECT"]
    generation = os.environ.get("SOURCE_GENERATION", "")
    out_bucket = os.environ.get("OUTPUT_BUCKET", f"{project}-policies")
    attempt = int(os.environ.get("CLOUD_RUN_TASK_ATTEMPT", "0"))  # set by Cloud Run Jobs

    gcs = storage.Client(project=project)
    db = firestore.Client(project=project)

    source = f"gs://{bucket_name}/{object_name}"
    doc_id = doc_id_for(bucket_name, object_name, generation)
    ref = db.collection("documents").document(doc_id)
    now = dt.datetime.now(dt.UTC)

    # 1. Idempotency: duplicate event or re-run -> skip
    snap = ref.get()
    if snap.exists and snap.get("status") == "done":
        log("INFO", "already ingested, skipping", doc_id=doc_id, source=source)
        return 0

    ref.set({"source": source, "generation": generation, "status": "processing",
             "attempt": attempt, "updated_at": now}, merge=True)

    # 2. Download the EXACT version that triggered us (not whatever is there now)
    blob = gcs.bucket(bucket_name).blob(object_name, generation=int(generation) if generation else None)
    data = blob.download_as_bytes()  # network/permission errors crash -> task retry (transient)

    # 3. Extract + chunk. ValueError = permanent: record it, exit 0, no retries.
    try:
        text = extract_text(data, object_name)
    except ValueError as e:
        ref.set({"status": "failed", "error": str(e), "updated_at": now}, merge=True)
        log("ERROR", "permanent ingest failure", doc_id=doc_id, source=source, error=str(e))
        return 0
    chunks = chunk_text(text)

    # 4. Write chunks as JSON Lines (one chunk per line). Deterministic path = idempotent.
    out_name = f"chunks/{doc_id}.jsonl"
    lines = [
        json.dumps({"doc_id": doc_id, "chunk_index": i, "source": source, "text": chunk})
        for i, chunk in enumerate(chunks)
    ]
    gcs.bucket(out_bucket).blob(out_name).upload_from_string(
        "\n".join(lines), content_type="application/jsonl"
    )

    # 5. Mark done
    ref.set({"status": "done", "chunks": len(chunks), "chars": len(text),
             "output": f"gs://{out_bucket}/{out_name}", "updated_at": now}, merge=True)
    log("INFO", "ingested", doc_id=doc_id, source=source, chunks=len(chunks), attempt=attempt)
    return 0


if __name__ == "__main__":
    sys.exit(main())
