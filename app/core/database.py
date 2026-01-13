"""
Database connection and session management module.
Provides SQLAlchemy setup with async support, connection pooling, and health checks.
"""

import asyncio
import logging
import os
import time
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Optional, Dict, Any, List, Tuple

from sqlalchemy import text, MetaData
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    AsyncEngine,
    AsyncConnection,
    create_async_engine,
    async_sessionmaker,
)
from sqlalchemy.pool import AsyncAdaptedQueuePool, Pool
from sqlalchemy.exc import SQLAlchemyError, OperationalError

from app.core.config import settings
from app.core.metrics import database_metrics

logger = logging.getLogger(__name__)

# SQLAlchemy metadata for declarative base
metadata = MetaData()


class DatabaseConnectionError(Exception):
    """Custom exception for database connection failures."""
    pass


class DatabaseHealth:
    """Database health monitoring and metrics."""
    
    def __init__(self):
        self._connection_errors = 0
        self._last_health_check = 0
        self._health_check_interval = 30  # seconds
        self._is_healthy = True
        
    def record_error(self):
        """Record a connection error."""
        self._connection_errors += 1
        database_metrics.connection_errors.inc()
        
    def record_success(self):
        """Record a successful operation."""
        database_metrics.successful_operations.inc()
        
    def record_query(self, duration: float):
        """Record query execution time."""
        database_metrics.query_duration.observe(duration)
        
    async def check_health(self, engine: AsyncEngine) -> bool:
        """Perform health check on database."""
        current_time = time.time()
        if current_time - self._last_health_check < self._health_check_interval:
            return self._is_healthy
            
        try:
            async with engine.connect() as conn:
                start_time = time.time()
                await conn.execute(text("SELECT 1"))
                latency = time.time() - start_time
                
                database_metrics.health_check_latency.set(latency)
                self._is_healthy = True
                self._last_health_check = current_time
                
                # Check pool status
                pool: Pool = engine.pool
                database_metrics.connections_in_use.set(pool.checkedin())
                database_metrics.connections_idle.set(pool.checkedout())
                
                logger.debug(f"Database health check passed. Latency: {latency:.3f}s")
                return True
                
        except Exception as e:
            logger.error(f"Database health check failed: {e}")
            self._is_healthy = False
            self._last_health_check = current_time
            database_metrics.health_check_failures.inc()
            return False


