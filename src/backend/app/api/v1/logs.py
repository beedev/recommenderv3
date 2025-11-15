"""
Log Viewer API

Single unified endpoint for viewing logs from multiple sources:
- Application logs (request/response/errors from log files)
- Session archives (conversation history from PostgreSQL)
- Agent traces (agent actions, Neo4j queries, LLM extractions)
- Performance metrics (timing data from logs)

Best Practices:
- Pydantic models for request validation and response structure
- Comprehensive error handling with proper HTTP status codes
- Structured logging for observability
- Input validation (max limits, format validation)
- Consistent error response format
"""

from fastapi import APIRouter, Query, HTTPException
from fastapi import status as http_status
from pydantic import BaseModel, Field, validator
from typing import List, Dict, Optional, Any
from datetime import datetime
from enum import Enum
import structlog

from ...utils.log_parser import (
    get_application_logs,
    get_session_logs,
    get_agent_logs,
    get_performance_metrics
)

logger = structlog.get_logger(__name__)

router = APIRouter(
    prefix="/api/v1/logs",
    tags=["logs"],
    responses={404: {"description": "Not found"}}
)


# Enums for validation
class LogSource(str, Enum):
    """Log source types"""
    APPLICATION = "application"
    SESSION = "session"
    AGENTS = "agents"
    PERFORMANCE = "performance"


class LogLevel(str, Enum):
    """Log levels"""
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


# Response Models
class LogEntry(BaseModel):
    """Individual log entry"""
    timestamp: Optional[str] = Field(None, description="ISO8601 timestamp")
    level: Optional[str] = Field(None, description="Log level (debug/info/warning/error)")
    message: Optional[str] = Field(None, description="Log message")
    session_id: Optional[str] = Field(None, description="Session ID if available")
    correlation_id: Optional[str] = Field(None, description="Correlation ID if available")
    context: Optional[Dict[str, Any]] = Field(None, description="Additional context")

    class Config:
        extra = "allow"  # Allow additional fields from different log sources


class LogResponse(BaseModel):
    """Unified log response"""
    success: bool = Field(..., description="Whether request was successful")
    source: str = Field(..., description="Log source (application/session/agents/performance)")
    total: int = Field(..., description="Total number of logs matching filters")
    limit: int = Field(..., description="Limit applied")
    offset: int = Field(..., description="Offset applied")
    logs: List[Dict[str, Any]] = Field(..., description="List of log entries")
    error: Optional[str] = Field(None, description="Error message if unsuccessful")
    filters_applied: Optional[Dict[str, Any]] = Field(None, description="Filters that were applied")

    class Config:
        schema_extra = {
            "example": {
                "success": True,
                "source": "application",
                "total": 245,
                "limit": 100,
                "offset": 0,
                "logs": [
                    {
                        "timestamp": "2025-01-11T10:30:45.123Z",
                        "level": "info",
                        "message": "Processing message",
                        "correlation_id": "abc-123",
                        "session_id": "xyz-789",
                        "duration_ms": 120
                    }
                ],
                "error": None,
                "filters_applied": {
                    "level": "info",
                    "limit": 100,
                    "offset": 0
                }
            }
        }


class ErrorResponse(BaseModel):
    """Error response"""
    success: bool = False
    error: str = Field(..., description="Error message")
    detail: Optional[str] = Field(None, description="Detailed error information")

    class Config:
        schema_extra = {
            "example": {
                "success": False,
                "error": "Invalid session_id format",
                "detail": "session_id must be a valid UUID"
            }
        }


