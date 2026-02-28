# EKS Module Variables

variable "cluster_name" {
  description = "Name of the EKS cluster"
  type        = string
}

variable "cluster_version" {
  description = "Kubernetes version"
  type        = string
  default     = "1.28"
}

variable "vpc_id" {
  description = "VPC ID"
  type        = string
}

variable "subnet_ids" {
  description = "List of subnet IDs"
  type        = list(string)
}

variable "cluster_endpoint_private_access" {
  description = "Enable private API server endpoint"
  type        = bool
  default     = true
}

variable "cluster_endpoint_public_access" {
  description = "Enable public API server endpoint"
  type        = bool
  default     = true
}

variable "cluster_endpoint_public_access_cidrs" {
  description = "CIDR blocks for public API access"
  type        = list(string)
  default     = ["0.0.0.0/0"]
}

variable "cluster_enabled_log_types" {
  description = "List of log types to enable"
  type        = list(string)
  default     = ["api", "audit", "authenticator"]
}

variable "cluster_encryption_config" {
  description = "Encryption configuration"
  type = object({
    provider_key_arn = string
    resources        = list(string)
  })
  default = {
    provider_key_arn = ""
    resources        = ["secrets"]
  }
}

variable "eks_managed_node_groups" {
  description = "Map of managed node group definitions"
  type        = any
  default     = {}
}

variable "fargate_profiles" {
  description = "Map of Fargate profile definitions"
  type        = any
  default     = {}
}

variable "manage_aws_auth_configmap" {
  description = "Manage aws-auth ConfigMap"
  type        = bool
  default     = false
}

variable "aws_auth_roles" {
  description = "List of IAM roles to add to aws-auth"
  type        = list(any)
  default     = []
}

variable "aws_auth_users" {
  description = "List of IAM users to add to aws-auth"
  type        = list(any)
  default     = []
}

variable "kms_key_id" {
  description = "KMS key ID for encryption"
  type        = string
  default     = null
}

variable "tags" {
  description = "Tags to apply to resources"
  type        = map(string)
  default     = {}
}
