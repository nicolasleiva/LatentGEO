# AWS staging deployment toolkit

This folder contains a reproducible deployment flow for AWS staging in `us-east-1`.

## Files
- `config.example.env`: required configuration values.
- `deploy.ps1`: orchestrates infra + images + ECS + CloudFront + validation hooks.
- `freeze-source.ps1`: creates a deploy branch, commit, and release tag from current local state.
- `credits-activities.ps1`: optional best-effort script to complete AWS credit activities.
- `templates/network.yml`: VPC, subnets, NAT, and security groups.
- `templates/data.yml`: RDS PostgreSQL + ElastiCache Redis.
- `templates/app.yml`: ECS Fargate services, ALB, CloudFront, IAM roles, and logs.

## Quick start
1. Copy config template:
   `Copy-Item scripts/aws/staging/config.example.env scripts/aws/staging/config.env`
2. Fill required values in `scripts/aws/staging/config.env`.
   - `ALB_ORIGIN_DOMAIN`: FQDN used by CloudFront to reach ALB origin (for example `alb-origin.staging.example.com`).
   - `ROUTE53_HOSTED_ZONE_ID`: public hosted zone ID that owns `ALB_ORIGIN_DOMAIN`.
3. Configure AWS CLI profile (`default`) with SSO:
   - `aws configure sso --profile default`
   - SSO Start URL: `https://d-9066007ac4.awsapps.com/start`
   - SSO Region: `us-east-1`
   - Default region: `us-east-1`
   - Output format: `json`
4. Login and validate account:
   - `aws sso login --profile default`
   - `aws sts get-caller-identity --profile default --query Account --output text`
   - Expected account: `077415454081`
5. Freeze source snapshot:
   `pwsh ./scripts/aws/staging/freeze-source.ps1 -Push`
6. Deploy staging:
   `pwsh ./scripts/aws/staging/deploy.ps1 -ConfigPath ./scripts/aws/staging/config.env`
7. Optional credits activities (run only after stable deploy):
   `pwsh ./scripts/aws/staging/deploy.ps1 -ConfigPath ./scripts/aws/staging/config.env -EnableCredits`

## Notes
- Region is fixed to `us-east-1` unless you override `AWS_REGION`.
- The deploy script creates/updates Secrets Manager secret `${PROJECT_NAME}/${ENVIRONMENT_NAME}/app`.
- If `DB_PASSWORD` is empty, `deploy.ps1` generates a strong random password at runtime.
- CloudFront default domain is used for staging URL.
- ALB origin traffic is restricted using AWS managed prefix list `com.amazonaws.global.cloudfront.origin-facing`.
- `ROUTE53_HOSTED_ZONE_ID` is your domain hosted zone. The ALB alias target hosted zone is derived automatically from ALB `CanonicalHostedZoneID`.
- Credits activities are optional and should not block release.
