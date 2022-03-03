/* ==================== Fork Dispatcher ==================== */

resource "google_cloud_run_service" "dispatcher" {
  name     = "fork-dispatcher"
  location = var.region

  template {
    spec {
      containers {
        image = "${var.region}-docker.pkg.dev/${var.project_name}/${var.repo_name}/dispatcher:latest"

        resources {
          limits = {
            cpu    = 4
            memory = "4000M"
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
        image = "${var.region}-docker.pkg.dev/${var.project_name}/${var.repo_name}/analyzer:latest"

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
        env {
          name  = "SENTRY_DSN"
          value = var.analyzer_sentry_dsn
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
