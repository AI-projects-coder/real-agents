data "google_project" "this" {}

locals {
  # Google's own Pub/Sub service agent - it moves messages into the DLQ for us
  pubsub_agent = "serviceAccount:service-${data.google_project.this.number}@gcp-sa-pubsub.iam.gserviceaccount.com"
}

# ---------- Topics ----------
resource "google_pubsub_topic" "ticket_events" {
  name                       = "ticket-events"
  message_retention_duration = "86400s" # keep 1 day (allows replay/seek)
  labels                     = local.common_labels
  depends_on                 = [google_project_service.apis]
}

resource "google_pubsub_topic" "ticket_events_dlq" {
  name       = "ticket-events-dlq"
  labels     = local.common_labels
  depends_on = [google_project_service.apis]
}

# ---------- Subscriptions ----------
# Main worker queue: retries with backoff, DLQ after 5 failed attempts
resource "google_pubsub_subscription" "learn" {
  name                       = "ticket-events-learn"
  topic                      = google_pubsub_topic.ticket_events.id
  ack_deadline_seconds       = 20
  message_retention_duration = "86400s"
  labels                     = local.common_labels

  retry_policy {
    minimum_backoff = "5s"
    maximum_backoff = "60s"
  }

  dead_letter_policy {
    dead_letter_topic     = google_pubsub_topic.ticket_events_dlq.id
    max_delivery_attempts = 5
  }

  expiration_policy {
    ttl = "" # never auto-delete this subscription when idle
  }
}

# Fan-out: a second, independent consumer of the same events
resource "google_pubsub_subscription" "analytics" {
  name                       = "ticket-events-analytics"
  topic                      = google_pubsub_topic.ticket_events.id
  ack_deadline_seconds       = 20
  message_retention_duration = "86400s"
  labels                     = local.common_labels
  expiration_policy {
    ttl = ""
  }
}

# Where we inspect dead letters
resource "google_pubsub_subscription" "dlq" {
  name                       = "ticket-events-dlq-sub"
  topic                      = google_pubsub_topic.ticket_events_dlq.id
  message_retention_duration = "604800s" # 7 days to investigate
  labels                     = local.common_labels
  expiration_policy {
    ttl = ""
  }
}

# ---------- IAM ----------
# The DLQ only works if Pub/Sub's service agent can publish to the DLQ topic...
resource "google_pubsub_topic_iam_member" "agent_publishes_dlq" {
  topic  = google_pubsub_topic.ticket_events_dlq.name
  role   = "roles/pubsub.publisher"
  member = local.pubsub_agent
}

# ...and ack the original message on the source subscription
resource "google_pubsub_subscription_iam_member" "agent_acks_learn" {
  subscription = google_pubsub_subscription.learn.name
  role         = "roles/pubsub.subscriber"
  member       = local.pubsub_agent
}

# Our app identity: may publish ticket events (the API in 3B) and consume them (the worker)
resource "google_pubsub_topic_iam_member" "app_publishes" {
  topic  = google_pubsub_topic.ticket_events.name
  role   = "roles/pubsub.publisher"
  member = data.google_service_account.app.member
}

resource "google_pubsub_subscription_iam_member" "app_consumes" {
  subscription = google_pubsub_subscription.learn.name
  role         = "roles/pubsub.subscriber"
  member       = data.google_service_account.app.member
}
