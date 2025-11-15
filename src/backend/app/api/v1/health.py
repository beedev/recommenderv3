"""
Health Check API Endpoints for Configuration Validation
GET /api/v1/health/config - Overall configuration health
GET /api/v1/health/config/{config_name} - Specific config health
GET /api/v1/health/config/validation/full - Comprehensive validation
"""

import logging
from typing import Dict, Any, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ...services.config.config_monitor import get_config_monitor, ConfigStatus

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/health", tags=["Health"])


class ConfigHealthResponse(BaseModel):
    """Response model for config health check"""
    config_name: str
    status: str
    last_validated: str
    validation_errors: list
    validation_warnings: list
    file_size_bytes: Optional[int]
    last_modified: Optional[str]


class SystemHealthResponse(BaseModel):
    """Response model for system health check"""
    status: str
    configs: Dict[str, Dict[str, Any]]
    summary: Dict[str, int]
    last_check: str


@router.get("/config", response_model=SystemHealthResponse)
async def get_config_health():
    """
    Get overall configuration health status

    Returns:
        SystemHealthResponse with health of all configs

    Example:
        GET /api/v1/health/config

        Response:
        {
            "status": "healthy",
            "configs": {
                "component_types": {
                    "status": "healthy",
                    "last_validated": "2025-01-28T10:30:00",
                    ...
                },
                ...
            },
            "summary": {
                "total_configs": 4,
                "healthy": 4,
                "warnings": 0,
                "errors": 0
            },
            "last_check": "2025-01-28T10:30:00"
        }
    """
    try:
        monitor = get_config_monitor()
        system_health = monitor.validate_all_configs()

        return SystemHealthResponse(
            status=system_health.status.value,
            configs={name: health.to_dict() for name, health in system_health.configs.items()},
            summary={
                "total_configs": system_health.total_configs,
                "healthy": system_health.healthy_configs,
                "warnings": system_health.warning_configs,
                "errors": system_health.error_configs
            },
            last_check=system_health.last_check.isoformat()
        )

    except Exception as e:
        logger.error(f"Config health check failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Health check failed: {str(e)}"
        )


@router.get("/config/{config_name}", response_model=ConfigHealthResponse)
async def get_specific_config_health(config_name: str):
    """
    Get health status for a specific configuration file

    Args:
        config_name: Name of config (component_types, state_prompts, etc.)

    Returns:
        ConfigHealthResponse with validation details

    Example:
        GET /api/v1/health/config/component_types

        Response:
        {
            "config_name": "component_types",
            "status": "healthy",
            "last_validated": "2025-01-28T10:30:00",
            "validation_errors": [],
            "validation_warnings": [],
            "file_size_bytes": 5432,
            "last_modified": "2025-01-28T09:15:00"
        }
    """
    try:
        monitor = get_config_monitor()

        # Validate allowed config names
        allowed_configs = [
            "component_types",
            "state_prompts",
            "powersource_state_specifications",
            "master_parameter_schema"
        ]

        if config_name not in allowed_configs:
            raise HTTPException(
                status_code=404,
                detail=f"Config '{config_name}' not found. Allowed: {', '.join(allowed_configs)}"
            )

        health = monitor.validate_config(config_name)

        return ConfigHealthResponse(
            config_name=health.config_name,
            status=health.status.value,
            last_validated=health.last_validated.isoformat(),
            validation_errors=health.validation_errors,
            validation_warnings=health.validation_warnings,
            file_size_bytes=health.file_size_bytes,
            last_modified=health.last_modified.isoformat() if health.last_modified else None
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Config health check failed for {config_name}: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Health check failed: {str(e)}"
        )


@router.get("/config/validation/full", response_model=SystemHealthResponse)
async def get_comprehensive_health():
    """
    Get comprehensive health check including all validations

    Includes:
    - All config file validations
    - State consistency checks
    - Applicability logic validation

    Returns:
        SystemHealthResponse with comprehensive health status

    Example:
        GET /api/v1/health/config/validation/full

        Response:
        {
            "status": "healthy",
            "configs": {
                "component_types": {...},
                "state_prompts": {...},
                "powersource_state_specifications": {...},
                "master_parameter_schema": {...},
                "state_consistency": {...},
                "applicability_logic": {...}
            },
            "summary": {
                "total_configs": 6,
                "healthy": 6,
                "warnings": 0,
                "errors": 0
            },
            "last_check": "2025-01-28T10:30:00"
        }
    """
    try:
        monitor = get_config_monitor()
        system_health = monitor.get_comprehensive_health()

        return SystemHealthResponse(
            status=system_health.status.value,
            configs={name: health.to_dict() for name, health in system_health.configs.items()},
            summary={
                "total_configs": system_health.total_configs,
                "healthy": system_health.healthy_configs,
                "warnings": system_health.warning_configs,
                "errors": system_health.error_configs
            },
            last_check=system_health.last_check.isoformat()
        )

    except Exception as e:
        logger.error(f"Comprehensive health check failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Health check failed: {str(e)}"
        )


@router.get("/config/consistency")
async def get_consistency_check():
    """
    Check consistency between configuration files

    Validates:
    - State sequence matches state prompts
    - State orders are sequential
    - No duplicate state orders
    - All states have required fields

    Returns:
        Health status for consistency checks

    Example:
        GET /api/v1/health/config/consistency

        Response:
        {
            "status": "healthy",
            "validation_errors": [],
            "validation_warnings": [],
            "last_validated": "2025-01-28T10:30:00"
        }
    """
    try:
        monitor = get_config_monitor()
        health = monitor.validate_state_consistency()

        return {
            "status": health.status.value,
            "validation_errors": health.validation_errors,
            "validation_warnings": health.validation_warnings,
            "last_validated": health.last_validated.isoformat()
        }

    except Exception as e:
        logger.error(f"Consistency check failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Consistency check failed: {str(e)}"
        )


@router.get("/config/applicability")
async def get_applicability_check():
    """
    Check component applicability configuration

    Validates:
    - All power sources have applicability rules
    - Applicability flags are valid (Y/N)
    - Referenced components exist

    Returns:
        Health status for applicability config

    Example:
        GET /api/v1/health/config/applicability

        Response:
        {
            "status": "healthy",
            "validation_errors": [],
            "validation_warnings": [],
            "last_validated": "2025-01-28T10:30:00"
        }
    """
    try:
        monitor = get_config_monitor()
        health = monitor.validate_applicability_config()

        return {
            "status": health.status.value,
            "validation_errors": health.validation_errors,
            "validation_warnings": health.validation_warnings,
            "last_validated": health.last_validated.isoformat()
        }

    except Exception as e:
        logger.error(f"Applicability check failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Applicability check failed: {str(e)}"
        )


@router.post("/config/cache/clear")
async def clear_health_cache():
    """
    Clear health check cache

    Forces re-validation on next health check.
    Useful after manual config changes.

    Returns:
        Success message

    Example:
        POST /api/v1/health/config/cache/clear

        Response:
        {
            "message": "Health cache cleared successfully",
            "next_check_will_revalidate": true
        }
    """
    try:
        monitor = get_config_monitor()
        monitor.clear_cache()

        return {
            "message": "Health cache cleared successfully",
            "next_check_will_revalidate": True
        }

    except Exception as e:
        logger.error(f"Failed to clear cache: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Cache clear failed: {str(e)}"
        )
