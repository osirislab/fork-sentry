// Allow service account to instantiate authenticated tokens
resource "google_project_iam_binding" "token_creator" {
  role = "roles/iam.serviceAccountTokenCreator"
  members = [
    "serviceAccount:service-${var.project_num}@gcp-sa-pubsub.iam.gserviceaccount.com",
  ]
}

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
resource "google_cloud_run_service_iam_member" "fork_analyzer_iam_member" {
  service  = google_cloud_run_service.analyzer.name
  location = google_cloud_run_service.analyzer.location
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.fork_analyzer_sa.email}"
}

// Restrict publish access only to bot dispatcher
resource "google_pubsub_topic_iam_binding" "fork_analysis_binding" {
  topic   = google_pubsub_topic.fork_analysis_ingestion.name
  role    = "roles/pubsub.publisher"
  members = ["serviceAccount:${google_service_account.service_account.email}"]
}

/* ====================  Alert Function IAM Permissions ==================== */

resource "google_service_account" "fork_alert_sa" {
  account_id = "fork-alert-sa"
}

// Allow invocation by pubsub to function by dispatcher only
resource "google_cloudfunctions_function_iam_member" "fork_alert_iam_member" {
  cloud_function = google_cloudfunctions_function.alert.name
  role           = "roles/cloudfunctions.invoker"
  member         = "serviceAccount:${google_service_account.fork_alert_sa.email}"
}