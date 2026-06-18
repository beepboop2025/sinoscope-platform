# EKS Module - DragonScope Enterprise
# Creates a production-ready EKS cluster

locals {
  cluster_name = var.cluster_name
  tags         = var.tags
}

# =============================================================================
# EKS CLUSTER
# =============================================================================
resource "aws_eks_cluster" "this" {
  name     = local.cluster_name
  version  = var.cluster_version
  role_arn = aws_iam_role.cluster.arn
  
  vpc_config {
    subnet_ids              = var.subnet_ids
    endpoint_private_access = var.cluster_endpoint_private_access
    endpoint_public_access  = var.cluster_endpoint_public_access
    public_access_cidrs     = var.cluster_endpoint_public_access_cidrs
    security_group_ids      = [aws_security_group.cluster.id]
  }
  
  encryption_config {
    provider {
      key_arn = var.cluster_encryption_config.provider_key_arn
    }
    resources = var.cluster_encryption_config.resources
  }
  
  enabled_cluster_log_types = var.cluster_enabled_log_types
  
  depends_on = [
    aws_iam_role_policy_attachment.cluster_policies,
    aws_cloudwatch_log_group.cluster
  ]
  
  tags = local.tags
}

# =============================================================================
# CLOUDWATCH LOG GROUP
# =============================================================================
resource "aws_cloudwatch_log_group" "cluster" {
  name              = "/aws/eks/${local.cluster_name}/cluster"
  retention_in_days = 30
  
  tags = local.tags
}

# =============================================================================
# IAM ROLES
# =============================================================================
resource "aws_iam_role" "cluster" {
  name = "${local.cluster_name}-cluster-role"
  
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "eks.amazonaws.com"
        }
      }
    ]
  })
  
  tags = local.tags
}

resource "aws_iam_role_policy_attachment" "cluster_policies" {
  for_each = toset([
    "arn:aws:iam::aws:policy/AmazonEKSClusterPolicy",
    "arn:aws:iam::aws:policy/AmazonEKSVPCResourceController"
  ])
  
  policy_arn = each.value
  role       = aws_iam_role.cluster.name
}

resource "aws_iam_role" "node" {
  name = "${local.cluster_name}-node-role"
  
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "ec2.amazonaws.com"
        }
      }
    ]
  })
  
  tags = local.tags
}

resource "aws_iam_role_policy_attachment" "node_policies" {
  for_each = toset([
    "arn:aws:iam::aws:policy/AmazonEKSWorkerNodePolicy",
    "arn:aws:iam::aws:policy/AmazonEKS_CNI_Policy",
    "arn:aws:iam::aws:policy/AmazonEC2ContainerRegistryReadOnly",
    "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
  ])
  
  policy_arn = each.value
  role       = aws_iam_role.node.name
}

# =============================================================================
# SECURITY GROUPS
# =============================================================================
resource "aws_security_group" "cluster" {
  name_prefix = "${local.cluster_name}-cluster"
  description = "EKS cluster security group"
  vpc_id      = var.vpc_id
  
  tags = merge(local.tags, {
    Name = "${local.cluster_name}-cluster"
  })
}

resource "aws_security_group_rule" "cluster_ingress_nodes" {
  description              = "Allow nodes to communicate with the cluster API Server"
  from_port                = 443
  protocol                 = "tcp"
  security_group_id        = aws_security_group.cluster.id
  source_security_group_id = aws_security_group.node.id
  to_port                  = 443
  type                     = "ingress"
}

resource "aws_security_group_rule" "cluster_egress" {
  description       = "Allow cluster egress"
  from_port         = 0
  to_port           = 0
  protocol          = "-1"
  cidr_blocks       = ["0.0.0.0/0"]
  security_group_id = aws_security_group.cluster.id
  type              = "egress"
}

resource "aws_security_group" "node" {
  name_prefix = "${local.cluster_name}-node"
  description = "EKS node security group"
  vpc_id      = var.vpc_id
  
  tags = merge(local.tags, {
    Name                                        = "${local.cluster_name}-node"
    "kubernetes.io/cluster/${local.cluster_name}" = "owned"
  })
}

resource "aws_security_group_rule" "node_ingress_self" {
  description              = "Allow nodes to communicate with each other"
  from_port                = 0
  protocol                 = "-1"
  security_group_id        = aws_security_group.node.id
  source_security_group_id = aws_security_group.node.id
  to_port                  = 65535
  type                     = "ingress"
}

resource "aws_security_group_rule" "node_ingress_cluster" {
  description              = "Allow worker Kubelets and pods to receive communication from the cluster control plane"
  from_port                = 1025
  protocol                 = "tcp"
  security_group_id        = aws_security_group.node.id
  source_security_group_id = aws_security_group.cluster.id
  to_port                  = 65535
  type                     = "ingress"
}

resource "aws_security_group_rule" "node_egress" {
  description       = "Allow node egress"
  from_port         = 0
  to_port           = 0
  protocol          = "-1"
  cidr_blocks       = ["0.0.0.0/0"]
  security_group_id = aws_security_group.node.id
  type              = "egress"
}

