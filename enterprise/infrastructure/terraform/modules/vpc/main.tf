# VPC Module - DragonScope Enterprise
# Creates a production-ready VPC with public, private, and database subnets

locals {
  name   = var.name
  region = data.aws_region.current.name
  azs    = slice(data.aws_availability_zones.available.names, 0, 3)
  
  tags = merge(
    var.tags,
    {
      Name = local.name
    }
  )
}

data "aws_region" "current" {}
data "aws_availability_zones" "available" {
  state = "available"
}

# =============================================================================
# VPC
# =============================================================================
resource "aws_vpc" "this" {
  cidr_block           = var.cidr
  instance_tenancy     = "default"
  enable_dns_hostnames = var.enable_dns_hostnames
  enable_dns_support   = var.enable_dns_support
  
  tags = merge(local.tags, {
    Name = local.name
  })
}

# =============================================================================
# INTERNET GATEWAY
# =============================================================================
resource "aws_internet_gateway" "this" {
  vpc_id = aws_vpc.this.id
  
  tags = merge(local.tags, {
    Name = "${local.name}-igw"
  })
}

# =============================================================================
# SUBNETS
# =============================================================================
# Public Subnets
resource "aws_subnet" "public" {
  count = length(var.public_subnets)
  
  vpc_id                  = aws_vpc.this.id
  cidr_block              = var.public_subnets[count.index]
  availability_zone       = local.azs[count.index]
  map_public_ip_on_launch = true
  
  tags = merge(
    local.tags,
    var.public_subnet_tags,
    {
      Name = "${local.name}-public-${local.azs[count.index]}"
      Type = "public"
    }
  )
}

# Private Subnets
resource "aws_subnet" "private" {
  count = length(var.private_subnets)
  
  vpc_id            = aws_vpc.this.id
  cidr_block        = var.private_subnets[count.index]
  availability_zone = local.azs[count.index]
  
  tags = merge(
    local.tags,
    var.private_subnet_tags,
    {
      Name = "${local.name}-private-${local.azs[count.index]}"
      Type = "private"
    }
  )
}

# Database Subnets
resource "aws_subnet" "database" {
  count = length(var.database_subnets)
  
  vpc_id            = aws_vpc.this.id
  cidr_block        = var.database_subnets[count.index]
  availability_zone = local.azs[count.index]
  
  tags = merge(local.tags, {
    Name = "${local.name}-database-${local.azs[count.index]}"
    Type = "database"
  })
}

# =============================================================================
# ROUTE TABLES
# =============================================================================
# Public Route Table
resource "aws_route_table" "public" {
  vpc_id = aws_vpc.this.id
  
  tags = merge(local.tags, {
    Name = "${local.name}-public"
  })
}

resource "aws_route" "public_internet_gateway" {
  route_table_id         = aws_route_table.public.id
  destination_cidr_block = "0.0.0.0/0"
  gateway_id             = aws_internet_gateway.this.id
  
  timeouts {
    create = "5m"
  }
}

resource "aws_route_table_association" "public" {
  count = length(var.public_subnets)
  
  subnet_id      = aws_subnet.public[count.index].id
  route_table_id = aws_route_table.public.id
}

# Private Route Tables (one per AZ for NAT Gateway)
resource "aws_route_table" "private" {
  count = var.single_nat_gateway ? 1 : length(var.private_subnets)
  
  vpc_id = aws_vpc.this.id
  
  tags = merge(local.tags, {
    Name = "${local.name}-private-${count.index}"
  })
}

resource "aws_route" "private_nat_gateway" {
  count = var.single_nat_gateway ? 1 : length(var.private_subnets)
  
  route_table_id         = aws_route_table.private[count.index].id
  destination_cidr_block = "0.0.0.0/0"
  nat_gateway_id         = aws_nat_gateway.this[count.index].id
  
  timeouts {
    create = "5m"
  }
}

resource "aws_route_table_association" "private" {
  count = length(var.private_subnets)
  
  subnet_id      = aws_subnet.private[count.index].id
  route_table_id = aws_route_table.private[var.single_nat_gateway ? 0 : count.index].id
}

# Database Route Table
resource "aws_route_table" "database" {
  count = length(var.database_subnets) > 0 ? 1 : 0
  
  vpc_id = aws_vpc.this.id
  
  tags = merge(local.tags, {
    Name = "${local.name}-database"
  })
}

