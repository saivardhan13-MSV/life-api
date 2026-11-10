# ---------------------------------------------------------------- data lake
resource "aws_s3_bucket" "lake" {
  bucket = "${local.name}-lake-${local.account_id}"
}

resource "aws_s3_bucket_public_access_block" "lake" {
  bucket                  = aws_s3_bucket.lake.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_server_side_encryption_configuration" "lake" {
  bucket = aws_s3_bucket.lake.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_versioning" "lake" {
  bucket = aws_s3_bucket.lake.id
  versioning_configuration {
    status = "Enabled" # protects raw data from accidental overwrite/delete
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "lake" {
  bucket = aws_s3_bucket.lake.id

  rule {
    id     = "expire-old-versions"
    status = "Enabled"
    filter {}
    noncurrent_version_expiration {
      noncurrent_days = 30
    }
    abort_incomplete_multipart_upload {
      days_after_initiation = 1
    }
  }
}

# ---------------------------------------------------------- athena results
resource "aws_s3_bucket" "athena_results" {
  bucket        = "${local.name}-athena-${local.account_id}"
  force_destroy = true
}

resource "aws_s3_bucket_public_access_block" "athena_results" {
  bucket                  = aws_s3_bucket.athena_results.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_lifecycle_configuration" "athena_results" {
  bucket = aws_s3_bucket.athena_results.id
  rule {
    id     = "expire-query-results"
    status = "Enabled"
    filter {}
    expiration {
      days = 7
    }
  }
}

# ---------------------------------------------------------------- dynamodb
resource "aws_dynamodb_table" "life" {
  name         = local.name
  billing_mode = "PAY_PER_REQUEST" # no idle cost
  hash_key     = "pk"
  range_key    = "sk"

  attribute {
    name = "pk"
    type = "S"
  }
  attribute {
    name = "sk"
    type = "S"
  }

  point_in_time_recovery {
    enabled = true
  }

  # Encrypted at rest by default with an AWS-owned key (no KMS cost).

  deletion_protection_enabled = true
}

# --------------------------------------------------------------- secrets
resource "random_password" "api_key" {
  length  = 40
  special = false
}

resource "aws_ssm_parameter" "api_key" {
  name  = "/${var.project}/${var.environment}/api-key"
  type  = "SecureString"
  value = random_password.api_key.result
}

# Filled in by scripts/google_health_auth.py; Terraform only creates the slot.
resource "aws_ssm_parameter" "google_client" {
  name  = "/${var.project}/${var.environment}/google-health/client"
  type  = "SecureString"
  value = jsonencode({ client_id = "set-me", client_secret = "set-me" })
  lifecycle {
    ignore_changes = [value]
  }
}

resource "aws_ssm_parameter" "google_token" {
  name  = "/${var.project}/${var.environment}/google-health/token"
  type  = "SecureString"
  value = jsonencode({ refresh_token = "set-me" })
  lifecycle {
    ignore_changes = [value]
  }
}
