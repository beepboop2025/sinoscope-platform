# DragonScope Enterprise - Terraform Infrastructure
# AWS Cloud Infrastructure for Production Deployment

terraform {
  required_version = ">= 1.5.0"
  
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    kubernetes = {
      source  = "hashicorp/kubernetes"
      version = "~> 2.23"
    }
    helm = {
      source  = "hashicorp/helm"
      version = "~> 2.11"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.5"
    }
  }
  
  backend "s3" {
    bucket         = "dragonscope-terraform-state"
    key            = "enterprise/production/terraform.tfstate"
    region         = "us-west-2"
    encrypt        = true
    dynamodb_table = "dragonscope-terraform-locks"
  }
}

# Configure AWS Provider
provider "aws" {
  region = var.aws_region
  
  default_tags {
    tags = {
      Project     = "DragonScope"
      Environment = var.environment
      ManagedBy   = "Terraform"
      Owner       = "Platform Team"
      CostCenter  = "Engineering"
    }
  }
}

# Alternative regions for disaster recovery
provider "aws" {
  alias  = "dr"
  region = var.dr_region
}

# Data sources
data "aws_caller_identity" "current" {}
data "aws_region" "current" {}
data "aws_availability_zones" "available" {
  state = "available"
}

# =============================================================================
# LOCALS
# =============================================================================
locals {
  account_id = data.aws_caller_identity.current.account_id
  region     = data.aws_region.current.name
  
  common_tags = {
    Project     = "DragonScope"
    Environment = var.environment
    ManagedBy   = "Terraform"
    Owner       = "Platform Team"
  }
  
  cluster_name = "dragonscope-${var.environment}"
}

# =============================================================================
# VPC MODULE
# =============================================================================
module "vpc" {
  source = "./modules/vpc"
  
  name                 = "${local.cluster_name}-vpc"
  cidr                 = var.vpc_cidr
  azs                  = slice(data.aws_availability_zones.available.names, 0, 3)
  private_subnets      = var.private_subnets
  public_subnets       = var.public_subnets
  database_subnets     = var.database_subnets
  
  enable_nat_gateway   = true
  single_nat_gateway   = false
  enable_vpn_gateway   = var.environment == "production" ? true : false
  enable_dns_hostnames = true
  enable_dns_support   = true
  
  # VPC Flow Logs
  enable_flow_log                      = true
  create_flow_log_cloudwatch_iam_role  = true
  create_flow_log_cloudwatch_log_group = true
  flow_log_max_aggregation_interval    = 60
  
  # VPC Endpoints
  enable_ec2_endpoint              = true
  ec2_endpoint_private_dns_enabled = true
  ec2_endpoint_security_group_ids  = [aws_security_group.vpc_endpoints.id]
  
  # Tags for Kubernetes integration
  private_subnet_tags = {
    "kubernetes.io/cluster/${local.cluster_name}" = "shared"
    "kubernetes.io/role/internal-elb"             = "1"
  }
  
  public_subnet_tags = {
    "kubernetes.io/cluster/${local.cluster_name}" = "shared"
    "kubernetes.io/role/elb"                      = "1"
  }
  
  tags = local.common_tags
}

# =============================================================================
# EKS CLUSTER
# =============================================================================
module "eks" {
  source = "./modules/eks"
  
  cluster_name    = local.cluster_name
  cluster_version = var.kubernetes_version
  
  vpc_id     = module.vpc.vpc_id
  subnet_ids = module.vpc.private_subnets
  
  # Control Plane Logging
  cluster_enabled_log_types = ["api", "audit", "authenticator", "controllerManager", "scheduler"]
  
  # Public endpoint restricted to specific CIDRs
  cluster_endpoint_public_access       = true
  cluster_endpoint_public_access_cidrs = var.allowed_admin_cidrs
  cluster_endpoint_private_access      = true
  
