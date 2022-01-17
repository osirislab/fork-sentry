/* ====================  Fork Analysis - forks are dispatched ==================== */

resource "google_pubsub_topic" "fork_analysis_ingestion" {
  name = "fork_analysis_ingestion"
}

// Pushes an excavated fork to analyzer
resource "google_pubsub_subscription" "fork_analyzer_sub" {
  name  = "fork_analyzer_sub"
  topic = google_pubsub_topic.fork_analysis_ingestion.name

  // Forks will take time to acknowledge, set deadline to max
  ack_deadline_seconds = 600

  // Make push subscription to the Cloud Run listener endpoint
  push_config {
    push_endpoint = google_cloud_run_service.analyzer.status[0].url

    attributes = {
      x-goog-version = "v1"
    }

    // service to service auth, as this is not deployed publicly
    oidc_token {
      service_account_email = google_service_account.fork_analyzer_sa.email
    }
  }

  // Drop failed requests in DLQ after 2 failed requests
  dead_letter_policy {
    dead_letter_topic     = google_pubsub_topic.fork_analysis_dlq.id
    max_delivery_attempts = 5
  }
}

// Retry queue for rate-limited messages
resource "google_pubsub_topic" "fork_analysis_retry" {
  name = "fork_analysis_retry"
}


// Dead letter queue for non-retryable messages
resource "google_pubsub_topic" "fork_analysis_dlq" {
  name = "fork_analysis_dlq"
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

// Pushes results to trigger alert function
resource "google_pubsub_subscription" "fork_out_sub" {
  name  = "fork_alert_output_sub"
  topic = google_pubsub_topic.fork_alert_output.name

  ack_deadline_seconds = 20

  // Make push subscription to the HTTP endpoint of function
  push_config {
    push_endpoint = google_cloudfunctions_function.alert.https_trigger_url

    attributes = {
      x-goog-version = "v1"
    }

    // service to service auth, as this is not deployed publicly
    oidc_token {
      service_account_email = google_service_account.fork_alert_sa.email
    }
  }

  // Drop failed requests in DLQ after 2 failed requests
  dead_letter_policy {
    dead_letter_topic     = google_pubsub_topic.fork_out_dlq.id
    max_delivery_attempts = 5
  }
}

// Retry queue for rate-limited messages
resource "google_pubsub_topic" "fork_out_retry" {
  name = "fork_out_retry"
}

// Dead letter queue for non-retryable messages
resource "google_pubsub_topic" "fork_out_dlq" {
  name = "fork_out_dlq"
}

// Subscription for dead letter queue
resource "google_pubsub_subscription" "fork_out_dlq_sub" {
  name  = "fork_out_dlq_sub"
  topic = google_pubsub_topic.fork_out_dlq.name
}