@router.get(
    "",
    response_model=LogResponse,
    responses={
        200: {"description": "Logs retrieved successfully"},
        400: {"description": "Invalid request parameters", "model": ErrorResponse},
        404: {"description": "Log source not found", "model": ErrorResponse},
        500: {"description": "Internal server error", "model": ErrorResponse}
    },
    summary="Get Logs",
    description="""
    Unified endpoint to retrieve logs from multiple sources.

    **Log Sources:**
    - `application`: Application logs (request/response/errors from log files)
    - `session`: Archived session data (conversation history from PostgreSQL)
    - `agents`: Agent execution logs (agent actions, Neo4j queries, LLM extractions)
    - `performance`: Performance metrics (timing data from logs)

    **Filtering:**
    - Filter by session_id, correlation_id, log level, time range
    - Pagination with limit/offset
    - Results cached for 5 minutes (Redis)

    **Example Queries:**
    - Get recent errors: `?source=application&level=error&limit=50`
    - Trace request: `?source=application&correlation_id=abc-123`
    - View session: `?source=session&session_id=xyz-789`
    - Agent logs: `?source=agents&session_id=xyz-789`
    - Performance data: `?source=performance&start_time=2025-01-01T00:00:00Z`
    """
)
async def get_logs(
    source: LogSource = Query(
        ...,
        description="Log source: application, session, agents, or performance"
    ),
    session_id: Optional[str] = Query(
        None,
        description="Filter by session ID",
        min_length=1,
        max_length=100
    ),
    correlation_id: Optional[str] = Query(
        None,
        description="Filter by correlation ID",
        min_length=1,
        max_length=100
    ),
    user_id: Optional[str] = Query(
        None,
        description="Filter by user ID (session logs only)",
        min_length=1,
        max_length=100
    ),
    level: Optional[LogLevel] = Query(
        None,
        description="Filter by log level: debug, info, warning, or error (application logs only)"
    ),
    status: Optional[str] = Query(
        None,
        description="Filter by status: completed, abandoned, or finalized (session logs only)",
        regex="^(completed|abandoned|finalized)$"
    ),
    start_time: Optional[datetime] = Query(
        None,
        description="Filter logs after this time (ISO8601 format: 2025-01-11T10:30:00Z)"
    ),
    end_time: Optional[datetime] = Query(
        None,
        description="Filter logs before this time (ISO8601 format: 2025-01-11T10:30:00Z)"
    ),
    limit: int = Query(
        100,
        description="Maximum number of results to return",
        ge=1,
        le=1000
    ),
    offset: int = Query(
        0,
        description="Number of results to skip (for pagination)",
        ge=0
    )
) -> LogResponse:
    """
    Get logs from specified source with optional filters.

    Args:
        source: Log source (application/session/agents/performance)
        session_id: Filter by session ID
        correlation_id: Filter by correlation ID
        user_id: Filter by user ID (session logs only)
        level: Filter by log level (application logs only)
        status: Filter by status (session logs only)
        start_time: Filter logs after this time
        end_time: Filter logs before this time
        limit: Maximum number of results (1-1000, default 100)
        offset: Pagination offset (default 0)

    Returns:
        LogResponse with logs and metadata

    Raises:
        HTTPException: For invalid parameters or errors
    """
    logger.info(
        "get_logs_request",
        source=source.value,
        session_id=session_id,
        correlation_id=correlation_id,
        level=level.value if level else None,
        limit=limit,
        offset=offset
    )

    try:
        # Collect filters for response
        filters_applied = {
            "source": source.value,
            "limit": limit,
            "offset": offset
        }
        if session_id:
            filters_applied["session_id"] = session_id
        if correlation_id:
            filters_applied["correlation_id"] = correlation_id
        if user_id:
            filters_applied["user_id"] = user_id
        if level:
            filters_applied["level"] = level.value
        if status:
            filters_applied["status"] = status
        if start_time:
            filters_applied["start_time"] = start_time.isoformat()
        if end_time:
            filters_applied["end_time"] = end_time.isoformat()

        # Route to appropriate log source
        if source == LogSource.APPLICATION:
            logs, total = await get_application_logs(
                level=level.value if level else None,
                session_id=session_id,
                correlation_id=correlation_id,
                start_time=start_time,
                end_time=end_time,
                limit=limit,
                offset=offset
            )

        elif source == LogSource.SESSION:
            logs, total = await get_session_logs(
                session_id=session_id,
                user_id=user_id,
                status=status,
                start_time=start_time,
                end_time=end_time,
                limit=limit,
                offset=offset
            )

        elif source == LogSource.AGENTS:
            # Agent logs require session_id
            if not session_id:
                raise HTTPException(
                    status_code=http_status.HTTP_400_BAD_REQUEST,
                    detail="session_id is required for agent logs"
                )

            logs, total = await get_agent_logs(
                session_id=session_id,
                limit=limit,
                offset=offset
            )

        elif source == LogSource.PERFORMANCE:
            logs, total = await get_performance_metrics(
                start_time=start_time,
                end_time=end_time,
                limit=limit,
                offset=offset
            )

        else:
            raise HTTPException(
                status_code=http_status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid log source: {source}"
            )

        logger.info(
            "get_logs_success",
            source=source.value,
            total=total,
            returned=len(logs)
        )

        return LogResponse(
            success=True,
            source=source.value,
            total=total,
            limit=limit,
            offset=offset,
            logs=logs,
            filters_applied=filters_applied
        )

    except HTTPException:
        # Re-raise HTTP exceptions
        raise

    except FileNotFoundError as e:
        logger.error("log_file_not_found", error=str(e))
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail=f"Log file not found: {str(e)}"
        )

    except ValueError as e:
        logger.error("invalid_parameter", error=str(e))
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid parameter: {str(e)}"
        )

    except Exception as e:
        logger.error(
            "get_logs_error",
            source=source.value,
            error=str(e),
            exc_info=True
        )
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving logs: {str(e)}"
        )


