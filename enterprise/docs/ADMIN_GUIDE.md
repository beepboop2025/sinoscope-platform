# DragonScope Enterprise - Administration Guide

Complete guide for system administrators deploying and managing DragonScope Enterprise.

---

## Table of Contents

1. [Installation and Setup](#installation-and-setup)
2. [Configuration Reference](#configuration-reference)
3. [Scaling Guide](#scaling-guide)
4. [Monitoring Setup](#monitoring-setup)
5. [Backup and Disaster Recovery](#backup-and-disaster-recovery)
6. [Troubleshooting](#troubleshooting)
7. [Security](#security)

---

## Installation and Setup

### System Requirements

#### Minimum Requirements (Development/Small Team)

| Component | Specification |
|-----------|---------------|
| CPU | 8 cores (Intel Xeon or AMD EPYC) |
| RAM | 32 GB |
| Storage | 500 GB SSD (NVMe preferred) |
| Network | 1 Gbps |
| OS | Ubuntu 22.04 LTS / RHEL 8 / Windows Server 2022 |

#### Recommended Requirements (Production)

| Component | Specification |
|-----------|---------------|
| CPU | 32+ cores |
| RAM | 128 GB |
| Storage | 2 TB NVMe SSD |
| Network | 10 Gbps |
| OS | Ubuntu 22.04 LTS / RHEL 9 |

#### Database Requirements

| Database | Version | Purpose |
|----------|---------|---------|
| PostgreSQL | 15+ | Primary data store |
| Redis | 7+ | Caching & sessions |
| ClickHouse | 23+ | Time-series data |
| Kafka | 3.5+ | Event streaming |

### Installation Methods

#### Method 1: Docker Compose (Recommended for Small Deployments)

```yaml
# docker-compose.yml
version: '3.8'

services:
  dragonscope:
    image: dragonscope/enterprise:3.2.1
    ports:
      - "8080:8080"
      - "8443:8443"
    environment:
      - DS_DATABASE_URL=postgresql://ds_user:${DB_PASSWORD}@postgres:5432/dragonscope
      - DS_REDIS_URL=redis://redis:6379
      - DS_LICENSE_KEY=${LICENSE_KEY}
      - DS_ADMIN_EMAIL=${ADMIN_EMAIL}
    volumes:
      - ds_data:/data
      - ds_config:/config
      - ds_logs:/logs
    depends_on:
      - postgres
      - redis
      - clickhouse
    networks:
      - dragonscope

  postgres:
    image: postgres:15-alpine
    environment:
      - POSTGRES_USER=ds_user
      - POSTGRES_PASSWORD=${DB_PASSWORD}
      - POSTGRES_DB=dragonscope
    volumes:
      - postgres_data:/var/lib/postgresql/data
    networks:
      - dragonscope

  redis:
    image: redis:7-alpine
    volumes:
      - redis_data:/data
    networks:
      - dragonscope

  clickhouse:
    image: clickhouse/clickhouse-server:23
    volumes:
      - clickhouse_data:/var/lib/clickhouse
    networks:
      - dragonscope

  kafka:
    image: confluentinc/cp-kafka:7.5.0
    environment:
      KAFKA_ZOOKEEPER_CONNECT: zookeeper:2181
      KAFKA_ADVERTISED_LISTENERS: PLAINTEXT://kafka:9092
    depends_on:
      - zookeeper
    networks:
      - dragonscope

  zookeeper:
    image: confluentinc/cp-zookeeper:7.5.0
    environment:
      ZOOKEEPER_CLIENT_PORT: 2181
    networks:
      - dragonscope

volumes:
  ds_data:
  ds_config:
  ds_logs:
  postgres_data:
  redis_data:
  clickhouse_data:

networks:
  dragonscope:
    driver: bridge
```

**Installation Steps:**

```bash
# 1. Create installation directory
mkdir -p /opt/dragonscope && cd /opt/dragonscope

# 2. Download compose file
curl -o docker-compose.yml https://install.dragonscope.io/enterprise/docker-compose.yml

# 3. Create environment file
cat > .env << EOF
LICENSE_KEY=your-license-key
DB_PASSWORD=$(openssl rand -base64 32)
ADMIN_EMAIL=admin@yourcompany.com
EOF

# 4. Start services
docker-compose up -d

# 5. Verify installation
docker-compose ps
docker-compose logs -f dragonscope

# 6. Access the application
# Web UI: https://localhost:8443
# API: https://localhost:8443/api/v3
```

#### Method 2: Kubernetes (Recommended for Enterprise)

```yaml
# dragonscope-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: dragonscope-enterprise
  namespace: dragonscope
spec:
  replicas: 3
  selector:
    matchLabels:
      app: dragonscope
  template:
    metadata:
      labels:
        app: dragonscope
    spec:
      containers:
      - name: dragonscope
        image: dragonscope/enterprise:3.2.1
        ports:
        - containerPort: 8080
          name: http
        - containerPort: 8443
          name: https
        - containerPort: 9090
          name: metrics
        env:
        - name: DS_DATABASE_URL
          valueFrom:
            secretKeyRef:
              name: dragonscope-secrets
              key: database-url
        - name: DS_LICENSE_KEY
          valueFrom:
            secretKeyRef:
              name: dragonscope-secrets
              key: license-key
        resources:
          requests:
            memory: "8Gi"
            cpu: "4"
          limits:
            memory: "32Gi"
            cpu: "16"
        volumeMounts:
        - name: config
          mountPath: /config
        - name: data
          mountPath: /data
        livenessProbe:
          httpGet:
            path: /health
            port: 8080
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /ready
            port: 8080
          initialDelaySeconds: 5
          periodSeconds: 5
      volumes:
      - name: config
        configMap:
          name: dragonscope-config
      - name: data
        persistentVolumeClaim:
          claimName: dragonscope-data
---
apiVersion: v1
kind: Service
metadata:
  name: dragonscope-service
  namespace: dragonscope
spec:
  selector:
    app: dragonscope
  ports:
  - name: http
    port: 80
    targetPort: 8080
  - name: https
    port: 443
    targetPort: 8443
  type: LoadBalancer
---
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: dragonscope-ingress
  namespace: dragonscope
  annotations:
    cert-manager.io/cluster-issuer: "letsencrypt-prod"
    nginx.ingress.kubernetes.io/ssl-redirect: "true"
spec:
  tls:
  - hosts:
    - dragonscope.yourcompany.com
    secretName: dragonscope-tls
  rules:
  - host: dragonscope.yourcompany.com
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: dragonscope-service
            port:
              number: 443
```

**Installation Steps:**

```bash
# 1. Create namespace
kubectl create namespace dragonscope

# 2. Create secrets
kubectl create secret generic dragonscope-secrets \
  --from-literal=database-url='postgresql://...' \
  --from-literal=license-key='your-license-key' \
  -n dragonscope

# 3. Deploy
kubectl apply -f dragonscope-deployment.yaml

# 4. Verify
kubectl get pods -n dragonscope
kubectl logs -f deployment/dragonscope-enterprise -n dragonscope
```

#### Method 3: Bare Metal / VM Installation

```bash
# 1. Install dependencies
# Ubuntu/Debian
sudo apt-get update
sudo apt-get install -y postgresql-15 redis-server nodejs npm

# RHEL/CentOS
sudo yum install -y postgresql15 redis nodejs npm

# 2. Download DragonScope
curl -fsSL https://install.dragonscope.io/enterprise.sh | sudo bash

# 3. Run configuration wizard
sudo dragonscope-config wizard

# 4. Start services
sudo systemctl enable dragonscope
sudo systemctl start dragonscope

# 5. Verify
sudo systemctl status dragonscope
sudo dragonscope health-check
```

### Post-Installation Configuration

#### Initial Setup Wizard

After installation, access the setup wizard:

```
https://your-server:8443/setup
```

**Setup Steps:**

1. **Administrator Account**
   ```
   Email: admin@company.com
   Password: [secure password]
   MFA: Enable (recommended)
   ```

2. **Organization Settings**
   ```
   Organization Name: Acme Trading
   Timezone: America/New_York
   Default Currency: USD
   ```

3. **Data Sources**
   ```
   Market Data: [Select provider]
   News Feed: [Select provider]
   Broker Connections: [Configure]
   ```

4. **License Activation**
   ```
   License Key: XXXX-XXXX-XXXX-XXXX
   Validate and activate
   ```

---

## Configuration Reference

### Configuration Files

#### Main Configuration (`/config/dragonscope.yaml`)

```yaml
# DragonScope Enterprise Configuration
version: "3.2"

# Server Configuration
server:
  host: "0.0.0.0"
  port: 8080
  tls:
    enabled: true
    port: 8443
    cert_file: "/config/certs/server.crt"
    key_file: "/config/certs/server.key"
    hsts: true
  cors:
    enabled: true
    allowed_origins:
      - "https://dragonscope.yourcompany.com"
      - "https://app.dragonscope.io"
    allowed_methods: ["GET", "POST", "PUT", "DELETE", "PATCH"]
    allowed_headers: ["*"]
    max_age: 86400
  compression:
    enabled: true
    level: 6
  timeout:
    read: 30s
    write: 30s
    idle: 120s

# Database Configuration
database:
  primary:
    type: "postgresql"
    host: "postgres"
    port: 5432
    name: "dragonscope"
    user: "ds_user"
    password: "${DB_PASSWORD}"
    pool:
      min: 10
      max: 100
      max_lifetime: 1h
  timeseries:
    type: "clickhouse"
    host: "clickhouse"
    port: 8123
    name: "dragonscope_ts"
    user: "default"
    password: ""
  cache:
    type: "redis"
    host: "redis"
    port: 6379
    db: 0
    password: ""
    pool_size: 50

# Message Queue
messaging:
  type: "kafka"
  brokers:
    - "kafka:9092"
  topics:
    market_data: "ds.marketdata"
    orders: "ds.orders"
    notifications: "ds.notifications"
  consumer_group: "dragonscope-main"

# Authentication & Security
auth:
  type: "jwt"
  jwt:
    secret: "${JWT_SECRET}"
    expiry: 24h
    refresh_expiry: 7d
    issuer: "dragonscope.io"
    audience: "api.dragonscope.io"
  oauth:
    enabled: true
    providers:
      - name: "google"
        client_id: "${GOOGLE_CLIENT_ID}"
        client_secret: "${GOOGLE_CLIENT_SECRET}"
      - name: "azure_ad"
        client_id: "${AZURE_CLIENT_ID}"
        client_secret: "${AZURE_CLIENT_SECRET}"
        tenant: "${AZURE_TENANT}"
  sso:
    enabled: true
    saml:
      idp_metadata_url: "https://sso.company.com/metadata"
      sp_entity_id: "dragonscope-enterprise"
      callback_url: "https://dragonscope.company.com/auth/saml/callback"
  mfa:
    enabled: true
    methods: ["totp", "sms", "email"]
    required_for_roles: ["admin", "trader"]
  password_policy:
    min_length: 12
    require_uppercase: true
    require_lowercase: true
    require_numbers: true
    require_special: true
    max_age: 90d
    prevent_reuse: 10

# Session Management
session:
  type: "redis"
  ttl: 24h
  secure: true
  http_only: true
  same_site: "strict"

# API Configuration
api:
  rate_limiting:
    enabled: true
    default_tier:
      requests_per_minute: 1000
      burst: 100
    tiers:
      free:
        requests_per_minute: 60
        burst: 10
      basic:
        requests_per_minute: 300
        burst: 50
      pro:
        requests_per_minute: 1000
        burst: 200
      enterprise:
        requests_per_minute: 10000
        burst: 1000
  versioning:
    default: "v3"
    supported: ["v3", "v2"]
    deprecated: ["v1"]
  
# WebSocket Configuration
websocket:
  enabled: true
  port: 8081
  path: "/ws"
  max_connections: 10000
  per_client_limit: 100
  heartbeat_interval: 30s
  message_size_limit: 65536

# Market Data Configuration
market_data:
  providers:
    primary:
      name: "bloomberg"
      enabled: true
      api_key: "${BLOOMBERG_API_KEY}"
      rate_limit: 10000
    fallback:
      name: "iex"
      enabled: true
      api_key: "${IEX_API_KEY}"
  realtime:
    enabled: true
    protocols: ["websocket", "sse"]
  historical:
    retention_days: 2555  # 7 years
  symbols:
    refresh_interval: 24h
    sources: ["exchange", "refinitiv", "bloomberg"]

# Order Management
orders:
  risk_checks:
    enabled: true
    pre_trade:
      - position_limits
      - buying_power
      - concentration_limits
    post_trade:
      - compliance_reporting
  routing:
    default_broker: "interactive_brokers"
    smart_order_routing: true
    backup_brokers: ["alpaca", "tradestation"]
  
# Logging
logging:
  level: "info"  # debug, info, warn, error
  format: "json"  # json, text
  output: "stdout"  # stdout, file, both
  file:
    path: "/logs/dragonscope.log"
    max_size: 100  # MB
    max_age: 30    # days
    max_backups: 10
    compress: true
  audit:
    enabled: true
    path: "/logs/audit.log"
    events:
      - login
      - logout
      - order_created
      - order_modified
      - order_cancelled
      - settings_changed
      - user_created
      - user_deleted

# Monitoring
monitoring:
  metrics:
    enabled: true
    port: 9090
    path: "/metrics"
    format: "prometheus"
  tracing:
    enabled: true
    type: "jaeger"
    endpoint: "http://jaeger:14268/api/traces"
    sampling_rate: 0.1
  health_check:
    enabled: true
    path: "/health"
    interval: 30s
  alerts:
    enabled: true
    channels:
      - type: "email"
        recipients: ["ops@company.com"]
      - type: "slack"
        webhook: "${SLACK_WEBHOOK_URL}"
        channel: "#alerts"
      - type: "pagerduty"
        integration_key: "${PAGERDUTY_KEY}"

# Notifications
notifications:
  email:
    enabled: true
    smtp:
      host: "smtp.company.com"
      port: 587
      username: "${SMTP_USER}"
      password: "${SMTP_PASS}"
      from: "dragonscope@company.com"
      tls: true
  sms:
    enabled: true
    provider: "twilio"
    account_sid: "${TWILIO_SID}"
    auth_token: "${TWILIO_TOKEN}"
    from_number: "+1234567890"
  push:
    enabled: true
    firebase:
      project_id: "dragonscope-push"
      credentials: "/config/firebase-credentials.json"
  webhooks:
    enabled: true
    timeout: 30s
    retry:
      max_attempts: 3
      backoff: exponential

# Backup
backup:
  enabled: true
  schedule: "0 2 * * *"  # Daily at 2 AM
  retention:
    daily: 7
    weekly: 4
    monthly: 12
  destinations:
    - type: "s3"
      bucket: "dragonscope-backups"
      region: "us-east-1"
      access_key: "${AWS_ACCESS_KEY}"
      secret_key: "${AWS_SECRET_KEY}"
    - type: "gcs"
      bucket: "dragonscope-backups"
      credentials: "/config/gcs-credentials.json"

# Feature Flags
features:
  options_trading: true
  crypto_trading: true
  forex_trading: true
  algorithmic_trading: true
  paper_trading: true
  social_features: false
  beta_features: false
```

### Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `DS_LICENSE_KEY` | Yes | Enterprise license key |
| `DS_DATABASE_URL` | Yes | PostgreSQL connection string |
| `DS_REDIS_URL` | No | Redis connection string |
| `DS_JWT_SECRET` | Yes | Secret for JWT signing |
| `DS_ADMIN_EMAIL` | Yes | Initial admin email |
| `DS_LOG_LEVEL` | No | Logging level (default: info) |
| `DS_NODE_ENV` | No | Environment (production/development) |

---

## Scaling Guide

### Horizontal Scaling Architecture

```
                              ┌─────────────┐
                              │   CDN/WAF   │
                              │  (CloudFlare)│
                              └──────┬──────┘
                                     │
                              ┌──────▼──────┐
                              │ Load Balancer│
                              │   (NGINX)   │
                              └──────┬──────┘
                                     │
         ┌───────────────────────────┼───────────────────────────┐
         │                           │                           │
    ┌────┴────┐               ┌──────┴──────┐              ┌──────┴──────┐
    │DragonScope│              │DragonScope  │              │DragonScope  │
    │  Node 1  │               │   Node 2    │              │   Node N    │
    └────┬────┘               └──────┬──────┘              └──────┬──────┘
         │                           │                           │
         └───────────────────────────┼───────────────────────────┘
                                     │
    ┌────────────────────────────────┼────────────────────────────────┐
    │                                │                                │
┌───┴────┐  ┌──────────┐  ┌─────────┴────────┐  ┌──────────┐  ┌──────┴────┐
│PostgreSQL│  │  Redis   │  │   ClickHouse    │  │  Kafka   │  │   MinIO   │
│ Cluster  │  │ Cluster  │  │    Cluster      │  │ Cluster  │  │  (S3 API) │
└──────────┘  └──────────┘  └─────────────────┘  └──────────┘  └───────────┘
```

### Scaling Strategies

#### 1. Application Tier Scaling

```yaml
# Horizontal Pod Autoscaler
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: dragonscope-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: dragonscope-enterprise
  minReplicas: 3
  maxReplicas: 50
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
  - type: Resource
    resource:
      name: memory
      target:
        type: Utilization
        averageUtilization: 80
  - type: Pods
    pods:
      metric:
        name: websocket_connections
      target:
        type: AverageValue
        averageValue: "500"
  behavior:
    scaleUp:
      stabilizationWindowSeconds: 60
      policies:
      - type: Percent
        value: 100
        periodSeconds: 60
    scaleDown:
      stabilizationWindowSeconds: 300
      policies:
      - type: Percent
        value: 10
        periodSeconds: 60
```

#### 2. Database Scaling

**PostgreSQL Read Replicas:**
```yaml
database:
  primary:
    host: "postgres-primary"
  replicas:
    - host: "postgres-replica-1"
      weight: 100
    - host: "postgres-replica-2"
      weight: 100
  routing:
    writes: primary
    reads: round_robin
```

**ClickHouse Sharding:**
```sql
-- Create distributed table
CREATE TABLE market_data_distributed AS market_data
ENGINE = Distributed('cluster_1', 'dragonscope', 'market_data', rand());
```

#### 3. Cache Scaling

**Redis Cluster:**
```yaml
cache:
  type: "redis_cluster"
  nodes:
    - "redis-node-1:6379"
    - "redis-node-2:6379"
    - "redis-node-3:6379"
  password: "${REDIS_PASSWORD}"
  max_redirects: 16
```

### Performance Benchmarks

| Metric | Single Node | 3-Node Cluster | 10-Node Cluster |
|--------|-------------|----------------|-----------------|
| Concurrent Users | 500 | 2,000 | 10,000 |
| WebSocket Connections | 1,000 | 5,000 | 25,000 |
| API Requests/sec | 5,000 | 20,000 | 100,000 |
| Market Data Updates/sec | 50,000 | 200,000 | 1,000,000 |
| Order Processing/sec | 1,000 | 5,000 | 25,000 |

---

## Monitoring Setup

### Prometheus Metrics

DragonScope exposes metrics at `/metrics`:

```yaml
# prometheus.yml
scrape_configs:
  - job_name: 'dragonscope'
    static_configs:
      - targets: ['dragonscope:9090']
    metrics_path: /metrics
    scrape_interval: 15s
    
  - job_name: 'dragonscope-websocket'
    static_configs:
      - targets: ['dragonscope:9091']
    metrics_path: /metrics
```

### Key Metrics

| Metric | Type | Description |
|--------|------|-------------|
| `ds_api_requests_total` | Counter | Total API requests |
| `ds_api_request_duration_seconds` | Histogram | API response times |
| `ds_websocket_connections` | Gauge | Active WebSocket connections |
| `ds_websocket_messages_sent` | Counter | Messages sent |
| `ds_websocket_messages_received` | Counter | Messages received |
| `ds_orders_created_total` | Counter | Orders created |
| `ds_orders_filled_total` | Counter | Orders filled |
| `ds_database_query_duration_seconds` | Histogram | DB query times |
| `ds_cache_hit_ratio` | Gauge | Cache hit ratio |
| `ds_market_data_latency_ms` | Gauge | Market data latency |

### Grafana Dashboards

**System Overview Dashboard:**

```json
{
  "dashboard": {
    "title": "DragonScope Enterprise - Overview",
    "panels": [
      {
        "title": "API Requests/sec",
        "targets": [
          {
            "expr": "rate(ds_api_requests_total[1m])"
          }
        ]
      },
      {
        "title": "Active WebSocket Connections",
        "targets": [
          {
            "expr": "ds_websocket_connections"
          }
        ]
      },
      {
        "title": "Order Processing Rate",
        "targets": [
          {
            "expr": "rate(ds_orders_created_total[1m])"
          }
        ]
      },
      {
        "title": "Market Data Latency",
        "targets": [
          {
            "expr": "ds_market_data_latency_ms"
          }
        ]
      }
    ]
  }
}
```

### Alerting Rules

```yaml
# alertmanager.yml
groups:
  - name: dragonscope
    rules:
      - alert: HighErrorRate
        expr: rate(ds_api_requests_total{status=~"5.."}[5m]) > 0.05
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "High error rate detected"
          
      - alert: WebSocketConnectionsHigh
        expr: ds_websocket_connections > 8000
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "WebSocket connections approaching limit"
          
      - alert: DatabaseLatencyHigh
        expr: histogram_quantile(0.95, ds_database_query_duration_seconds) > 0.5
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "Database query latency is high"
          
      - alert: MarketDataStale
        expr: time() - ds_last_market_data_timestamp > 60
        for: 1m
        labels:
          severity: critical
        annotations:
          summary: "Market data feed is stale"
```

### Health Checks

```bash
# System health
curl https://dragonscope.company.com/health

# Detailed health
curl https://dragonscope.company.com/health/detailed

# Readiness probe
curl https://dragonscope.company.com/ready

# Liveness probe
curl https://dragonscope.company.com/live
```

**Health Check Response:**
```json
{
  "status": "healthy",
  "timestamp": "2026-01-15T14:30:00Z",
  "version": "3.2.1",
  "checks": {
    "database": { "status": "up", "latency_ms": 5 },
    "cache": { "status": "up", "latency_ms": 2 },
    "message_queue": { "status": "up" },
    "market_data": { "status": "up", "last_update": "2026-01-15T14:29:59Z" }
  }
}
```

---

## Backup and Disaster Recovery

### Backup Strategy

#### Automated Backups

```bash
# Daily backup script
#!/bin/bash
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="/backups/${DATE}"
mkdir -p ${BACKUP_DIR}

# PostgreSQL backup
pg_dump -h postgres -U ds_user dragonscope > ${BACKUP_DIR}/database.sql

# Redis backup
redis-cli BGSAVE
cp /var/lib/redis/dump.rdb ${BACKUP_DIR}/redis.rdb

# ClickHouse backup
clickhouse-backup create ds_backup_${DATE}
clickhouse-backup upload ds_backup_${DATE}

# Configuration backup
tar -czf ${BACKUP_DIR}/config.tar.gz /config

# Upload to S3
aws s3 sync ${BACKUP_DIR} s3://dragonscope-backups/${DATE}/

# Cleanup old backups
find /backups -type d -mtime +30 -exec rm -rf {} \;
```

#### Point-in-Time Recovery

```bash
# Restore from backup
# 1. Stop services
docker-compose down

# 2. Restore database
psql -h postgres -U ds_user dragonscope < backup.sql

# 3. Restore Redis
cp redis.rdb /var/lib/redis/dump.rdb

# 4. Restore ClickHouse
clickhouse-backup download ds_backup_20260115
clickhouse-backup restore ds_backup_20260115

# 5. Restart services
docker-compose up -d
```

### Disaster Recovery Plan

#### Recovery Time Objectives (RTO)

| Scenario | RTO | RPO |
|----------|-----|-----|
| Single node failure | 5 minutes | 0 |
| Database corruption | 30 minutes | 1 hour |
| Complete site failure | 4 hours | 1 hour |
| Regional outage | 8 hours | 1 hour |

#### Multi-Region Deployment

```yaml
# Primary Region (us-east-1)
primary:
  region: us-east-1
  database:
    host: postgres-primary.use1.internal
    replication:
      - region: us-west-2
        host: postgres-replica.usw2.internal
        mode: synchronous
      - region: eu-west-1
        host: postgres-replica.euwe1.internal
        mode: asynchronous

# Disaster Recovery Region (us-west-2)
dr:
  region: us-west-2
  auto_failover: true
  failover_threshold: 60s
```

### Testing Recovery Procedures

```bash
# Monthly DR drill
./scripts/dr-drill.sh --region us-west-2 --validate

# Validate backup integrity
./scripts/verify-backup.sh --date 2026-01-15
```

---

## Troubleshooting

### Common Issues

#### Issue: High Memory Usage

**Symptoms:** OOM kills, slow performance

**Diagnosis:**
```bash
# Check memory usage
docker stats dragonscope

# Check heap dumps
curl http://localhost:9090/debug/pprof/heap > heap.prof

# Analyze memory
go tool pprof heap.prof
```

**Resolution:**
```yaml
# Increase memory limits
resources:
  limits:
    memory: "64Gi"
  
# Adjust cache settings
cache:
  max_memory: "32Gi"
  eviction_policy: "allkeys-lru"
```

#### Issue: WebSocket Connection Drops

**Symptoms:** Clients disconnecting frequently

**Diagnosis:**
```bash
# Check connection limits
sysctl net.core.somaxconn
sysctl net.ipv4.tcp_max_syn_backlog

# Check WebSocket logs
docker logs dragonscope | grep websocket
```

**Resolution:**
```bash
# Increase connection limits
sysctl -w net.core.somaxconn=65535
sysctl -w net.ipv4.tcp_max_syn_backlog=65535

# Update nginx
worker_connections 65535;
worker_rlimit_nofile 65535;
```

#### Issue: Database Connection Pool Exhaustion

**Symptoms:** "too many connections" errors

**Diagnosis:**
```sql
-- Check active connections
SELECT count(*), state FROM pg_stat_activity GROUP BY state;

-- Check connection pool stats
SELECT * FROM pg_stat_database;
```

**Resolution:**
```yaml
# Increase pool size
database:
  pool:
    max: 200
    
# Enable connection pooling with PgBouncer
pgbouncer:
  max_client_conn: 10000
  default_pool_size: 100
  max_db_connections: 200
```

### Log Analysis

```bash
# Search for errors
docker logs dragonscope 2>&1 | grep ERROR

# Filter by time
docker logs --since 2026-01-15T10:00:00 dragonscope

# Follow logs
docker logs -f dragonscope | grep -E "(ERROR|WARN|order_id:12345)"
```

### Debug Mode

```bash
# Enable debug logging
export DS_LOG_LEVEL=debug

# Enable API request logging
curl -X POST http://localhost:8080/admin/debug/enable-request-logging

# Capture packet traces
tcpdump -i eth0 -w capture.pcap port 8080 or port 8443
```

### Support Bundle

```bash
# Generate support bundle
dragonscope support-bundle --output support.tar.gz

# Contents:
# - System logs
# - Configuration files (sanitized)
# - Metrics snapshot
# - Database schema
# - Network diagnostics
```

---

## Security

### Security Checklist

- [ ] TLS 1.3 enabled for all connections
- [ ] Strong password policy enforced
- [ ] MFA enabled for all admin accounts
- [ ] API keys rotated every 90 days
- [ ] Network segmentation implemented
- [ ] WAF configured
- [ ] DDoS protection enabled
- [ ] Regular security audits scheduled
- [ ] Penetration testing completed
- [ ] Incident response plan documented

### Compliance

| Standard | Status | Documentation |
|----------|--------|---------------|
| SOC 2 Type II | ✅ Certified | [Report](compliance/soc2.pdf) |
| ISO 27001 | ✅ Certified | [Certificate](compliance/iso27001.pdf) |
| GDPR | ✅ Compliant | [DPA](compliance/gdpr-dpa.pdf) |
| PCI DSS | ✅ Compliant | [AOC](compliance/pci-aoc.pdf) |
| FINRA | ✅ Compliant | [Documentation](compliance/finra.md) |

---

<p align="center">
  Enterprise Support: <a href="mailto:enterprise-support@dragonscope.io">enterprise-support@dragonscope.io</a>
</p>