  # KMS encryption
  cluster_encryption_config = {
    provider_key_arn = aws_kms_key.eks.arn
    resources        = ["secrets"]
  }
  
  # Managed Node Groups
  eks_managed_node_groups = {
    general = {
      desired_size = 3
      min_size     = 2
      max_size     = 20
      
      instance_types = ["m6i.2xlarge"]
      capacity_type  = "ON_DEMAND"
      
      k8s_labels = {
        Environment = var.environment
        NodeGroup   = "general"
      }
      
      update_config = {
        max_unavailable_percentage = 25
      }
      
      block_device_mappings = {
        xvda = {
          device_name = "/dev/xvda"
          ebs = {
            volume_size           = 100
            volume_type           = "gp3"
            iops                  = 3000
            throughput            = 125
            encrypted             = true
            kms_key_id            = aws_kms_key.ebs.arn
            delete_on_termination = true
          }
        }
      }
    }
    
    spot = {
      desired_size = 2
      min_size     = 1
      max_size     = 50
      
      instance_types = ["m6i.xlarge", "m5.xlarge", "m5a.xlarge"]
      capacity_type  = "SPOT"
      
      k8s_labels = {
        Environment = var.environment
        NodeGroup   = "spot"
        Workload    = "batch"
      }
      
      taints = [{
        key    = "dedicated"
        value  = "spot"
        effect = "NO_SCHEDULE"
      }]
    }
    
    memory_optimized = {
      desired_size = 2
      min_size     = 1
      max_size     = 10
      
      instance_types = ["r6i.2xlarge"]
      capacity_type  = "ON_DEMAND"
      
      k8s_labels = {
        Environment = var.environment
        NodeGroup   = "memory-optimized"
        Workload    = "data"
      }
      
      taints = [{
        key    = "dedicated"
        value  = "data"
        effect = "NO_SCHEDULE"
      }]
    }
  }
  
  # Fargate Profiles
  fargate_profiles = {
    kube_system = {
      name = "kube-system"
      selectors = [
        { namespace = "kube-system" }
      ]
    }
    
    monitoring = {
      name = "monitoring"
      selectors = [
        { namespace = "dragonscope-monitoring" }
      ]
      subnets = module.vpc.private_subnets
    }
  }
  
  # AWS Auth configuration
  manage_aws_auth_configmap = true
  aws_auth_roles = [
    {
      rolearn  = aws_iam_role.cluster_admin.arn
      username = "admin:{{SessionName}}"
      groups   = ["system:masters"]
    },
    {
      rolearn  = aws_iam_role.developer.arn
      username = "developer:{{SessionName}}"
      groups   = ["developers"]
    }
  ]
  
  tags = local.common_tags
}

# =============================================================================
# RDS (PostgreSQL for Metadata)
# =============================================================================
module "rds" {
  source = "./modules/rds"
  
  identifier = "${local.cluster_name}-metadata"
  
  engine               = "postgres"
  engine_version       = "15.4"
  instance_class       = var.rds_instance_class
  allocated_storage    = 100
  max_allocated_storage = 1000
  storage_type         = "gp3"
  storage_encrypted    = true
  kms_key_id           = aws_kms_key.rds.arn
  
  db_name  = "dragonscope_metadata"
  username = "dragonscope_admin"
  port     = 5432
  
  multi_az               = var.environment == "production" ? true : false
  db_subnet_group_name   = module.vpc.database_subnet_group_name
  vpc_security_group_ids = [aws_security_group.rds.id]
  
  backup_retention_period = 35
  backup_window          = "03:00-04:00"
  maintenance_window     = "Mon:04:00-Mon:05:00"
  
  enabled_cloudwatch_logs_exports = ["postgresql", "upgrade"]
  
  performance_insights_enabled          = true
  performance_insights_retention_period = 7
  
  create_monitoring_role                = true
  monitoring_interval                   = 60
  
