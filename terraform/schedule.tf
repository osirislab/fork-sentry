/*
resource "google_cloud_scheduler_job" "reanalyze" {
  name             = "reanalyze"
  description      = "Hourly job to re-enqueue failed forks due to rate-limit"
  time_zone        = "America/New_York"
  attempt_deadline = "320s"

  retry_config {
    retry_count = 1
  }

  http_target {
    http_method = "POST"
    uri         = "https://example.com/ping"
    body        = base64encode("{\"foo\":\"bar\"}")
  }
}

resource "google_cloud_scheduler_job" "realert" {
  name             = "realert"
  description      = "Hourly job to re-enqueue alerting on failed forks"
  time_zone        = "America/New_York"
  attempt_deadline = "320s"

  retry_config {
    retry_count = 1
  }

  http_target {
    http_method = "POST"
    uri         = "https://example.com/ping"
    body        = base64encode("{\"foo\":\"bar\"}")
  }
}
*/