# Dedicated identity for Cloud Build (never the default compute SA)
resource "google_service_account" "build" {
  account_id   = "shoppilot-build"
  display_name = "ShopPilot Cloud Build"
}

# Write build logs
resource "google_project_iam_member" "build_logs" {
  project = var.project_id
  role    = "roles/logging.logWriter"
  member  = google_service_account.build.member
}

# Push images - ONLY to our repo, not every repo in the project
resource "google_artifact_registry_repository_iam_member" "build_push" {
  location   = google_artifact_registry_repository.app.location
  repository = google_artifact_registry_repository.app.name
  role       = "roles/artifactregistry.writer"
  member     = google_service_account.build.member
}

# Read the uploaded source tarball (bucket auto-created by `gcloud builds submit`)
resource "google_storage_bucket_iam_member" "build_reads_source" {
  bucket = "${var.project_id}_cloudbuild"
  role   = "roles/storage.objectViewer"
  member = google_service_account.build.member
}


# Deploy Cloud Run revisions and shift traffic
resource "google_project_iam_member" "build_deploys_run" {
  project = var.project_id
  role    = "roles/run.developer"
  member  = google_service_account.build.member
}

# Allowed to deploy services that run AS shoppilot-dev (and only that SA)
resource "google_service_account_iam_member" "build_acts_as_app" {
  service_account_id = data.google_service_account.app.name
  role               = "roles/iam.serviceAccountUser"
  member             = google_service_account.build.member
}
