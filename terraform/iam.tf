/* ====================  Fork Dispatcher IAM Permissions ==================== */

resource "google_service_account" "fork_dispatcher_sa" {
  account_id = "fork-dispatcher-sa"
}

data "google_iam_policy" "noauth" {
  binding {
    role = "roles/run.invoker"
    members = [
      "allUsers",
    ]
  }
}

// Publicly exposed endpoint to GitHub Actions
resource "google_cloud_run_service_iam_policy" "dispatcher_iam_member" {
  service  = google_cloud_run_service.dispatcher.name
  location = google_cloud_run_service.dispatcher.location
  policy_data = data.google_iam_policy.noauth.policy_data
}

/* ====================  Fork Analyzer IAM Permissions ==================== */

resource "google_service_account" "fork_analyzer_sa" {
  account_id = "fork-analyzer-sa"
}

// Allow invocation by pubsub to analyzer only
resource "google_cloud_run_service_iam_member" "analyzer_iam_member" {
  service  = google_cloud_run_service.analyzer.name
  location = google_cloud_run_service.analyzer.location
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.fork_analyzer_sa.email}"
}
