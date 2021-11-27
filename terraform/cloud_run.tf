/* ==================== Fork Dispatcher ==================== */

resource "google_cloud_run_service" "dispatcher" {
  name     = "fork-dispatcher"
  location = var.region

  template {
    spec {
      containers {
        image = var.dispatcher_image

        resources {
          limits = {
            cpu    = 2
            memory = "1024M"
          }
        }

        // Cloud Resources
        env {
          name  = "GOOGLE_PROJECT_ID"
          value = var.project_name
        }
        env {
          name  = "ANALYSIS_QUEUE"
          value = google_pubsub_topic.fork_analysis_ingestion.name
        }
        env {
          name  = "ROOT_API_TOKEN"
          value = var.root_api_token
        }
      }
    }
  }

  traffic {
    percent         = 100
    latest_revision = true
  }

  autogenerate_revision_name = true
}

/* ==================== Fork Analyzer ==================== */

resource "google_cloud_run_service" "analyzer" {
  name     = "fork-analyzer"
  location = var.region

  template {
    spec {
      containers {
        image = var.analyzer_image

        resources {
          limits = {
            cpu    = 2
            memory = "1024M"
          }
        }

        // Cloud Resources
        env {
          name  = "GOOGLE_PROJECT_ID"
          value = var.project_name
        }
        env {
          name  = "ALERT_TOPIC"
          value = google_pubsub_topic.fork_alert_output.name
        }
      }
    }
  }

  traffic {
    percent         = 100
    latest_revision = true
  }

  autogenerate_revision_name = true
}
