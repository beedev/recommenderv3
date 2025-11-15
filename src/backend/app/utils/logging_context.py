"""
Logging Context Management Utilities

Provides helpers for adding and managing context in structured logs.
Context automatically appears in all log statements within the scope.
"""

from contextlib import contextmanager
from typing import Dict, Any, Optional
import structlog
from structlog.contextvars import bind_contextvars, unbind_contextvars


def bind_session_context(
    session_id: Optional[str] = None,
    user_id: Optional[str] = None,
    customer_id: Optional[str] = None,
    **kwargs
):
    """
    Bind session-related context to all logs.

    Args:
        session_id: Unique session identifier
        user_id: User identifier
        customer_id: Customer/organization identifier
        **kwargs: Additional context key-value pairs

    Example:
        ```python
        from app.utils.logging_context import bind_session_context
        import structlog

        logger = structlog.get_logger(__name__)

        # Bind session context
        bind_session_context(session_id="abc123", user_id="user_42")

        # All subsequent logs will include session_id and user_id
        logger.info("processing request")  # Automatically includes session_id, user_id
        ```
    """
    context = {}

    if session_id:
        context["session_id"] = session_id
    if user_id:
        context["user_id"] = user_id
    if customer_id:
        context["customer_id"] = customer_id

    # Add any additional context
    context.update(kwargs)

    # Bind to contextvars (available to all logs in this execution context)
    bind_contextvars(**context)


def bind_agent_context(
    agent_name: str,
    agent_step: Optional[int] = None,
    **kwargs
):
    """
    Bind agent-specific context for multi-agent orchestration tracking.

    Args:
        agent_name: Name of the agent (e.g., "parameter_extractor", "product_search")
        agent_step: Step number in multi-agent workflow
        **kwargs: Additional agent context

    Example:
        ```python
        bind_agent_context(agent_name="parameter_extractor", agent_step=1)
        logger.info("extracting parameters")  # Includes agent_name, agent_step
        ```
    """
    context = {"agent_name": agent_name}

    if agent_step is not None:
        context["agent_step"] = agent_step

    context.update(kwargs)
    bind_contextvars(**context)


def bind_state_context(
    current_state: str,
    previous_state: Optional[str] = None,
    **kwargs
):
    """
    Bind state machine context for state transition tracking.

    Args:
        current_state: Current configurator state (e.g., "power_source_selection")
        previous_state: Previous state (for transition tracking)
        **kwargs: Additional state context

    Example:
        ```python
        bind_state_context(
            current_state="feeder_selection",
            previous_state="power_source_selection"
        )
        logger.info("state transition")
        ```
    """
    context = {"current_state": current_state}

    if previous_state:
        context["previous_state"] = previous_state

    context.update(kwargs)
    bind_contextvars(**context)


def unbind_context(*keys: str):
    """
    Remove specific keys from logging context.

    Args:
        *keys: Keys to remove from context

    Example:
        ```python
        unbind_context("agent_name", "agent_step")
        ```
    """
    unbind_contextvars(*keys)


@contextmanager
def log_context(**context_vars):
    """
    Context manager for temporary logging context.

    Context is automatically added on enter and removed on exit.

    Args:
        **context_vars: Key-value pairs to add to logging context

    Example:
        ```python
        with log_context(operation="product_search", query_type="fuzzy"):
            logger.info("searching products")  # Includes operation, query_type
            # ... do work ...
        # operation and query_type automatically removed after with block
        ```
    """
    # Bind context on entry
    bind_contextvars(**context_vars)

    try:
        yield
    finally:
        # Unbind context on exit
        unbind_contextvars(*context_vars.keys())


@contextmanager
def log_performance(operation_name: str, logger=None):
    """
    Context manager for logging operation performance.

    Automatically logs operation start, end, and duration.

    Args:
        operation_name: Name of the operation being timed
        logger: Logger instance (defaults to structlog.get_logger())

    Example:
        ```python
        with log_performance("neo4j_product_search"):
            results = await search_products(...)
        # Automatically logs: operation_name, duration_ms
        ```
    """
    import time

    if logger is None:
        logger = structlog.get_logger()

    start_time = time.time()

    logger.info(f"{operation_name}_started", operation=operation_name)

    try:
        yield
    finally:
        duration_ms = int((time.time() - start_time) * 1000)
        logger.info(
            f"{operation_name}_completed",
            operation=operation_name,
            duration_ms=duration_ms
        )


def get_logger_with_context(name: str, **context) -> structlog.BoundLogger:
    """
    Get a logger with pre-bound context.

    Useful for creating module-level loggers with static context.

    Args:
        name: Logger name (usually __name__)
        **context: Context to bind to all logs from this logger

    Returns:
        BoundLogger with context pre-bound

    Example:
        ```python
        # At module level
        logger = get_logger_with_context(__name__, component="orchestrator")

        # All logs from this logger will include component="orchestrator"
        logger.info("processing state")  # Includes component="orchestrator"
        ```
    """
    return structlog.get_logger(name).bind(**context)
