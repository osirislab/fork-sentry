/* ====================  Function Source Code Bucket ==================== */

locals {
  timestamp = formatdate("YYMMDDhhmmss", timestamp())
}

data "archive_file" "alert_source_code" {
  type        = "zip"
  source_dir  = abspath("../alert")
  output_path = "/tmp/function-${local.timestamp}.zip"
}

resource "google_storage_bucket" "source_bucket" {
  name = "alert_source_bucket"
}

resource "google_storage_bucket_object" "alert_archive" {
  name   = "source.zip#${data.archive_file.alert_source_code.output_md5}"
  bucket = google_storage_bucket.source_bucket.name
  source = data.archive_file.alert_source_code.output_path
}


/* ====================  Artifact Bucket ==================== */

resource "google_storage_bucket" "infected_bucket" {
  name = "infected-bucket"
}