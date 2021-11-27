/* ====================  Fork Analysis - forks are dispatched ==================== */

resource "google_pubsub_topic" "fork_analysis_ingestion" {
  name = "fork_analysis_ingestion"
}

resource "google_pubsub_topic" "fork_analysis_dlq" {
  name = "fork_analysis_dlq"
}

// Pushes an excavated fork to analyzer
resource "google_pubsub_subscription" "fork_analyzer_sub" {
  name  = "fork_analyzer_sub"
  topic = google_pubsub_topic.fork_analysis_ingestion.name

  ack_deadline_seconds = 10

  // Make push subscription to the CLoud Run listener endpoint
  push_config {
    push_endpoint = google_cloud_run_service.analyzer.status[0].url

    attributes = {
      x-goog-version = "v1"
    }

    // service to service auth, as this is not deployed publicly
    oidc_token {
      service_account_email = google_service_account.fork_dispatcher_sa.email
    }
  }

  // Drop failed requests in DLQ after 2 failed requests
  dead_letter_policy {
    dead_letter_topic     = google_pubsub_topic.fork_analysis_dlq.id
    max_delivery_attempts = 5
  }
}

// Subscription for dead letter queue
resource "google_pubsub_subscription" "fork_analysis_dlq_sub" {
  name  = "fork_analysis_dlq_sub"
  topic = google_pubsub_topic.fork_analysis_dlq.name
}

/* ====================  Output - results are written after analysis ==================== */

resource "google_pubsub_topic" "fork_alert_output" {
  name = "fork_alert_output"
}
