#!/usr/bin/env python3
"""
DragonScope Enterprise Monitoring Module
========================================
Provides terminal-based dashboards, log streaming, and metrics visualization.

Features:
    - Real-time service status dashboard
    - Log streaming with filtering and coloring
    - Metrics visualization with sparklines
    - Alert management and notifications
"""

import re
import time
import json
import random
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Callable, Any, Iterator
from dataclasses import dataclass, field
from enum import Enum

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.live import Live
from rich.layout import Layout
from rich.text import Text
from rich.syntax import Syntax
from rich.progress import Progress, BarColumn, TextColumn
from rich.tree import Tree
from rich import box


class ServiceStatus(Enum):
    """Service health status."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"
    MAINTENANCE = "maintenance"


class LogLevel(Enum):
    """Log level classifications."""
    DEBUG = ("DEBUG", "dim blue")
    INFO = ("INFO", "green")
    WARN = ("WARN", "yellow")
    WARNING = ("WARNING", "yellow")
    ERROR = ("ERROR", "red")
    FATAL = ("FATAL", "bold red")
    
    def __init__(self, label: str, style: str):
        self.label = label
        self.style = style
    
    @classmethod
    def from_string(cls, level: str) -> "LogLevel":
        """Parse log level from string."""
        level_map = {
            "debug": cls.DEBUG,
            "info": cls.INFO,
            "warn": cls.WARN,
            "warning": cls.WARNING,
            "error": cls.ERROR,
            "fatal": cls.FATAL
        }
        return level_map.get(level.lower(), cls.INFO)


@dataclass
class ServiceMetrics:
    """Metrics for a single service."""
    cpu_percent: float = 0.0
    memory_percent: float = 0.0
    memory_mb: float = 0.0
    requests_per_second: float = 0.0
    response_time_ms: float = 0.0
    error_rate: float = 0.0
    uptime_seconds: int = 0
    replica_count: int = 0
    healthy_replicas: int = 0
    
    # Historical data for sparklines
    cpu_history: List[float] = field(default_factory=list)
    memory_history: List[float] = field(default_factory=list)
    rps_history: List[float] = field(default_factory=list)
    
    def update_history(self):
        """Update historical data (keep last 20 points)."""
        self.cpu_history.append(self.cpu_percent)
        self.memory_history.append(self.memory_percent)
        self.rps_history.append(self.requests_per_second)
        
        # Keep only last 20 points
        self.cpu_history = self.cpu_history[-20:]
        self.memory_history = self.memory_history[-20:]
        self.rps_history = self.rps_history[-20:]


@dataclass
class ServiceInfo:
    """Information about a service."""
    name: str
    version: str
    status: ServiceStatus
    metrics: ServiceMetrics
    last_updated: datetime = field(default_factory=datetime.now)
    alerts: List[Dict[str, Any]] = field(default_factory=list)
    endpoints: List[str] = field(default_factory=list)


@dataclass
class Alert:
    """Alert information."""
    id: str
    service: str
    severity: str  # critical, warning, info
    message: str
    timestamp: datetime
    acknowledged: bool = False
    resolved: bool = False


class Monitor:
    """
    Terminal-based monitoring dashboard for DragonScope services.
    """
    
    DEFAULT_SERVICES = [
        "api-gateway", "auth-service", "user-service",
        "billing-service", "notification-service",
        "analytics-service", "cache-service"
    ]
    
    def __init__(self, env: str = "production", services: Optional[List[str]] = None):
        self.env = env
        self.services = services or self.DEFAULT_SERVICES
        self.service_data: Dict[str, ServiceInfo] = {}
        self.alerts: List[Alert] = []
        self._initialize_services()
    
    def _initialize_services(self):
        """Initialize service data structures."""
        for service in self.services:
            self.service_data[service] = ServiceInfo(
                name=service,
                version="2.5.0",
                status=ServiceStatus.HEALTHY,
                metrics=ServiceMetrics()
            )
    
    def _fetch_metrics(self, service: str) -> ServiceMetrics:
        """Fetch metrics for a service (simulated)."""
        metrics = ServiceMetrics()
        
        # Simulate realistic metrics
        base_cpu = random.uniform(20, 40)
        if service in ["api-gateway", "cache-service"]:
            base_cpu += 20  # Higher CPU for these services
        
        metrics.cpu_percent = round(base_cpu + random.uniform(-5, 5), 1)
        metrics.memory_percent = round(random.uniform(30, 70), 1)
        metrics.memory_mb = round(random.uniform(200, 800), 0)
        metrics.requests_per_second = round(random.uniform(100, 2000), 0)
        metrics.response_time_ms = round(random.uniform(10, 150), 1)
        metrics.error_rate = round(random.uniform(0, 0.5), 2)
        metrics.uptime_seconds = random.randint(86400, 604800)  # 1-7 days
        metrics.replica_count = 3 if self.env == "production" else 1
        metrics.healthy_replicas = metrics.replica_count
        
        # Occasionally simulate issues
        if random.random() < 0.1:
            metrics.error_rate = round(random.uniform(1, 5), 2)
            metrics.healthy_replicas = max(1, metrics.replica_count - 1)
        
        # Update history
        metrics.cpu_history = [base_cpu + random.uniform(-5, 5) for _ in range(20)]
        metrics.memory_history = [random.uniform(30, 70) for _ in range(20)]
        metrics.rps_history = [random.uniform(100, 2000) for _ in range(20)]
        
        return metrics
    
    def _get_status_icon(self, status: ServiceStatus) -> str:
        """Get icon for service status."""
        icons = {
            ServiceStatus.HEALTHY: "✓",
            ServiceStatus.DEGRADED: "⚠",
            ServiceStatus.UNHEALTHY: "✗",
            ServiceStatus.UNKNOWN: "?",
            ServiceStatus.MAINTENANCE: "🔧"
        }
        return icons.get(status, "?")
    
    def _get_status_style(self, status: ServiceStatus) -> str:
        """Get rich style for service status."""
        styles = {
            ServiceStatus.HEALTHY: "green",
            ServiceStatus.DEGRADED: "yellow",
            ServiceStatus.UNHEALTHY: "red",
            ServiceStatus.UNKNOWN: "dim",
            ServiceStatus.MAINTENANCE: "blue"
        }
        return styles.get(status, "white")
    
    def _sparkline(self, data: List[float], width: int = 20) -> str:
        """Generate ASCII sparkline from data."""
        if not data:
            return ""
        
        bars = "▁▂▃▄▅▆▇█"
        min_val, max_val = min(data), max(data)
        
        if max_val == min_val:
            return bars[0] * width
        
        # Normalize to bar characters
        result = []
        for val in data[-width:]:
            idx = int((val - min_val) / (max_val - min_val) * (len(bars) - 1))
            result.append(bars[idx])
        
        return "".join(result)
    
    def _format_duration(self, seconds: int) -> str:
        """Format duration in human-readable format."""
        if seconds < 60:
            return f"{seconds}s"
        elif seconds < 3600:
            return f"{seconds // 60}m"
        elif seconds < 86400:
            return f"{seconds // 3600}h"
        else:
            return f"{seconds // 86400}d"
    
    def update(self):
        """Update all service metrics."""
        for service in self.services:
            metrics = self._fetch_metrics(service)
            
            # Determine status based on metrics
            if metrics.error_rate > 2:
                status = ServiceStatus.UNHEALTHY
            elif metrics.error_rate > 0.5 or metrics.healthy_replicas < metrics.replica_count:
                status = ServiceStatus.DEGRADED
            else:
                status = ServiceStatus.HEALTHY
            
            self.service_data[service].metrics = metrics
            self.service_data[service].status = status
            self.service_data[service].last_updated = datetime.now()
    
    def display_status(self, console: Console):
        """Display service status dashboard."""
        self.update()
        
        # Header
        console.print(Panel.fit(
            f"[bold cyan]🐉 DragonScope Service Status[/bold cyan]\n"
            f"[dim]Environment: {self.env.upper()} | {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}[/dim]",
            border_style="cyan"
        ))
        
        # Services table
        table = Table(
            title=f"Services ({len(self.services)})",
            box=box.ROUNDED,
            show_header=True,
            header_style="bold cyan"
        )
        
        table.add_column("Service", style="cyan", width=20)
        table.add_column("Status", width=12)
        table.add_column("Version", width=10)
        table.add_column("Replicas", width=10)
        table.add_column("CPU", width=15)
        table.add_column("Memory", width=15)
        table.add_column("RPS", width=12)
        table.add_column("Latency", width=10)
        table.add_column("Uptime", width=10)
        
        for service_name, info in self.service_data.items():
            status_icon = self._get_status_icon(info.status)
            status_style = self._get_status_style(info.status)
            
            metrics = info.metrics
            cpu_spark = self._sparkline(metrics.cpu_history, 10)
            mem_spark = self._sparkline(metrics.memory_history, 10)
            
            table.add_row(
                service_name,
                f"[{status_style}]{status_icon} {info.status.value}[/{status_style}]",
                info.version,
                f"{metrics.healthy_replicas}/{metrics.replica_count}",
                f"{metrics.cpu_percent}% {cpu_spark}",
                f"{metrics.memory_percent}% {mem_spark}",
                f"{metrics.requests_per_second:.0f}",
                f"{metrics.response_time_ms:.1f}ms",
                self._format_duration(metrics.uptime_seconds)
            )
        
        console.print(table)
        
        # Summary stats
        healthy = sum(1 for s in self.service_data.values() if s.status == ServiceStatus.HEALTHY)
        degraded = sum(1 for s in self.service_data.values() if s.status == ServiceStatus.DEGRADED)
        unhealthy = sum(1 for s in self.service_data.values() if s.status == ServiceStatus.UNHEALTHY)
        
        console.print()
        console.print(
            f"[bold]Summary:[/bold] "
            f"[green]{healthy} Healthy[/green] | "
            f"[yellow]{degraded} Degraded[/yellow] | "
            f"[red]{unhealthy} Unhealthy[/red]"
        )
    
    def get_layout(self) -> Layout:
        """Get a Rich Layout for live display."""
        layout = Layout()
        
        layout.split_column(
            Layout(name="header", size=3),
            Layout(name="main"),
            Layout(name="footer", size=3)
        )
        
        layout["main"].split_row(
            Layout(name="services"),
            Layout(name="metrics", ratio=2)
        )
        
        return layout


class LogStreamer:
    """
    Stream and filter logs from DragonScope services.
    """
    
    # Sample log lines for simulation
    SAMPLE_LOGS = [
        ("INFO", "Request processed successfully", "200 OK"),
        ("DEBUG", "Cache hit for key", "user:12345"),
        ("INFO", "User authenticated", "user_id=67890"),
        ("WARN", "Slow query detected", "duration=2.5s"),
        ("ERROR", "Database connection failed", "retrying..."),
        ("INFO", "Payment processed", "amount=$99.99"),
        ("DEBUG", "Webhook received", "type=invoice.paid"),
        ("INFO", "Email sent", "to=user@example.com"),
        ("WARN", "Rate limit approaching", "requests=95/100"),
        ("ERROR", "Invalid API key", "key=sk_***1234"),
    ]
    
    def __init__(self, env: str = "production"):
        self.env = env
        self.running = False
    
    def _generate_log_line(self, service: str) -> Dict[str, Any]:
        """Generate a simulated log line."""
        level_name, message, details = random.choice(self.SAMPLE_LOGS)
        level = LogLevel.from_string(level_name)
        
        # Add some service-specific logs
        if service == "auth-service":
            message = random.choice([
                "Token validated", "Login attempt", "Session refreshed",
                "Password reset requested", "MFA challenge sent"
            ])
        elif service == "billing-service":
            message = random.choice([
                "Invoice generated", "Payment processed", "Subscription updated",
                "Refund issued", "Usage recorded"
            ])
        
        return {
            "timestamp": datetime.now().isoformat(),
            "service": service,
            "level": level,
            "message": message,
            "details": details,
            "trace_id": f"trace-{random.randint(10000, 99999)}"
        }
    
    def _format_log_line(self, log: Dict[str, Any], grep: Optional[str] = None) -> Optional[Text]:
        """Format a log line for display."""
        # Apply grep filter
        if grep:
            pattern = re.compile(grep, re.IGNORECASE)
            log_text = f"{log['message']} {log.get('details', '')}"
            if not pattern.search(log_text):
                return None
        
        # Build formatted log line
        timestamp = log["timestamp"].split("T")[1].split(".")[0]
        level = log["level"]
        
        text = Text()
        text.append(f"{timestamp} ", style="dim")
        text.append(f"[{log['service']:20}] ", style="cyan")
        text.append(f"{level.label:8} ", style=level.style)
        text.append(log["message"], style="white")
        
        if log.get("details"):
            text.append(f" {log['details']}", style="dim")
        
        return text
    
    def stream(
        self,
        service: str,
        follow: bool = True,
        tail: int = 100,
        since: Optional[str] = None,
        grep: Optional[str] = None,
        level: Optional[str] = None,
        console: Optional[Console] = None
    ):
        """
        Stream logs from a service.
        
        Args:
            service: Service name to stream logs from
            follow: Continue streaming new logs
            tail: Number of lines to show from end
            since: Show logs since duration (e.g., 5m, 1h)
            grep: Filter logs by pattern
            level: Filter by log level
            console: Rich console for output
        """
        if console is None:
            console = Console()
        
        self.running = True
        
        # Header
        console.print(Panel.fit(
            f"[bold]Streaming logs from {service}[/bold]\n"
            f"[dim]Environment: {self.env} | Press Ctrl+C to stop[/dim]",
            border_style="blue"
        ))
        console.print()
        
        # Show historical logs (tail)
        for _ in range(min(tail, 20)):  # Limit to 20 for demo
            log = self._generate_log_line(service)
            
            # Apply level filter
            if level and log["level"].label != level:
                continue
            
            formatted = self._format_log_line(log, grep)
            if formatted:
                console.print(formatted)
        
        # Follow mode
        if follow:
            try:
                while self.running:
                    log = self._generate_log_line(service)
                    
                    # Apply level filter
                    if level and log["level"].label != level:
                        continue
                    
                    formatted = self._format_log_line(log, grep)
                    if formatted:
                        console.print(formatted)
                    
                    time.sleep(0.5)  # Simulate log rate
            except KeyboardInterrupt:
                self.running = False
                raise


class MetricsDashboard:
    """
    Metrics visualization dashboard.
    """
    
    def __init__(self, env: str = "production"):
        self.env = env
        self.metrics_history: Dict[str, List[Dict]] = {}
    
    def display_metrics(self, console: Console, service: Optional[str] = None):
        """Display metrics dashboard."""
        console.print(Panel.fit(
            f"[bold cyan]📊 Metrics Dashboard[/bold cyan]\n"
            f"[dim]Environment: {self.env.upper()}[/dim]",
            border_style="cyan"
        ))
        
        # HTTP Status Codes
        status_table = Table(title="HTTP Status Codes (last hour)", box=box.SIMPLE)
        status_table.add_column("Status", style="cyan")
        status_table.add_column("Count", justify="right")
        status_table.add_column("Percentage", justify="right")
        status_table.add_column("Bar")
        
        status_data = [
            ("2xx Success", 45231, "green"),
            ("3xx Redirect", 1234, "blue"),
            ("4xx Client Error", 567, "yellow"),
            ("5xx Server Error", 23, "red")
        ]
        
        total = sum(c for _, c, _ in status_data)
        for name, count, color in status_data:
            pct = count / total * 100
            bar_width = int(pct / 2)
            bar = "█" * bar_width
            status_table.add_row(
                name,
                f"{count:,}",
                f"{pct:.1f}%",
                f"[{color}]{bar}[/{color}]"
            )
        
        console.print(status_table)
        console.print()
        
        # Top Endpoints
        endpoints_table = Table(title="Top Endpoints", box=box.SIMPLE)
        endpoints_table.add_column("Endpoint", style="cyan")
        endpoints_table.add_column("Method", style="yellow")
        endpoints_table.add_column("Requests/min", justify="right")
        endpoints_table.add_column("Avg Latency", justify="right")
        endpoints_table.add_column("Error Rate", justify="right")
        
        endpoints = [
            ("/api/v1/users", "GET", 1250, 45, "0.01%"),
            ("/api/v1/auth/login", "POST", 890, 120, "0.05%"),
            ("/api/v1/billing/invoices", "GET", 650, 80, "0.00%"),
            ("/api/v1/analytics/events", "POST", 2100, 25, "0.02%"),
            ("/health", "GET", 5000, 5, "0.00%")
        ]
        
        for endpoint, method, rpm, latency, errors in endpoints:
            endpoints_table.add_row(
                endpoint,
                f"[bold]{method}[/bold]",
                f"{rpm:,}",
                f"{latency}ms",
                errors if errors == "0.00%" else f"[red]{errors}[/red]"
            )
        
        console.print(endpoints_table)
        console.print()
        
        # Database Metrics
        db_table = Table(title="Database Metrics", box=box.SIMPLE)
        db_table.add_column("Metric", style="cyan")
        db_table.add_column("Value", justify="right")
        db_table.add_column("Trend")
        
        db_metrics = [
            ("Connections", "245 / 500", "↑"),
            ("Queries/sec", "12,450", "→"),
            ("Slow queries", "3", "↓"),
            ("Cache hit rate", "94.2%", "→"),
            ("Replication lag", "12ms", "→")
        ]
        
        for metric, value, trend in db_metrics:
            trend_style = {"↑": "green", "↓": "green", "→": "dim"}.get(trend, "dim")
            db_table.add_row(metric, value, f"[{trend_style}]{trend}[/{trend_style}]")
        
        console.print(db_table)
    
    def display_alerts(self, console: Console):
        """Display active alerts."""
        console.print(Panel.fit(
            "[bold red]🔔 Active Alerts[/bold red]",
            border_style="red"
        ))
        
        # Simulated alerts
        alerts = [
            ("critical", "api-gateway", "High error rate detected", "5m ago"),
            ("warning", "cache-service", "Memory usage > 80%", "12m ago"),
            ("warning", "analytics-service", "Slow queries detected", "23m ago")
        ]
        
        if not alerts:
            console.print("[green]No active alerts[/green]")
            return
        
        table = Table(box=box.SIMPLE)
        table.add_column("Severity", width=10)
        table.add_column("Service", style="cyan")
        table.add_column("Message")
        table.add_column("Age", justify="right", style="dim")
        
        for severity, svc, message, age in alerts:
            sev_style = {"critical": "red", "warning": "yellow", "info": "blue"}.get(severity, "white")
            table.add_row(
                f"[{sev_style}]{severity.upper()}[/{sev_style}]",
                svc,
                message,
                age
            )
        
        console.print(table)


def display_live_dashboard(env: str = "production"):
    """Display a live updating dashboard."""
    monitor = Monitor(env=env)
    metrics = MetricsDashboard(env=env)
    
    console = Console()
    
    with Live(console=console, screen=True, refresh_per_second=1) as live:
        while True:
            layout = Layout()
            layout.split_column(
                Layout(name="header", size=3),
                Layout(name="body"),
                Layout(name="alerts", size=8)
            )
            
            # Header
            layout["header"].update(Panel(
                f"[bold cyan]🐉 DragonScope Live Dashboard[/bold cyan] | "
                f"Environment: [bold]{env.upper()}[/bold] | "
                f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                style="on blue"
            ))
            
            # Update and get service status
            monitor.update()
            
            # Build services panel
            table = Table(box=box.SIMPLE, show_header=True, header_style="bold")
            table.add_column("Service", width=18)
            table.add_column("Status", width=12)
            table.add_column("CPU", width=8)
            table.add_column("Memory", width=8)
            table.add_column("RPS", width=8)
            table.add_column("Latency", width=10)
            
            for svc, info in monitor.service_data.items():
                status_icon = monitor._get_status_icon(info.status)
                status_style = monitor._get_status_style(info.status)
                m = info.metrics
                
                table.add_row(
                    svc,
                    f"[{status_style}]{status_icon}[/{status_style}]",
                    f"{m.cpu_percent:.0f}%",
                    f"{m.memory_percent:.0f}%",
                    f"{m.requests_per_second:.0f}",
                    f"{m.response_time_ms:.0f}ms"
                )
            
            layout["body"].update(Panel(table, title="Services", border_style="cyan"))
            
            # Alerts panel
            alerts_text = Text()
            alerts_text.append("🔔 Alerts\n", style="bold red")
            alerts_text.append("• [red]CRITICAL[/red] api-gateway: High error rate (5m ago)\n")
            alerts_text.append("• [yellow]WARN[/yellow] cache-service: Memory > 80% (12m ago)\n")
            layout["alerts"].update(Panel(alerts_text, border_style="red"))
            
            live.update(layout)


if __name__ == "__main__":
    # Demo the monitoring functionality
    console = Console()
    
    monitor = Monitor(env="production")
    monitor.display_status(console)
    
    console.print("\n")
    
    dashboard = MetricsDashboard(env="production")
    dashboard.display_metrics(console)
    
    console.print("\n")
    
    dashboard.display_alerts(console)