  deletion_protection = var.environment == "production" ? true : false
  skip_final_snapshot = var.environment == "production" ? false : true
  
  tags = local.common_tags
}

# =============================================================================
# ELASTICACHE (Redis)
# =============================================================================
module "elasticache" {
  source = "./modules/cache"
  
  cluster_id               = "${local.cluster_name}-redis"
  engine                   = "redis"
  engine_version           = "7.1"
  node_type                = var.redis_node_type
  num_cache_clusters       = 3
  port                     = 6379
  parameter_group_name     = aws_elasticache_parameter_group.redis.name
  
  automatic_failover_enabled = true
  multi_az_enabled         = var.environment == "production" ? true : false
  
  at_rest_encryption_enabled = true
  transit_encryption_enabled = true
  
  security_group_ids = [aws_security_group.elasticache.id]
  subnet_group_name  = aws_elasticache_subnet_group.redis.name
  
  snapshot_retention_limit = 7
  snapshot_window          = "05:00-06:00"
  maintenance_window       = "tue:06:00-tue:07:00"
  
  apply_immediately = false
  
  tags = local.common_tags
}

resource "aws_elasticache_parameter_group" "redis" {
  family = "redis7"
  name   = "${local.cluster_name}-redis-params"
  
  parameter {
    name  = "maxmemory-policy"
    value = "allkeys-lru"
  }
  
  parameter {
    name  = "activedefrag"
    value = "yes"
  }
}

resource "aws_elasticache_subnet_group" "redis" {
  name       = "${local.cluster_name}-redis-subnet"
  subnet_ids = module.vpc.database_subnets
  
  tags = local.common_tags
}

# =============================================================================
# MSK (Kafka)
# =============================================================================
module "msk" {
  source = "./modules/msk"
  
  cluster_name           = "${local.cluster_name}-kafka"
  kafka_version          = "3.5.1"
  number_of_broker_nodes = 3
  
  broker_node_group_info {
    instance_type   = var.msk_instance_type
    client_subnets  = module.vpc.private_subnets
    security_groups = [aws_security_group.msk.id]
    
    storage_info {
      ebs_storage_info {
        volume_size = 1000
        provisioned_throughput {
          enabled           = true
          volume_throughput = 250
        }
      }
    }
  }
  
  encryption_info {
    encryption_at_rest_kms_key_arn = aws_kms_key.msk.arn
    encryption_in_transit {
      client_broker = "TLS"
      in_cluster    = true
    }
  }
  
  open_monitoring {
    prometheus {
      jmx_exporter {
        enabled_in_broker = true
      }
      node_exporter {
        enabled_in_broker = true
      }
    }
  }
  
  logging_info {
    broker_logs {
      cloudwatch_logs {
        enabled   = true
        log_group = aws_cloudwatch_log_group.msk.name
      }
      s3 {
        enabled = true
        bucket  = aws_s3_bucket.logs.id
        prefix  = "msk/"
      }
    }
  }
  
  configuration_info {
    arn      = aws_msk_configuration.kafka.arn
    revision = 1
  }
  
  tags = local.common_tags
}

resource "aws_msk_configuration" "kafka" {
  kafka_versions    = ["3.5.1"]
  name              = "${local.cluster_name}-config"
  server_properties = <<-PROPERTIES
    auto.create.topics.enable=false
    default.replication.factor=3
    min.insync.replicas=2
    num.io.threads=8
    num.network.threads=5
    num.partitions=12
    num.replica.fetchers=2
    replica.lag.time.max.ms=30000
    socket.receive.buffer.bytes=102400
    socket.request.max.bytes=104857600
    socket.send.buffer.bytes=102400
    unclean.leader.election.enable=false
    zookeeper.session.timeout.ms=18000
  PROPERTIES
}

# =============================================================================
# S3 BUCKETS
# =============================================================================
module "s3" {
  source = "./modules/s3"
  
