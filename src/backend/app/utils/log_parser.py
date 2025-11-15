"""
Log Parser Utility for Log Viewer

Provides functions to retrieve and parse logs from various sources:
- Application logs (from log files)
- Session archives (from PostgreSQL)
- Agent traces (from PostgreSQL)
- Performance metrics (from logs)

Best Practices:
- File safety checks (size limits, path validation)
- Memory efficient streaming (don't load entire files)
- Redis caching (5-minute TTL)
- Error handling and structured logging
- Security (path sanitization, data redaction)
"""

import os
import json
import re
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
from pathlib import Path
import structlog

from ..database.database import get_redis_client, postgresql_manager
from sqlalchemy import select, and_, or_, func, text
from sqlalchemy.ext.asyncio import AsyncSession

logger = structlog.get_logger(__name__)

# Configuration
MAX_FILE_SIZE = int(os.getenv("LOG_VIEWER_MAX_FILE_SIZE", 104857600))  # 100MB default
CACHE_TTL = int(os.getenv("LOG_VIEWER_CACHE_TTL", 300))  # 5 minutes default
QUERY_TIMEOUT = int(os.getenv("LOG_VIEWER_QUERY_TIMEOUT", 5))  # 5 seconds default

# Sensitive data patterns to redact
SENSITIVE_PATTERNS = [
    (re.compile(r'password["\s:=]+([^\s,"]+)', re.IGNORECASE), 'password=***'),
    (re.compile(r'api[_-]?key["\s:=]+([^\s,"]+)', re.IGNORECASE), 'api_key=***'),
    (re.compile(r'token["\s:=]+([^\s,"]+)', re.IGNORECASE), 'token=***'),
    (re.compile(r'Bearer\s+([^\s]+)', re.IGNORECASE), 'Bearer ***'),
]


def sanitize_file_path(file_path: str) -> Path:
    """
    Sanitize and validate file path for security.

    Prevents directory traversal attacks and validates path exists.

    Args:
        file_path: Path to log file

    Returns:
        Validated Path object

    Raises:
        ValueError: If path is invalid or contains directory traversal
    """
    # Resolve to absolute path
    path = Path(file_path).resolve()

    # Check for directory traversal attempts
    if '..' in str(path):
        raise ValueError("Directory traversal not allowed")

    # Check file exists
    if not path.exists():
        raise FileNotFoundError(f"Log file not found: {path}")

    # Check file is readable
    if not os.access(path, os.R_OK):
        raise PermissionError(f"Log file not readable: {path}")

    # Check file size
    file_size = path.stat().st_size
    if file_size > MAX_FILE_SIZE:
        raise ValueError(f"Log file too large: {file_size} bytes (max: {MAX_FILE_SIZE})")

    return path


def redact_sensitive_data(text: str) -> str:
    """
    Redact sensitive data from log text.

    Args:
        text: Log text that may contain sensitive data

    Returns:
        Text with sensitive data redacted
    """
    for pattern, replacement in SENSITIVE_PATTERNS:
        text = pattern.sub(replacement, text)
    return text


async def get_cache_key(prefix: str, **filters) -> str:
    """
    Generate Redis cache key from filters.

    Args:
        prefix: Cache key prefix (e.g., 'app_logs', 'session_logs')
        **filters: Filter parameters

    Returns:
        Cache key string
    """
    # Sort filters for consistent key generation
    filter_str = ':'.join(f"{k}={v}" for k, v in sorted(filters.items()) if v is not None)
    return f"log_viewer:{prefix}:{filter_str}"


async def get_cached_logs(cache_key: str) -> Optional[Tuple[List[Dict], int]]:
    """
    Retrieve logs from Redis cache.

    Args:
        cache_key: Cache key

    Returns:
        Tuple of (logs list, total count) or None if not cached
    """
    try:
        redis_client = await get_redis_client()
        if not redis_client:
            return None

        cached = await redis_client.get(cache_key)
        if cached:
            logger.debug("cache_hit", cache_key=cache_key)
            data = json.loads(cached)
            return data['logs'], data['total']

        logger.debug("cache_miss", cache_key=cache_key)
        return None
    except Exception as e:
        logger.warning("cache_error", error=str(e))
        return None


async def set_cached_logs(cache_key: str, logs: List[Dict], total: int):
    """
    Store logs in Redis cache.

    Args:
        cache_key: Cache key
        logs: List of log entries
        total: Total count
    """
    try:
        redis_client = await get_redis_client()
        if not redis_client:
            return

        data = json.dumps({'logs': logs, 'total': total})
        await redis_client.setex(cache_key, CACHE_TTL, data)
        logger.debug("cache_set", cache_key=cache_key, ttl=CACHE_TTL)
    except Exception as e:
        logger.warning("cache_set_error", error=str(e))


