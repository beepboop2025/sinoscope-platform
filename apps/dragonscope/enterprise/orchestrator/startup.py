"""
DragonScope Enterprise - Startup Orchestrator

Service startup orchestration with dependency ordering, readiness probes,
graceful startup sequence, and bootstrap configuration.
"""

from __future__ import annotations

import asyncio
import enum
import logging
import signal
import sys
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Callable, Coroutine, Generic, TypeVar
from collections import defaultdict
from datetime import datetime
from enum import Enum, auto

import aiohttp
from aiohttp import ClientTimeout


logger = logging.getLogger("dragonscope.mso.startup")


T = TypeVar('T')


class StartupPhase(Enum):
    """Startup phases in order of execution."""
    INFRASTRUCTURE = auto()   # Phase 0: Database migrations, cache warming
    FOUNDATION = auto()       # Phase 1: Config, Discovery, Secrets
    PLATFORM = auto()         # Phase 2: Auth, Audit, Rate Limiter
    CORE = auto()             # Phase 3: Core business services
    EDGE = auto()             # Phase 4: API Gateway, WebSocket, BFF
    SUPPORTING = auto()       # Phase 5: Notification, Analytics, ML


class ServiceState(Enum):
    """Service startup states."""
    PENDING = "pending"
    STARTING = "starting"
    INITIALIZING = "initializing"
    READY = "ready"
    DEGRADED = "degraded"
    FAILED = "failed"
    STOPPING = "stopping"
    STOPPED = "stopped"


@dataclass
class ServiceDependency:
    """Service dependency definition."""
    service_name: str
    required: bool = True
    readiness_check: bool = True
    max_wait_seconds: float = 60.0
    retry_interval_seconds: float = 2.0


@dataclass
class ReadinessProbe:
    """Readiness probe configuration."""
    http_path: str = "/health/ready"
    initial_delay_seconds: float = 5.0
    period_seconds: float = 5.0
    timeout_seconds: float = 3.0
    success_threshold: int = 1
    failure_threshold: int = 3
    
    async def check(self, base_url: str, session: aiohttp.ClientSession) -> bool:
        """Execute readiness probe."""
        try:
            url = f"{base_url}{self.http_path}"
            async with session.get(url, timeout=ClientTimeout(total=self.timeout_seconds)) as response:
                return response.status == 200
        except Exception:
            return False


@dataclass
class LivenessProbe:
    """Liveness probe configuration."""
    http_path: str = "/health/live"
    period_seconds: float = 10.0
    timeout_seconds: float = 3.0
    failure_threshold: int = 3
    
    async def check(self, base_url: str, session: aiohttp.ClientSession) -> bool:
        """Execute liveness probe."""
        try:
            url = f"{base_url}{self.http_path}"
            async with session.get(url, timeout=ClientTimeout(total=self.timeout_seconds)) as response:
                return response.status == 200
        except Exception:
            return False


@dataclass
class ServiceDefinition:
    """Service definition for startup orchestration."""
    name: str
    phase: StartupPhase
    instance_id: str
    host: str
    port: int
    dependencies: list[ServiceDependency] = field(default_factory=list)
    readiness_probe: ReadinessProbe | None = None
    liveness_probe: LivenessProbe | None = None
    startup_timeout_seconds: float = 120.0
    shutdown_timeout_seconds: float = 30.0
    metadata: dict[str, Any] = field(default_factory=dict)
    environment: dict[str, str] = field(default_factory=dict)
    
    @property
    def address(self) -> str:
        """Full service address."""
        return f"{self.host}:{self.port}"
    
    @property
    def url(self) -> str:
        """Service URL."""
        scheme = "https" if self.metadata.get("tls", False) else "http"
        return f"{scheme}://{self.address}"


@dataclass
class StartupResult:
    """Result of service startup."""
    service_name: str
    instance_id: str
    success: bool
    state: ServiceState
    start_time: float
    end_time: float
    error_message: str = ""
    initialization_logs: list[str] = field(default_factory=list)
    
    @property
    def duration_seconds(self) -> float:
        """Startup duration."""
        return self.end_time - self.start_time


