output "frontend_url" {
  description = "Public frontend URL."
  value       = "https://${var.domain_name}"
}

output "api_url" {
  description = "Public API URL."
  value       = "https://${local.api_domain}"
}

output "ecr_repository_url" {
  description = "ECR repository URL for API container images."
  value       = aws_ecr_repository.api.repository_url
}

output "expected_image_uri" {
  description = "Image URI referenced by the ECS task definition."
  value       = local.ecr_image
}

output "frontend_bucket" {
  description = "S3 bucket for static frontend files."
  value       = aws_s3_bucket.frontend.id
}

output "cloudfront_distribution_id" {
  description = "CloudFront distribution ID for cache invalidations."
  value       = aws_cloudfront_distribution.frontend.id
}

output "alb_dns_name" {
  description = "Application Load Balancer DNS name."
  value       = aws_lb.api.dns_name
}

output "rds_endpoint" {
  description = "Private RDS PostgreSQL endpoint."
  value       = aws_db_instance.postgres.endpoint
}

output "ecs_cluster_name" {
  description = "ECS cluster name."
  value       = aws_ecs_cluster.main.name
}

output "ecs_service_name" {
  description = "ECS service name."
  value       = aws_ecs_service.api.name
}
