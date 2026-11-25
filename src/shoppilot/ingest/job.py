"""Ingest ONE document. Used by the single-file job (4A) and the backfill job (4B).

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


def ingest_one(
    gcs: storage.Client,
    db: firestore.Client,
    bucket_name: str,
    object_name: str,
    generation: str,
    out_bucket: str | None = None,
    attempt: int = 0,
) -> str:
    """Returns "done" | "skipped" | "failed". Raises on transient errors."""
    out_bucket = out_bucket or f"{gcs.project}-policies"
    source = f"gs://{bucket_name}/{object_name}"
    doc_id = doc_id_for(bucket_name, object_name, generation)
    ref = db.collection("documents").document(doc_id)
    now = dt.datetime.now(dt.UTC)

    snap = ref.get()
    if snap.exists and snap.get("status") == "done":
        log("INFO", "already ingested, skipping", doc_id=doc_id, source=source)
        return "skipped"

    ref.set({"source": source, "generation": generation, "status": "processing",
             "attempt": attempt, "updated_at": now}, merge=True)

    blob = gcs.bucket(bucket_name).blob(object_name, generation=int(generation) if generation else None)
    data = blob.download_as_bytes()

    try:
        text = extract_text(data, object_name)
    except ValueError as e:
        ref.set({"status": "failed", "error": str(e), "updated_at": now}, merge=True)
        log("ERROR", "permanent ingest failure", doc_id=doc_id, source=source, error=str(e))
        return "failed"
    chunks = chunk_text(text)

    out_name = f"chunks/{doc_id}.jsonl"
    lines = [
        json.dumps({"doc_id": doc_id, "chunk_index": i, "source": source, "text": chunk})
        for i, chunk in enumerate(chunks)
    ]
    gcs.bucket(out_bucket).blob(out_name).upload_from_string(
        "\n".join(lines), content_type="application/jsonl"
    )

    ref.set({"status": "done", "chunks": len(chunks), "chars": len(text),
             "output": f"gs://{out_bucket}/{out_name}", "updated_at": now}, merge=True)
    log("INFO", "ingested", doc_id=doc_id, source=source, chunks=len(chunks), attempt=attempt)
    return "done"


def main() -> int:
    project = os.environ["PROJECT_ID"]
    ingest_one(
        storage.Client(project=project),
        firestore.Client(project=project),
        os.environ["SOURCE_BUCKET"],
        os.environ["SOURCE_OBJECT"],
        os.environ.get("SOURCE_GENERATION", ""),
        out_bucket=os.environ.get("OUTPUT_BUCKET"),
        attempt=int(os.environ.get("CLOUD_RUN_TASK_ATTEMPT", "0")),
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