@router.get(
    "/health",
    summary="Log Viewer Health Check",
    description="Check if log viewer is operational and can access log sources"
)
async def health_check() -> Dict[str, Any]:
    """
    Health check for log viewer.

    Tests access to:
    - Log files (application logs)
    - PostgreSQL (session/agent logs)
    - Redis (caching)

    Returns:
        Health status dict
    """
    health = {
        "status": "healthy",
        "checks": {}
    }

    # Check application logs
    try:
        logs, total = await get_application_logs(limit=1)
        if total == 0:
            # No logs found or file doesn't exist yet
            health["checks"]["application_logs"] = {
                "status": "warning",
                "accessible": True,
                "sample_count": 0,
                "message": "No log file found or empty (development/fresh install)"
            }
        else:
            health["checks"]["application_logs"] = {
                "status": "healthy",
                "accessible": True,
                "sample_count": total
            }
    except Exception as e:
        health["checks"]["application_logs"] = {
            "status": "unhealthy",
            "accessible": False,
            "error": str(e)
        }
        health["status"] = "degraded"

    # Check session logs
    try:
        logs, total = await get_session_logs(limit=1)
        if total == 0:
            # No archived sessions yet
            health["checks"]["session_logs"] = {
                "status": "warning",
                "accessible": True,
                "sample_count": 0,
                "message": "No archived sessions yet"
            }
        else:
            health["checks"]["session_logs"] = {
                "status": "healthy",
                "accessible": True,
                "sample_count": total
            }
    except Exception as e:
        health["checks"]["session_logs"] = {
            "status": "unhealthy",
            "accessible": False,
            "error": str(e)
        }
        health["status"] = "degraded"

    # Check Redis cache
    try:
        from ...database.database import get_redis_client
        redis_client = await get_redis_client()
        if redis_client:
            await redis_client.ping()
            health["checks"]["redis_cache"] = {
                "status": "healthy",
                "accessible": True
            }
        else:
            health["checks"]["redis_cache"] = {
                "status": "warning",
                "accessible": False,
                "message": "Redis not configured"
            }
    except Exception as e:
        health["checks"]["redis_cache"] = {
            "status": "unhealthy",
            "accessible": False,
            "error": str(e)
        }

    logger.info("log_viewer_health_check", health=health)
    return health