# =============================================================================
# MANAGED NODE GROUPS
# =============================================================================
resource "aws_eks_node_group" "this" {
  for_each = var.eks_managed_node_groups
  
  cluster_name    = aws_eks_cluster.this.name
  node_group_name = each.key
  node_role_arn   = aws_iam_role.node.arn
  subnet_ids      = var.subnet_ids
  
  capacity_type   = lookup(each.value, "capacity_type", "ON_DEMAND")
  instance_types  = each.value.instance_types
  
  scaling_config {
    desired_size = each.value.desired_size
    max_size     = each.value.max_size
    min_size     = each.value.min_size
  }
  
  update_config {
    max_unavailable_percentage = lookup(each.value, "update_config", {}).max_unavailable_percentage
  }
  
  labels = lookup(each.value, "k8s_labels", {})
  
  dynamic "taint" {
    for_each = lookup(each.value, "taints", [])
    content {
      key    = taint.value.key
      value  = taint.value.value
      effect = taint.value.effect
    }
  }
  
  launch_template {
    id      = aws_launch_template.node[each.key].id
    version = aws_launch_template.node[each.key].latest_version
  }
  
  depends_on = [
    aws_iam_role_policy_attachment.node_policies
  ]
  
  tags = merge(local.tags, {
    Name = "${local.cluster_name}-${each.key}"
  })
  
  lifecycle {
    ignore_changes = [scaling_config[0].desired_size]
  }
}

# =============================================================================
# LAUNCH TEMPLATES
# =============================================================================
resource "aws_launch_template" "node" {
  for_each = var.eks_managed_node_groups
  
  name_prefix   = "${local.cluster_name}-${each.key}-"
  image_id      = data.aws_ami.eks_default.image_id
  instance_type = each.value.instance_types[0]
  
  block_device_mappings {
    device_name = "/dev/xvda"
    
    ebs {
      volume_size           = 100
      volume_type           = "gp3"
      iops                  = 3000
      throughput            = 125
      encrypted             = true
      kms_key_id            = var.kms_key_id
      delete_on_termination = true
    }
  }
  
  metadata_options {
    http_endpoint               = "enabled"
    http_tokens                 = "required"
    http_put_response_hop_limit = 1
  }
  
  monitoring {
    enabled = true
  }
  
  tag_specifications {
    resource_type = "instance"
    
    tags = merge(local.tags, {
      Name = "${local.cluster_name}-${each.key}"
      "kubernetes.io/cluster/${local.cluster_name}" = "owned"
    })
  }
  
  user_data = base64encode(templatefile("${path.module}/templates/userdata.sh", {
    cluster_name     = local.cluster_name
    cluster_endpoint = aws_eks_cluster.this.endpoint
    cluster_ca_cert  = aws_eks_cluster.this.certificate_authority[0].data
  }))
  
  tags = local.tags
}

data "aws_ami" "eks_default" {
  most_recent = true
  owners      = ["amazon"]
  
  filter {
    name   = "name"
    values = ["amazon-eks-node-${var.cluster_version}-v*"]
  }
}

# =============================================================================
# FARGATE PROFILES
# =============================================================================
resource "aws_eks_fargate_profile" "this" {
  for_each = var.fargate_profiles
  
  cluster_name           = aws_eks_cluster.this.name
  fargate_profile_name   = each.value.name
  pod_execution_role_arn = aws_iam_role.fargate.arn
  subnet_ids             = lookup(each.value, "subnets", var.subnet_ids)
  
  dynamic "selector" {
    for_each = each.value.selectors
    content {
      namespace = selector.value.namespace
      labels    = lookup(selector.value, "labels", {})
    }
  }
  
  depends_on = [
    aws_iam_role_policy_attachment.fargate_policies
  ]
  
  tags = local.tags
}

resource "aws_iam_role" "fargate" {
  name = "${local.cluster_name}-fargate-role"
  
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "eks-fargate-pods.amazonaws.com"
        }
      }
    ]
  })
  
  tags = local.tags
}

resource "aws_iam_role_policy_attachment" "fargate_policies" {
  policy_arn = "arn:aws:iam::aws:policy/AmazonEKSFargatePodExecutionRolePolicy"
  role       = aws_iam_role.fargate.name
}

# =============================================================================
# AWS AUTH CONFIGMAP
# =============================================================================
resource "kubernetes_config_map_v1_data" "aws_auth" {
  count = var.manage_aws_auth_configmap ? 1 : 0
  
  metadata {
    name      = "aws-auth"
    namespace = "kube-system"
  }
  
  data = {
    mapRoles = yamlencode(concat(
      [for ng in aws_eks_node_group.this : {
        rolearn  = aws_iam_role.node.arn
        username = "system:node:{{EC2PrivateDNSName}}"
        groups   = ["system:bootstrappers", "system:nodes"]
      }],
      var.aws_auth_roles
    ))
    mapUsers = yamlencode(var.aws_auth_users)
  }
  
  force = true
}
