"""
Database configuration for Redis and PostgreSQL.

Redis: Hot session data with LangGraph checkpointing
PostgreSQL: Archival storage and analytics
"""

import logging
import os
from typing import AsyncGenerator, Optional
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.pool import NullPool

logger = logging.getLogger(__name__)


class Base(DeclarativeBase):
    """SQLAlchemy declarative base for PostgreSQL models."""
    pass


class RedisManager:
    """
    Redis manager for hot session data and LangGraph checkpoints.

    Features:
    - Session state caching (24hr TTL)
    - LangGraph checkpoint storage
    - Async connection pooling
    """

    def __init__(self):
        """Initialize Redis manager with .env configuration."""
        self.redis_url = os.getenv("REDIS_URL")
        self.redis_host = os.getenv("REDIS_HOST", "localhost")
        self.redis_port = int(os.getenv("REDIS_PORT", "6379"))
        self.redis_password = os.getenv("REDIS_PASSWORD")
        self.redis_db = int(os.getenv("REDIS_DB", "0"))
        self.enable_caching = os.getenv("ENABLE_REDIS_CACHING", "true").lower() == "true"
        self.cache_ttl = int(os.getenv("CACHE_TTL", "3600"))

        self.client: Optional[Redis] = None
        self._initialized = False

    async def init_redis(self):
        """Initialize Redis connection."""
        if self._initialized:
            return

        try:
            # Use REDIS_URL if available, otherwise construct from components
            if self.redis_url:
                self.client = Redis.from_url(
                    self.redis_url,
                    decode_responses=True,
                    encoding="utf-8"
                )
            else:
                self.client = Redis(
                    host=self.redis_host,
                    port=self.redis_port,
                    password=self.redis_password,
                    db=self.redis_db,
                    decode_responses=True,
                    encoding="utf-8"
                )

            # Test connection
            await self.client.ping()
            self._initialized = True
            logger.info(f"Redis connected: {self.redis_host}:{self.redis_port}")

        except Exception as e:
            logger.error(f"Redis connection failed: {e}")
            self.client = None
            raise

    async def close(self):
        """Close Redis connection."""
        if self.client:
            await self.client.close()
            logger.info("Redis connection closed")


class PostgreSQLManager:
    """
    PostgreSQL manager for archival storage and analytics.

    Features:
    - Session archival (permanent storage)
    - Analytics queries
    - Async SQLAlchemy session management
    """

    def __init__(self):
        """Initialize PostgreSQL manager with .env configuration."""
        self.postgres_host = os.getenv("POSTGRES_HOST", "localhost")
        self.postgres_port = int(os.getenv("POSTGRES_PORT", "5432"))
        self.postgres_db = os.getenv("POSTGRES_DB", "pconfig")
        self.postgres_user = os.getenv("POSTGRES_USER", "postgres")
        self.postgres_password = os.getenv("POSTGRES_PASSWORD", "root")

        self.engine = None
        self.session_factory = None
        self._initialized = False

    def init_db(self):
        """Initialize PostgreSQL engine and session factory."""
        if self._initialized:
            return

        # Create async database URL
        database_url = (
            f"postgresql+asyncpg://{self.postgres_user}:"
            f"{self.postgres_password}@{self.postgres_host}:"
            f"{self.postgres_port}/{self.postgres_db}"
        )

        # Create async engine
        self.engine = create_async_engine(
            database_url,
            echo=False,  # Set to True for SQL debugging
            poolclass=NullPool,  # Use NullPool to avoid connection pool conflicts
            future=True
        )

        # Create session factory
        self.session_factory = async_sessionmaker(
            bind=self.engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autoflush=True,
            autocommit=False
        )

        self._initialized = True
        logger.info(f"PostgreSQL connected: {self.postgres_host}:{self.postgres_port}/{self.postgres_db}")

    async def close(self):
        """Close PostgreSQL engine."""
        if self.engine:
            await self.engine.dispose()
            logger.info("PostgreSQL engine disposed")


