# Turn on the APIs this module needs
resource "google_project_service" "apis" {
  for_each = toset([
    "run.googleapis.com",
    "artifactregistry.googleapis.com",
    "secretmanager.googleapis.com",
    "cloudbuild.googleapis.com",
    "pubsub.googleapis.com",
    "firestore.googleapis.com",
    "eventarc.googleapis.com",
    "cloudscheduler.googleapis.com",


  ])
  service            = each.value
  disable_on_destroy = false
}

# Private Docker image registry
resource "google_artifact_registry_repository" "app" {
  location      = var.region
  repository_id = "shoppilot"
  format        = "DOCKER"
  labels        = local.common_labels

  # Cost control: always keep the 5 newest images, delete anything older than 30 days
  cleanup_policy_dry_run = false
  cleanup_policies {
    id     = "keep-recent"
    action = "KEEP"
    most_recent_versions {
      keep_count = 5
    }
  }
  cleanup_policies {
    id     = "delete-old"
    action = "DELETE"
    condition {
      older_than = "2592000s" # 30 days
    }
  }

  depends_on = [google_project_service.apis]
}

# The secret "container". The VALUE is added with gcloud, so it never lands in tf state.
resource "google_secret_manager_secret" "api_key" {
  secret_id = "shoppilot-api-key"
  labels    = local.common_labels
  replication {
    auto {}
  }
  depends_on = [google_project_service.apis]
}

# Only our app's service account can read this one secret
resource "google_secret_manager_secret_iam_member" "app_reads_api_key" {
  secret_id = google_secret_manager_secret.api_key.id
  role      = "roles/secretmanager.secretAccessor"
  member    = data.google_service_account.app.member
}