  # Data lake buckets
  data_lake_bucket = {
    name          = "dragonscope-data-lake-${local.account_id}"
    versioning    = true
    force_destroy = var.environment != "production"
    
    lifecycle_rules = [
      {
        id      = "raw-data-transition"
        enabled = true
        
        transition = [
          {
            days          = 30
            storage_class = "STANDARD_IA"
          },
          {
            days          = 90
            storage_class = "GLACIER"
          }
        ]
        
        expiration = {
          days = 2555  # 7 years
        }
      }
    ]
    
    server_side_encryption_configuration = {
      rule = {
        apply_server_side_encryption_by_default = {
          kms_master_key_id = aws_kms_key.s3.arn
          sse_algorithm     = "aws:kms"
        }
        bucket_key_enabled = true
      }
    }
    
    tags = local.common_tags
  }
  
  # Backups bucket
  backups_bucket = {
    name          = "dragonscope-backups-${local.account_id}"
    versioning    = true
    force_destroy = false
    
    lifecycle_rules = [
      {
        id      = "backup-retention"
        enabled = true
        
        transition = [
          {
            days          = 30
            storage_class = "GLACIER"
          }
        ]
        
        noncurrent_version_expiration = {
          days = 90
        }
      }
    ]
    
    server_side_encryption_configuration = {
      rule = {
        apply_server_side_encryption_by_default = {
          kms_master_key_id = aws_kms_key.s3.arn
          sse_algorithm     = "aws:kms"
        }
      }
    }
    
    tags = local.common_tags
  }
  
  # Logs bucket
  logs_bucket = {
    name          = "dragonscope-logs-${local.account_id}"
    versioning    = false
    force_destroy = var.environment != "production"
    
    lifecycle_rules = [
      {
        id      = "logs-retention"
        enabled = true
        
        expiration = {
          days = 90
        }
      }
    ]
    
    tags = local.common_tags
  }
}

# =============================================================================
# CLOUDFRONT CDN
# =============================================================================
module "cdn" {
  source = "./modules/cdn"
  
  enabled             = true
  is_ipv6_enabled     = true
  comment             = "DragonScope Enterprise CDN"
  default_root_object = "index.html"
  price_class         = "PriceClass_All"
  
  aliases = [
    "app.dragonscope.io",
    "cdn.dragonscope.io",
    "static.dragonscope.io"
  ]
  
  origin {
    domain_name = aws_s3_bucket.data_lake.bucket_regional_domain_name
    origin_id   = "S3-${aws_s3_bucket.data_lake.id}"
    
    s3_origin_config {
      origin_access_identity = aws_cloudfront_origin_access_identity.oai.cloudfront_access_identity_path
    }
  }
  
  origin {
    domain_name = "api.dragonscope.io"
    origin_id   = "ALB-dragonscope-api"
    
    custom_origin_config {
      http_port              = 80
      https_port             = 443
      origin_protocol_policy = "https-only"
      origin_ssl_protocols   = ["TLSv1.2"]
    }
  }
  
  default_cache_behavior {
    allowed_methods  = ["GET", "HEAD", "OPTIONS"]
    cached_methods   = ["GET", "HEAD"]
    target_origin_id = "S3-${aws_s3_bucket.data_lake.id}"
    
    forwarded_values {
      query_string = false
      
      cookies {
        forward = "none"
      }
    }
    
    viewer_protocol_policy = "redirect-to-https"
    min_ttl                = 0
    default_ttl            = 3600
    max_ttl                = 86400
    compress               = true
  }
  
  ordered_cache_behavior {
    path_pattern     = "/api/*"
    allowed_methods  = ["DELETE", "GET", "HEAD", "OPTIONS", "PATCH", "POST", "PUT"]
    cached_methods   = ["GET", "HEAD"]
    target_origin_id = "ALB-dragonscope-api"
    
    forwarded_values {
      query_string = true
      headers      = ["Origin", "Access-Control-Request-Headers", "Access-Control-Request-Method"]
      
      cookies {
        forward = "whitelist"
        whitelisted_names = ["session", "auth"]
      }
    }
    
    viewer_protocol_policy = "https-only"
    min_ttl                = 0
    default_ttl            = 0
    max_ttl                = 0
  }
  
