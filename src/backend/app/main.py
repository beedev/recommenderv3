"""
Recommender_v2 - S1→SN Dynamic State Configurator
FastAPI Application Entry Point
"""

import logging
import logging.config
import logging.handlers
import json
import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path
import structlog
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv

from .api.v1.configurator import router as configurator_router
from .api.v1.health import router as health_router
from .api.v1.logs import router as logs_router
from .middleware import LoggingMiddleware, SessionContextMiddleware
from .services.intent.parameter_extractor import ParameterExtractor
from .services.neo4j.product_search import Neo4jProductSearch
from .services.response.message_generator import MessageGenerator
from .services.orchestrator.state_orchestrator import StateByStateOrchestrator

# Database and LangGraph imports
from .database.database import (
    init_redis,
    init_postgresql,
    init_neo4j,
    close_redis,
    close_postgresql,
    close_neo4j,
    get_redis_client,
    get_neo4j_driver,
    Base
)
from .database.redis_session_storage import init_redis_session_storage
from .database.postgres_archival import postgres_archival_service
from .services.observability.langsmith_service import get_langsmith_service
from .services.config.config_monitor import init_config_monitor
from .services.config.config_validator import validate_configs_on_startup
from .services.config.configuration_service import get_config_service
from .models.conversation import init_configurator_state
from .services.orchestrator.state_processors import init_processor_registry

# Load environment variables
load_dotenv()

# Configure structured logging with structlog
def configure_logging():
    """
    Configure structured logging using structlog.

    - Production (ENV=production): JSON output for log aggregation
    - Development (ENV=development): Human-readable console output
    - Includes automatic context: timestamp, level, logger name, correlation_id, session_id
    """
    # Get environment and log level from environment variables
    env = os.getenv("ENV", "development").lower()
    log_level_str = os.getenv("LOG_LEVEL", "INFO").upper()
    log_level = getattr(logging, log_level_str, logging.INFO)

    # Configure timestamper
    timestamper = structlog.processors.TimeStamper(fmt="iso")

    # Shared processors for all environments
    shared_processors = [
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.contextvars.merge_contextvars,
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        timestamper,
    ]

    # Environment-specific renderer
    if env == "production":
        # JSON output for production (machine-readable, log aggregator friendly)
        renderer = structlog.processors.JSONRenderer()
    else:
        # Human-readable console output for development
        renderer = structlog.dev.ConsoleRenderer(
            colors=True,
            exception_formatter=structlog.dev.plain_traceback
        )

    # Configure structlog
    structlog.configure(
        processors=shared_processors + [
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        cache_logger_on_first_use=True,
    )

    # Configure standard library logging to work with structlog
    formatter = structlog.stdlib.ProcessorFormatter(
        foreign_pre_chain=shared_processors,
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            renderer,
        ],
    )

    # Get log file path from environment, with absolute path default
    # Calculate project root (3 levels up from backend/app/main.py)
    current_dir = Path(__file__).resolve().parent  # app/
    backend_dir = current_dir.parent  # backend/
    src_dir = backend_dir.parent  # src/
    project_root = src_dir.parent  # project root

    # Default log path at project root
    default_log_path = project_root / "logs" / "esab-recommender.log"
    log_file_path = os.getenv("LOG_FILE_PATH", str(default_log_path))

    # Ensure we're using absolute path
    log_file_path = str(Path(log_file_path).resolve())
    log_dir = os.path.dirname(log_file_path)

    # Create log directory if it doesn't exist
    if log_dir:
        os.makedirs(log_dir, exist_ok=True)
    
    # Setup stdout handler (keep existing console logging)
    stdout_handler = logging.StreamHandler(sys.stdout)
    stdout_handler.setFormatter(formatter)
    
    # Setup file handler with rotation
    file_handler = logging.handlers.RotatingFileHandler(
        filename=log_file_path,
        maxBytes=10 * 1024 * 1024,  # 10MB per file
        backupCount=5,               # Keep 5 backup files (50MB total)
        encoding='utf-8'
    )
    file_handler.setFormatter(formatter)
    
    # Configure root logger with BOTH handlers
    root_logger = logging.getLogger()
    root_logger.addHandler(stdout_handler)   # Console
    root_logger.addHandler(file_handler)     # File
    root_logger.setLevel(log_level)

    # Reduce noise from verbose libraries
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)

    return structlog.get_logger(__name__)

