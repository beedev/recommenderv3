"""
Configuration Monitor Service
Provides runtime validation, monitoring, and health checks for dynamic configuration
"""

import logging
import asyncio
from typing import Dict, Any, Optional, List
from datetime import datetime
from pathlib import Path
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class ConfigStatus(str, Enum):
    """Configuration health status"""
    HEALTHY = "healthy"
    WARNING = "warning"
    ERROR = "error"
    UNKNOWN = "unknown"


@dataclass
class ConfigHealth:
    """Health status for a configuration file"""
    config_name: str
    status: ConfigStatus
    last_validated: datetime
    validation_errors: List[str] = field(default_factory=list)
    validation_warnings: List[str] = field(default_factory=list)
    file_size_bytes: Optional[int] = None
    last_modified: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API responses"""
        return {
            "config_name": self.config_name,
            "status": self.status.value,
            "last_validated": self.last_validated.isoformat(),
            "validation_errors": self.validation_errors,
            "validation_warnings": self.validation_warnings,
            "file_size_bytes": self.file_size_bytes,
            "last_modified": self.last_modified.isoformat() if self.last_modified else None
        }


@dataclass
class SystemHealth:
    """Overall system configuration health"""
    status: ConfigStatus
    configs: Dict[str, ConfigHealth]
    total_configs: int
    healthy_configs: int
    warning_configs: int
    error_configs: int
    last_check: datetime

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API responses"""
        return {
            "status": self.status.value,
            "configs": {name: health.to_dict() for name, health in self.configs.items()},
            "summary": {
                "total_configs": self.total_configs,
                "healthy": self.healthy_configs,
                "warnings": self.warning_configs,
                "errors": self.error_configs
            },
            "last_check": self.last_check.isoformat()
        }