  restrictions {
    geo_restriction {
      restriction_type = "none"
    }
  }
  
  viewer_certificate {
    acm_certificate_arn      = aws_acm_certificate.cdn.arn
    ssl_support_method       = "sni-only"
    minimum_protocol_version = "TLSv1.2_2021"
  }
  
  logging_config {
    include_cookies = false
    bucket          = aws_s3_bucket.logs.bucket_domain_name
    prefix          = "cdn/"
  }
  
  web_acl_id = aws_wafv2_web_acl.cdn.arn
  
  tags = local.common_tags
}

resource "aws_cloudfront_origin_access_identity" "oai" {
  comment = "DragonScope OAI"
}

# =============================================================================
# ROUTE53 DNS
# =============================================================================
module "dns" {
  source = "./modules/dns"
  
  zone_name = "dragonscope.io"
  
  records = [
    {
      name = "app"
      type = "A"
      alias = {
        name                   = module.cdn.domain_name
        zone_id                = module.cdn.hosted_zone_id
        evaluate_target_health = false
      }
    },
    {
      name = "api"
      type = "A"
      alias = {
        name                   = aws_lb.dragonscope.dns_name
        zone_id                = aws_lb.dragonscope.zone_id
        evaluate_target_health = true
      }
    },
    {
      name = "grafana"
      type = "CNAME"
      ttl  = 300
      records = [aws_lb.monitoring.dns_name]
    },
    {
      name = ""
      type = "MX"
      ttl  = 3600
      records = [
        "10 mx1.improvmx.com",
        "20 mx2.improvmx.com"
      ]
    },
    {
      name = ""
      type = "TXT"
      ttl  = 3600
      records = [
        "v=spf1 include:_spf.google.com ~all"
      ]
    }
  ]
  
  tags = local.common_tags
}

# =============================================================================
# SECURITY GROUPS
# =============================================================================
resource "aws_security_group" "vpc_endpoints" {
  name_prefix = "${local.cluster_name}-vpc-endpoints"
  description = "Security group for VPC endpoints"
  vpc_id      = module.vpc.vpc_id
  
  ingress {
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = [module.vpc.vpc_cidr_block]
  }
  
  tags = merge(local.common_tags, {
    Name = "${local.cluster_name}-vpc-endpoints"
  })
}

resource "aws_security_group" "rds" {
  name_prefix = "${local.cluster_name}-rds"
  description = "Security group for RDS"
  vpc_id      = module.vpc.vpc_id
  
  ingress {
    from_port       = 5432
    to_port         = 5432
    protocol        = "tcp"
    security_groups = [module.eks.cluster_security_group_id]
  }
  
  tags = merge(local.common_tags, {
    Name = "${local.cluster_name}-rds"
  })
}

resource "aws_security_group" "elasticache" {
  name_prefix = "${local.cluster_name}-elasticache"
  description = "Security group for ElastiCache"
  vpc_id      = module.vpc.vpc_id
  
  ingress {
    from_port       = 6379
    to_port         = 6379
    protocol        = "tcp"
    security_groups = [module.eks.cluster_security_group_id]
  }
  
  tags = merge(local.common_tags, {
    Name = "${local.cluster_name}-elasticache"
  })
}

resource "aws_security_group" "msk" {
  name_prefix = "${local.cluster_name}-msk"
  description = "Security group for MSK"
  vpc_id      = module.vpc.vpc_id
  
  ingress {
    from_port       = 9092
    to_port         = 9094
    protocol        = "tcp"
    security_groups = [module.eks.cluster_security_group_id]
  }
  
  ingress {
    from_port       = 2181
    to_port         = 2181
    protocol        = "tcp"
    security_groups = [module.eks.cluster_security_group_id]
  }
  
  tags = merge(local.common_tags, {
    Name = "${local.cluster_name}-msk"
  })
}

