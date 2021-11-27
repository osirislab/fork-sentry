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
