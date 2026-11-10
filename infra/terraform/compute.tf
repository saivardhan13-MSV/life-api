locals {
  lambda_env = {
    LIFE_TABLE_NAME          = aws_dynamodb_table.life.name
    LIFE_LAKE_BUCKET         = aws_s3_bucket.lake.bucket
    LIFE_TIMEZONE            = var.timezone
    LIFE_API_KEY_PARAM       = aws_ssm_parameter.api_key.name
    LIFE_GOOGLE_TOKEN_PARAM  = aws_ssm_parameter.google_token.name
    LIFE_GOOGLE_CLIENT_PARAM = aws_ssm_parameter.google_client.name
    LIFE_CORS_ORIGINS        = jsonencode(local.cors_origins)
  }
  cors_origins = concat(["https://${aws_cloudfront_distribution.site.domain_name}"], var.extra_cors_origins)
}

# ------------------------------------------------------------------ IAM
data "aws_iam_policy_document" "lambda_assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "api" {
  name               = "${local.name}-api"
  assume_role_policy = data.aws_iam_policy_document.lambda_assume.json
}

resource "aws_iam_role" "ingest" {
  name               = "${local.name}-ingest"
  assume_role_policy = data.aws_iam_policy_document.lambda_assume.json
}

resource "aws_iam_role_policy_attachment" "api_logs" {
  role       = aws_iam_role.api.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

resource "aws_iam_role_policy_attachment" "ingest_logs" {
  role       = aws_iam_role.ingest.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

# Least privilege: the API can read/write the table, write screen time to the
# lake, and read its own API key. Nothing else.
data "aws_iam_policy_document" "api" {
  statement {
    actions   = ["dynamodb:GetItem", "dynamodb:PutItem", "dynamodb:UpdateItem", "dynamodb:DeleteItem", "dynamodb:Query"]
    resources = [aws_dynamodb_table.life.arn]
  }
  statement {
    actions   = ["s3:PutObject"]
    resources = ["${aws_s3_bucket.lake.arn}/clean/screen_time/*"]
  }
  statement {
    actions   = ["ssm:GetParameter"]
    resources = [aws_ssm_parameter.api_key.arn]
  }
}

resource "aws_iam_role_policy" "api" {
  role   = aws_iam_role.api.id
  policy = data.aws_iam_policy_document.api.json
}

data "aws_iam_policy_document" "ingest" {
  statement {
    actions   = ["dynamodb:UpdateItem", "dynamodb:Query"]
    resources = [aws_dynamodb_table.life.arn]
  }
  statement {
    actions = ["s3:PutObject"]
    resources = [
      "${aws_s3_bucket.lake.arn}/raw/*",
      "${aws_s3_bucket.lake.arn}/clean/daily_health/*",
      "${aws_s3_bucket.lake.arn}/clean/applications/*",
    ]
  }
  statement {
    actions   = ["ssm:GetParameter"]
    resources = [aws_ssm_parameter.google_client.arn, aws_ssm_parameter.google_token.arn]
  }
  statement {
    # Google may rotate the refresh token; the job writes it back.
    actions   = ["ssm:PutParameter"]
    resources = [aws_ssm_parameter.google_token.arn]
  }
}

resource "aws_iam_role_policy" "ingest" {
  role   = aws_iam_role.ingest.id
  policy = data.aws_iam_policy_document.ingest.json
}

# --------------------------------------------------------------- Lambdas
resource "aws_cloudwatch_log_group" "api" {
  name              = "/aws/lambda/${local.name}-api"
  retention_in_days = 14
}

resource "aws_cloudwatch_log_group" "ingest" {
  name              = "/aws/lambda/${local.name}-ingest"
  retention_in_days = 30
}

resource "aws_lambda_function" "api" {
  function_name    = "${local.name}-api"
  role             = aws_iam_role.api.arn
  runtime          = "python3.12"
  architectures    = ["arm64"] # ~20% cheaper than x86
  handler          = "life_api.handlers.api_handler"
  filename         = var.lambda_zip_path
  source_code_hash = filebase64sha256(var.lambda_zip_path)
  memory_size      = 512
  timeout          = 10

  environment {
    variables = local.lambda_env
  }

  depends_on = [aws_cloudwatch_log_group.api]
}

resource "aws_lambda_function" "ingest" {
  function_name    = "${local.name}-ingest"
  role             = aws_iam_role.ingest.arn
  runtime          = "python3.12"
  architectures    = ["arm64"]
  handler          = "life_api.handlers.ingest_handler"
  filename         = var.lambda_zip_path
  source_code_hash = filebase64sha256(var.lambda_zip_path)
  memory_size      = 256
  timeout          = 300

  environment {
    variables = local.lambda_env
  }

  depends_on = [aws_cloudwatch_log_group.ingest]
}

# ----------------------------------------------------------- API Gateway
resource "aws_apigatewayv2_api" "http" {
  name          = local.name
  protocol_type = "HTTP"

  cors_configuration {
    allow_origins = local.cors_origins
    allow_methods = ["GET", "POST", "PATCH", "DELETE"]
    allow_headers = ["content-type", "x-api-key"]
    max_age       = 3600
  }
}

resource "aws_apigatewayv2_integration" "api" {
  api_id                 = aws_apigatewayv2_api.http.id
  integration_type       = "AWS_PROXY"
  integration_uri        = aws_lambda_function.api.invoke_arn
  payload_format_version = "2.0"
}

resource "aws_apigatewayv2_route" "default" {
  api_id    = aws_apigatewayv2_api.http.id
  route_key = "$default"
  target    = "integrations/${aws_apigatewayv2_integration.api.id}"
}

resource "aws_cloudwatch_log_group" "api_access" {
  name              = "/aws/apigateway/${local.name}"
  retention_in_days = 14
}

resource "aws_apigatewayv2_stage" "default" {
  api_id      = aws_apigatewayv2_api.http.id
  name        = "$default"
  auto_deploy = true

  # A public endpoint can be hammered; throttling caps both abuse and cost.
  default_route_settings {
    throttling_burst_limit = 20
    throttling_rate_limit  = 10
  }

  access_log_settings {
    destination_arn = aws_cloudwatch_log_group.api_access.arn
    format = jsonencode({
      requestId = "$context.requestId"
      ip        = "$context.identity.sourceIp"
      method    = "$context.httpMethod"
      path      = "$context.path"
      status    = "$context.status"
      latencyMs = "$context.responseLatency"
    })
  }
}

resource "aws_lambda_permission" "apigw" {
  statement_id  = "AllowApiGateway"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.api.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.http.execution_arn}/*/*"
}

# ------------------------------------------------------------- scheduler
data "aws_iam_policy_document" "scheduler_assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["scheduler.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "scheduler" {
  name               = "${local.name}-scheduler"
  assume_role_policy = data.aws_iam_policy_document.scheduler_assume.json
}

resource "aws_iam_role_policy" "scheduler" {
  role = aws_iam_role.scheduler.id
  policy = jsonencode({
    Version   = "2012-10-17"
    Statement = [{ Effect = "Allow", Action = "lambda:InvokeFunction", Resource = aws_lambda_function.ingest.arn }]
  })
}

resource "aws_scheduler_schedule" "daily_ingest" {
  name                         = "${local.name}-daily-ingest"
  schedule_expression          = "cron(0 */3 * * ? *)" # every 3h local: yesterday final + today so far
  schedule_expression_timezone = var.timezone

  flexible_time_window {
    mode = "OFF"
  }

  target {
    arn      = aws_lambda_function.ingest.arn
    role_arn = aws_iam_role.scheduler.arn
    input    = jsonencode({})

    retry_policy {
      maximum_retry_attempts       = 2
      maximum_event_age_in_seconds = 3600
    }
  }
}
