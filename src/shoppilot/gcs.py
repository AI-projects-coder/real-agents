"""Module 1: Cloud Storage with the Python SDK."""
import datetime as dt
import os
from pathlib import Path

import google.auth
from dotenv import load_dotenv
from google.auth.transport.requests import Request
from google.cloud import storage

load_dotenv()  # reads .env -> os.environ

PROJECT_ID = os.environ["PROJECT_ID"]
BUCKET_NAME = f"{PROJECT_ID}-policies"
SIGNER_SA = f"shoppilot-dev@{PROJECT_ID}.iam.gserviceaccount.com"

# The client finds credentials automatically via ADC.
client = storage.Client(project=PROJECT_ID)


def ensure_bucket(name: str) -> storage.Bucket:
    """Create the bucket if missing. Safe to run many times (idempotent)."""
    bucket = client.lookup_bucket(name)
    if bucket is not None:
        print(f"bucket exists: {name}")
        return bucket

    bucket = client.bucket(name)
    bucket.iam_configuration.uniform_bucket_level_access_enabled = True
    bucket.iam_configuration.public_access_prevention = "enforced"
    bucket.versioning_enabled = True
    bucket = client.create_bucket(bucket, location="us-central1")
    print(f"created bucket: {name}")
    return bucket


def upload_dir(bucket: storage.Bucket, local_dir: str, prefix: str) -> None:
    """Upload every .md file in local_dir under gs://bucket/prefix/."""
    for path in sorted(Path(local_dir).glob("*.md")):
        blob = bucket.blob(f"{prefix}/{path.name}")
        blob.upload_from_filename(path, content_type="text/markdown")
        print(f"uploaded: gs://{bucket.name}/{blob.name}")


def list_objects(bucket: storage.Bucket, prefix: str) -> None:
    for blob in client.list_blobs(bucket, prefix=prefix):
        print(f"{blob.name:40} {blob.size:>6} bytes  updated={blob.updated}")


def read_text(bucket: storage.Bucket, name: str) -> str:
    return bucket.blob(name).download_as_text()


def signed_url(bucket: storage.Bucket, name: str, minutes: int = 15) -> str:
    """Temporary GET link, signed by the service account via IAM (no key file)."""
    creds, _ = google.auth.default()
    creds.refresh(Request())  # get a fresh access token for YOUR identity
    return bucket.blob(name).generate_signed_url(
        version="v4",
        expiration=dt.timedelta(minutes=minutes),
        method="GET",
        service_account_email=SIGNER_SA,  # who signs
        access_token=creds.token,  # proves you may sign as them
    )


def main() -> None:
    bucket = ensure_bucket(BUCKET_NAME)
    upload_dir(bucket, "data/policies", prefix="policies")

    print("\n--- objects ---")
    list_objects(bucket, prefix="policies/")

    print("\n--- refund policy ---")
    print(read_text(bucket, "policies/refund-policy.md"))

    print("--- signed url (valid 15 min) ---")
    print(signed_url(bucket, "policies/refund-policy.md"))


if __name__ == "__main__":
    main()
