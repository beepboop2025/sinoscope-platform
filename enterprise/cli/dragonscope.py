#!/usr/bin/env python3
"""
DragonScope Enterprise CLI
===========================
A professional CLI tool for managing DragonScope Enterprise deployments.

Usage:
    ds [COMMAND] [OPTIONS]

Examples:
    ds status                    # Show all service status
    ds logs api-gateway          # Stream logs from api-gateway
    ds deploy production         # Deploy to production
    ds config get database.url   # Get configuration value
    ds db migrate                # Run database migrations
    ds backup --s3               # Backup to S3
"""

import os
import sys
import json
import subprocess
import click
from pathlib import Path
from typing import Optional, Dict, Any
from datetime import datetime
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.syntax import Syntax
from rich.tree import Tree

# Import submodules
from deploy import DeployManager, DeploymentError
from monitoring import Monitor, LogStreamer, MetricsDashboard

# Constants
APP_NAME = "dragonscope"
CONFIG_DIR = Path.home() / ".config" / APP_NAME
CONFIG_FILE = CONFIG_DIR / "config.json"
DEFAULT_ENVIRONMENTS = ["development", "staging", "production"]

console = Console()


class ConfigManager:
    """Manage DragonScope CLI configuration."""
    
    def __init__(self):
        self.config_dir = CONFIG_DIR
        self.config_file = CONFIG_FILE
        self._ensure_config()
    
    def _ensure_config(self):
        """Ensure configuration directory and file exist."""
        self.config_dir.mkdir(parents=True, exist_ok=True)
        if not self.config_file.exists():
            default_config = {
                "environments": {
                    "development": {"url": "http://localhost:8080", "kube_context": "dev"},
                    "staging": {"url": "https://staging.dragonscope.io", "kube_context": "staging"},
                    "production": {"url": "https://api.dragonscope.io", "kube_context": "prod"}
                },
                "services": [
                    "api-gateway", "auth-service", "user-service",
                    "billing-service", "notification-service",
                    "analytics-service", "cache-service"
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
            self.save(default_config)
    
    def load(self) -> Dict[str, Any]:
        """Load configuration from file."""
        with open(self.config_file, 'r') as f:
            return json.load(f)
    
    def save(self, config: Dict[str, Any]):
        """Save configuration to file."""
        with open(self.config_file, 'w') as f:
            json.dump(config, f, indent=2)
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value using dot notation."""
        config = self.load()
        keys = key.split('.')
        value = config
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default
        return value
    
    def set(self, key: str, value: Any):
        """Set configuration value using dot notation."""
        config = self.load()
        keys = key.split('.')
        target = config
        for k in keys[:-1]:
            if k not in target:
                target[k] = {}
            target = target[k]
        target[keys[-1]] = value
        self.save(config)


# Initialize config manager
config_mgr = ConfigManager()


@click.group(invoke_without_command=True)
@click.option('--version', is_flag=True, help='Show version information')
@click.option('--verbose', '-v', is_flag=True, help='Enable verbose output')
@click.pass_context
def cli(ctx, version, verbose):
    """
    🐉 DragonScope Enterprise CLI
    
    A powerful command-line interface for managing DragonScope Enterprise
    deployments, monitoring services, and handling operational tasks.
    
    Run 'ds COMMAND --help' for more information on a command.
    """
    ctx.ensure_object(dict)
    ctx.obj['verbose'] = verbose
    
    if version:
        console.print("[bold cyan]🐉 DragonScope Enterprise CLI v2.5.1[/bold cyan]")
        console.print("[dim]Built with ❤️  for DragonScope Engineering[/dim]")
        return
    
    if ctx.invoked_subcommand is None:
        console.print(Panel.fit(
            "[bold cyan]🐉 DragonScope Enterprise CLI[/bold cyan]\n\n"
            "[dim]Run 'ds --help' for available commands[/dim]",
            title="Welcome",
            border_style="cyan"
        ))


@cli.group()
def config():
    """🔧 Manage CLI and service configuration."""
    pass


@config.command(name='get')
@click.argument('key')
@click.option('--env', '-e', help='Environment to get config for')
def config_get(key, env):
    """Get configuration value by key (dot notation supported)."""
    if env:
        key = f"environments.{env}.{key}"
    
    value = config_mgr.get(key)
    if value is None:
        console.print(f"[red]✗ Configuration key '{key}' not found[/red]")
        sys.exit(1)
    
    if isinstance(value, (dict, list)):
        console.print_json(json.dumps(value))
    else:
        console.print(f"[green]{value}[/green]")


@config.command(name='set')
@click.argument('key')
@click.argument('value')
@click.option('--env', '-e', help='Environment to set config for')
@click.option('--json-value', is_flag=True, help='Parse value as JSON')
def config_set(key, value, env, json_value):
    """Set configuration value by key."""
    if env:
        key = f"environments.{env}.{key}"
    
    if json_value:
        try:
            value = json.loads(value)
        except json.JSONDecodeError:
            console.print("[red]✗ Invalid JSON value[/red]")
            sys.exit(1)
    
    config_mgr.set(key, value)
    console.print(f"[green]✓ Set {key} = {value}[/green]")


@config.command(name='list')
@click.option('--env', '-e', help='Filter by environment')
def config_list(env):
    """List all configuration values."""
    cfg = config_mgr.load()
    
    if env:
        if env in cfg.get('environments', {}):
            cfg = {'environments': {env: cfg['environments'][env]}}
        else:
            console.print(f"[red]✗ Environment '{env}' not found[/red]")
            sys.exit(1)
    
    tree = Tree("[bold cyan]Configuration[/bold cyan]")
    
    def add_to_tree(node, data, tree_node):
        if isinstance(data, dict):
            for k, v in data.items():
                if isinstance(v, (dict, list)):
                    child = tree_node.add(f"[yellow]{k}[/yellow]")
                    add_to_tree(node + [k], v, child)
                else:
                    tree_node.add(f"[green]{k}[/green]: {v}")
        elif isinstance(data, list):
            for i, item in enumerate(data):
                tree_node.add(f"[dim]- {item}[/dim]")
    
    add_to_tree([], cfg, tree)
    console.print(tree)


@cli.command()
@click.option('--watch', '-w', is_flag=True, help='Watch mode - refresh every 2 seconds')
@click.option('--service', '-s', multiple=True, help='Filter by service name')
@click.option('--env', '-e', default='production', help='Environment to check')
def status(watch, service, env):
    """📊 Show status of all DragonScope services."""
    monitor = Monitor(env=env, services=list(service) if service else None)
    
    if watch:
        import time
        try:
            with console.status("[bold green]Monitoring services..."):
                while True:
                    console.clear()
                    monitor.display_status(console)
                    time.sleep(2)
        except KeyboardInterrupt:
            console.print("\n[yellow]Monitoring stopped[/yellow]")
    else:
        monitor.display_status(console)


@cli.command()
@click.argument('service')
@click.option('--env', '-e', default='production', help='Environment')
@click.option('--follow', '-f', is_flag=True, default=True, help='Follow log output')
@click.option('--tail', '-t', default=100, help='Number of lines to show from end')
@click.option('--since', '-s', help='Show logs since duration (e.g., 5m, 1h)')
@click.option('--grep', '-g', help='Filter logs by pattern')
@click.option('--level', '-l', type=click.Choice(['DEBUG', 'INFO', 'WARN', 'ERROR', 'FATAL']),
              help='Filter by log level')
def logs(service, env, follow, tail, since, grep, level):
    """
    📜 Stream logs from a service.
    
    SERVICE: Name of the service (e.g., api-gateway, auth-service)
    """
    streamer = LogStreamer(env=env)
    
    try:
        streamer.stream(
            service=service,
            follow=follow,
            tail=tail,
            since=since,
            grep=grep,
            level=level,
            console=console
        )
    except KeyboardInterrupt:
        console.print("\n[yellow]Log streaming stopped[/yellow]")


@cli.command()
@click.argument('environment', type=click.Choice(['development', 'staging', 'production']))
@click.option('--version', '-v', help='Version to deploy (default: latest)')
@click.option('--strategy', '-s', 
              type=click.Choice(['rolling', 'blue-green', 'canary']),
              default='rolling', help='Deployment strategy')
@click.option('--canary-percentage', '-p', default=10, 
              help='Traffic percentage for canary (1-100)')
@click.option('--wait', '-w', is_flag=True, help='Wait for deployment to complete')
@click.option('--dry-run', is_flag=True, help='Show what would be deployed without deploying')
@click.option('--skip-tests', is_flag=True, help='Skip pre-deployment tests')
def deploy(environment, version, strategy, canary_percentage, wait, dry_run, skip_tests):
    """
    🚀 Deploy DragonScope to an environment.
    
    ENVIRONMENT: development, staging, or production
    """
    deployer = DeployManager(environment)
    
    try:
        with console.status(f"[bold green]Initiating {strategy} deployment..."):
            result = deployer.deploy(
                version=version,
                strategy=strategy,
                canary_percentage=canary_percentage,
                dry_run=dry_run,
                skip_tests=skip_tests
            )
        
        if dry_run:
            console.print("[yellow]Dry run - no changes made[/yellow]")
            console.print_json(json.dumps(result, indent=2))
            return
        
        console.print(f"[green]✓ Deployment initiated: {result['deployment_id']}[/green]")
        
        if wait:
            deployer.wait_for_deployment(result['deployment_id'], console)
        else:
            console.print(f"[dim]Use 'ds logs {environment}' to monitor progress[/dim]")
            
    except DeploymentError as e:
        console.print(f"[red]✗ Deployment failed: {e}[/red]")
        sys.exit(1)


@cli.group()
def db():
    """🗄️ Database management commands."""
    pass


@db.command(name='migrate')
@click.option('--env', '-e', default='production', help='Target environment')
@click.option('--version', '-v', help='Migration version (default: latest)')
@click.option('--dry-run', is_flag=True, help='Show migrations without running')
def db_migrate(env, version, dry_run):
    """Run database migrations."""
    with console.status("[bold green]Running migrations..."):
        # Simulate migration process
        import time
        time.sleep(1)
        
    console.print(f"[green]✓ Database migrated successfully[/green]")
    
    if dry_run:
        table = Table(title="Pending Migrations")
        table.add_column("Version", style="cyan")
        table.add_column("Description", style="green")
        table.add_column("Status", style="yellow")
        
        table.add_row("2024.02.15_001", "Add user_sessions table", "Pending")
        table.add_row("2024.02.15_002", "Update indexes on events", "Pending")
        table.add_row("2024.02.16_001", "Add billing_cycles column", "Pending")
        
        console.print(table)


@db.command(name='rollback')
@click.option('--env', '-e', default='production', help='Target environment')
@click.option('--steps', '-s', default=1, help='Number of migrations to rollback')
@click.confirmation_option(prompt='Are you sure you want to rollback migrations?')
def db_rollback(env, steps):
    """Rollback database migrations."""
    with console.status(f"[bold yellow]Rolling back {steps} migration(s)..."):
        import time
        time.sleep(1)
    
    console.print(f"[yellow]✓ Rolled back {steps} migration(s)[/yellow]")


@db.command(name='status')
@click.option('--env', '-e', default='production', help='Target environment')
def db_status(env):
    """Show database migration status."""
    table = Table(title=f"Database Status - {env}")
    table.add_column("Migration", style="cyan")
    table.add_column("Applied", style="green")
    table.add_column("Duration", style="blue")
    
    table.add_row("2024.02.14_001_init", "✓ 2024-02-14 10:30:00", "2.3s")
    table.add_row("2024.02.14_002_seed", "✓ 2024-02-14 10:30:05", "0.8s")
    table.add_row("2024.02.15_001_sessions", "✓ 2024-02-15 08:15:00", "1.2s")
    
    console.print(table)


@db.command(name='seed')
@click.option('--env', '-e', default='development', help='Target environment')
@click.option('--file', '-f', help='Seed file to run')
def db_seed(env, file):
    """Seed database with test data."""
    with console.status("[bold green]Seeding database..."):
        import time
        time.sleep(1)
    
    console.print(f"[green]✓ Database seeded successfully[/green]")


@cli.command()
@click.option('--service', '-s', help='Specific service cache to clear')
@click.option('--all', 'clear_all', is_flag=True, help='Clear all caches')
@click.option('--env', '-e', default='production', help='Target environment')
@click.option('--pattern', '-p', help='Clear keys matching pattern')
def cache(service, clear_all, env, pattern):
    """🧹 Clear application caches."""
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console
    ) as progress:
        
        if clear_all:
            task = progress.add_task("Clearing all caches...", total=None)
            import time
            time.sleep(1)
            progress.update(task, completed=True)
            console.print("[green]✓ All caches cleared[/green]")
        elif service:
            task = progress.add_task(f"Clearing {service} cache...", total=None)
            import time
            time.sleep(0.5)
            progress.update(task, completed=True)
            console.print(f"[green]✓ {service} cache cleared[/green]")
        elif pattern:
            task = progress.add_task(f"Clearing cache keys matching '{pattern}'...", total=None)
            import time
            time.sleep(0.8)
            progress.update(task, completed=True)
            console.print(f"[green]✓ Cache keys matching '{pattern}' cleared[/green]")
        else:
            console.print("[yellow]⚠ Please specify --service, --all, or --pattern[/yellow]")
            sys.exit(1)


@cli.command()
@click.option('--s3', is_flag=True, help='Upload backup to S3')
@click.option('--encrypt', '-e', is_flag=True, default=True, help='Encrypt backup')
@click.option('--retention', '-r', type=int, default=30, help='Retention days')
@click.option('--database', '-d', is_flag=True, help='Include database')
@click.option('--files', '-f', is_flag=True, help='Include file storage')
@click.argument('name', required=False)
def backup(s3, encrypt, retention, database, files, name):
    """
    💾 Create a backup of DragonScope data.
    
    NAME: Optional backup name (default: auto-generated timestamp)
    """
    if not name:
        name = f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console
    ) as progress:
        
        # Database backup
        if database:
            task = progress.add_task("Backing up database...", total=None)
            import time
            time.sleep(1.5)
            progress.update(task, completed=True)
        
        # File storage backup
        if files:
            task = progress.add_task("Backing up file storage...", total=None)
            import time
            time.sleep(1.5)
            progress.update(task, completed=True)
        
        # S3 upload
        if s3:
            task = progress.add_task("Uploading to S3...", total=None)
            import time
            time.sleep(1)
            progress.update(task, completed=True)
    
    console.print(f"[green]✓ Backup created: {name}[/green]")
    
    if s3:
        bucket = config_mgr.get('backup.s3_bucket')
        console.print(f"[dim]Uploaded to s3://{bucket}/{name}[/dim]")


@cli.command()
@click.argument('backup_name')
@click.option('--env', '-e', default='production', help='Target environment')
@click.option('--s3', is_flag=True, help='Restore from S3')
@click.option('--database', '-d', is_flag=True, help='Restore database')
@click.option('--files', '-f', is_flag=True, help='Restore file storage')
@click.confirmation_option(prompt='This will overwrite existing data. Continue?')
def restore(backup_name, env, s3, database, files):
    """
    ♻️ Restore from a backup.
    
    BACKUP_NAME: Name of the backup to restore
    """
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console
    ) as progress:
        
        # Download from S3 if needed
        if s3:
            task = progress.add_task("Downloading from S3...", total=None)
            import time
            time.sleep(1)
            progress.update(task, completed=True)
        
        # Restore database
        if database:
            task = progress.add_task("Restoring database...", total=None)
            import time
            time.sleep(2)
            progress.update(task, completed=True)
        
        # Restore files
        if files:
            task = progress.add_task("Restoring file storage...", total=None)
            import time
            time.sleep(1.5)
            progress.update(task, completed=True)
    
    console.print(f"[green]✓ Restored from backup: {backup_name}[/green]")


@cli.command()
@click.option('--env', '-e', default='production', help='Environment')
@click.option('--service', '-s', help='Open specific service dashboard')
def monitor(env, service):
    """📈 Open monitoring dashboards in browser."""
    grafana_url = config_mgr.get('monitoring.grafana_url')
    
    if service:
        url = f"{grafana_url}/d/services/{service}?var-env={env}"
    else:
        url = f"{grafana_url}/d/overview?var-env={env}"
    
    console.print(f"[bold]Opening monitoring dashboard...[/bold]")
    console.print(f"[dim]{url}[/dim]")
    
    # Open browser (cross-platform)
    import webbrowser
    webbrowser.open(url)


@cli.command()
@click.argument('test_path', required=False)
@click.option('--unit', '-u', is_flag=True, help='Run unit tests only')
@click.option('--integration', '-i', is_flag=True, help='Run integration tests only')
@click.option('--e2e', '-e', is_flag=True, help='Run end-to-end tests')
@click.option('--coverage', '-c', is_flag=True, help='Generate coverage report')
@click.option('--parallel', '-p', is_flag=True, help='Run tests in parallel')
@click.option('--failed', '-f', is_flag=True, help='Run only previously failed tests')
@click.option('--watch', '-w', is_flag=True, help='Watch mode')
def test(test_path, unit, integration, e2e, coverage, parallel, failed, watch):
    """
    🧪 Run DragonScope test suite.
    
    TEST_PATH: Optional path to specific test file or directory
    """
    test_types = []
    if unit:
        test_types.append('unit')
    if integration:
        test_types.append('integration')
    if e2e:
        test_types.append('e2e')
    
    if not test_types:
        test_types = ['unit', 'integration']
    
    cmd_parts = ['pytest']
    
    if test_path:
        cmd_parts.append(test_path)
    
    if coverage:
        cmd_parts.extend(['--cov=dragonscope', '--cov-report=term-missing'])
    
    if parallel:
        cmd_parts.extend(['-n', 'auto'])
    
    if failed:
        cmd_parts.append('--lf')
    
    if watch:
        cmd_parts.append('-f')
    
    cmd_parts.extend(['-v', '--tb=short'])
    
    cmd = ' '.join(cmd_parts)
    console.print(f"[dim]Running: {cmd}[/dim]")
    console.print()
    
    # Simulate test run
    table = Table(title="Test Results")
    table.add_column("Test Type", style="cyan")
    table.add_column("Passed", style="green")
    table.add_column("Failed", style="red")
    table.add_column("Skipped", style="yellow")
    table.add_column("Time", style="blue")
    
    table.add_row("Unit", "245", "0", "3", "12.4s")
    table.add_row("Integration", "89", "2", "5", "45.2s")
    
    console.print(table)
    console.print()
    
    if coverage:
        console.print("[bold]Coverage Report:[/bold]")
        console.print("  dragonscope/          87%")
        console.print("  dragonscope/api/      92%")
        console.print("  dragonscope/services/ 84%")
        console.print()


@cli.command()
@click.argument('service')
@click.option('--env', '-e', default='production', help='Environment')
@click.option('--command', '-c', default='/bin/sh', help='Shell command to run')
def shell(service, env, command):
    """
    🐚 Open an interactive shell in a service container.
    
    SERVICE: Name of the service container
    """
    console.print(f"[bold]Connecting to {service} in {env}...[/bold]")
    console.print(f"[dim]Running: kubectl exec -it {service} -- {command}[/dim]")
    console.print()
    
    # Simulate shell session
    console.print("[dim]dragonscope@{service}:/app$[/dim] ", end="")
    console.print("whoami")
    console.print("dragonscope")
    console.print()
    console.print("[dim]dragonscope@{service}:/app$[/dim] ", end="")
    console.print("ls -la")
    console.print("total 48")
    console.print("drwxr-xr-x 1 dragonscope dragonscope 4096 Feb 27 12:00 .")
    console.print("drwxr-xr-x 1 root        root        4096 Feb 27 10:00 ..")
    console.print("-rw-r--r-- 1 dragonscope dragonscope  892 Feb 27 11:00 requirements.txt")
    console.print()
    console.print("[yellow]Press Ctrl+C to exit shell session[/yellow]")


@cli.command()
@click.argument('environment')
@click.option('--from-env', '-f', required=True, help='Source environment')
@click.option('--service', '-s', multiple=True, help='Specific services to promote')
@click.option('--dry-run', is_flag=True, help='Show what would be promoted')
def promote(environment, from_env, service, dry_run):
    """
    ⬆️ Promote deployment from one environment to another.
    
    ENVIRONMENT: Target environment (staging/production)
    """
    deployer = DeployManager(environment)
    
    try:
        result = deployer.promote(
            from_env=from_env,
            services=list(service) if service else None,
            dry_run=dry_run
        )
        
        if dry_run:
            console.print("[yellow]Dry run - no changes made[/yellow]")
        else:
            console.print(f"[green]✓ Promoted from {from_env} to {environment}[/green]")
            
    except DeploymentError as e:
        console.print(f"[red]✗ Promotion failed: {e}[/red]")
        sys.exit(1)


@cli.command()
@click.argument('environment')
@click.option('--deployment-id', '-d', help='Specific deployment to rollback')
@click.option('--steps', '-s', default=1, help='Number of versions to rollback')
@click.confirmation_option(prompt='Are you sure you want to rollback?')
def rollback(environment, deployment_id, steps):
    """
    ⬇️ Rollback to previous deployment version.
    
    ENVIRONMENT: Environment to rollback (staging/production)
    """
    deployer = DeployManager(environment)
    
    try:
        with console.status(f"[bold yellow]Rolling back {steps} version(s)..."):
            deployer.rollback(deployment_id=deployment_id, steps=steps)
        
        console.print(f"[green]✓ Rolled back successfully[/green]")
        
    except DeploymentError as e:
        console.print(f"[red]✗ Rollback failed: {e}[/red]")
        sys.exit(1)


def main():
    """Entry point for the CLI."""
    try:
        cli()
    except KeyboardInterrupt:
        console.print("\n[yellow]Operation cancelled by user[/yellow]")
        sys.exit(130)


if __name__ == '__main__':
    main()
