resource "google_artifact_registry_repository" "artifacts" {
  provider      = google-beta
  location      = var.region
  repository_id = var.repo_name
  description   = "Container images for Fork Sentry"
  format        = "DOCKER"
}