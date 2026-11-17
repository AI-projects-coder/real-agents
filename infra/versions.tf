terraform {
  required_version = ">= 1.9"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 7.0"
    }
  }

  # Remote state. NOTE: the backend block cannot use variables.
  backend "gcs" {
    bucket = "shoppilot-514613-tfstate"
    prefix = "core"
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}
