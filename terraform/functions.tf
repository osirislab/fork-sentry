locals {
  timestamp = formatdate("YYMMDDhhmmss", timestamp())
}

/* ====================  Alert Function ==================== */

data "archive_file" "alert_source_code" {
  type        = "zip"
  source_dir  = abspath("../alert")
  output_path = "/tmp/alert-${local.timestamp}.zip"
}

resource "google_cloudfunctions_function" "alert" {
  name        = "alert-function"
  description = "Suspicious Fork Alert Function"
  runtime     = "python38"

  available_memory_mb   = 128
  source_archive_bucket = google_storage_bucket.source_bucket.name
  source_archive_object = google_storage_bucket_object.alert_archive.name
  trigger_http          = true
  entry_point           = "handler"
}

/* ====================  Retry Function ==================== */

data "archive_file" "retry_source_code" {
  type        = "zip"
  source_dir  = abspath("../retry")
  output_path = "/tmp/retry-${local.timestamp}.zip"
}

resource "google_cloudfunctions_function" "retry_function" {
  name        = "retry-function"
  description = "Re-enqueues messages for retry"
  runtime     = "python38"

  available_memory_mb   = 128
  source_archive_bucket = google_storage_bucket.source_bucket.name
  source_archive_object = google_storage_bucket_object.alert_archive.name
  trigger_http          = true
  entry_point           = "handler"
}