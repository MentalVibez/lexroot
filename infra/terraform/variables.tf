variable "aws_region" {
  description = "AWS region for all resources. CloudFront ACM certificates must be in us-east-1."
  type        = string
  default     = "us-east-1"
}

variable "project_name" {
  description = "Short name used to prefix AWS resources."
  type        = string
  default     = "living-lexicon"
}

variable "domain_name" {
  description = "Apex domain hosted in Route 53."
  type        = string
  default     = "pensiveape.com"
}

variable "api_subdomain" {
  description = "Subdomain for the FastAPI service."
  type        = string
  default     = "api"
}

variable "container_image_tag" {
  description = "Docker image tag deployed to ECS from the ECR repository."
  type        = string
  default     = "latest"
}

variable "container_port" {
  description = "Port exposed by the FastAPI container."
  type        = number
  default     = 8000
}

variable "app_cpu" {
  description = "Fargate task CPU units."
  type        = number
  default     = 512
}

variable "app_memory" {
  description = "Fargate task memory in MiB."
  type        = number
  default     = 1024
}

variable "app_desired_count" {
  description = "Number of ECS tasks to run."
  type        = number
  default     = 1
}

variable "db_name" {
  description = "PostgreSQL database name."
  type        = string
  default     = "living_lexicon"
}

variable "db_username" {
  description = "PostgreSQL master username."
  type        = string
  default     = "lexicon"
}

variable "db_instance_class" {
  description = "RDS PostgreSQL instance class."
  type        = string
  default     = "db.t4g.micro"
}

variable "db_allocated_storage" {
  description = "RDS allocated storage in GiB."
  type        = number
  default     = 20
}

variable "cors_origins" {
  description = "Comma-separated CORS origins for the API."
  type        = string
  default     = "https://pensiveape.com,https://www.pensiveape.com"
}

variable "enable_write_endpoints" {
  description = "Enable write/admin endpoints in production."
  type        = bool
  default     = false
}

variable "require_api_key" {
  description = "Require X-API-Key for non-public API routes."
  type        = bool
  default     = false
}

variable "log_retention_days" {
  description = "CloudWatch log retention for ECS app logs."
  type        = number
  default     = 30
}

variable "rds_backup_retention_days" {
  description = "Automated RDS backup retention."
  type        = number
  default     = 7
}

variable "deletion_protection" {
  description = "Protect RDS from accidental deletion."
  type        = bool
  default     = true
}
