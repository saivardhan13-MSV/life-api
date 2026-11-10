# Setup

Order: AWS account → first deploy from your laptop → Google Health OAuth → GitHub CI/CD → screen time.

## 1. AWS account and guardrails

1. Create an AWS account and turn on MFA for the root user. Don't use root after that.
2. Create an IAM Identity Center (SSO) user with admin access and log in with `aws configure sso`.
3. Region: `us-east-1` (default here).

Terraform also creates a **$5/month budget** that emails you at 50% actual and 100% forecast spend.

## 2. Remote state bucket (one time)

```bash
aws s3api create-bucket --bucket <yourname>-tfstate --region us-east-1
aws s3api put-bucket-versioning --bucket <yourname>-tfstate --versioning-configuration Status=Enabled
```

## 3. First deploy (from your laptop)

```bash
python scripts/build_lambda.py
cd infra/terraform
cp terraform.tfvars.example terraform.tfvars   # set alert_email, timezone, github_repo
terraform init -backend-config="bucket=<yourname>-tfstate" \
  -backend-config="key=life-api/prod.tfstate" -backend-config="region=us-east-1"
terraform apply
```

Confirm the SNS subscription email you receive. Get your API key:

```bash
aws ssm get-parameter --with-decryption --name /life-api/prod/api-key --query Parameter.Value --output text
```

## 4. Google Health API (Fitbit data)

The legacy Fitbit Web API was turned off on **2026-11-02**. Fitbit data now comes from the Google Health API.

1. In Google Cloud Console, create a project and enable the **Google Health API**.
2. OAuth consent screen: User type **External**, Publishing status **Testing**, and add your own Google account as a **test user**.
3. Data Access: add these scopes:
   - `https://www.googleapis.com/auth/googlehealth.sleep.readonly`
   - `https://www.googleapis.com/auth/googlehealth.activity_and_fitness.readonly`
   - `https://www.googleapis.com/auth/googlehealth.health_metrics_and_measurements.readonly`
4. Create an OAuth client of type **Web application** with the redirect URI `http://localhost:8765/callback`.
5. Make sure your Fitbit is linked in the Google Health app on your phone.
6. Run the consent helper. It stores the client and token in SSM:

```bash
python scripts/google_health_auth.py --client-id <id> --client-secret <secret>
```

7. Test it once, with a two-week backfill:

```bash
aws lambda invoke --function-name life-api-prod-ingest \
  --payload '{"backfill_days": 14}' --cli-binary-format raw-in-base64-out out.json && cat out.json
```

> **Testing mode caveat:** Google issues refresh tokens that **expire after 7 days** while the OAuth app is in Testing mode. When that happens the ingest alarm emails you; re-run step 6. Google's docs are unclear on whether a one-user app can be published without a security review for these restricted scopes.

> **Check after the first run:** the docs don't show the response shape for `daily-resting-heart-rate`. Open `raw/source=google_health/dataset=resting_heart_rate/` in S3. If `resting_heart_rate` is empty in the clean data, adjust `RHR_VALUE_KEYS` in `src/life_api/ingest/transform.py` and replay with `{"backfill_days": N}`.

## 5. GitHub CI/CD

1. Push the repo to GitHub, then set `github_repo = "<you>/life-api"` in `terraform.tfvars` and run `terraform apply` again. This creates the OIDC roles.
2. In the repo settings, create an environment named **`prod`**, then add:
   - **Secrets**: `AWS_DEPLOY_ROLE_ARN`, `AWS_DBT_ROLE_ARN` (from `terraform output`), `TF_STATE_BUCKET`, `ALERT_EMAIL`
   - **Variables**: `AWS_REGION`, `TIMEZONE`, and the values from `terraform output dbt_env`
3. From then on: a PR runs CI, a merge to `main` deploys, and dbt runs daily at 15:00 UTC.

## 6. Screen time from Android

Digital Wellbeing has no export button. Options, from simplest:

1. Use any usage-tracking app that exports CSV, rename its columns to `date,package,app_name,minutes`, then:
   ```bash
   LIFE_API_KEY=<key> python scripts/import_screen_time.py usage.csv --api <api_url>
   ```
2. Automate it with Tasker or Automate, posting JSON to `POST /v1/screen-time` each night.
3. Roadmap: a small Android app that reads `UsageStatsManager` and posts the numbers automatically.

## 7. Log a job application

```bash
curl -X POST "$API/v1/applications" -H "X-API-Key: $KEY" -H "Content-Type: application/json" \
  -d '{"company":"Amazon","role":"SDE I","url":"https://amazon.jobs/..."}'
```

## Troubleshooting

- **Git Bash on Windows rewrites `/life-api/...` into a file path** (you'll see `ParameterNotFound`). Prefix AWS commands with `MSYS_NO_PATHCONV=1`, or use PowerShell.
- **`KMS validation error ... Key does not exist` creating DynamoDB:** some accounts have a broken `aws/dynamodb` managed key. The table here uses DynamoDB's default AWS-owned encryption, so this doesn't apply anymore.
- **Windows "path too long" during `pip install` or the Lambda build:** keep the repo in a short path, or set `LIFE_BUILD_DIR` to a short folder.
