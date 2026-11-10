variable "project" {
  type    = string
  default = "life-api"
}

variable "environment" {
  type    = string
  default = "prod"
}

variable "region" {
  type    = string
  default = "us-east-1"
}

variable "timezone" {
  description = "IANA timezone used for 'today' and the ingest schedule."
  type        = string
  default     = "America/New_York"
}

variable "alert_email" {
  description = "Email for CloudWatch alarms and budget alerts (you must confirm the SNS subscription)."
  type        = string
}

variable "monthly_budget_usd" {
  type    = number
  default = 5
}

variable "lambda_zip_path" {
  description = "Path to the package built by scripts/build_lambda.py."
  type        = string
  default     = "../../build/lambda.zip"
}

variable "github_repo" {
  description = "owner/name of the GitHub repo allowed to deploy via OIDC. Empty disables the CI roles."
  type        = string
  default     = ""
}

variable "create_github_oidc_provider" {
  description = "Set false if the account already has the GitHub OIDC provider."
  type        = bool
  default     = true
}

variable "extra_cors_origins" {
  description = "Extra origins allowed to call the API (e.g. http://localhost:8000 for local dashboard dev)."
  type        = list(string)
  default     = []
}

locals {
  name       = "${var.project}-${var.environment}"
  account_id = data.aws_caller_identity.current.account_id
  # Glue database names cannot contain hyphens.
  glue_prefix = replace(local.name, "-", "_")
}