resource "aws_route_table_association" "database" {
  count = length(var.database_subnets)
  
  subnet_id      = aws_subnet.database[count.index].id
  route_table_id = aws_route_table.database[0].id
}

# =============================================================================
# NAT GATEWAY
# =============================================================================
resource "aws_eip" "nat" {
  count = var.enable_nat_gateway ? (var.single_nat_gateway ? 1 : length(var.private_subnets)) : 0
  
  domain = "vpc"
  
  depends_on = [aws_internet_gateway.this]
  
  tags = merge(local.tags, {
    Name = "${local.name}-nat-${count.index}"
  })
}

resource "aws_nat_gateway" "this" {
  count = var.enable_nat_gateway ? (var.single_nat_gateway ? 1 : length(var.private_subnets)) : 0
  
  allocation_id = aws_eip.nat[count.index].id
  subnet_id     = aws_subnet.public[count.index].id
  
  depends_on = [aws_internet_gateway.this]
  
  tags = merge(local.tags, {
    Name = "${local.name}-${count.index}"
  })
}

# =============================================================================
# VPC ENDPOINTS
# =============================================================================
resource "aws_vpc_endpoint" "s3" {
  vpc_id            = aws_vpc.this.id
  service_name      = "com.amazonaws.${local.region}.s3"
  vpc_endpoint_type = "Gateway"
  route_table_ids   = concat([aws_route_table.public.id], aws_route_table.private[*].id)
  
  tags = merge(local.tags, {
    Name = "${local.name}-s3"
  })
}

resource "aws_vpc_endpoint" "ec2" {
  count = var.enable_ec2_endpoint ? 1 : 0
  
  vpc_id              = aws_vpc.this.id
  service_name        = "com.amazonaws.${local.region}.ec2"
  vpc_endpoint_type   = "Interface"
  subnet_ids          = aws_subnet.private[*].id
  security_group_ids  = var.ec2_endpoint_security_group_ids
  private_dns_enabled = var.ec2_endpoint_private_dns_enabled
  
  tags = merge(local.tags, {
    Name = "${local.name}-ec2"
  })
}

# =============================================================================
# VPC FLOW LOGS
# =============================================================================
resource "aws_flow_log" "this" {
  count = var.enable_flow_log ? 1 : 0
  
  vpc_id                   = aws_vpc.this.id
  log_destination_type     = "cloud-watch-logs"
  log_destination          = aws_cloudwatch_log_group.flow_log[0].arn
  traffic_type             = "ALL"
  max_aggregation_interval = var.flow_log_max_aggregation_interval
  iam_role_arn             = aws_iam_role.flow_log[0].arn
  
  tags = merge(local.tags, {
    Name = "${local.name}-flow-log"
  })
}

resource "aws_cloudwatch_log_group" "flow_log" {
  count = var.enable_flow_log && var.create_flow_log_cloudwatch_log_group ? 1 : 0
  
  name              = "/aws/vpc/${local.name}-flow-log"
  retention_in_days = 30
  
  tags = local.tags
}

resource "aws_iam_role" "flow_log" {
  count = var.enable_flow_log && var.create_flow_log_cloudwatch_iam_role ? 1 : 0
  
  name = "${local.name}-flow-log-role"
  
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "vpc-flow-logs.amazonaws.com"
        }
      }
    ]
  })
  
  tags = local.tags
}

resource "aws_iam_role_policy" "flow_log" {
  count = var.enable_flow_log && var.create_flow_log_cloudwatch_iam_role ? 1 : 0
  
  name = "${local.name}-flow-log-policy"
  role = aws_iam_role.flow_log[0].id
  
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents",
          "logs:DescribeLogGroups",
          "logs:DescribeLogStreams"
        ]
        Resource = "*"
      }
    ]
  })
}

# =============================================================================
# VPN GATEWAY (Optional)
# =============================================================================
resource "aws_vpn_gateway" "this" {
  count = var.enable_vpn_gateway ? 1 : 0
  
  vpc_id = aws_vpc.this.id
  
  tags = merge(local.tags, {
    Name = "${local.name}-vpn-gw"
  })
}

resource "aws_vpn_gateway_attachment" "this" {
  count = var.enable_vpn_gateway ? 1 : 0
  
  vpc_id         = aws_vpc.this.id
  vpn_gateway_id = aws_vpn_gateway.this[0].id
}