class ConfigMonitor:
    """
    Configuration monitoring service

    Provides:
    - Runtime configuration validation
    - Health check reporting
    - Configuration change detection
    - Metrics for monitoring
    """

    def __init__(self, config_dir: Optional[Path] = None):
        """
        Initialize configuration monitor

        Args:
            config_dir: Path to config directory (auto-detected if not provided)
        """
        if config_dir is None:
            config_dir = Path(__file__).parent.parent.parent / "config"

        self.config_dir = config_dir
        self._health_cache: Dict[str, ConfigHealth] = {}
        self._last_system_check: Optional[datetime] = None
        self._validator: Optional[Any] = None

        logger.info(f"ConfigMonitor initialized for directory: {self.config_dir}")

    def _get_validator(self):
        """Lazy-load config validator"""
        if self._validator is None:
            from .config_validator import get_validator
            self._validator = get_validator()
        return self._validator

    def _get_config_file_info(self, config_name: str) -> Dict[str, Any]:
        """Get file information for a config"""
        try:
            config_path = self.config_dir / f"{config_name}.json"

            if not config_path.exists():
                return {
                    "file_size_bytes": None,
                    "last_modified": None,
                    "exists": False
                }

            stat = config_path.stat()
            return {
                "file_size_bytes": stat.st_size,
                "last_modified": datetime.fromtimestamp(stat.st_mtime),
                "exists": True
            }
        except Exception as e:
            logger.error(f"Failed to get file info for {config_name}: {e}")
            return {
                "file_size_bytes": None,
                "last_modified": None,
                "exists": False
            }

    def validate_config(self, config_name: str) -> ConfigHealth:
        """
        Validate a single configuration file

        Args:
            config_name: Name of config to validate (without .json extension)

        Returns:
            ConfigHealth status
        """
        validator = self._get_validator()
        file_info = self._get_config_file_info(config_name)

        # Run validation
        try:
            result = validator.validate_config_schema(config_name)

            errors = []
            warnings = []

            # Collect errors
            if not result.is_valid:
                errors = result.errors

            # Collect warnings
            if result.warnings:
                warnings = result.warnings

            # Determine status
            if errors:
                status = ConfigStatus.ERROR
            elif warnings:
                status = ConfigStatus.WARNING
            else:
                status = ConfigStatus.HEALTHY

            health = ConfigHealth(
                config_name=config_name,
                status=status,
                last_validated=datetime.utcnow(),
                validation_errors=errors,
                validation_warnings=warnings,
                file_size_bytes=file_info.get("file_size_bytes"),
                last_modified=file_info.get("last_modified")
            )

            # Update cache
            self._health_cache[config_name] = health

            return health

        except FileNotFoundError:
            logger.error(f"Config file not found: {config_name}")
            health = ConfigHealth(
                config_name=config_name,
                status=ConfigStatus.ERROR,
                last_validated=datetime.utcnow(),
                validation_errors=[f"Config file not found: {config_name}.json"],
                file_size_bytes=None,
                last_modified=None
            )
            self._health_cache[config_name] = health
            return health

        except Exception as e:
            logger.error(f"Validation failed for {config_name}: {e}", exc_info=True)
            health = ConfigHealth(
                config_name=config_name,
                status=ConfigStatus.ERROR,
                last_validated=datetime.utcnow(),
                validation_errors=[f"Validation error: {str(e)}"],
                file_size_bytes=file_info.get("file_size_bytes"),
                last_modified=file_info.get("last_modified")
            )
            self._health_cache[config_name] = health
            return health

    def validate_all_configs(self) -> SystemHealth:
        """
        Validate all configuration files

        Returns:
            SystemHealth with status for all configs
        """
        logger.info("Running full configuration validation")

        # List of configs to validate (only those with schema files)
        config_names = [
            "component_types",
            "state_prompts",
            "powersource_state_specifications"
            # Note: master_parameter_schema doesn't have a schema file
        ]

        # Validate each config
        health_map = {}
        for config_name in config_names:
            health = self.validate_config(config_name)
            health_map[config_name] = health

        # Calculate summary statistics
        total = len(health_map)
        healthy = sum(1 for h in health_map.values() if h.status == ConfigStatus.HEALTHY)
        warnings = sum(1 for h in health_map.values() if h.status == ConfigStatus.WARNING)
        errors = sum(1 for h in health_map.values() if h.status == ConfigStatus.ERROR)

        # Determine overall status
        if errors > 0:
            overall_status = ConfigStatus.ERROR
        elif warnings > 0:
            overall_status = ConfigStatus.WARNING
        else:
            overall_status = ConfigStatus.HEALTHY

        system_health = SystemHealth(
            status=overall_status,
            configs=health_map,
            total_configs=total,
            healthy_configs=healthy,
            warning_configs=warnings,
            error_configs=errors,
            last_check=datetime.utcnow()
        )

        self._last_system_check = datetime.utcnow()

        logger.info(
            f"Configuration validation complete: "
            f"{healthy}/{total} healthy, {warnings} warnings, {errors} errors"
        )

        return system_health

    def validate_state_consistency(self) -> ConfigHealth:
        """
        Validate consistency between configurations

        Returns:
            ConfigHealth for cross-config consistency
        """
        validator = self._get_validator()

        try:
            result = validator.validate_state_consistency()

            errors = []
            warnings = []

            if not result.is_valid:
                errors = result.errors

            if result.warnings:
                warnings = result.warnings

            # Determine status
            if errors:
                status = ConfigStatus.ERROR
            elif warnings:
                status = ConfigStatus.WARNING
            else:
                status = ConfigStatus.HEALTHY

            return ConfigHealth(
                config_name="state_consistency",
                status=status,
                last_validated=datetime.utcnow(),
                validation_errors=errors,
                validation_warnings=warnings
            )

        except Exception as e:
            logger.error(f"State consistency validation failed: {e}", exc_info=True)
            return ConfigHealth(
                config_name="state_consistency",
                status=ConfigStatus.ERROR,
                last_validated=datetime.utcnow(),
                validation_errors=[f"Consistency check error: {str(e)}"]
            )

    def validate_applicability_config(self) -> ConfigHealth:
        """
        Validate component applicability configuration

        Returns:
            ConfigHealth for applicability config
        """
        validator = self._get_validator()

        try:
            result = validator.validate_component_mappings()

            errors = []
            warnings = []

            if not result.is_valid:
                errors = result.errors

            if result.warnings:
                warnings = result.warnings

            # Determine status
            if errors:
                status = ConfigStatus.ERROR
            elif warnings:
                status = ConfigStatus.WARNING
            else:
                status = ConfigStatus.HEALTHY

            return ConfigHealth(
                config_name="applicability_logic",
                status=status,
                last_validated=datetime.utcnow(),
                validation_errors=errors,
                validation_warnings=warnings
            )

        except Exception as e:
            logger.error(f"Applicability validation failed: {e}", exc_info=True)
            return ConfigHealth(
                config_name="applicability_logic",
                status=ConfigStatus.ERROR,
                last_validated=datetime.utcnow(),
                validation_errors=[f"Applicability check error: {str(e)}"]
            )

    def get_comprehensive_health(self) -> SystemHealth:
        """
        Get comprehensive health check including all validations

        Returns:
            SystemHealth with all checks
        """
        # Validate all configs
        system_health = self.validate_all_configs()

        # Add consistency check
        consistency_health = self.validate_state_consistency()
        system_health.configs["state_consistency"] = consistency_health
        system_health.total_configs += 1

        if consistency_health.status == ConfigStatus.HEALTHY:
            system_health.healthy_configs += 1
        elif consistency_health.status == ConfigStatus.WARNING:
            system_health.warning_configs += 1
        else:
            system_health.error_configs += 1

        # Add applicability check
        applicability_health = self.validate_applicability_config()
        system_health.configs["applicability_logic"] = applicability_health
        system_health.total_configs += 1

        if applicability_health.status == ConfigStatus.HEALTHY:
            system_health.healthy_configs += 1
        elif applicability_health.status == ConfigStatus.WARNING:
            system_health.warning_configs += 1
        else:
            system_health.error_configs += 1

        # Update overall status
        if system_health.error_configs > 0:
            system_health.status = ConfigStatus.ERROR
        elif system_health.warning_configs > 0:
            system_health.status = ConfigStatus.WARNING
        else:
            system_health.status = ConfigStatus.HEALTHY

        return system_health

    def get_cached_health(self, config_name: str) -> Optional[ConfigHealth]:
        """
        Get cached health status (no validation)

        Args:
            config_name: Name of config

        Returns:
            ConfigHealth or None if not cached
        """
        return self._health_cache.get(config_name)

    def clear_cache(self):
        """Clear health cache (force re-validation on next check)"""
        self._health_cache.clear()
        self._last_system_check = None
        logger.debug("Health cache cleared")


# Singleton instance
_monitor: Optional[ConfigMonitor] = None


def get_config_monitor() -> ConfigMonitor:
    """
    Get singleton config monitor instance

    Returns:
        ConfigMonitor instance
    """
    global _monitor

    if _monitor is None:
        _monitor = ConfigMonitor()

    return _monitor


def init_config_monitor(config_dir: Optional[Path] = None) -> ConfigMonitor:
    """
    Initialize config monitor

    Args:
        config_dir: Path to config directory (optional)

    Returns:
        Initialized ConfigMonitor
    """
    global _monitor

    if _monitor is not None:
        logger.debug("ConfigMonitor already initialized")
        return _monitor

    _monitor = ConfigMonitor(config_dir)
    logger.info("[OK] ConfigMonitor initialized")

    return _monitor


def clear_config_monitor():
    """Clear monitor singleton (useful for testing)"""
    global _monitor
    _monitor = None
    logger.debug("ConfigMonitor singleton cleared")
