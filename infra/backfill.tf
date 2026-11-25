# ---------- Parallel backfill job ----------
resource "google_cloud_run_v2_job" "backfill" {
  name                = "shoppilot-backfill"
  location            = var.region
  deletion_protection = false
  labels              = local.common_labels

  template {
    task_count  = 3 # split work into 3 slices
    parallelism = 3 # run all 3 at once

    template {
      service_account = google_service_account.ingest.email # same permissions as single ingest
      max_retries     = 1
      timeout         = "1800s"

      containers {
        image   = var.worker_image
        command = ["python"]
        args    = ["-m", "shoppilot.ingest.backfill"]

        env {
          name  = "PROJECT_ID"
          value = var.project_id
        }
        env {
          name  = "SOURCE_BUCKET"
          value = google_storage_bucket.uploads.name
        }
        env {
          name  = "PREFIX"
          value = "policies/"
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

# ---------- Cloud Scheduler ----------
resource "google_service_account" "scheduler" {
  account_id   = "shoppilot-scheduler"
  display_name = "Cloud Scheduler identity"
}

# Scheduler may run THIS job only
resource "google_cloud_run_v2_job_iam_member" "scheduler_runs_backfill" {
  name     = google_cloud_run_v2_job.backfill.name
  location = google_cloud_run_v2_job.backfill.location
  role     = "roles/run.invoker"
  member   = google_service_account.scheduler.member
}

resource "google_cloud_scheduler_job" "nightly_backfill" {
  name             = "nightly-backfill"
  region           = var.region
  description      = "Safety net: re-ingest anything missed, every night"
  schedule         = "0 2 * * *" # 02:00 every day
  time_zone        = "Asia/Kolkata"
  attempt_deadline = "60s"

  retry_config {
    retry_count = 2 # if the API call to START the job fails
  }

  http_target {
    http_method = "POST"
    uri         = "https://run.googleapis.com/v2/${google_cloud_run_v2_job.backfill.id}:run"

    # Google API -> OAuth access token (not OIDC!)
    oauth_token {
      service_account_email = google_service_account.scheduler.email
      scope                 = "https://www.googleapis.com/auth/cloud-platform"
    }
  }

  depends_on = [
    google_project_service.apis,
    google_cloud_run_v2_job_iam_member.scheduler_runs_backfill,
  ]
}
