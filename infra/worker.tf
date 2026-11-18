# Cloud Run service defined in Terraform. Terraform owns CONFIG, CI owns the IMAGE.
resource "google_cloud_run_v2_service" "worker" {
  name                = "shoppilot-worker"
  location            = var.region
  ingress             = "INGRESS_TRAFFIC_ALL" # reachable by Pub/Sub; protected by IAM (not public!)
  deletion_protection = false
  labels              = local.common_labels

  template {
    service_account                  = google_service_account.worker.email
    max_instance_request_concurrency = 10
    timeout                          = "60s"

    scaling {
      min_instance_count = 0 # scale to zero when no tickets
      max_instance_count = 3 # cost cap + protects Firestore
    }

    containers {
      image   = var.worker_image
      command = ["uvicorn"]
      args    = ["shoppilot.worker.main:app", "--host", "0.0.0.0", "--port", "8080"]

      env {
        name  = "PROJECT_ID"
        value = var.project_id
      }

      resources {
        limits = {
          cpu    = "1"
          memory = "512Mi"
        }
      }
    }
  }

  lifecycle {
    # CI deploys new images; don't let Terraform roll them back
    ignore_changes = [template[0].containers[0].image, client, client_version]
  }

  depends_on = [google_project_iam_member.worker_firestore]
}

# ONLY the push identity may invoke the worker
resource "google_cloud_run_v2_service_iam_member" "push_invokes_worker" {
  name     = google_cloud_run_v2_service.worker.name
  location = google_cloud_run_v2_service.worker.location
  role     = "roles/run.invoker"
  member   = google_service_account.push.member
}

# The push subscription: Pub/Sub POSTs each message to the worker
resource "google_pubsub_subscription" "worker_push" {
  name                       = "ticket-events-worker"
  topic                      = google_pubsub_topic.ticket_events.id
  ack_deadline_seconds       = 60 # for push = how long Pub/Sub waits for the HTTP response
  message_retention_duration = "86400s"
  labels                     = local.common_labels

  push_config {
    push_endpoint = "${google_cloud_run_v2_service.worker.uri}/pubsub/tickets"
    oidc_token {
      service_account_email = google_service_account.push.email
      audience              = google_cloud_run_v2_service.worker.uri
    }
  }

  retry_policy {
    minimum_backoff = "5s"
    maximum_backoff = "60s"
  }

  dead_letter_policy {
    dead_letter_topic     = google_pubsub_topic.ticket_events_dlq.id
    max_delivery_attempts = 5
  }

  expiration_policy {
    ttl = ""
  }

  depends_on = [google_cloud_run_v2_service_iam_member.push_invokes_worker]
}

# DLQ forwarding needs the Pub/Sub agent on this subscription too
resource "google_pubsub_subscription_iam_member" "agent_acks_worker" {
  subscription = google_pubsub_subscription.worker_push.name
  role         = "roles/pubsub.subscriber"
  member       = local.pubsub_agent
}

output "worker_url" {
  value = google_cloud_run_v2_service.worker.uri
}
