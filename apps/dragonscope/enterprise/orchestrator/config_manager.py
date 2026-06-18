"""
DragonScope Enterprise - Configuration Manager

Hierarchical configuration management with environment-based configs,
feature flags, dynamic reloading, and validation schemas.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import time
import yaml
from dataclasses import dataclass, field
from enum import Enum, auto
from pathlib import Path
from typing import Any, Callable, Coroutine, Generic, TypeVar, get_type_hints
from collections import defaultdict
from contextvars import ContextVar
from functools import wraps

import jsonschema
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileModifiedEvent


logger = logging.getLogger("dragonscope.mso.config")


T = TypeVar('T')


# Context variable for current environment
_current_environment: ContextVar[str] = ContextVar('environment', default='development')


class ConfigEnvironment(Enum):
    """Configuration environments."""
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"
    TESTING = "testing"


class ConfigScope(Enum):
    """Configuration scope levels."""
    DEFAULT = auto()      # Base defaults
    ENVIRONMENT = auto()  # Environment-specific
    SERVICE = auto()      # Service-specific
    INSTANCE = auto()     # Instance-specific
    OVERRIDE = auto()     # Emergency overrides


@dataclass
class ConfigChangeEvent:
    """Configuration change event."""
    path: str
    old_value: Any
    new_value: Any
    scope: ConfigScope
    timestamp: float = field(default_factory=time.time)


@dataclass
class FeatureFlag:
    """Feature flag definition."""
    name: str
    enabled: bool
    description: str = ""
    rollout_percentage: float = 100.0
    target_users: list[str] = field(default_factory=list)
    target_groups: list[str] = field(default_factory=list)
    conditions: dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    
    def is_enabled_for(self, user_id: str | None = None, groups: list[str] | None = None) -> bool:
        """Check if feature is enabled for a specific user."""
        if not self.enabled:
            return False
        
        # Check user-specific targeting
        if user_id and self.target_users:
            return user_id in self.target_users
        
        # Check group targeting
        if groups and self.target_groups:
            return any(g in self.target_groups for g in groups)
        
        # Check percentage rollout
        if self.rollout_percentage < 100.0 and user_id:
            user_hash = int(hashlib.md5(f"{self.name}:{user_id}".encode()).hexdigest(), 16)
            user_percentage = (user_hash % 10000) / 100.0
            return user_percentage < self.rollout_percentage
        
        return True
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "enabled": self.enabled,
            "description": self.description,
            "rollout_percentage": self.rollout_percentage,
            "target_users": self.target_users,
            "target_groups": self.target_groups,
            "conditions": self.conditions,
            "created_at": self.created_at,
            "updated_at": self.updated_at
        }
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> FeatureFlag:
        """Create from dictionary."""
        return cls(
            name=data["name"],
            enabled=data["enabled"],
            description=data.get("description", ""),
            rollout_percentage=data.get("rollout_percentage", 100.0),
            target_users=data.get("target_users", []),
            target_groups=data.get("target_groups", []),
            conditions=data.get("conditions", {}),
            created_at=data.get("created_at", time.time()),
            updated_at=data.get("updated_at", time.time())
        )


class ConfigValidator:
    """Configuration validation using JSON Schema."""
    
    def __init__(self):
        self._schemas: dict[str, dict[str, Any]] = {}
    
    def register_schema(self, name: str, schema: dict[str, Any]) -> None:
        """Register a validation schema."""
        self._schemas[name] = schema
    
    def validate(self, config: dict[str, Any], schema_name: str) -> list[str]:
        """
        Validate configuration against schema.
        
        Returns:
            List of validation errors (empty if valid)
        """
        if schema_name not in self._schemas:
            return []
        
        schema = self._schemas[schema_name]
        validator = jsonschema.Draft7Validator(schema)
        errors = list(validator.iter_errors(config))
        
        return [f"{e.path}: {e.message}" for e in errors]
    
    def validate_type(self, value: Any, expected_type: type) -> bool:
        """Validate value against expected type."""
        if expected_type == Any:
            return True
        
        origin = getattr(expected_type, '__origin__', None)
        
        if origin is None:
            return isinstance(value, expected_type)
        
        # Handle generic types
        if origin is list:
            args = getattr(expected_type, '__args__', (Any,))
            if not isinstance(value, list):
                return False
            return all(self.validate_type(item, args[0]) for item in value)
        
        if origin is dict:
            args = getattr(expected_type, '__args__', (str, Any))
            if not isinstance(value, dict):
                return False
            return all(
                self.validate_type(k, args[0]) and self.validate_type(v, args[1])
                for k, v in value.items()
            )
        
        if origin is tuple:
            args = getattr(expected_type, '__args__', ())
            if not isinstance(value, tuple) or len(value) != len(args):
                return False
            return all(self.validate_type(v, t) for v, t in zip(value, args))
        
        return isinstance(value, origin)


class ConfigFileHandler(FileSystemEventHandler):
    """File system event handler for config changes."""
    
    def __init__(self, callback: Callable[[str], Coroutine[Any, Any, None]]):
        self.callback = callback
    
    def on_modified(self, event: FileModifiedEvent) -> None:
        if not event.is_directory and event.src_path.endswith(('.yml', '.yaml', '.json')):
            asyncio.create_task(self.callback(event.src_path))


class ConfigManager:
    """
    Enterprise Configuration Manager for DragonScope.
    
    Provides hierarchical configuration with:
    - Environment-based configuration
    - Feature flags
    - Dynamic reloading
    - Schema validation
    - Secret management
    """
    
    def __init__(
        self,
        config_dir: str | Path = "./config",
        environment: str | None = None,
        auto_reload: bool = True
    ):
        self.config_dir = Path(config_dir)
        self.environment = environment or os.getenv("DRAGONSCOPE_ENV", "development")
        self.auto_reload = auto_reload
        
        # Configuration stores by scope
        self._configs: dict[ConfigScope, dict[str, Any]] = {
            ConfigScope.DEFAULT: {},
            ConfigScope.ENVIRONMENT: {},
            ConfigScope.SERVICE: {},
            ConfigScope.INSTANCE: {},
            ConfigScope.OVERRIDE: {}
        }
        
        # Feature flags
        self._feature_flags: dict[str, FeatureFlag] = {}
        
        # Validator
        self._validator = ConfigValidator()
        
        # Change handlers
        self._change_handlers: list[Callable[[ConfigChangeEvent], Coroutine[Any, Any, None]]] = []
        
        # File watching
        self._observer: Observer | None = None
        self._config_hashes: dict[str, str] = {}
        
        # Cache
        self._cache: dict[str, Any] = {}
        self._cache_timestamps: dict[str, float] = {}
        self._cache_ttl = 5.0  # seconds
        
        # Locks
        self._lock = asyncio.Lock()
        
        logger.info(f"ConfigManager initialized for environment: {self.environment}")
    
    async def start(self) -> None:
        """Start the configuration manager."""
        # Load initial configuration
        await self._load_all_configs()
        
        # Start file watching
        if self.auto_reload:
            self._start_file_watching()
        
        logger.info("ConfigManager started")
    
    async def stop(self) -> None:
        """Stop the configuration manager."""
        if self._observer:
            self._observer.stop()
            self._observer.join()
        
        logger.info("ConfigManager stopped")
    
    def _start_file_watching(self) -> None:
        """Start watching configuration files for changes."""
        if not self.config_dir.exists():
            return
        
        handler = ConfigFileHandler(self._on_file_changed)
        self._observer = Observer()
        self._observer.schedule(handler, str(self.config_dir), recursive=True)
        self._observer.start()
        logger.info(f"Started watching config directory: {self.config_dir}")
    
    async def _on_file_changed(self, file_path: str) -> None:
        """Handle configuration file changes."""
        try:
            with open(file_path, 'r') as f:
                content = f.read()
            
            # Check if actually changed (avoid duplicate events)
            content_hash = hashlib.md5(content.encode()).hexdigest()
            if self._config_hashes.get(file_path) == content_hash:
                return
            
            self._config_hashes[file_path] = content_hash
            
            logger.info(f"Configuration file changed: {file_path}")
            await self._reload_config(Path(file_path))
            
        except Exception as e:
            logger.error(f"Error handling config change: {e}")
    
    async def _load_all_configs(self) -> None:
        """Load all configuration files."""
        if not self.config_dir.exists():
            logger.warning(f"Config directory does not exist: {self.config_dir}")
            return
        
        # Load default configs
        defaults_dir = self.config_dir / "defaults"
        if defaults_dir.exists():
            await self._load_directory(defaults_dir, ConfigScope.DEFAULT)
        
        # Load environment-specific configs
        env_dir = self.config_dir / "environments" / self.environment
        if env_dir.exists():
            await self._load_directory(env_dir, ConfigScope.ENVIRONMENT)
        
        # Load service configs
        services_dir = self.config_dir / "services"
        if services_dir.exists():
            await self._load_directory(services_dir, ConfigScope.SERVICE)
        
        # Load overrides
        overrides_dir = self.config_dir / "overrides"
        if overrides_dir.exists():
            await self._load_directory(overrides_dir, ConfigScope.OVERRIDE)
        
        # Load feature flags
        await self._load_feature_flags()
        
        logger.info("All configurations loaded")
    
    async def _load_directory(self, directory: Path, scope: ConfigScope) -> None:
        """Load all config files from a directory."""
        for config_file in directory.rglob("*.yml"):
            await self._load_config_file(config_file, scope)
        for config_file in directory.rglob("*.yaml"):
            await self._load_config_file(config_file, scope)
        for config_file in directory.rglob("*.json"):
            await self._load_config_file(config_file, scope)
    
    async def _load_config_file(self, file_path: Path, scope: ConfigScope) -> None:
        """Load a single configuration file."""
        try:
            with open(file_path, 'r') as f:
                if file_path.suffix == '.json':
                    data = json.load(f)
                else:
                    data = yaml.safe_load(f) or {}
            
            # Store hash for change detection
            with open(file_path, 'r') as f:
                content = f.read()
            self._config_hashes[str(file_path)] = hashlib.md5(content.encode()).hexdigest()
            
            # Merge into scope
            key = self._get_config_key(file_path, scope)
            self._configs[scope][key] = data
            
            logger.debug(f"Loaded config: {file_path} (scope: {scope.name})")
            
        except Exception as e:
            logger.error(f"Failed to load config file {file_path}: {e}")
    
    async def _reload_config(self, file_path: Path) -> None:
        """Reload a configuration file."""
        # Determine scope from path
        scope = self._get_scope_from_path(file_path)
        
        # Get old values for change detection
        old_config = self._get_merged_config()
        
        # Reload file
        await self._load_config_file(file_path, scope)
        
        # Get new values
        new_config = self._get_merged_config()
        
        # Find changes and notify handlers
        changes = self._detect_changes(old_config, new_config)
        for change in changes:
            for handler in self._change_handlers:
                try:
                    await handler(change)
                except Exception as e:
                    logger.error(f"Change handler error: {e}")
        
        # Clear cache
        self._cache.clear()
        self._cache_timestamps.clear()
    
    def _get_scope_from_path(self, file_path: Path) -> ConfigScope:
        """Determine config scope from file path."""
        path_str = str(file_path)
        
        if "overrides" in path_str:
            return ConfigScope.OVERRIDE
        elif "services" in path_str:
            return ConfigScope.SERVICE
        elif "environments" in path_str:
            return ConfigScope.ENVIRONMENT
        elif "defaults" in path_str:
            return ConfigScope.DEFAULT
        
        return ConfigScope.DEFAULT
    
    def _get_config_key(self, file_path: Path, scope: ConfigScope) -> str:
        """Generate config key from file path."""
        relative = file_path.relative_to(self.config_dir)
        return str(relative.with_suffix(''))
    
    def _get_merged_config(self) -> dict[str, Any]:
        """Get fully merged configuration."""
        result = {}
        
        # Merge in priority order
        for scope in [
            ConfigScope.DEFAULT,
            ConfigScope.ENVIRONMENT,
            ConfigScope.SERVICE,
            ConfigScope.INSTANCE,
            ConfigScope.OVERRIDE
        ]:
            for config in self._configs[scope].values():
                self._deep_merge(result, config)
        
        return result
    
    def _deep_merge(self, base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
        """Deep merge two dictionaries."""
        for key, value in override.items():
            if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                self._deep_merge(base[key], value)
            else:
                base[key] = value
        return base
    
    def _detect_changes(
        self,
        old: dict[str, Any],
        new: dict[str, Any],
        path: str = ""
    ) -> list[ConfigChangeEvent]:
        """Detect changes between old and new config."""
        changes = []
        all_keys = set(old.keys()) | set(new.keys())
        
        for key in all_keys:
            current_path = f"{path}.{key}" if path else key
            old_val = old.get(key)
            new_val = new.get(key)
            
            if old_val != new_val:
                if isinstance(old_val, dict) and isinstance(new_val, dict):
                    changes.extend(self._detect_changes(old_val, new_val, current_path))
                else:
                    changes.append(ConfigChangeEvent(
                        path=current_path,
                        old_value=old_val,
                        new_value=new_val,
                        scope=ConfigScope.ENVIRONMENT
                    ))
        
        return changes
    
    async def _load_feature_flags(self) -> None:
        """Load feature flags configuration."""
        flags_file = self.config_dir / "feature-flags.yml"
        if not flags_file.exists():
            flags_file = self.config_dir / "feature_flags.yml"
        
        if flags_file.exists():
            try:
                with open(flags_file, 'r') as f:
                    data = yaml.safe_load(f) or {}
                
                for name, flag_data in data.get("flags", {}).items():
                    flag_data["name"] = name
                    self._feature_flags[name] = FeatureFlag.from_dict(flag_data)
                
                logger.info(f"Loaded {len(self._feature_flags)} feature flags")
                
            except Exception as e:
                logger.error(f"Failed to load feature flags: {e}")
    
    def get(
        self,
        key: str,
        default: T | None = None,
        type_hint: type[T] | None = None,
        environment: str | None = None
    ) -> T | None:
        """
        Get configuration value by key.
        
        Args:
            key: Dot-notation key (e.g., "database.primary.host")
            default: Default value if not found
            type_hint: Expected type for validation
            environment: Override environment (uses current if not specified)
        
        Returns:
            Configuration value or default
        """
        # Check cache
        cache_key = f"{environment or self.environment}:{key}"
        if cache_key in self._cache:
            if time.time() - self._cache_timestamps.get(cache_key, 0) < self._cache_ttl:
                return self._cache[cache_key]
        
        # Get merged config
        config = self._get_merged_config()
        
        # Navigate key path
        value = config
        for part in key.split('.'):
            if isinstance(value, dict) and part in value:
                value = value[part]
            else:
                return default
        
        # Validate type
        if type_hint and not self._validator.validate_type(value, type_hint):
            logger.warning(f"Config type mismatch for {key}: expected {type_hint}, got {type(value)}")
            return default
        
        # Process environment variables
        if isinstance(value, str) and value.startswith('${') and value.endswith('}'):
            value = self._resolve_env_var(value)
        
        # Cache result
        self._cache[cache_key] = value
        self._cache_timestamps[cache_key] = time.time()
        
        return value
    
    def get_required(self, key: str, type_hint: type[T] | None = None) -> T:
        """Get required configuration value."""
        value = self.get(key, type_hint=type_hint)
        if value is None:
            raise ConfigurationError(f"Required configuration missing: {key}")
        return value
    
    def get_config(self, section: str, environment: str | None = None) -> dict[str, Any]:
        """Get entire configuration section."""
        return self.get(section, default={}, type_hint=dict) or {}
    
    def _resolve_env_var(self, value: str) -> str:
        """Resolve environment variable placeholder."""
        # Format: ${VAR} or ${VAR:default}
        inner = value[2:-1]  # Remove ${ and }
        
        if ':' in inner:
            var_name, default = inner.split(':', 1)
            return os.getenv(var_name, default)
        else:
            env_value = os.getenv(inner)
            if env_value is None:
                logger.warning(f"Environment variable not set: {inner}")
            return env_value or ""
    
    def is_feature_enabled(
        self,
        flag_name: str,
        user_id: str | None = None,
        groups: list[str] | None = None
    ) -> bool:
        """
        Check if a feature flag is enabled.
        
        Args:
            flag_name: Feature flag name
            user_id: Optional user ID for targeted rollout
            groups: Optional user groups for targeting
        
        Returns:
            True if feature is enabled
        """
        if flag_name not in self._feature_flags:
            return False
        
        return self._feature_flags[flag_name].is_enabled_for(user_id, groups)
    
    def get_feature_flag(self, flag_name: str) -> FeatureFlag | None:
        """Get feature flag definition."""
        return self._feature_flags.get(flag_name)
    
    def set_feature_flag(self, flag: FeatureFlag) -> None:
        """Set or update a feature flag."""
        flag.updated_at = time.time()
        self._feature_flags[flag.name] = flag
        logger.info(f"Updated feature flag: {flag.name}")
    
    def get_all_feature_flags(self) -> dict[str, FeatureFlag]:
        """Get all feature flags."""
        return dict(self._feature_flags)
    
    def register_schema(self, name: str, schema: dict[str, Any]) -> None:
        """Register a validation schema."""
        self._validator.register_schema(name, schema)
    
    def validate(self, config: dict[str, Any], schema_name: str) -> list[str]:
        """Validate configuration against schema."""
        return self._validator.validate(config, schema_name)
    
    def on_change(
        self,
        handler: Callable[[ConfigChangeEvent], Coroutine[Any, Any, None]]
    ) -> None:
        """Register a configuration change handler."""
        self._change_handlers.append(handler)
    
    def get_environment(self) -> str:
        """Get current environment."""
        return self.environment
    
    def set_environment(self, environment: str) -> None:
        """Change current environment."""
        self.environment = environment
        _current_environment.set(environment)
        self._cache.clear()
        logger.info(f"Environment changed to: {environment}")
    
    def get_all_config(self) -> dict[str, Any]:
        """Get complete merged configuration."""
        return self._get_merged_config()
    
    def export(self, format: str = "yaml") -> str:
        """Export configuration to string."""
        config = self._get_merged_config()
        
        if format == "yaml":
            return yaml.dump(config, default_flow_style=False)
        elif format == "json":
            return json.dumps(config, indent=2)
        else:
            raise ValueError(f"Unsupported format: {format}")
    
    def inject_config(self, prefix: str = "DS") -> Callable:
        """
        Decorator to inject configuration into function arguments.
        
        Usage:
            @config_manager.inject_config()
            async def my_function(database_host: str, database_port: int):
                ...
        """
        def decorator(func: Callable) -> Callable:
            sig = get_type_hints(func)
            
            @wraps(func)
            async def async_wrapper(*args, **kwargs):
                for param_name, param_type in sig.items():
                    if param_name not in kwargs:
                        config_key = f"{prefix.lower()}.{param_name}"
                        value = self.get(config_key, type_hint=param_type)
                        if value is not None:
                            kwargs[param_name] = value
                return await func(*args, **kwargs)
            
            @wraps(func)
            def sync_wrapper(*args, **kwargs):
                for param_name, param_type in sig.items():
                    if param_name not in kwargs:
                        config_key = f"{prefix.lower()}.{param_name}"
                        value = self.get(config_key, type_hint=param_type)
                        if value is not None:
                            kwargs[param_name] = value
                return func(*args, **kwargs)
            
            return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper
        
        return decorator


class ConfigurationError(Exception):
    """Raised when configuration is invalid or missing."""
    pass


# Singleton instance
_config_instance: ConfigManager | None = None


def get_config() -> ConfigManager:
    """Get singleton ConfigManager instance."""
    global _config_instance
    if _config_instance is None:
        _config_instance = ConfigManager()
    return _config_instance


def set_config(config: ConfigManager) -> None:
    """Set singleton ConfigManager instance."""
    global _config_instance
    _config_instance = config
