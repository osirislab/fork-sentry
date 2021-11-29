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