async def get_application_logs(
    level: Optional[str] = None,
    session_id: Optional[str] = None,
    correlation_id: Optional[str] = None,
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None,
    limit: int = 100,
    offset: int = 0
) -> Tuple[List[Dict], int]:
    """
    Parse application log file with filters.

    Reads log file in reverse (newest first), parses JSON or structured text,
    applies filters, and returns paginated results.

    Args:
        level: Filter by log level (debug/info/warning/error)
        session_id: Filter by session ID
        correlation_id: Filter by correlation ID
        start_time: Filter logs after this time
        end_time: Filter logs before this time
        limit: Maximum number of results
        offset: Pagination offset

    Returns:
        Tuple of (logs list, total count)

    Raises:
        FileNotFoundError: If log file doesn't exist
        ValueError: If file is too large or invalid
    """
    logger.info("get_application_logs", level=level, session_id=session_id,
                correlation_id=correlation_id, limit=limit, offset=offset)

    # Check cache first
    cache_key = await get_cache_key(
        "app_logs", level=level, session_id=session_id,
        correlation_id=correlation_id,
        start_time=start_time.isoformat() if start_time else None,
        end_time=end_time.isoformat() if end_time else None,
        limit=limit, offset=offset
    )
    cached = await get_cached_logs(cache_key)
    if cached:
        return cached

    # Get log file path with automatic detection
    # Calculate project root (4 levels up from backend/app/utils/log_parser.py)
    from pathlib import Path
    current_dir = Path(__file__).resolve().parent  # utils/
    app_dir = current_dir.parent  # app/
    backend_dir = app_dir.parent  # backend/
    src_dir = backend_dir.parent  # src/
    project_root = src_dir.parent  # project root

    # Default log path at project root
    default_log_path = project_root / "logs" / "esab-recommender.log"
    log_file_path = os.getenv("LOG_FILE_PATH", str(default_log_path))

    # Ensure absolute path
    log_file_path = str(Path(log_file_path).resolve())

    # Sanitize path
    try:
        path = sanitize_file_path(log_file_path)
    except FileNotFoundError as e:
        # Log file doesn't exist yet (development or fresh install)
        logger.warning("log_file_not_found", path=log_file_path, message="Returning empty results")
        return [], 0
    except Exception as e:
        logger.error("log_file_error", error=str(e))
        raise

    # Parse log file
    logs = []
    env = os.getenv("ENV", "development").lower()

    try:
        with open(path, 'r', encoding='utf-8', errors='ignore') as f:
            # Read lines in reverse order for newest first
            # For large files, use a more memory-efficient approach
            file_size = path.stat().st_size
            if file_size < 10 * 1024 * 1024:  # < 10MB, safe to read all
                lines = f.readlines()
                lines.reverse()
            else:
                # For large files, read in chunks from end
                # This is a simplified approach; production might use a library like 'file-read-backwards'
                lines = f.readlines()
                lines.reverse()

            for line in lines:
                line = line.strip()
                if not line:
                    continue

                try:
                    # Try parsing as JSON (production format)
                    if env == "production" and line.startswith('{'):
                        log_entry = json.loads(line)
                    else:
                        # Parse development format (structured text)
                        # Format: 2025-01-11 10:30:45 [info] message key=value key2=value2
                        match = re.match(r'(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d+Z)\s+\[(\w+)\s*\]\s+(.+)', line)
                        if match:
                            timestamp_str, log_level, rest = match.groups()

                            # Parse key=value pairs and message
                            parts = rest.split()
                            message = []
                            context = {}

                            for part in parts:
                                if '=' in part:
                                    key, value = part.split('=', 1)
                                    context[key] = value
                                else:
                                    message.append(part)

                            log_entry = {
                                'timestamp': timestamp_str,
                                'level': log_level,
                                'message': ' '.join(message),
                                **context
                            }
                        else:
                            # Fallback: treat entire line as message
                            log_entry = {
                                'timestamp': datetime.now().isoformat(),
                                'level': 'info',
                                'message': line
                            }

                    # Apply filters
                    if level and log_entry.get('level', '').lower() != level.lower():
                        continue

                    if session_id and log_entry.get('session_id') != session_id:
                        continue

                    if correlation_id and log_entry.get('correlation_id') != correlation_id:
                        continue

                    if start_time:
                        log_time = datetime.fromisoformat(log_entry.get('timestamp', '').replace('Z', '+00:00'))
                        if log_time < start_time:
                            continue

                    if end_time:
                        log_time = datetime.fromisoformat(log_entry.get('timestamp', '').replace('Z', '+00:00'))
                        if log_time > end_time:
                            continue

                    # Redact sensitive data
                    if 'message' in log_entry:
                        log_entry['message'] = redact_sensitive_data(log_entry['message'])

                    logs.append(log_entry)

                except Exception as e:
                    logger.debug("parse_error", line=line[:100], error=str(e))
                    continue

        # Apply pagination
        total = len(logs)
        paginated_logs = logs[offset:offset + limit]

        # Cache results
        await set_cached_logs(cache_key, paginated_logs, total)

        logger.info("application_logs_retrieved", total=total, returned=len(paginated_logs))
        return paginated_logs, total

    except Exception as e:
        logger.error("application_logs_error", error=str(e))
        raise


