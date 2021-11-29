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
  service     = google_cloud_run_service.dispatcher.name
  location    = google_cloud_run_service.dispatcher.location
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

// Allow service account to instantiate authenticated tokens
resource "google_project_iam_binding" "project" {
  role = "roles/iam.serviceAccountTokenCreator"
  members = [
    "serviceAccount:service-${google_project.project.number}@gcp-sa-pubsub.iam.gserviceaccount.com",
  ]
}

/* ====================  Pub/Sub IAM Permissions ==================== */

// Restrict publish access only to bot dispatcher
resource "google_pubsub_topic_iam_binding" "fork_analysis_binding" {
  topic   = google_pubsub_topic.fork_analysis_ingestion.name
  role    = "roles/pubsub.publisher"
  members = ["serviceAccount:${google_service_account.service_account.email}"]
}