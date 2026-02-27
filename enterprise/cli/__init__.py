"""
DragonScope Enterprise CLI
==========================

A professional command-line interface for managing DragonScope Enterprise deployments.

Usage:
    from dragonscope import DeployManager, Monitor
    
    # Deploy to production
    deployer = DeployManager("production")
    result = deployer.deploy(version="2.5.0", strategy="blue-green")
    
    # Monitor services
    monitor = Monitor(env="production")
    monitor.display_status(console)

Available Commands:
    ds status           Show service status dashboard
    ds logs             Stream logs from services
    ds deploy           Deploy to environment
    ds config           Manage configuration
    ds db               Database operations
    ds cache            Cache management
    ds backup           Create backups
    ds restore          Restore from backup
    ds monitor          Open monitoring dashboards
    ds test             Run test suite
    ds shell            Open shell in container
"""

__version__ = "2.5.1"
__author__ = "DragonScope Engineering"
__license__ = "Proprietary"

from .deploy import DeployManager, DeploymentError, DeploymentStrategy
from .monitoring import Monitor, LogStreamer, MetricsDashboard

__all__ = [
    "DeployManager",
    "DeploymentError", 
    "DeploymentStrategy",
    "Monitor",
    "LogStreamer",
    "MetricsDashboard"
]