# Initialize structured logging
logger = configure_logging()

# Global instances
parameter_extractor = None
neo4j_search = None
message_generator = None
orchestrator = None
powersource_state_specifications_config = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager - startup and shutdown"""

    # Startup
    logger.info("Starting Recommender_v2 application...")

    global parameter_extractor, neo4j_search, message_generator, orchestrator, powersource_state_specifications_config

    # Load environment variables
    openai_api_key = os.getenv("OPENAI_API_KEY")
    neo4j_uri = os.getenv("NEO4J_URI")
    neo4j_username = os.getenv("NEO4J_USERNAME")
    neo4j_password = os.getenv("NEO4J_PASSWORD")

    if not all([openai_api_key, neo4j_uri, neo4j_username, neo4j_password]):
        raise ValueError("Missing required environment variables")

    # Initialize databases
    logger.info("Initializing databases...")

    # Check if Redis is enabled via environment variable
    enable_redis = os.getenv("ENABLE_REDIS_CACHING", "true").lower() == "true"

    if enable_redis:
        try:
            # Initialize Redis for hot session data
            await init_redis()
            logger.info("✓ Redis initialized")

            # Initialize Redis session storage
            redis_client = await get_redis_client()
            session_ttl = get_config_service().get_session_ttl()
            init_redis_session_storage(redis_client, ttl=session_ttl)
            logger.info("✓ Redis session storage initialized")
        except Exception as e:
            logger.warning(f"Redis initialization failed: {e}. Continuing without Redis caching.")
    else:
        # Redis disabled - use in-memory session storage
        logger.info("Redis disabled via ENABLE_REDIS_CACHING=false")
        session_ttl = get_config_service().get_session_ttl()
        init_redis_session_storage(redis_client=None, ttl=session_ttl)
        logger.info("✓ In-memory session storage initialized (no persistence across restarts)")

    try:
        # Initialize PostgreSQL for archival
        init_postgresql()
        logger.info("✓ PostgreSQL initialized")

        # Create database tables
        from sqlalchemy.ext.asyncio import create_async_engine
        from .database.database import postgresql_manager

        async with postgresql_manager.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        logger.info("✓ Database tables created/verified")

    except Exception as e:
        logger.warning(f"PostgreSQL initialization failed: {e}. Continuing without archival.")

    # Initialize LangSmith observability
    langsmith_service = get_langsmith_service()
    if langsmith_service.is_enabled():
        logger.info("✓ LangSmith observability enabled")
    else:
        logger.info("LangSmith observability disabled")

    # Load PowerSource state specifications config
    config_path = os.path.join(
        os.path.dirname(__file__),
        "config",
        "powersource_state_specifications.json"
    )

    with open(config_path, 'r') as f:
        powersource_state_specifications_config = json.load(f)

    logger.info("Loaded PowerSource state specifications configuration")

    # Validate configurations on startup
    logger.info("Validating configurations...")
    try:
        is_valid, report = validate_configs_on_startup()
        if is_valid:
            logger.info("✓ Configuration validation passed")
        else:
            logger.warning("Configuration validation found issues - check logs for details")
    except Exception as e:
        logger.error(f"Configuration validation failed: {e}")
        logger.warning("Continuing with startup despite validation errors")

    # Initialize configuration monitor
    try:
        init_config_monitor()
        logger.info("✓ Configuration monitor initialized")
    except Exception as e:
        logger.warning(f"Config monitor initialization failed: {e}")

    # Initialize dynamic state machine components
    logger.info("Initializing dynamic state machine...")
    try:
        # Initialize ConfiguratorState enum from configuration
        init_configurator_state()
        logger.info("✓ ConfiguratorState enum initialized")

        # Initialize processor registry
        init_processor_registry()
        logger.info("✓ Processor registry initialized")
    except Exception as e:
        logger.error(f"Dynamic state machine initialization failed: {e}")
        logger.warning("Falling back to hardcoded state machine")

    # Initialize Neo4j driver (centralized connection management)
    await init_neo4j(neo4j_uri, neo4j_username, neo4j_password)
    neo4j_driver = await get_neo4j_driver()
    logger.info("✓ Neo4j driver initialized")

    # Initialize services
    parameter_extractor = ParameterExtractor(openai_api_key)
    neo4j_search = Neo4jProductSearch(driver=neo4j_driver)
    message_generator = MessageGenerator()

    # Phase 1: Initialize Pluggable Search Architecture (Configuration-Driven)
    from .services.search.strategy_factory import StrategyFactory
    from .services.search.consolidator import ResultConsolidator
    from .services.search.orchestrator import SearchOrchestrator
    from .services.config.configuration_service import get_config_service
    from openai import AsyncOpenAI

    # Load search configuration
    config_service = get_config_service()
    search_config = config_service.get_search_config()

    # Initialize OpenAI client for vector and LLM strategies
    openai_client = AsyncOpenAI(api_key=openai_api_key)

    # Create all strategies automatically from search_config.json
    strategy_factory = StrategyFactory(
        search_config=search_config,
        neo4j_product_search=neo4j_search,
        openai_client=openai_client
    )
    all_strategies = strategy_factory.create_all_strategies()

    # Build consolidator config from search_config.json
    strategy_weights = {
        name: cfg.get("weight", 0.5)
        for name, cfg in search_config.get("strategies", {}).items()
        if isinstance(cfg, dict)  # Filter out description fields
    }
    consolidator_config = search_config.get("consolidation", {})
    consolidator_config["strategy_weights"] = strategy_weights
    consolidator_config.setdefault("default_score_for_unscored", 0.5)
    consolidator_config.setdefault("score_normalization", "none")

    # Create result consolidator
    consolidator = ResultConsolidator(config=consolidator_config)

    # Build orchestrator config from search_config.json
    orchestration_config = search_config.get("orchestration", {})
    orchestration_config.setdefault("execution_mode", "parallel")
    orchestration_config.setdefault("timeout_seconds", 30)
    orchestration_config.setdefault("fallback_on_error", True)
    orchestration_config.setdefault("require_at_least_one_success", True)

    # Create search orchestrator with all strategies
    search_orchestrator = SearchOrchestrator(
        strategies=all_strategies,
        consolidator=consolidator,
        config=orchestration_config
    )

    logger.info(f"✓ SearchOrchestrator initialized with {len(all_strategies)} strategies: {[s.get_name() for s in all_strategies]}")

    # Phase 2: Initialize streamlined orchestrator (creates its own processor registry)
    # No longer need separate registry initialization - orchestrator handles it internally
    orchestrator = StateByStateOrchestrator(
        parameter_extractor=parameter_extractor,
        message_generator=message_generator,
        search_orchestrator=search_orchestrator,
        state_config_path="app/config/state_config.json",
        powersource_applicability_config=powersource_state_specifications_config
    )

    logger.info("✓ Orchestrator initialized")
    logger.info("All services initialized successfully")

    yield

    # Shutdown
    logger.info("Shutting down Recommender_v2 application...")

    # Stop in-memory session storage cleanup task if running
    try:
        from .database.redis_session_storage import get_redis_session_storage
        storage = get_redis_session_storage()
        if storage and hasattr(storage, 'stop_cleanup_loop'):
            await storage.stop_cleanup_loop()
            logger.info("✓ Session storage cleanup task stopped")
    except Exception as e:
        logger.error(f"Error stopping session storage cleanup: {e}")

    # Close databases
    try:
        await close_redis()
        logger.info("✓ Redis closed")
    except Exception as e:
        logger.error(f"Error closing Redis: {e}")

    try:
        await close_postgresql()
        logger.info("✓ PostgreSQL closed")
    except Exception as e:
        logger.error(f"Error closing PostgreSQL: {e}")

    # Close Neo4j (centralized driver management)
    try:
        await close_neo4j()
        logger.info("✓ Neo4j driver closed")
    except Exception as e:
        logger.error(f"Error closing Neo4j: {e}")

    logger.info("Shutdown complete")


# Create FastAPI application
app = FastAPI(
    title="Recommender_v2 - S1→SN Configurator",
    description="State-by-state welding equipment configurator with compatibility validation",
    version="2.0.0",
    lifespan=lifespan
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Update for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add logging middleware for correlation IDs and request tracking
# Note: Middleware is executed in reverse order of addition
# So SessionContextMiddleware runs BEFORE LoggingMiddleware
app.add_middleware(SessionContextMiddleware)
app.add_middleware(LoggingMiddleware)


# Dependency injection for orchestrator
def get_orchestrator() -> StateByStateOrchestrator:
    """Get orchestrator instance for dependency injection"""
    return orchestrator


# Include routers
app.include_router(configurator_router)
app.include_router(health_router)
app.include_router(logs_router)

# Override dependency in app (not router)
from .api.v1.configurator import get_orchestrator_dep
app.dependency_overrides[get_orchestrator_dep] = get_orchestrator

# Mount static files (HTML test interfaces)
# Static files are in src/frontend/ directory
static_dir = Path(__file__).parent.parent.parent / "frontend"
if (static_dir / "index.html").exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")
    logger.info(f"✓ Static files mounted from: {static_dir}")


@app.get("/")
async def root():
    """Root endpoint - health check"""
    return {
        "service": "Recommender_v2",
        "version": "2.0.0",
        "description": "S1→SN Dynamic State Welding Equipment Configurator",
        "endpoints": {
            "configurator": "/api/v1/configurator/message",
            "docs": "/docs"
        }
    }


@app.get("/health")
async def health_check():
    """Health check endpoint"""

    from .database.database import redis_manager, postgresql_manager
    from .database.redis_session_storage import get_redis_session_storage, InMemorySessionStorage

    langsmith_service = get_langsmith_service()

    # Determine session storage type
    session_storage = get_redis_session_storage()
    storage_type = "in-memory" if isinstance(session_storage, InMemorySessionStorage) else "redis"
    session_ttl = get_config_service().get_session_ttl()

    health_status = {
        "status": "healthy",
        "services": {
            "parameter_extractor": parameter_extractor is not None,
            "neo4j_search": neo4j_search is not None,
            "message_generator": message_generator is not None,
            "orchestrator": orchestrator is not None,
            "redis": redis_manager._initialized,
            "postgresql": postgresql_manager._initialized,
            "langsmith": langsmith_service.is_enabled()
        },
        "session_storage": {
            "type": storage_type,
            "ttl_seconds": session_ttl,
            "persistent": storage_type == "redis",
            "note": "Sessions are not persisted across restarts" if storage_type == "in-memory" else "Sessions are persisted in Redis"
        }
    }

    # Core services must be healthy
    core_services_healthy = all([
        health_status["services"]["parameter_extractor"],
        health_status["services"]["neo4j_search"],
        health_status["services"]["message_generator"],
        health_status["services"]["orchestrator"]
    ])

    if not core_services_healthy:
        health_status["status"] = "unhealthy"

    return health_status


if __name__ == "__main__":
    import uvicorn

    # Run on port 8000
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
