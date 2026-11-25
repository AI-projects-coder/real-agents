# ---------- Identities ----------
resource "google_service_account" "ingest" {
  account_id   = "shoppilot-ingest"
  display_name = "ShopPilot ingestion job"
}

resource "google_service_account" "eventarc" {
  account_id   = "shoppilot-eventarc"
  display_name = "Eventarc trigger identity"
}

# ---------- Ingest job permissions ----------
resource "google_storage_bucket_iam_member" "ingest_reads_uploads" {
  bucket = google_storage_bucket.uploads.name
  role   = "roles/storage.objectViewer"
  member = google_service_account.ingest.member
}

resource "google_storage_bucket_iam_member" "ingest_writes_policies" {
  bucket = google_storage_bucket.policies.name
  role   = "roles/storage.objectUser" # read/write/overwrite objects (no bucket admin)
  member = google_service_account.ingest.member
}

resource "google_project_iam_member" "ingest_firestore" {
  project = var.project_id
  role    = "roles/datastore.user"
  member  = google_service_account.ingest.member
}

# ---------- Eventarc plumbing ----------
# GCS publishes its events through Pub/Sub, so GCS's service agent needs publisher rights
data "google_storage_project_service_account" "gcs" {}

resource "google_project_iam_member" "gcs_agent_pubsub" {
  project = var.project_id
  role    = "roles/pubsub.publisher"
  member  = "serviceAccount:${data.google_storage_project_service_account.gcs.email_address}"
}

# The trigger's identity: receive events + call the worker
resource "google_project_iam_member" "eventarc_receiver" {
  project = var.project_id
  role    = "roles/eventarc.eventReceiver"
  member  = google_service_account.eventarc.member
}

resource "google_cloud_run_v2_service_iam_member" "eventarc_invokes_worker" {
  name     = google_cloud_run_v2_service.worker.name
  location = google_cloud_run_v2_service.worker.location
  role     = "roles/run.invoker"
  member   = google_service_account.eventarc.member
}

# CI will update the job's image -> must be allowed to act as the ingest SA
resource "google_service_account_iam_member" "build_acts_as_ingest" {
  service_account_id = google_service_account.ingest.name
  role               = "roles/iam.serviceAccountUser"
  member             = google_service_account.build.member
}