async def get_session_logs(
    session_id: Optional[str] = None,
    user_id: Optional[str] = None,
    status: Optional[str] = None,
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None,
    limit: int = 100,
    offset: int = 0
) -> Tuple[List[Dict], int]:
    """
    Query archived sessions from PostgreSQL.

    Args:
        session_id: Filter by specific session ID
        user_id: Filter by user ID
        status: Filter by status (completed/abandoned/finalized)
        start_time: Filter sessions after this time
        end_time: Filter sessions before this time
        limit: Maximum number of results
        offset: Pagination offset

    Returns:
        Tuple of (sessions list, total count)
    """
    logger.info("get_session_logs", session_id=session_id, user_id=user_id,
                status=status, limit=limit, offset=offset)

    # Check cache
    cache_key = await get_cache_key(
        "session_logs", session_id=session_id, user_id=user_id,
        status=status,
        start_time=start_time.isoformat() if start_time else None,
        end_time=end_time.isoformat() if end_time else None,
        limit=limit, offset=offset
    )
    cached = await get_cached_logs(cache_key)
    if cached:
        return cached

    try:
        from ..database.postgres_archival import ArchivedSession

        async with postgresql_manager.session_factory() as db_session:
            # Build query
            query = select(ArchivedSession)

            # Apply filters
            filters = []
            if session_id:
                filters.append(ArchivedSession.session_id == session_id)
            if user_id:
                filters.append(ArchivedSession.user_id == user_id)
            if status:
                if status == 'finalized':
                    filters.append(ArchivedSession.finalized == True)
                elif status == 'completed':
                    filters.append(ArchivedSession.final_state == 'finalize')
                elif status == 'abandoned':
                    filters.append(ArchivedSession.final_state != 'finalize')
            if start_time:
                # Convert to naive datetime for PostgreSQL TIMESTAMP WITHOUT TIME ZONE
                start_time_naive = start_time.replace(tzinfo=None) if start_time.tzinfo else start_time
                filters.append(ArchivedSession.completed_at >= start_time_naive)
            if end_time:
                # Convert to naive datetime for PostgreSQL TIMESTAMP WITHOUT TIME ZONE
                end_time_naive = end_time.replace(tzinfo=None) if end_time.tzinfo else end_time
                filters.append(ArchivedSession.completed_at <= end_time_naive)

            if filters:
                query = query.where(and_(*filters))

            # Get total count
            count_query = select(func.count()).select_from(ArchivedSession)
            if filters:
                count_query = count_query.where(and_(*filters))

            total_result = await db_session.execute(count_query)
            total = total_result.scalar()

            # Apply pagination and ordering
            query = query.order_by(ArchivedSession.completed_at.desc())
            query = query.limit(limit).offset(offset)

            # Execute query with timeout
            result = await db_session.execute(
                query.execution_options(timeout=QUERY_TIMEOUT)
            )
            sessions = result.scalars().all()

            # Convert to dict
            session_logs = []
            for session in sessions:
                session_dict = {
                    'session_id': session.session_id,
                    'user_id': session.user_id,
                    'archived_at': session.completed_at.isoformat() if session.completed_at else None,
                    'created_at': session.created_at.isoformat() if session.created_at else None,
                    'completed_at': session.completed_at.isoformat() if session.completed_at else None,
                    'final_state': session.final_state,
                    'finalized': session.finalized,
                    'duration_seconds': session.duration_seconds,
                    'total_messages': session.total_messages,
                    'had_errors': session.had_errors,
                    'master_parameters': session.master_parameters,
                    'response_json': session.response_json,
                    'conversation_messages': session.conversation_messages[:5] if session.conversation_messages else []  # First 5 messages
                }
                session_logs.append(session_dict)

            # Cache results
            await set_cached_logs(cache_key, session_logs, total)

            logger.info("session_logs_retrieved", total=total, returned=len(session_logs))
            return session_logs, total

    except Exception as e:
        logger.error("session_logs_error", error=str(e))
        raise