class DatabaseManager:
    """
    Manages database connections, sessions, and connection pooling.
    Supports automatic reconnection and connection health monitoring.
    """
    
    def __init__(self):
        self._engine: Optional[AsyncEngine] = None
        self._session_factory: Optional[async_sessionmaker] = None
        self._health_monitor = DatabaseHealth()
        self._initialized = False
        self._shutting_down = False
        
    def _build_connection_string(self) -> str:
        """Build database connection string from settings."""
        if settings.DATABASE_URL:
            return settings.DATABASE_URL
            
        # Construct from individual components
        driver = "asyncpg"  # Default async driver for PostgreSQL
        return (
            f"postgresql+{driver}://"
            f"{settings.POSTGRES_USER}:{settings.POSTGRES_PASSWORD}"
            f"@{settings.POSTGRES_HOST}:{settings.POSTGRES_PORT}"
            f"/{settings.POSTGRES_DB}"
        )
        
    def _create_engine(self) -> AsyncEngine:
        """Create and configure SQLAlchemy async engine."""
        connection_string = self._build_connection_string()
        
        # Connection pool configuration
        pool_config = {
            "poolclass": AsyncAdaptedQueuePool,
            "pool_size": settings.DB_POOL_SIZE,
            "max_overflow": settings.DB_MAX_OVERFLOW,
            "pool_timeout": settings.DB_POOL_TIMEOUT,
            "pool_recycle": settings.DB_POOL_RECYCLE,
            "pool_pre_ping": settings.DB_POOL_PRE_PING,
            "echo": settings.DB_ECHO,
            "echo_pool": settings.DB_ECHO_POOL,
            "hide_parameters": not settings.DB_SHOW_PARAMETERS,
        }
        
        # SSL configuration if needed
        if settings.DB_SSL_ENABLED:
            pool_config["connect_args"] = {
                "ssl": "require" if settings.DB_SSL_REQUIRE else "prefer"
            }
            
        logger.info(
            f"Creating database engine for {settings.POSTGRES_HOST}:"
            f"{settings.POSTGRES_PORT}/{settings.POSTGRES_DB}"
        )
        logger.debug(f"Pool config: size={pool_config['pool_size']}, "
                    f"max_overflow={pool_config['max_overflow']}")
        
        return create_async_engine(
            connection_string,
            **pool_config,
            future=True,
        )
        
    async def initialize(self) -> None:
        """Initialize database connection and verify connectivity."""
        if self._initialized:
            return
            
        try:
            self._engine = self._create_engine()
            
            # Test connection
            async with self._engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
                
            # Create session factory
            self._session_factory = async_sessionmaker(
                self._engine,
                class_=AsyncSession,
                expire_on_commit=False,
                autocommit=False,
                autoflush=False,
            )
            
            self._initialized = True
            self._health_monitor.record_success()
            
            logger.info("Database connection initialized successfully")
            
            # Start background health monitoring
            asyncio.create_task(self._health_monitoring_task())
            
        except Exception as e:
            logger.error(f"Failed to initialize database: {e}")
            self._health_monitor.record_error()
            raise DatabaseConnectionError(f"Database initialization failed: {e}")
            
    async def _health_monitoring_task(self) -> None:
        """Background task for continuous health monitoring."""
        while not self._shutting_down and self._initialized:
            try:
                await self._health_monitor.check_health(self._engine)
                await asyncio.sleep(settings.DB_HEALTH_CHECK_INTERVAL)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Health monitoring task error: {e}")
                await asyncio.sleep(5)  # Backoff on error
                
    @property
    def engine(self) -> AsyncEngine:
        """Get the database engine."""
        if not self._initialized:
            raise RuntimeError("Database not initialized. Call initialize() first.")
        return self._engine
        
    @property
    def session_factory(self) -> async_sessionmaker:
        """Get the session factory."""
        if not self._initialized:
            raise RuntimeError("Database not initialized. Call initialize() first.")
        return self._session_factory
        
    @asynccontextmanager
    async def session(self) -> AsyncGenerator[AsyncSession, None]:
        """
        Get a database session with automatic commit/rollback.
        
        Usage:
            async with database.session() as session:
                result = await session.execute(query)
                await session.commit()
        """
        if not self._initialized:
            raise RuntimeError("Database not initialized. Call initialize() first.")
            
        session_instance: AsyncSession = self._session_factory()
        try:
            start_time = time.time()
            yield session_instance
            duration = time.time() - start_time
            self._health_monitor.record_query(duration)
            self._health_monitor.record_success()
        except SQLAlchemyError as e:
            await session_instance.rollback()
            self._health_monitor.record_error()
            logger.error(f"Database session error: {e}")
            raise
        except Exception as e:
            await session_instance.rollback()
            logger.error(f"Unexpected error in database session: {e}")
            raise
        finally:
            await session_instance.close()
            
    @asynccontextmanager
    async def connection(self) -> AsyncGenerator[AsyncConnection, None]:
        """
        Get a raw database connection for low-level operations.
        
        Usage:
            async with database.connection() as conn:
                await conn.execute(text("..."))
        """
        if not self._initialized:
            raise RuntimeError("Database not initialized. Call initialize() first.")
            
        async with self._engine.connect() as conn:
            try:
                start_time = time.time()
                yield conn
                duration = time.time() - start_time
                self._health_monitor.record_query(duration)
                self._health_monitor.record_success()
            except SQLAlchemyError as e:
                self._health_monitor.record_error()
                logger.error(f"Database connection error: {e}")
                raise
                
    async def execute_raw(self, query: str, params: Optional[Dict] = None) -> Any:
        """
        Execute raw SQL query and return result.
        
        Args:
            query: SQL query string
            params: Query parameters
            
        Returns:
            Query result
        """
        async with self.session() as session:
            result = await session.execute(text(query), params or {})
            await session.commit()
            return result
            
    async def fetch_all(self, query: str, params: Optional[Dict] = None) -> List[Any]:
        """Fetch all rows from a raw SQL query."""
        result = await self.execute_raw(query, params)
        return result.fetchall()
        
    async def fetch_one(self, query: str, params: Optional[Dict] = None) -> Optional[Any]:
        """Fetch one row from a raw SQL query."""
        result = await self.execute_raw(query, params)
        return result.fetchone()
        
    async def get_pool_stats(self) -> Dict[str, Any]:
        """Get connection pool statistics."""
        if not self._initialized:
            return {}
            
        pool: Pool = self._engine.pool
        return {
            "checkedin": pool.checkedin(),
            "checkedout": pool.checkedout(),
            "size": pool.size(),
            "overflow": pool.overflow(),
            "connections": pool.checkedin() + pool.checkedout(),
        }
        
    async def get_health_status(self) -> Dict[str, Any]:
        """Get database health status."""
        is_healthy = await self._health_monitor.check_health(self._engine)
        
        return {
            "healthy": is_healthy,
            "connection_errors": self._health_monitor._connection_errors,
            "last_health_check": self._health_monitor._last_health_check,
            "pool_stats": await self.get_pool_stats(),
        }
        
    async def close(self) -> None:
        """Close all database connections and cleanup."""
        if not self._initialized:
            return
            
        self._shutting_down = True
        
        try:
            if self._engine:
                await self._engine.dispose()
                logger.info("Database connections closed")
        except Exception as e:
            logger.error(f"Error closing database connections: {e}")
        finally:
            self._initialized = False
            self._engine = None
            self._session_factory = None
            
    async def __aenter__(self):
        """Async context manager entry."""
        await self.initialize()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()


# Global database instance
database = DatabaseManager()


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency for getting database session.
    
    Usage in FastAPI routes:
        @app.get("/items")
        async def get_items(db: AsyncSession = Depends(get_db)):
            ...
    """
    async with database.session() as session:
        yield session


async def get_db_connection() -> AsyncGenerator[AsyncConnection, None]:
    """
    FastAPI dependency for getting raw database connection.
    """
    async with database.connection() as conn:
        yield conn


async def init_database() -> None:
    """Initialize database connection on application startup."""
    try:
        await database.initialize()
        logger.info("Database initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        raise


async def close_database() -> None:
    """Close database connections on application shutdown."""
    await database.close()
    logger.info("Database connections closed")


# Export common SQLAlchemy types for convenience
__all__ = [
    "database",
    "get_db",
    "get_db_connection",
    "init_database",
    "close_database",
    "metadata",
    "AsyncSession",
    "AsyncEngine",
    "AsyncConnection",
    "DatabaseConnectionError",
]
