# Glue tables over the clean JSONL zone. Partition projection on `dt` means no
# crawlers and no MSCK REPAIR: Athena computes partitions from the S3 layout.

resource "aws_glue_catalog_database" "clean" {
  name = "${local.glue_prefix}_clean"
}

resource "aws_glue_catalog_database" "curated" {
  name         = "${local.glue_prefix}_curated"
  location_uri = "s3://${aws_s3_bucket.lake.bucket}/curated/"
}

locals {
  clean_tables = {
    daily_health = [
      { name = "day", type = "string" },
      { name = "sleep_minutes", type = "int" },
      { name = "deep_sleep_minutes", type = "int" },
      { name = "light_sleep_minutes", type = "int" },
      { name = "rem_sleep_minutes", type = "int" },
      { name = "awake_minutes", type = "int" },
      { name = "sleep_start", type = "string" },
      { name = "sleep_end", type = "string" },
      { name = "steps", type = "int" },
      { name = "resting_heart_rate", type = "int" },
      { name = "_ingested_at", type = "string" },
    ]
    screen_time = [
      { name = "day", type = "string" },
      { name = "package", type = "string" },
      { name = "app_name", type = "string" },
      { name = "minutes", type = "double" },
      { name = "is_doomscroll", type = "boolean" },
      { name = "_ingested_at", type = "string" },
    ]
    applications = [
      { name = "id", type = "string" },
      { name = "company", type = "string" },
      { name = "role", type = "string" },
      { name = "status", type = "string" },
      { name = "source", type = "string" },
      { name = "location", type = "string" },
      { name = "url", type = "string" },
      { name = "notes", type = "string" },
      { name = "applied_on", type = "string" },
      { name = "created_at", type = "string" },
      { name = "updated_at", type = "string" },
      { name = "_ingested_at", type = "string" },
    ]
  }
}

resource "aws_glue_catalog_table" "clean" {
  for_each      = local.clean_tables
  name          = each.key
  database_name = aws_glue_catalog_database.clean.name
  table_type    = "EXTERNAL_TABLE"

  parameters = {
    "classification"              = "json"
    "projection.enabled"          = "true"
    "projection.dt.type"          = "date"
    "projection.dt.format"        = "yyyy-MM-dd"
    "projection.dt.range"         = "2024-01-01,NOW"
    "projection.dt.interval"      = "1"
    "projection.dt.interval.unit" = "DAYS"
    "storage.location.template"   = "s3://${aws_s3_bucket.lake.bucket}/clean/${each.key}/dt=$${dt}/"
  }

  partition_keys {
    name = "dt"
    type = "string"
  }

  storage_descriptor {
    location      = "s3://${aws_s3_bucket.lake.bucket}/clean/${each.key}/"
    input_format  = "org.apache.hadoop.mapred.TextInputFormat"
    output_format = "org.apache.hadoop.hive.ql.io.HiveIgnoreKeyTextOutputFormat"

    ser_de_info {
      serialization_library = "org.openx.data.jsonserde.JsonSerDe"
      parameters            = { "ignore.malformed.json" = "true" }
    }

    dynamic "columns" {
      for_each = each.value
      content {
        name = columns.value.name
        type = columns.value.type
      }
    }
  }
}

resource "aws_athena_workgroup" "life" {
  name          = local.name
  force_destroy = true

  configuration {
    enforce_workgroup_configuration    = true
    publish_cloudwatch_metrics_enabled = true
    bytes_scanned_cutoff_per_query     = 1073741824 # 1 GB hard cap per query = max ~$0.005

    result_configuration {
      output_location = "s3://${aws_s3_bucket.athena_results.bucket}/results/"
      encryption_configuration {
        encryption_option = "SSE_S3"
      }
    }
  }
}
