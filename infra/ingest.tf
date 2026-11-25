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

# ---------- The Job ----------
resource "google_cloud_run_v2_job" "ingest" {
  name                = "shoppilot-ingest"
  location            = var.region
  deletion_protection = false
  labels              = local.common_labels

  template {
    task_count = 1
    template {
      service_account = google_service_account.ingest.email
      max_retries     = 2      # transient failures retried per task
      timeout         = "600s" # per task attempt

      containers {
        image   = var.worker_image # same image, third entrypoint
        command = ["python"]
        args    = ["-m", "shoppilot.ingest.job"]
        env {
          name  = "PROJECT_ID"
          value = var.project_id
        }
        resources {
          limits = {
            cpu    = "1"
            memory = "1Gi"
          }
        }
      }
    }
  }

  lifecycle {
    ignore_changes = [template[0].template[0].containers[0].image, client, client_version]
  }
}

# The worker (dispatcher) may run THIS job with env overrides, and nothing else
resource "google_cloud_run_v2_job_iam_member" "worker_runs_ingest" {
  name     = google_cloud_run_v2_job.ingest.name
  location = google_cloud_run_v2_job.ingest.location
  role     = "roles/run.jobsExecutorWithOverrides"
  member   = google_service_account.worker.member
}

# ---------- The Eventarc trigger ----------
resource "google_eventarc_trigger" "uploads" {
  name            = "uploads-finalized"
  location        = var.region # must match the bucket's region
  service_account = google_service_account.eventarc.email
  labels          = local.common_labels

  matching_criteria {
    attribute = "type"
    value     = "google.cloud.storage.object.v1.finalized"
  }
  matching_criteria {
    attribute = "bucket"
    value     = google_storage_bucket.uploads.name
  }

  destination {
    cloud_run_service {
      service = google_cloud_run_v2_service.worker.name
      region  = var.region
      path    = "/events/upload"
    }
  }

  depends_on = [
    google_project_iam_member.gcs_agent_pubsub,
    google_project_iam_member.eventarc_receiver,
    google_cloud_run_v2_service_iam_member.eventarc_invokes_worker,
  ]
}
