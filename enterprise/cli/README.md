# 🐉 DragonScope Enterprise CLI

A professional command-line interface for managing DragonScope Enterprise deployments, monitoring services, and handling operational tasks.

## Features

- **🚀 Deployment Management**
  - Rolling, Blue/Green, and Canary deployment strategies
  - Automatic rollback on failure
  - Environment promotion workflows

- **📊 Monitoring & Observability**
  - Real-time service status dashboard
  - Live log streaming with filtering
  - Metrics visualization
  - Alert management

- **🔧 Operations**
  - Database migrations and seeding
  - Cache management
  - Backup and restore operations
  - Shell access to containers

- **⚡ Developer Experience**
  - Rich terminal output with colors and progress bars
  - Shell autocompletion (Bash, Zsh, Fish)
  - Comprehensive help documentation
  - Watch mode for continuous monitoring

## Installation

```bash
# Clone the repository
git clone https://github.com/dragonscope/enterprise.git
cd enterprise/cli

# Install dependencies
pip install -r requirements.txt

# Make the CLI executable
chmod +x dragonscope.py

# Optional: Create symlink for global access
ln -s $(pwd)/dragonscope.py /usr/local/bin/ds

# Setup autocompletion
python setup_autocomplete.py
```

## Quick Start

```bash
# Check CLI version
ds --version

# View service status
ds status

# Stream logs from a service
ds logs api-gateway -f

# Deploy to staging
ds deploy staging --strategy canary --canary-percentage 20

# Run database migrations
ds db migrate --env production
```

## Commands

### Core Commands

| Command | Description |
|---------|-------------|
| `ds status` | Show all service status |
| `ds logs <service>` | Stream logs from a service |
| `ds deploy <env>` | Deploy to an environment |
| `ds config get/set/list` | Manage configuration |

### Database Commands

| Command | Description |
|---------|-------------|
| `ds db migrate` | Run database migrations |
| `ds db rollback` | Rollback migrations |
| `ds db status` | Show migration status |
| `ds db seed` | Seed database with test data |

### Operations Commands

| Command | Description |
|---------|-------------|
| `ds cache clear` | Clear application caches |
| `ds backup` | Create data backup |
| `ds restore <backup>` | Restore from backup |
| `ds monitor` | Open monitoring dashboard |
| `ds test` | Run test suite |
| `ds shell <service>` | Open shell in container |

### Deployment Commands

| Command | Description |
|---------|-------------|
| `ds deploy <env>` | Deploy to environment |
| `ds promote <env>` | Promote from another environment |
| `ds rollback <env>` | Rollback to previous version |

## Configuration

Configuration is stored in `~/.config/dragonscope/config.json`:

```json
{
  "environments": {
    "development": {
      "url": "http://localhost:8080",
      "kube_context": "dev"
    },
    "staging": {
      "url": "https://staging.dragonscope.io",
      "kube_context": "staging"
    },
    "production": {
      "url": "https://api.dragonscope.io",
      "kube_context": "prod"
    }
  },
  "services": [
    "api-gateway",
    "auth-service",
    "user-service",
    "billing-service",
    "notification-service",
    "analytics-service",
    "cache-service"
  ],
  "backup": {
    "s3_bucket": "dragonscope-backups",
    "retention_days": 30
  },
  "monitoring": {
    "grafana_url": "https://grafana.dragonscope.io",
    "prometheus_url": "https://prometheus.dragonscope.io"
  }
}
```

Manage configuration via CLI:

```bash
# Get configuration value
ds config get environments.production.url

# Set configuration value
ds config set environments.production.url https://new-url.dragonscope.io

# List all configuration
ds config list
```

## Deployment Strategies

### Rolling Deployment (Default)

Gradually replaces old pods with new ones:

```bash
ds deploy production --version 2.5.0 --strategy rolling
```

### Blue/Green Deployment

Deploy to a separate environment, then switch traffic:

```bash
ds deploy production --version 2.5.0 --strategy blue-green
```

### Canary Deployment

Release to a small percentage of users first:

```bash
ds deploy production --version 2.5.0 --strategy canary --canary-percentage 10
```

## Log Streaming

Stream logs with powerful filtering:

```bash
# Follow logs
ds logs api-gateway -f

# Show last 500 lines
ds logs api-gateway --tail 500

# Filter by level
ds logs api-gateway --level ERROR

# Grep for pattern
ds logs api-gateway --grep "payment failed"

# Show logs since duration
ds logs api-gateway --since 1h
```

## Monitoring

Real-time service status with watch mode:

```bash
# Show current status
ds status

# Continuous monitoring (refreshes every 2 seconds)
ds status --watch

# Filter specific services
ds status --service api-gateway --service auth-service

# Open Grafana dashboard
ds monitor

# Open specific service dashboard
ds monitor --service billing-service
```

## Testing

Run tests with various options:

```bash
# Run all tests
ds test

# Run unit tests only
ds test --unit

# Run with coverage
ds test --coverage

# Run in parallel
ds test --parallel

# Run only failed tests
ds test --failed

# Watch mode (re-run on file changes)
ds test --watch
```

## Backup & Restore

```bash
# Create backup with S3 upload
ds backup my-backup --s3 --database --files

# Create encrypted backup
ds backup --encrypt

# Restore from backup
ds restore my-backup --s3 --database --files
```

## Shell Access

Open an interactive shell in a service container:

```bash
# Default shell (/bin/sh)
ds shell api-gateway

# Specific shell
ds shell api-gateway --command /bin/bash

# Specific environment
ds shell api-gateway --env staging
```

## Autocompletion

Setup shell autocompletion for faster command entry:

```bash
# Auto-detect shell
python setup_autocomplete.py

# Specify shell explicitly
python setup_autocomplete.py --shell zsh
```

Supported shells:
- Bash
- Zsh
- Fish

## Environment Promotion

Promote deployments between environments:

```bash
# Promote from staging to production
ds promote production --from-env staging

# Promote specific services
ds promote production --from-env staging --service api-gateway --service auth-service

# Dry run
ds promote production --from-env staging --dry-run
```

## Rollback

Rollback to previous versions:

```bash
# Rollback last deployment
ds rollback production

# Rollback specific deployment
ds rollback production --deployment-id dep-prod-20240227120000-abc123

# Rollback multiple versions
ds rollback production --steps 2
```

## Development

```bash
# Install development dependencies
pip install -r requirements.txt

# Run tests
pytest

# Check code style
black dragonscope.py deploy.py monitoring.py

# Type checking
mypy dragonscope.py deploy.py monitoring.py
```

## License

Proprietary - DragonScope Enterprise

## Support

For support, contact:
- Engineering Team: engineering@dragonscope.io
- DevOps Team: devops@dragonscope.io
- On-call: +1-555-DRAGONSCOPE
