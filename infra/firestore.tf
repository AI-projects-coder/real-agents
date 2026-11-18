resource "google_firestore_database" "main" {
  name                    = "(default)" # the free tier applies to the (default) database
  location_id             = var.region
  type                    = "FIRESTORE_NATIVE"
  delete_protection_state = "DELETE_PROTECTION_DISABLED" # learning project; ENABLE in production
  deletion_policy         = "DELETE"
  depends_on              = [google_project_service.apis]
}

# TTL policy: Firestore auto-deletes processed_events docs after their expire_at time
resource "google_firestore_field" "processed_events_ttl" {
  database   = google_firestore_database.main.name
  collection = "processed_events"
  field      = "expire_at"
  ttl_config {}
}

# ---------- Identities ----------
resource "google_service_account" "worker" {
  account_id   = "shoppilot-worker"
  display_name = "ShopPilot ticket worker"
}

resource "google_service_account" "push" {
  account_id   = "shoppilot-pubsub-push"
  display_name = "Identity Pub/Sub uses to call the worker"
}

# Worker reads/writes Firestore
resource "google_project_iam_member" "worker_firestore" {
  project = var.project_id
  role    = "roles/datastore.user"
  member  = google_service_account.worker.member
}

# API only READS tickets (GET /tickets/{id})
resource "google_project_iam_member" "app_firestore_read" {
  project = var.project_id
  role    = "roles/datastore.viewer"
  member  = data.google_service_account.app.member
}

# CI may deploy services that run as the worker SA
resource "google_service_account_iam_member" "build_acts_as_worker" {
  service_account_id = google_service_account.worker.name
  role               = "roles/iam.serviceAccountUser"
  member             = google_service_account.build.member
}