class Neo4jManager:
    """
    Neo4j driver manager with centralized connection pooling.

    Features:
    - Single driver instance (singleton pattern)
    - Connection pooling coordination
    - Health checks and monitoring
    - Automatic reconnection on failures
    """

    def __init__(self):
        """Initialize Neo4j manager with configuration."""
        self.uri: Optional[str] = None
        self.username: Optional[str] = None
        self.password: Optional[str] = None
        self.driver: Optional[object] = None  # AsyncDriver type
        self._initialized = False
        self._reconnect_attempts = 0
        self._max_reconnect_attempts = 3

        # Connection pool configuration
        self._max_connection_lifetime = 3600  # 1 hour
        self._max_connection_pool_size = 50
        self._connection_acquisition_timeout = 60  # seconds

    async def init_neo4j(
        self,
        uri: str,
        username: str,
        password: str
    ):
        """
        Initialize Neo4j driver with connection pooling.

        Args:
            uri: Neo4j connection URI (bolt:// or neo4j://)
            username: Neo4j username
            password: Neo4j password
        """
        if self._initialized:
            logger.info("Neo4j already initialized")
            return

        self.uri = uri
        self.username = username
        self.password = password

        try:
            # Import here to avoid circular dependency
            from neo4j import AsyncGraphDatabase

            # Create driver with connection pool configuration
            # Note: encrypted parameter can only be used with bolt:// and neo4j:// schemes
            # For bolt+s:// and neo4j+s:// schemes, encryption is implicit and should not be specified
            driver_config = {
                "auth": (username, password),
                "max_connection_lifetime": self._max_connection_lifetime,
                "max_connection_pool_size": self._max_connection_pool_size,
                "connection_acquisition_timeout": self._connection_acquisition_timeout,
            }

            # Only add encrypted parameter for non-encrypted schemes
            if uri.startswith("bolt://") or uri.startswith("neo4j://"):
                driver_config["encrypted"] = False  # Explicitly no encryption for development

            self.driver = AsyncGraphDatabase.driver(uri, **driver_config)

            # Health check - verify connection
            await self._verify_connectivity()

            self._initialized = True
            self._reconnect_attempts = 0

            logger.info(f"✅ Neo4j driver initialized - URI: {uri}")
            logger.info(f"   Connection pool: max_size={self._max_connection_pool_size}, "
                       f"max_lifetime={self._max_connection_lifetime}s")

        except Exception as e:
            logger.error(f"❌ Failed to initialize Neo4j driver: {e}")
            raise

    async def _verify_connectivity(self):
        """
        Verify Neo4j connection with simple query.

        Raises:
            Exception if connection fails
        """
        if not self.driver:
            raise ValueError("Driver not initialized")

        try:
            async with self.driver.session() as session:
                result = await session.run("RETURN 1 as test")
                record = await result.single()
                assert record["test"] == 1

            logger.info("✅ Neo4j connectivity verified")

        except Exception as e:
            logger.error(f"❌ Neo4j connectivity check failed: {e}")
            raise

    async def get_driver(self):
        """
        Get Neo4j driver instance with automatic reconnection.

        Returns:
            AsyncDriver instance

        Raises:
            RuntimeError if driver not initialized or reconnection fails
        """
        if not self._initialized or not self.driver:
            raise RuntimeError("Neo4j driver not initialized. Call init_neo4j() first.")

        # Import here to avoid circular dependency
        from neo4j.exceptions import ServiceUnavailable, SessionExpired

        # Check if driver is still connected
        try:
            await self._verify_connectivity()
            self._reconnect_attempts = 0  # Reset on success
            return self.driver

        except (ServiceUnavailable, SessionExpired) as e:
            logger.warning(f"⚠️ Neo4j connection lost: {e}")

            # Attempt reconnection
            if self._reconnect_attempts < self._max_reconnect_attempts:
                logger.info(f"🔄 Attempting reconnection ({self._reconnect_attempts + 1}/{self._max_reconnect_attempts})")
                await self._reconnect()
                return self.driver
            else:
                logger.error(f"❌ Max reconnection attempts ({self._max_reconnect_attempts}) exceeded")
                raise RuntimeError("Neo4j connection lost and reconnection failed")

    async def _reconnect(self):
        """
        Attempt to reconnect to Neo4j with exponential backoff.
        """
        import asyncio

        self._reconnect_attempts += 1

        # Exponential backoff
        delay = min(2 ** self._reconnect_attempts, 30)  # Max 30 seconds
        logger.info(f"Waiting {delay}s before reconnection attempt...")
        await asyncio.sleep(delay)

        try:
            # Close existing driver
            if self.driver:
                await self.driver.close()

            # Reinitialize
            self._initialized = False
            await self.init_neo4j(self.uri, self.username, self.password)

            logger.info("✅ Neo4j reconnection successful")

        except Exception as e:
            logger.error(f"❌ Reconnection attempt failed: {e}")
            raise

    async def close(self):
        """
        Close Neo4j driver and cleanup resources.
        """
        if self.driver:
            try:
                await self.driver.close()
                logger.info("✅ Neo4j driver closed")
            except Exception as e:
                logger.error(f"Error closing Neo4j driver: {e}")
            finally:
                self.driver = None
                self._initialized = False
                self._reconnect_attempts = 0


# Global manager instances
redis_manager = RedisManager()
postgresql_manager = PostgreSQLManager()
neo4j_manager = Neo4jManager()


# Initialization functions
async def init_redis():
    """Initialize Redis connection."""
    await redis_manager.init_redis()


def init_postgresql():
    """Initialize PostgreSQL engine."""
    postgresql_manager.init_db()


async def init_neo4j(uri: str, username: str, password: str):
    """Initialize Neo4j connection manager."""
    await neo4j_manager.init_neo4j(uri, username, password)


# Dependency injection functions
async def get_redis_client() -> Redis:
    """
    Dependency for getting Redis client.

    Returns:
        Redis client instance
    """
    if not redis_manager._initialized:
        await redis_manager.init_redis()

    return redis_manager.client


async def get_postgres_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency for getting PostgreSQL session.

    Yields:
        SQLAlchemy async session
    """
    if not postgresql_manager._initialized:
        postgresql_manager.init_db()

    async with postgresql_manager.session_factory() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def get_neo4j_driver():
    """
    Dependency for getting Neo4j driver.

    Returns:
        Neo4j AsyncDriver instance

    Raises:
        RuntimeError if driver not initialized
    """
    return await neo4j_manager.get_driver()


# Cleanup functions
async def close_redis():
    """Close Redis connections."""
    await redis_manager.close()


async def close_postgresql():
    """Close PostgreSQL connections."""
    await postgresql_manager.close()


async def close_neo4j():
    """Close Neo4j connections."""
    await neo4j_manager.close()
