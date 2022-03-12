locals {
  services = [
    "cloudresourcemanager.googleapis.com",
    "cloudfunctions.googleapis.com",
    "cloudbuild.googleapis.com",
    "artifactregistry.googleapis.com",
    "iam.googleapis.com",
    "run.googleapis.com",
    "cloudscheduler.googleapis.com",
    "secretmanager.googleapis.com",
    "sourcerepo.googleapis.com",
    "pubsub.googleapis.com"
  ]
}

resource "google_project_service" "cloud_api_enables" {
  project            = var.project_name
  for_each           = toset(local.services)
  service            = each.value
  disable_on_destroy = false
}