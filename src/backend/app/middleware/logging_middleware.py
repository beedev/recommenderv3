"""
Logging Middleware for Correlation ID and Request Tracking

Automatically generates or extracts correlation IDs for every request,
enabling end-to-end request tracing across the entire system.
"""

import uuid
import time
from typing import Callable
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
import structlog
from structlog.contextvars import bind_contextvars, clear_contextvars

logger = structlog.get_logger(__name__)


class LoggingMiddleware(BaseHTTPMiddleware):
    """
    Middleware to inject correlation IDs and request context into all logs.

    Features:
    - Generates unique correlation_id for each request
    - Accepts correlation_id from X-Correlation-ID header
    - Binds correlation_id to contextvar for automatic inclusion in all logs
    - Adds correlation_id to response headers
    - Logs request/response timing
    - Adds request metadata (method, path, client IP)
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        Process each request and inject logging context.

        Args:
            request: FastAPI Request object
            call_next: Next middleware or route handler

        Returns:
            Response with correlation_id header added
        """
        # Clear any existing context from previous requests
        clear_contextvars()

        # Extract or generate correlation ID
        correlation_id = request.headers.get("X-Correlation-ID")
        if not correlation_id:
            correlation_id = str(uuid.uuid4())

        # Extract client IP
        client_ip = request.client.host if request.client else "unknown"

        # Bind correlation ID and request metadata to context
        # This will be automatically included in all logs during this request
        bind_contextvars(
            correlation_id=correlation_id,
            request_method=request.method,
            request_path=request.url.path,
            client_ip=client_ip,
        )

        # Start timing
        start_time = time.time()

        # Log incoming request
        logger.info(
            "request_started",
            method=request.method,
            path=request.url.path,
            query_params=dict(request.query_params),
        )

        # Process request
        try:
            response = await call_next(request)

            # Calculate request duration
            duration_ms = int((time.time() - start_time) * 1000)

            # Add correlation ID to response headers
            response.headers["X-Correlation-ID"] = correlation_id

            # Log successful response
            logger.info(
                "request_completed",
                status_code=response.status_code,
                duration_ms=duration_ms,
            )

            return response

        except Exception as e:
            # Calculate duration even for errors
            duration_ms = int((time.time() - start_time) * 1000)

            # Log error
            logger.error(
                "request_failed",
                error=str(e),
                error_type=type(e).__name__,
                duration_ms=duration_ms,
                exc_info=True,
            )

            # Re-raise to let FastAPI handle it
            raise

        finally:
            # Clear context after request completes
            clear_contextvars()


class SessionContextMiddleware(BaseHTTPMiddleware):
    """
    Middleware to extract and bind session_id from request body to logging context.

    This runs after LoggingMiddleware and adds session-specific context.
    Note: Only works for JSON bodies containing session_id field.
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        Extract session_id from request body and add to logging context.

        Args:
            request: FastAPI Request object
            call_next: Next middleware or route handler

        Returns:
            Response object
        """
        # Try to extract session_id from request
        # This is a best-effort approach - some routes may not have session_id
        session_id = None

        # Check if request has JSON body
        if request.method in ["POST", "PUT", "PATCH"]:
            try:
                # Get content type
                content_type = request.headers.get("content-type", "")

                if "application/json" in content_type:
                    # Read body (this consumes the stream)
                    body = await request.body()

                    if body:
                        import json
                        try:
                            body_json = json.loads(body.decode())
                            session_id = body_json.get("session_id")

                            # We need to restore the body for downstream handlers
                            # This is a workaround since request.body() consumes the stream
                            async def receive():
                                return {"type": "http.request", "body": body}

                            request._receive = receive

                        except (json.JSONDecodeError, UnicodeDecodeError):
                            pass

            except Exception:
                # If anything goes wrong, just continue without session_id
                pass

        # If we found a session_id, bind it to context
        if session_id:
            bind_contextvars(session_id=session_id)

        # Process request
        response = await call_next(request)

        return response