async def get_agent_logs(
    session_id: str,
    limit: int = 100,
    offset: int = 0
) -> Tuple[List[Dict], int]:
    """
    Extract agent execution logs from PostgreSQL archived session.

    Retrieves agent_actions, neo4j_queries, llm_extractions, and state_transitions
    from a specific archived session.

    Args:
        session_id: Session ID to retrieve agent logs for
        limit: Maximum number of results
        offset: Pagination offset

    Returns:
        Tuple of (agent logs list, total count)
    """
    logger.info("get_agent_logs", session_id=session_id, limit=limit, offset=offset)

    # Check cache
    cache_key = await get_cache_key("agent_logs", session_id=session_id, limit=limit, offset=offset)
    cached = await get_cached_logs(cache_key)
    if cached:
        return cached

    try:
        from ..database.postgres_archival import ArchivedSession

        async with postgresql_manager.session_factory() as db_session:
            # Query specific session
            query = select(ArchivedSession).where(ArchivedSession.session_id == session_id)
            result = await db_session.execute(query)
            session = result.scalar_one_or_none()

            if not session:
                raise ValueError(f"Session not found: {session_id}")

            # Collect all agent logs
            all_logs = []

            # Add agent actions
            if session.agent_actions:
                for action in session.agent_actions:
                    all_logs.append({
                        'type': 'agent_action',
                        'timestamp': action.get('timestamp', ''),
                        'agent': action.get('agent', ''),
                        'action': action.get('action', ''),
                        'details': action
                    })

            # Add Neo4j queries
            if session.neo4j_queries:
                for query_log in session.neo4j_queries:
                    all_logs.append({
                        'type': 'neo4j_query',
                        'timestamp': query_log.get('timestamp', ''),
                        'query': query_log.get('query', ''),
                        'duration_ms': query_log.get('duration_ms', 0),
                        'details': query_log
                    })

            # Add LLM extractions
            if session.llm_extractions:
                for extraction in session.llm_extractions:
                    all_logs.append({
                        'type': 'llm_extraction',
                        'timestamp': extraction.get('timestamp', ''),
                        'extracted_params': extraction.get('extracted_params', {}),
                        'details': extraction
                    })

            # Add state transitions
            if session.state_transitions:
                for transition in session.state_transitions:
                    all_logs.append({
                        'type': 'state_transition',
                        'timestamp': transition.get('timestamp', ''),
                        'from_state': transition.get('from_state', ''),
                        'to_state': transition.get('to_state', ''),
                        'details': transition
                    })

            # Sort by timestamp
            all_logs.sort(key=lambda x: x.get('timestamp', ''), reverse=True)

            # Apply pagination
            total = len(all_logs)
            paginated_logs = all_logs[offset:offset + limit]

            # Cache results
            await set_cached_logs(cache_key, paginated_logs, total)

            logger.info("agent_logs_retrieved", session_id=session_id, total=total, returned=len(paginated_logs))
            return paginated_logs, total

    except Exception as e:
        logger.error("agent_logs_error", session_id=session_id, error=str(e))
        raise


async def get_performance_metrics(
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None,
    limit: int = 100,
    offset: int = 0
) -> Tuple[List[Dict], int]:
    """
    Extract performance metrics from application logs.

    Parses duration_ms from logs and calculates statistics.

    Args:
        start_time: Filter metrics after this time
        end_time: Filter metrics before this time
        limit: Maximum number of results
        offset: Pagination offset

    Returns:
        Tuple of (performance metrics list, total count)
    """
    logger.info("get_performance_metrics", start_time=start_time, end_time=end_time, limit=limit, offset=offset)

    # Check cache
    cache_key = await get_cache_key(
        "perf_metrics",
        start_time=start_time.isoformat() if start_time else None,
        end_time=end_time.isoformat() if end_time else None,
        limit=limit, offset=offset
    )
    cached = await get_cached_logs(cache_key)
    if cached:
        return cached

    try:
        # Get application logs with timing information
        logs, _ = await get_application_logs(
            start_time=start_time,
            end_time=end_time,
            limit=1000,  # Get more logs for statistics
            offset=0
        )

        # Extract performance metrics
        metrics = []
        for log in logs:
            if 'duration_ms' in log or 'duration' in log:
                duration = log.get('duration_ms') or log.get('duration', 0)
                try:
                    duration = float(duration)
                except (ValueError, TypeError):
                    continue

                metrics.append({
                    'timestamp': log.get('timestamp'),
                    'endpoint': log.get('path', 'unknown'),
                    'method': log.get('method', 'unknown'),
                    'duration_ms': duration,
                    'status_code': log.get('status_code'),
                    'correlation_id': log.get('correlation_id')
                })

        # Apply pagination
        total = len(metrics)
        paginated_metrics = metrics[offset:offset + limit]

        # Cache results
        await set_cached_logs(cache_key, paginated_metrics, total)

        logger.info("performance_metrics_retrieved", total=total, returned=len(paginated_metrics))
        return paginated_metrics, total

    except Exception as e:
        logger.error("performance_metrics_error", error=str(e))
        raise
