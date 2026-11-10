# GitHub Actions authenticates with short-lived OIDC tokens: no AWS keys stored in GitHub.

locals {
  github_enabled = var.github_repo != ""
  oidc_url       = "token.actions.githubusercontent.com"
}

resource "aws_iam_openid_connect_provider" "github" {
  count          = local.github_enabled && var.create_github_oidc_provider ? 1 : 0
  url            = "https://${local.oidc_url}"
  client_id_list = ["sts.amazonaws.com"]
}

data "aws_iam_openid_connect_provider" "github" {
  count = local.github_enabled && !var.create_github_oidc_provider ? 1 : 0
  url   = "https://${local.oidc_url}"
}

locals {
  github_oidc_arn = !local.github_enabled ? "" : (
    var.create_github_oidc_provider
    ? aws_iam_openid_connect_provider.github[0].arn
    : data.aws_iam_openid_connect_provider.github[0].arn
  )
}

data "aws_iam_policy_document" "github_assume" {
  count = local.github_enabled ? 1 : 0
  statement {
    actions = ["sts:AssumeRoleWithWebIdentity"]
    principals {
      type        = "Federated"
      identifiers = [local.github_oidc_arn]
    }
    condition {
      test     = "StringEquals"
      variable = "${local.oidc_url}:aud"
      values   = ["sts.amazonaws.com"]
    }
    # Only main, or jobs in the protected "prod" environment, can assume the roles.
    condition {
      test     = "StringEquals"
      variable = "${local.oidc_url}:sub"
      values   = ["repo:${var.github_repo}:ref:refs/heads/main", "repo:${var.github_repo}:environment:prod"]
    }
  }
}

# Deploy role: Terraform has to create IAM roles, buckets, etc., so this is broad.
# It is only assumable from main. A stricter setup would split plan/apply roles.
resource "aws_iam_role" "github_deploy" {
  count              = local.github_enabled ? 1 : 0
  name               = "${local.name}-github-deploy"
  assume_role_policy = data.aws_iam_policy_document.github_assume[0].json
}

resource "aws_iam_role_policy_attachment" "github_deploy" {
  count      = local.github_enabled ? 1 : 0
  role       = aws_iam_role.github_deploy[0].name
  policy_arn = "arn:aws:iam::aws:policy/AdministratorAccess"
}

# dbt role: least privilege, only what Athena + Glue + the lake need.
resource "aws_iam_role" "github_dbt" {
  count              = local.github_enabled ? 1 : 0
  name               = "${local.name}-github-dbt"
  assume_role_policy = data.aws_iam_policy_document.github_assume[0].json
}

data "aws_iam_policy_document" "dbt" {
  statement {
    actions = [
      "athena:StartQueryExecution", "athena:GetQueryExecution", "athena:GetQueryResults",
      "athena:StopQueryExecution", "athena:GetWorkGroup", "athena:ListQueryExecutions",
    ]
    resources = [aws_athena_workgroup.life.arn]
  }
  statement {
    actions   = ["athena:ListDataCatalogs", "athena:GetDataCatalog", "athena:ListWorkGroups"]
    resources = ["*"]
  }
  statement {
    actions = [
      "glue:GetDatabase", "glue:GetDatabases", "glue:GetTable", "glue:GetTables",
      "glue:GetPartition", "glue:GetPartitions", "glue:BatchGetPartition",
      "glue:CreateTable", "glue:UpdateTable", "glue:DeleteTable", "glue:BatchCreatePartition",
      "glue:BatchDeletePartition", "glue:BatchDeleteTable",
    ]
    resources = [
      "arn:aws:glue:${var.region}:${local.account_id}:catalog",
      aws_glue_catalog_database.clean.arn,
      aws_glue_catalog_database.curated.arn,
      "arn:aws:glue:${var.region}:${local.account_id}:table/${aws_glue_catalog_database.clean.name}/*",
      "arn:aws:glue:${var.region}:${local.account_id}:table/${aws_glue_catalog_database.curated.name}/*",
    ]
  }
  statement {
    actions   = ["s3:GetObject", "s3:ListBucket", "s3:GetBucketLocation"]
    resources = [aws_s3_bucket.lake.arn, "${aws_s3_bucket.lake.arn}/clean/*"]
  }
  statement {
    actions   = ["s3:GetObject", "s3:PutObject", "s3:DeleteObject", "s3:ListBucket", "s3:GetBucketLocation"]
    resources = [aws_s3_bucket.lake.arn, "${aws_s3_bucket.lake.arn}/curated/*"]
  }
  statement {
    actions   = ["s3:GetObject", "s3:PutObject", "s3:ListBucket", "s3:GetBucketLocation", "s3:AbortMultipartUpload"]
    resources = [aws_s3_bucket.athena_results.arn, "${aws_s3_bucket.athena_results.arn}/*"]
  }
}

resource "aws_iam_role_policy" "github_dbt" {
  count  = local.github_enabled ? 1 : 0
  role   = aws_iam_role.github_dbt[0].id
  policy = data.aws_iam_policy_document.dbt.json
}