# =============================================================================
# KMS KEYS
# =============================================================================
resource "aws_kms_key" "eks" {
  description             = "KMS key for EKS secrets encryption"
  deletion_window_in_days = 30
  enable_key_rotation     = true
  multi_region            = var.environment == "production" ? true : false
  
  tags = local.common_tags
}

resource "aws_kms_alias" "eks" {
  name          = "alias/${local.cluster_name}-eks"
  target_key_id = aws_kms_key.eks.key_id
}

resource "aws_kms_key" "ebs" {
  description             = "KMS key for EBS encryption"
  deletion_window_in_days = 30
  enable_key_rotation     = true
  
  tags = local.common_tags
}

resource "aws_kms_alias" "ebs" {
  name          = "alias/${local.cluster_name}-ebs"
  target_key_id = aws_kms_key.ebs.key_id
}

resource "aws_kms_key" "rds" {
  description             = "KMS key for RDS encryption"
  deletion_window_in_days = 30
  enable_key_rotation     = true
  
  tags = local.common_tags
}

resource "aws_kms_alias" "rds" {
  name          = "alias/${local.cluster_name}-rds"
  target_key_id = aws_kms_key.rds.key_id
}

resource "aws_kms_key" "msk" {
  description             = "KMS key for MSK encryption"
  deletion_window_in_days = 30
  enable_key_rotation     = true
  
  tags = local.common_tags
}

resource "aws_kms_alias" "msk" {
  name          = "alias/${local.cluster_name}-msk"
  target_key_id = aws_kms_key.msk.key_id
}

resource "aws_kms_key" "s3" {
  description             = "KMS key for S3 encryption"
  deletion_window_in_days = 30
  enable_key_rotation     = true
  multi_region            = var.environment == "production" ? true : false
  
  tags = local.common_tags
}

resource "aws_kms_alias" "s3" {
  name          = "alias/${local.cluster_name}-s3"
  target_key_id = aws_kms_key.s3.key_id
}

# =============================================================================
# IAM ROLES
# =============================================================================
resource "aws_iam_role" "cluster_admin" {
  name = "${local.cluster_name}-cluster-admin"
  
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          AWS = "arn:aws:iam::${local.account_id}:root"
        }
      }
    ]
  })
  
  tags = local.common_tags
}

resource "aws_iam_role" "developer" {
  name = "${local.cluster_name}-developer"
  
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          AWS = "arn:aws:iam::${local.account_id}:root"
        }
      }
    ]
  })
  
  tags = local.common_tags
}

# =============================================================================
# OUTPUTS
# =============================================================================
output "cluster_endpoint" {
  description = "EKS cluster endpoint"
  value       = module.eks.cluster_endpoint
}

output "cluster_certificate_authority_data" {
  description = "EKS cluster CA certificate"
  value       = module.eks.cluster_certificate_authority_data
}

output "cluster_name" {
  description = "EKS cluster name"
  value       = module.eks.cluster_name
}

output "rds_endpoint" {
  description = "RDS instance endpoint"
  value       = module.rds.endpoint
  sensitive   = true
}

output "redis_endpoint" {
  description = "ElastiCache Redis endpoint"
  value       = module.elasticache.endpoint
  sensitive   = true
}

output "msk_bootstrap_brokers" {
  description = "MSK bootstrap brokers"
  value       = module.msk.bootstrap_brokers_tls
  sensitive   = true
}

output "s3_data_lake_bucket" {
  description = "S3 data lake bucket name"
  value       = module.s3.data_lake_bucket_name
}

output "cloudfront_domain" {
  description = "CloudFront distribution domain"
  value       = module.cdn.domain_name
}
