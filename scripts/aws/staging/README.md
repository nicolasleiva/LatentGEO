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
3. Configure AWS CLI credentials/profile.
4. Freeze source snapshot:
   `pwsh ./scripts/aws/staging/freeze-source.ps1 -Push`
5. Deploy staging:
   `pwsh ./scripts/aws/staging/deploy.ps1 -ConfigPath ./scripts/aws/staging/config.env`

## Notes
- Region is fixed to `us-east-1` unless you override `AWS_REGION`.
- The deploy script creates/updates Secrets Manager secret `${PROJECT_NAME}/${ENVIRONMENT_NAME}/app`.
- CloudFront default domain is used for staging URL.
- Credits activities are optional and should not block release.
