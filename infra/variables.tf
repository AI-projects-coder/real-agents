variable "project_id" {
  type        = string
  description = "GCP project ID"
}

variable "region" {
  type    = string
  default = "us-central1"
}

variable "worker_image" {
  type        = string
  description = "Initial image for the worker. CI updates it afterwards (Terraform ignores image changes)."
}

