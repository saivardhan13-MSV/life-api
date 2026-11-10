output "api_url" {
  value = aws_apigatewayv2_stage.default.invoke_url
}

output "dashboard_url" {
  value = "https://${aws_cloudfront_distribution.site.domain_name}"
}

output "api_key_parameter" {
  description = "Read with: aws ssm get-parameter --with-decryption --name <this> --query Parameter.Value --output text"
  value       = aws_ssm_parameter.api_key.name
}

output "google_token_parameter" {
  value = aws_ssm_parameter.google_token.name
}

output "google_client_parameter" {
  value = aws_ssm_parameter.google_client.name
}

output "lake_bucket" {
  value = aws_s3_bucket.lake.bucket
}

output "dbt_env" {
  description = "Environment variables for running dbt (locally or in CI)."
  value = {
    DBT_ATHENA_STAGING_DIR = "s3://${aws_s3_bucket.athena_results.bucket}/dbt/"
    DBT_ATHENA_DATA_DIR    = "s3://${aws_s3_bucket.lake.bucket}/curated/"
    DBT_ATHENA_WORKGROUP   = aws_athena_workgroup.life.name
    DBT_ATHENA_SCHEMA      = aws_glue_catalog_database.curated.name
    DBT_CLEAN_SCHEMA       = aws_glue_catalog_database.clean.name
  }
}

output "github_deploy_role_arn" {
  value = local.github_enabled ? aws_iam_role.github_deploy[0].arn : null
}

output "github_dbt_role_arn" {
  value = local.github_enabled ? aws_iam_role.github_dbt[0].arn : null
}
