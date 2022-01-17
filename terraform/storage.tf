/* ==================== Function Source Code Bucket ==================== */

resource "google_storage_bucket" "source_bucket" {
  name = "fork_sentry_source_bucket"
}

resource "google_storage_bucket_object" "alert_archive" {
  name   = "source.zip#${data.archive_file.alert_source_code.output_md5}"
  bucket = google_storage_bucket.source_bucket.name
  source = data.archive_file.alert_source_code.output_path
}

resource "google_storage_bucket_object" "retry_archive" {
  name   = "source.zip#${data.archive_file.retry_source_code.output_md5}"
  bucket = google_storage_bucket.source_bucket.name
  source = data.archive_file.retry_source_code.output_path
}

/* ==================== Artifact Bucket ==================== */

// Stores potential malware for auxiliary analysis
resource "google_storage_bucket" "infected_bucket" {
  name = "infected-bucket"
}
