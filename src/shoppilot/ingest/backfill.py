"""Parallel Cloud Run Job: (re)ingest every document under a prefix (Module 4B).

Task i handles the files where crc32(name) % TASK_COUNT == i.
"""
import os
import sys
import time
import zlib

from google.cloud import firestore, storage

from shoppilot.ingest.job import ingest_one
from shoppilot.logs import log

ALLOWED_EXT = (".md", ".txt", ".pdf")


def belongs_to_me(name: str, index: int, count: int) -> bool:
    """Stable sharding. NOT hash(): Python randomizes str hashes per process!"""
    return zlib.crc32(name.encode()) % count == index


def main() -> int:
    project = os.environ["PROJECT_ID"]
    bucket = os.environ["SOURCE_BUCKET"]
    prefix = os.environ.get("PREFIX", "policies/")
    index = int(os.environ.get("CLOUD_RUN_TASK_INDEX", "0"))  # set by Cloud Run
    count = int(os.environ.get("CLOUD_RUN_TASK_COUNT", "1"))  # set by Cloud Run
    attempt = int(os.environ.get("CLOUD_RUN_TASK_ATTEMPT", "0"))

    gcs = storage.Client(project=project)
    db = firestore.Client(project=project)
    stats = {"done": 0, "skipped": 0, "failed": 0, "errors": 0}
    start = time.perf_counter()

    for blob in gcs.list_blobs(bucket, prefix=prefix):
        if not blob.name.lower().endswith(ALLOWED_EXT):
            continue
        if not belongs_to_me(blob.name, index, count):
            continue  # another task's file
        try:
            result = ingest_one(gcs, db, bucket, blob.name, str(blob.generation), attempt=attempt)
            stats[result] += 1
        except Exception as e:  # transient: keep going, fail the TASK at the end so it retries
            stats["errors"] += 1
            log("ERROR", "backfill file error", object=blob.name, error=str(e))

    log("INFO", "backfill task finished", task_index=index, task_count=count, attempt=attempt,
        seconds=round(time.perf_counter() - start, 1), **stats)
    return 1 if stats["errors"] else 0


if __name__ == "__main__":
    sys.exit(main())
