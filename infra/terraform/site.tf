# Public dashboard: private S3 bucket served only through CloudFront (OAC).

resource "aws_s3_bucket" "site" {
  bucket        = "${local.name}-site-${local.account_id}"
  force_destroy = true
}

resource "aws_s3_bucket_public_access_block" "site" {
  bucket                  = aws_s3_bucket.site.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_cloudfront_origin_access_control" "site" {
  name                              = "${local.name}-site"
  origin_access_control_origin_type = "s3"
  signing_behavior                  = "always"
  signing_protocol                  = "sigv4"
}

resource "aws_cloudfront_distribution" "site" {
  enabled             = true
  default_root_object = "index.html"
  price_class         = "PriceClass_100"
  comment             = "${local.name} public dashboard"

  origin {
    domain_name              = aws_s3_bucket.site.bucket_regional_domain_name
    origin_id                = "site"
    origin_access_control_id = aws_cloudfront_origin_access_control.site.id
  }

  default_cache_behavior {
    target_origin_id       = "site"
    viewer_protocol_policy = "redirect-to-https"
    allowed_methods        = ["GET", "HEAD"]
    cached_methods         = ["GET", "HEAD"]
    compress               = true
    cache_policy_id        = "658327ea-f89d-4fab-a63d-7e88639e58f6" # AWS managed CachingOptimized
  }

  restrictions {
    geo_restriction {
      restriction_type = "none"
    }
  }

  viewer_certificate {
    cloudfront_default_certificate = true
  }
}

data "aws_iam_policy_document" "site" {
  statement {
    actions   = ["s3:GetObject"]
    resources = ["${aws_s3_bucket.site.arn}/*"]
    principals {
      type        = "Service"
      identifiers = ["cloudfront.amazonaws.com"]
    }
    condition {
      test     = "StringEquals"
      variable = "AWS:SourceArn"
      values   = [aws_cloudfront_distribution.site.arn]
    }
  }
}

resource "aws_s3_bucket_policy" "site" {
  bucket = aws_s3_bucket.site.id
  policy = data.aws_iam_policy_document.site.json
}

locals {
  site_files = {
    "index.html" = "text/html; charset=utf-8"
    "me.html"    = "text/html; charset=utf-8"
    "styles.css" = "text/css; charset=utf-8"
    "charts.js"  = "application/javascript"
  }
}

resource "aws_s3_object" "site" {
  for_each      = local.site_files
  bucket        = aws_s3_bucket.site.id
  key           = each.key
  source        = "${path.module}/../../web/${each.key}"
  etag          = filemd5("${path.module}/../../web/${each.key}")
  content_type  = each.value
  cache_control = "public, max-age=60"
}

moved {
  from = aws_s3_object.index
  to   = aws_s3_object.site["index.html"]
}

resource "aws_s3_object" "config" {
  bucket        = aws_s3_bucket.site.id
  key           = "config.js"
  content       = "window.LIFE_API_URL = ${jsonencode(aws_apigatewayv2_stage.default.invoke_url)};\nwindow.LIFE_TZ = ${jsonencode(var.timezone)};\n"
  content_type  = "application/javascript"
  cache_control = "public, max-age=300"
}
