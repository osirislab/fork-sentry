terraform {
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "3.81.0"
    }
  }
}

provider "google" {
  project = var.project_name
  region  = var.region
  zone    = var.zone

  credentials = var.google_application_credentials
}

// Imported manually
resource "google_project" "project" {
  name       = var.project_name
  project_id = var.project_name
}

// Imported manually from the root service account we're using as credentials
resource "google_service_account" "service_account" {
  account_id  = var.service_account_id
  description = "TF-managed service account for Fork Sentry"
}