@dataclass
class PhaseResult:
    """Result of startup phase."""
    phase: StartupPhase
    start_time: float
    end_time: float
    service_results: list[StartupResult] = field(default_factory=list)
    
    @property
    def duration_seconds(self) -> float:
        """Phase duration."""
        return self.end_time - self.start_time
    
    @property
    def success_count(self) -> int:
        """Number of successful startups."""
        return sum(1 for r in self.service_results if r.success)
    
    @property
    def failure_count(self) -> int:
        """Number of failed startups."""
        return sum(1 for r in self.service_results if not r.success)


class BootstrapConfig:
    """Bootstrap configuration loader."""
    
    def __init__(self, config_path: str | None = None):
        self.config_path = config_path
        self._config: dict[str, Any] = {}
    
    async def load(self) -> dict[str, Any]:
        """Load bootstrap configuration."""
        # Load from environment
        self._config["environment"] = self._get_env("DRAGONSCOPE_ENV", "development")
        self._config["region"] = self._get_env("DRAGONSCOPE_REGION", "us-east-1")
        self._config["cluster"] = self._get_env("DRAGONSCOPE_CLUSTER", "main")
        
        # Load from file if exists
        if self.config_path:
            import json
            import yaml
            from pathlib import Path
            
            path = Path(self.config_path)
            if path.exists():
                with open(path) as f:
                    if path.suffix == '.json':
                        file_config = json.load(f)
                    else:
                        file_config = yaml.safe_load(f)
                self._config.update(file_config)
        
        logger.info(f"Bootstrap config loaded: environment={self._config.get('environment')}")
        return self._config
    
    def _get_env(self, key: str, default: str) -> str:
        """Get environment variable."""
        import os
        return os.getenv(key, default)
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value."""
        return self._config.get(key, default)


class ServiceStarter(ABC):
    """Abstract base class for service starters."""
    
    @abstractmethod
    async def start(self, service: ServiceDefinition) -> StartupResult:
        """Start a service."""
        pass
    
    @abstractmethod
    async def stop(self, service: ServiceDefinition) -> bool:
        """Stop a service."""
        pass
    
    @abstractmethod
    async def check_readiness(self, service: ServiceDefinition) -> bool:
        """Check if service is ready."""
        pass


class DockerServiceStarter(ServiceStarter):
    """Docker-based service starter."""
    
    def __init__(self):
        self._running_containers: dict[str, str] = {}
        self._session: aiohttp.ClientSession | None = None
    
    async def start(self, service: ServiceDefinition) -> StartupResult:
        """Start Docker container for service."""
        import subprocess
        
        start_time = time.time()
        logs = []
        
        try:
            # Build docker run command
            env_vars = " ".join(f'-e {k}="{v}"' for k, v in service.environment.items())
            
            cmd = [
                "docker", "run", "-d",
                "--name", f"{service.name}-{service.instance_id}",
                "-p", f"{service.port}:{service.port}",
                *env_vars.split(),
                f"dragonscope/{service.name}:latest"
            ]
            
            logs.append(f"Executing: {' '.join(cmd)}")
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60
            )
            
            if result.returncode == 0:
                container_id = result.stdout.strip()
                self._running_containers[f"{service.name}:{service.instance_id}"] = container_id
                
                return StartupResult(
                    service_name=service.name,
                    instance_id=service.instance_id,
                    success=True,
                    state=ServiceState.STARTING,
                    start_time=start_time,
                    end_time=time.time(),
                    initialization_logs=logs
                )
            else:
                return StartupResult(
                    service_name=service.name,
                    instance_id=service.instance_id,
                    success=False,
                    state=ServiceState.FAILED,
                    start_time=start_time,
                    end_time=time.time(),
                    error_message=result.stderr,
                    initialization_logs=logs
                )
                
        except Exception as e:
            return StartupResult(
                service_name=service.name,
                instance_id=service.instance_id,
                success=False,
                state=ServiceState.FAILED,
                start_time=start_time,
                end_time=time.time(),
                error_message=str(e),
                initialization_logs=logs
            )
    
    async def stop(self, service: ServiceDefinition) -> bool:
        """Stop Docker container."""
        import subprocess
        
        key = f"{service.name}:{service.instance_id}"
        container_id = self._running_containers.get(key)
        
        if not container_id:
            return True
        
        try:
            subprocess.run(
                ["docker", "stop", container_id],
                capture_output=True,
                timeout=service.shutdown_timeout_seconds
            )
            subprocess.run(["docker", "rm", container_id], capture_output=True)
            del self._running_containers[key]
            return True
        except Exception as e:
            logger.error(f"Failed to stop container for {service.name}: {e}")
            return False
    
    async def check_readiness(self, service: ServiceDefinition) -> bool:
        """Check if Docker service is ready."""
        if not self._session:
            self._session = aiohttp.ClientSession()
        
        if service.readiness_probe:
            return await service.readiness_probe.check(service.url, self._session)
        
        # Default check
        try:
            async with self._session.get(
                f"{service.url}/health",
                timeout=ClientTimeout(total=2)
            ) as response:
                return response.status == 200
        except Exception:
            return False


class KubernetesServiceStarter(ServiceStarter):
    """Kubernetes-based service starter."""
    
    def __init__(self, namespace: str = "dragonscope"):
        self.namespace = namespace
    
    async def start(self, service: ServiceDefinition) -> StartupResult:
        """Start Kubernetes deployment for service."""
        # Implementation would use kubernetes client
        # This is a placeholder
        start_time = time.time()
        
        logger.info(f"Starting K8s deployment for {service.name}")
        
        return StartupResult(
            service_name=service.name,
            instance_id=service.instance_id,
            success=True,
            state=ServiceState.STARTING,
            start_time=start_time,
            end_time=time.time()
        )
    
    async def stop(self, service: ServiceDefinition) -> bool:
        """Stop Kubernetes deployment."""
        logger.info(f"Stopping K8s deployment for {service.name}")
        return True
    
    async def check_readiness(self, service: ServiceDefinition) -> bool:
        """Check Kubernetes pod readiness."""
        # Implementation would check pod status
        return True


class ProcessServiceStarter(ServiceStarter):
    """Local process-based service starter."""
    
    def __init__(self):
        self._processes: dict[str, asyncio.subprocess.Process] = {}
        self._session: aiohttp.ClientSession | None = None
    
    async def start(self, service: ServiceDefinition) -> StartupResult:
        """Start service as local process."""
        start_time = time.time()
        logs = []
        
        try:
            # Get service entry point from metadata
            entry_point = service.metadata.get("entry_point", "python -m service")
            
            # Prepare environment
            env = {**dict(os.environ), **service.environment}
            env["SERVICE_NAME"] = service.name
            env["SERVICE_INSTANCE"] = service.instance_id
            env["SERVICE_PORT"] = str(service.port)
            
            # Start process
            cmd = entry_point.split()
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env
            )
            
            key = f"{service.name}:{service.instance_id}"
            self._processes[key] = process
            
            logs.append(f"Started process {process.pid} for {service.name}")
            
            return StartupResult(
                service_name=service.name,
                instance_id=service.instance_id,
                success=True,
                state=ServiceState.STARTING,
                start_time=start_time,
                end_time=time.time(),
                initialization_logs=logs
            )
            
        except Exception as e:
            return StartupResult(
                service_name=service.name,
                instance_id=service.instance_id,
                success=False,
                state=ServiceState.FAILED,
                start_time=start_time,
                end_time=time.time(),
                error_message=str(e),
                initialization_logs=logs
            )
    
    async def stop(self, service: ServiceDefinition) -> bool:
        """Stop local process."""
        key = f"{service.name}:{service.instance_id}"
        process = self._processes.get(key)
        
        if not process:
            return True
        
        try:
            process.terminate()
            await asyncio.wait_for(process.wait(), timeout=service.shutdown_timeout_seconds)
            
            if process.returncode is None:
                process.kill()
                await process.wait()
            
            del self._processes[key]
            return True
            
        except Exception as e:
            logger.error(f"Failed to stop process for {service.name}: {e}")
            return False
    
    async def check_readiness(self, service: ServiceDefinition) -> bool:
        """Check if local process is ready."""
        if not self._session:
            self._session = aiohttp.ClientSession()
        
        if service.readiness_probe:
            return await service.readiness_probe.check(service.url, self._session)
        
        try:
            async with self._session.get(
                f"{service.url}/health",
                timeout=ClientTimeout(total=2)
            ) as response:
                return response.status == 200
        except Exception:
            return False


class StartupOrchestrator:
    """
    Enterprise Startup Orchestrator for DragonScope.
    
    Coordinates service startup with:
    - Dependency ordering
    - Readiness probes
    - Graceful startup sequence
    - Bootstrap configuration
    """
    
    def __init__(
        self,
        starter: ServiceStarter | None = None,
        bootstrap_config: BootstrapConfig | None = None
    ):
        self.starter = starter or ProcessServiceStarter()
        self.bootstrap = bootstrap_config or BootstrapConfig()
        
        # Service registry
        self._services: dict[str, ServiceDefinition] = {}
        self._service_states: dict[str, ServiceState] = {}
        self._service_results: dict[str, StartupResult] = {}
        
        # Phase tracking
        self._phase_order = [
            StartupPhase.INFRASTRUCTURE,
            StartupPhase.FOUNDATION,
            StartupPhase.PLATFORM,
            StartupPhase.CORE,
            StartupPhase.EDGE,
            StartupPhase.SUPPORTING
        ]
        
        # HTTP session for health checks
        self._session: aiohttp.ClientSession | None = None
        
        # Event handlers
        self._on_service_start: list[Callable[[str], Coroutine[Any, Any, None]]] = []
        self._on_service_ready: list[Callable[[str], Coroutine[Any, Any, None]]] = []
        self._on_service_failed: list[Callable[[str, str], Coroutine[Any, Any, None]]] = []
        
        # Shutdown handling
        self._shutdown_event = asyncio.Event()
        self._is_shutting_down = False
        
        logger.info("StartupOrchestrator initialized")
    
    async def start(self) -> None:
        """Initialize the orchestrator."""
        # Load bootstrap config
        await self.bootstrap.load()
        
        # Create HTTP session
        self._session = aiohttp.ClientSession()
        
        # Setup signal handlers
        self._setup_signal_handlers()
        
        logger.info("StartupOrchestrator started")
    
    async def stop(self) -> None:
        """Stop the orchestrator."""
        self._is_shutting_down = True
        
        if self._session:
            await self._session.close()
        
        logger.info("StartupOrchestrator stopped")
    
    def _setup_signal_handlers(self) -> None:
        """Setup signal handlers for graceful shutdown."""
        try:
            loop = asyncio.get_event_loop()
            
            for sig in (signal.SIGTERM, signal.SIGINT):
                loop.add_signal_handler(sig, lambda: asyncio.create_task(self._signal_handler()))
                
        except NotImplementedError:
            # Windows doesn't support add_signal_handler
            pass
    
    async def _signal_handler(self) -> None:
        """Handle shutdown signals."""
        logger.info("Shutdown signal received")
        self._shutdown_event.set()
        await self.graceful_shutdown()
    
    def register_service(self, service: ServiceDefinition) -> None:
        """Register a service for startup orchestration."""
        key = f"{service.name}:{service.instance_id}"
        self._services[key] = service
        self._service_states[key] = ServiceState.PENDING
        
        logger.debug(f"Registered service: {key} (phase: {service.phase.name})")
    
    def register_services(self, services: list[ServiceDefinition]) -> None:
        """Register multiple services."""
        for service in services:
            self.register_service(service)
    
    async def execute_startup(self) -> dict[StartupPhase, PhaseResult]:
        """
        Execute the full startup sequence.
        
        Returns:
            Results for each phase
        """
        logger.info("Starting DragonScope Enterprise services...")
        overall_start = time.time()
        
        phase_results: dict[StartupPhase, PhaseResult] = {}
        
        for phase in self._phase_order:
            if self._is_shutting_down or self._shutdown_event.is_set():
                logger.warning("Startup interrupted by shutdown signal")
                break
            
            # Get services for this phase
            phase_services = [
                s for s in self._services.values()
                if s.phase == phase
            ]
            
            if not phase_services:
                continue
            
            logger.info(f"Starting phase {phase.name} with {len(phase_services)} services...")
            
            phase_start = time.time()
            results = await self._start_phase(phase, phase_services)
            
            phase_results[phase] = PhaseResult(
                phase=phase,
                start_time=phase_start,
                end_time=time.time(),
                service_results=results
            )
            
            # Check for critical failures
            critical_failures = [
                r for r in results
                if not r.success and self._services[f"{r.service_name}:{r.instance_id}"].dependencies
            ]
            
            if critical_failures:
                logger.error(f"Phase {phase.name} had {len(critical_failures)} critical failures")
                # Continue but log warnings
        
        overall_duration = time.time() - overall_start
        
        # Log summary
        total_services = len(self._services)
        successful = sum(r.success_count for r in phase_results.values())
        failed = sum(r.failure_count for r in phase_results.values())
        
        logger.info(
            f"Startup complete: {successful}/{total_services} services started successfully "
            f"in {overall_duration:.1f}s"
        )
        
        return phase_results
    
    async def _start_phase(
        self,
        phase: StartupPhase,
        services: list[ServiceDefinition]
    ) -> list[StartupResult]:
        """Start all services in a phase."""
        results = []
        
        # Sort services by dependency count (start leaf services first)
        sorted_services = sorted(
            services,
            key=lambda s: len(s.dependencies)
        )
        
        for service in sorted_services:
            if self._is_shutting_down:
                break
            
            result = await self._start_service(service)
            results.append(result)
        
        return results
    
    async def _start_service(self, service: ServiceDefinition) -> StartupResult:
        """Start a single service with dependency resolution."""
        key = f"{service.name}:{service.instance_id}"
        
        logger.info(f"Starting service: {key}")
        self._service_states[key] = ServiceState.STARTING
        
        # Wait for dependencies
        for dependency in service.dependencies:
            dep_ready = await self._wait_for_dependency(dependency)
            if not dep_ready and dependency.required:
                error_msg = f"Required dependency not ready: {dependency.service_name}"
                logger.error(error_msg)
                
                result = StartupResult(
                    service_name=service.name,
                    instance_id=service.instance_id,
                    success=False,
                    state=ServiceState.FAILED,
                    start_time=time.time(),
                    end_time=time.time(),
                    error_message=error_msg
                )
                self._service_results[key] = result
                self._service_states[key] = ServiceState.FAILED
                
                for handler in self._on_service_failed:
                    await handler(key, error_msg)
                
                return result
        
        # Start the service
        self._service_states[key] = ServiceState.INITIALIZING
        
        for handler in self._on_service_start:
            await handler(key)
        
        result = await self.starter.start(service)
        
        if not result.success:
            self._service_states[key] = ServiceState.FAILED
            self._service_results[key] = result
            
            for handler in self._on_service_failed:
                await handler(key, result.error_message)
            
            return result
        
        # Wait for readiness
        if service.readiness_probe:
            ready = await self._wait_for_readiness(service)
            if ready:
                self._service_states[key] = ServiceState.READY
                result.state = ServiceState.READY
                
                for handler in self._on_service_ready:
                    await handler(key)
                
                logger.info(f"Service ready: {key}")
            else:
                self._service_states[key] = ServiceState.DEGRADED
                result.state = ServiceState.DEGRADED
                result.error_message = "Service did not become ready in time"
                logger.warning(f"Service degraded: {key}")
        else:
            self._service_states[key] = ServiceState.READY
            result.state = ServiceState.READY
        
        self._service_results[key] = result
        return result
    
    async def _wait_for_dependency(self, dependency: ServiceDependency) -> bool:
        """Wait for a dependency to be ready."""
        start_time = time.time()
        
        while time.time() - start_time < dependency.max_wait_seconds:
            # Check if any instance of the dependency is ready
            for key, state in self._service_states.items():
                if key.startswith(f"{dependency.service_name}:"):
                    if state == ServiceState.READY:
                        return True
            
            await asyncio.sleep(dependency.retry_interval_seconds)
        
        return False
    
    async def _wait_for_readiness(self, service: ServiceDefinition) -> bool:
        """Wait for service to become ready."""
        if not service.readiness_probe:
            return True
        
        # Initial delay
        await asyncio.sleep(service.readiness_probe.initial_delay_seconds)
        
        start_time = time.time()
        success_count = 0
        failure_count = 0
        
        while time.time() - start_time < service.startup_timeout_seconds:
            if self._is_shutting_down:
                return False
            
            is_ready = await self.starter.check_readiness(service)
            
            if is_ready:
                success_count += 1
                if success_count >= service.readiness_probe.success_threshold:
                    return True
            else:
                failure_count += 1
                if failure_count >= service.readiness_probe.failure_threshold:
                    return False
            
            await asyncio.sleep(service.readiness_probe.period_seconds)
        
        return False
    
    async def graceful_shutdown(self) -> None:
        """Execute graceful shutdown of all services."""
        logger.info("Starting graceful shutdown...")
        
        self._is_shutting_down = True
        
        # Stop services in reverse phase order
        for phase in reversed(self._phase_order):
            phase_services = [
                s for s in self._services.values()
                if s.phase == phase
            ]
            
            for service in phase_services:
                key = f"{service.name}:{service.instance_id}"
                
                if self._service_states.get(key) in (ServiceState.READY, ServiceState.DEGRADED):
                    logger.info(f"Stopping service: {key}")
                    self._service_states[key] = ServiceState.STOPPING
                    
                    await self.starter.stop(service)
                    
                    self._service_states[key] = ServiceState.STOPPED
        
        logger.info("Graceful shutdown complete")
    
    def get_service_state(self, service_name: str, instance_id: str) -> ServiceState:
        """Get current state of a service."""
        key = f"{service_name}:{instance_id}"
        return self._service_states.get(key, ServiceState.PENDING)
    
    def get_all_states(self) -> dict[str, ServiceState]:
        """Get states of all services."""
        return dict(self._service_states)
    
    def on_service_start(self, handler: Callable[[str], Coroutine[Any, Any, None]]) -> None:
        """Register handler for service start events."""
        self._on_service_start.append(handler)
    
    def on_service_ready(self, handler: Callable[[str], Coroutine[Any, Any, None]]) -> None:
        """Register handler for service ready events."""
        self._on_service_ready.append(handler)
    
    def on_service_failed(self, handler: Callable[[str, str], Coroutine[Any, Any, None]]) -> None:
        """Register handler for service failure events."""
        self._on_service_failed.append(handler)
    
    def get_startup_summary(self, phase_results: dict[StartupPhase, PhaseResult]) -> dict[str, Any]:
        """Get summary of startup results."""
        total_duration = sum(r.duration_seconds for r in phase_results.values())
        total_services = sum(len(r.service_results) for r in phase_results.values())
        successful = sum(r.success_count for r in phase_results.values())
        
        return {
            "total_duration_seconds": round(total_duration, 2),
            "total_services": total_services,
            "successful": successful,
            "failed": total_services - successful,
            "phases": {
                phase.name: {
                    "duration_seconds": round(result.duration_seconds, 2),
                    "services": len(result.service_results),
                    "successful": result.success_count,
                    "failed": result.failure_count
                }
                for phase, result in phase_results.items()
            }
        }


# Import os for ProcessServiceStarter
import os


# Singleton instance
_orchestrator_instance: StartupOrchestrator | None = None


def get_orchestrator() -> StartupOrchestrator:
    """Get singleton StartupOrchestrator instance."""
    global _orchestrator_instance
    if _orchestrator_instance is None:
        _orchestrator_instance = StartupOrchestrator()
    return _orchestrator_instance


def set_orchestrator(orchestrator: StartupOrchestrator) -> None:
    """Set singleton StartupOrchestrator instance."""
    global _orchestrator_instance
    _orchestrator_instance = orchestrator
