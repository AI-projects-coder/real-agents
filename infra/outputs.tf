output "policies_bucket" {
  value = google_storage_bucket.policies.url
}

output "uploads_bucket" {
  value = google_storage_bucket.uploads.url
}

output "image_repo" {
  value = "${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.app.repository_id}"
}
