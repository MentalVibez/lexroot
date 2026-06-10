# Living Lexicon AWS ECS Fargate Deployment

This Terraform stack deploys the MVP production architecture in `us-east-1`:

- S3 + CloudFront for `https://pensiveape.com`
- ECS Fargate + HTTPS ALB for `https://api.pensiveape.com`
- RDS PostgreSQL in private subnets
- ECR for the FastAPI Docker image
- Route 53 DNS and ACM TLS certificates
- Secrets Manager for generated app and database secrets

Neo4j and Ollama are intentionally disabled for this first production deployment.

## Prerequisites

- AWS credentials with permissions for VPC, ECS, ECR, RDS, S3, CloudFront, ACM, Route 53, IAM, CloudWatch, and Secrets Manager.
- The `pensiveape.com` public hosted zone exists in Route 53.
- Terraform 1.6+.
- Docker.
- AWS CLI.

## First Deployment

Copy the example variables:

```bash
cd infra/terraform
cp terraform.tfvars.example terraform.tfvars
```

Initialize Terraform:

```bash
terraform init
```

Create the ECR repository first:

```bash
terraform apply -target=aws_ecr_repository.api
```

Build and push the API image from the repository root:

```bash
AWS_REGION=us-east-1
ECR_REPO_URL=$(terraform -chdir=infra/terraform output -raw ecr_repository_url)

aws ecr get-login-password --region "$AWS_REGION" \
  | docker login --username AWS --password-stdin "$ECR_REPO_URL"

docker build -t "$ECR_REPO_URL:latest" .
docker push "$ECR_REPO_URL:latest"
```

Apply the full stack:

```bash
terraform apply
```

For later image-only deploys with the same tag:

```bash
aws ecs update-service \
  --region us-east-1 \
  --cluster "$(terraform -chdir=infra/terraform output -raw ecs_cluster_name)" \
  --service "$(terraform -chdir=infra/terraform output -raw ecs_service_name)" \
  --force-new-deployment
```

Upload the static frontend:

```bash
FRONTEND_BUCKET=$(terraform -chdir=infra/terraform output -raw frontend_bucket)
CLOUDFRONT_ID=$(terraform -chdir=infra/terraform output -raw cloudfront_distribution_id)

aws s3 sync frontend/ "s3://$FRONTEND_BUCKET/" --delete
aws cloudfront create-invalidation \
  --distribution-id "$CLOUDFRONT_ID" \
  --paths "/*"
```

Run database migrations from a trusted environment that can reach the RDS endpoint. For the MVP network, the simplest path is usually a one-off ECS task or a temporary bastion/VPN pattern.

## Important Notes

- This stack intentionally avoids NAT Gateway cost. ECS tasks run in public subnets with locked-down security groups; RDS stays private.
- The generated database password and URL secrets are stored in AWS Secrets Manager, but Terraform state also contains generated secret values. Use an encrypted remote backend such as S3 with bucket encryption and DynamoDB locking before using this with a team.
- `deletion_protection` defaults to `true` for RDS. Set it to `false` only when intentionally destroying the database.
- The frontend chooses `https://api.pensiveape.com` automatically when served from `pensiveape.com` or `www.pensiveape.com`.
- ECS sets `ENABLE_NEO4J=false` and `ENABLE_OLLAMA=false`; production health checks treat those services as disabled, not failed.

## Useful Checks

```bash
curl https://api.pensiveape.com/health
curl "https://api.pensiveape.com/pg/words/search?q=char&limit=5"
```

Check service status:

```bash
aws ecs describe-services \
  --region us-east-1 \
  --cluster "$(terraform output -raw ecs_cluster_name)" \
  --services "$(terraform output -raw ecs_service_name)"
```
