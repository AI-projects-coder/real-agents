locals {
  common_labels = {
    app        = "shoppilot"
    managed_by = "terraform"
  }
}

# DATA SOURCE: the service account already exists (made by gcloud). We only read it.
data "google_service_account" "app" {
  account_id = "shoppilot-dev"
}

# IMPORT: adopt the bucket you created with Python in 1A.
import {
  to = google_storage_bucket.policies
  id = "${var.project_id}-policies"
}

resource "google_storage_bucket" "policies" {
  name                        = "${var.project_id}-policies"
  location                    = "US-CENTRAL1"
  storage_class               = "STANDARD"
  uniform_bucket_level_access = true
  public_access_prevention    = "enforced"
  labels                      = local.common_labels

  versioning {
    enabled = true
  }

  # keep only the 3 most recent old versions of each file
  lifecycle_rule {
    condition {
      num_newer_versions = 3
      with_state         = "ARCHIVED"
    }
    action {
      type = "Delete"
    }
  }

  # safety net: terraform refuses to delete this bucket
  lifecycle {
    prevent_destroy = true
  }
}

# Same grant you did by hand in 1A, now as code.
resource "google_storage_bucket_iam_member" "app_reads_policies" {
  bucket = google_storage_bucket.policies.name
  role   = "roles/storage.objectViewer"
  member = data.google_service_account.app.member
}

# NEW bucket: raw customer uploads (used in Module 4 for event-driven ingestion).
resource "google_storage_bucket" "uploads" {
  name                        = "${var.project_id}-uploads"
  location                    = "US-CENTRAL1"
  uniform_bucket_level_access = true
  public_access_prevention    = "enforced"
  force_destroy               = true # allows deleting even if it has files (OK for non-critical data)
  labels                      = local.common_labels

  # auto-delete raw uploads after 30 days (controls cost)
  lifecycle_rule {
    condition {
      age = 30
    }
    action {
      type = "Delete"
    }
  }
}

