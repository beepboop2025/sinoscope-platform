# DragonScope Enterprise - Terraform Variables
# Configuration for AWS infrastructure deployment

# =============================================================================
# GENERAL
# =============================================================================
variable "aws_region" {
  description = "AWS region for primary resources"
  type        = string
  default     = "us-west-2"
}

variable "dr_region" {
  description = "AWS region for disaster recovery"
  type        = string
  default     = "us-east-1"
}

variable "environment" {
  description = "Environment name (production, staging, development)"
  type        = string
  default     = "production"
  
  validation {
    condition     = contains(["production", "staging", "development"], var.environment)
    error_message = "Environment must be production, staging, or development."
  }
}

variable "project_name" {
  description = "Project name"
  type        = string
  default     = "dragonscope"
}

# =============================================================================
# NETWORKING
# =============================================================================
variable "vpc_cidr" {
  description = "CIDR block for VPC"
  type        = string
  default     = "10.0.0.0/16"
}

variable "private_subnets" {
  description = "List of private subnet CIDRs"
  type        = list(string)
  default     = ["10.0.1.0/24", "10.0.2.0/24", "10.0.3.0/24"]
}

variable "public_subnets" {
  description = "List of public subnet CIDRs"
  type        = list(string)
  default     = ["10.0.101.0/24", "10.0.102.0/24", "10.0.103.0/24"]
}

variable "database_subnets" {
  description = "List of database subnet CIDRs"
  type        = list(string)
  default     = ["10.0.201.0/24", "10.0.202.0/24", "10.0.203.0/24"]
}

variable "allowed_admin_cidrs" {
  description = "CIDR blocks allowed for admin access"
  type        = list(string)
  default     = []
}

# =============================================================================
# KUBERNETES
# =============================================================================
variable "kubernetes_version" {
  description = "Kubernetes version"
  type        = string
  default     = "1.28"
}

variable "cluster_autoscaler_version" {
  description = "Cluster Autoscaler version"
  type        = string
  default     = "v1.28.0"
}

# =============================================================================
# DATABASE
# =============================================================================
variable "rds_instance_class" {
  description = "RDS instance type"
  type        = string
  default     = "db.r6g.xlarge"
}

variable "rds_multi_az" {
  description = "Enable Multi-AZ for RDS"
  type        = bool
  default     = true
}

variable "rds_backup_retention" {
  description = "RDS backup retention period in days"
  type        = number
  default     = 35
}

# =============================================================================
# CACHE
# =============================================================================
variable "redis_node_type" {
  description = "ElastiCache Redis node type"
  type        = string
  default     = "cache.r6g.large"
}

variable "redis_num_cache_nodes" {
  description = "Number of Redis cache nodes"
  type        = number
  default     = 3
}

# =============================================================================
# KAFKA
# =============================================================================
variable "msk_instance_type" {
  description = "MSK broker instance type"
  type        = string
  default     = "kafka.m5.large"
}

variable "msk_number_of_broker_nodes" {
  description = "Number of MSK broker nodes"
  type        = number
  default     = 3
}

# =============================================================================
# STORAGE
# =============================================================================
variable "s3_versioning" {
  description = "Enable S3 versioning"
  type        = bool
  default     = true
}

variable "s3_lifecycle_days" {
  description = "Number of days for S3 lifecycle transitions"
  type        = map(number)
  default = {
    standard_to_ia   = 30
    ia_to_glacier    = 90
    glacier_expiry   = 2555
    log_expiry       = 90
  }
}

# =============================================================================
# MONITORING
# =============================================================================
variable "enable_container_insights" {
  description = "Enable CloudWatch Container Insights"
  type        = bool
  default     = true
}

variable "retention_in_days" {
  description = "CloudWatch log retention in days"
  type        = number
  default     = 30
}

# =============================================================================
# SECURITY
# =============================================================================
variable "enable_waf" {
  description = "Enable AWS WAF"
  type        = bool
  default     = true
}

variable "enable_shield_advanced" {
  description = "Enable AWS Shield Advanced"
  type        = bool
  default     = false
}

variable "enable_guardduty" {
  description = "Enable GuardDuty"
  type        = bool
  default     = true
}

# =============================================================================
# TAGS
# =============================================================================
variable "additional_tags" {
  description = "Additional tags to apply to resources"
  type        = map(string)
  default     = {}
}
