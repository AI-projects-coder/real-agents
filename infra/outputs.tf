output "policies_bucket" {
  value = google_storage_bucket.policies.url
}

output "uploads_bucket" {
  value = google_storage_bucket.uploads.url
}
