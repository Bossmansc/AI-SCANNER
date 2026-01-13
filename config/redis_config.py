"""
Redis Configuration and Client Management Module

This module provides a robust, production-ready Redis client configuration with:
- Connection pooling for high concurrency
- Health checks and reconnection logic
- Environment-based configuration
- Support for multiple Redis deployment modes (single, sentinel, cluster)
- Comprehensive error handling and logging
- Type hints for better IDE support
"""

import asyncio
import logging
import os
import sys
from typing import Any, Dict, List, Optional, Union, cast

import redis.asyncio as redis
from redis.asyncio import Redis, Sentinel, ConnectionPool
from redis.asyncio.sentinel import SentinelConnectionPool
from redis.asyncio.cluster import RedisCluster
from redis.exceptions import (
    AuthenticationError,
    ConnectionError,
    RedisError,
    TimeoutError,
)
from pydantic import BaseSettings, Field, validator

# Configure module logger
logger = logging.getLogger(__name__)


class RedisSettings(BaseSettings):
    """
    Redis configuration settings with environment variable fallbacks.
    
    Environment Variables:
        REDIS_HOST: Redis server hostname (default: localhost)
        REDIS_PORT: Redis server port (default: 6379)
        REDIS_PASSWORD: Redis authentication password
        REDIS_DB: Redis database number (default: 0)
        REDIS_MODE: Redis deployment mode - 'single', 'sentinel', or 'cluster'
        REDIS_SENTINEL_MASTER: Sentinel master name
        REDIS_SENTINEL_NODES: Comma-separated list of sentinel nodes (host:port)
        REDIS_MAX_CONNECTIONS: Maximum connections in pool (default: 100)
        REDIS_TIMEOUT: Connection timeout in seconds (default: 5)
        REDIS_HEALTH_CHECK_INTERVAL: Health check interval in seconds (default: 30)
        REDIS_RETRY_ATTEMPTS: Number of connection retry attempts (default: 3)
        REDIS_RETRY_DELAY: Delay between retries in seconds (default: 1)
        REDIS_SSL: Use SSL/TLS connection (default: false)
        REDIS_SSL_CERT_REQS: SSL certificate requirements
        REDIS_DECODE_RESPONSES: Decode responses to strings (default: true)
    """
    
    # Basic connection settings
    host: str = Field(default="localhost", env="REDIS_HOST")
    port: int = Field(default=6379, env="REDIS_PORT")
    password: Optional[str] = Field(default=None, env="REDIS_PASSWORD")
    db: int = Field(default=0, env="REDIS_DB")
    
    # Deployment mode
    mode: str = Field(default="single", env="REDIS_MODE")
    
    # Sentinel configuration
    sentinel_master: Optional[str] = Field(default=None, env="REDIS_SENTINEL_MASTER")
    sentinel_nodes: Optional[str] = Field(default=None, env="REDIS_SENTINEL_NODES")
    
    # Connection pool settings
    max_connections: int = Field(default=100, env="REDIS_MAX_CONNECTIONS")
    timeout: int = Field(default=5, env="REDIS_TIMEOUT")
    health_check_interval: int = Field(default=30, env="REDIS_HEALTH_CHECK_INTERVAL")
    
    # Retry settings
    retry_attempts: int = Field(default=3, env="REDIS_RETRY_ATTEMPTS")
    retry_delay: float = Field(default=1.0, env="REDIS_RETRY_DELAY")
    
    # SSL/TLS settings
    ssl: bool = Field(default=False, env="REDIS_SSL")
    ssl_cert_reqs: Optional[str] = Field(default=None, env="REDIS_SSL_CERT_REQS")
    
    # Response handling
    decode_responses: bool = Field(default=True, env="REDIS_DECODE_RESPONSES")
    
    @validator('mode')
    def validate_mode(cls, v: str) -> str:
        """Validate Redis deployment mode."""
        valid_modes = ['single', 'sentinel', 'cluster']
        if v not in valid_modes:
            raise ValueError(f"Redis mode must be one of: {valid_modes}")
        return v
    
    @validator('sentinel_nodes')
    def parse_sentinel_nodes(cls, v: Optional[str], values: Dict[str, Any]) -> Optional[List[tuple]]:
        """Parse sentinel nodes from comma-separated string."""
        if v is None or values.get('mode') != 'sentinel':
            return None
        
        nodes = []
        for node in v.split(','):
            node = node.strip()
            if ':' in node:
                host, port = node.split(':', 1)
                nodes.append((host.strip(), int(port.strip())))
            else:
                nodes.append((node.strip(), 26379))  # Default sentinel port
        
        if not nodes:
            raise ValueError("At least one sentinel node must be specified for sentinel mode")
        
        return nodes
    
    @validator('ssl_cert_reqs')
    def validate_ssl_cert_reqs(cls, v: Optional[str]) -> Optional[str]:
        """Validate SSL certificate requirements."""
        if v is None:
            return None
        
        valid_values = ['none', 'optional', 'required']
        if v.lower() not in valid_values:
            raise ValueError(f"SSL certificate requirements must be one of: {valid_values}")
        
        return v.lower()
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


class RedisConnectionManager:
    """
    Manages Redis connections with health checks, reconnection logic, and pooling.
    
    This class provides a singleton-like interface for accessing Redis clients
    with automatic reconnection and health monitoring.
    """
    
    _instance: Optional['RedisConnectionManager'] = None
    _client: Optional[Union[Redis, RedisCluster]] = None
    _settings: Optional[RedisSettings] = None
    _connection_pool: Optional[Union[ConnectionPool, SentinelConnectionPool]] = None
    _health_check_task: Optional[asyncio.Task] = None
    _is_connected: bool = False
    _connection_lock: asyncio.Lock = asyncio.Lock()
    
    def __new__(cls) -> 'RedisConnectionManager':
        """Singleton pattern to ensure single instance."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self) -> None:
        """Initialize the connection manager."""
        if not hasattr(self, '_initialized'):
            self._initialized = True
            self._settings = RedisSettings()
            self._connection_lock = asyncio.Lock()
    
    async def get_client(self) -> Union[Redis, RedisCluster]:
        """
        Get or create a Redis client.
        
        Returns:
            Redis or RedisCluster client instance
            
        Raises:
            RedisError: If connection cannot be established
        """
        async with self._connection_lock:
            if self._client is None or not self._is_connected:
                await self._connect()
            
            return cast(Union[Redis, RedisCluster], self._client)
    
    async def _connect(self) -> None:
        """
        Establish Redis connection based on configuration mode.
        
        Raises:
            RedisError: If connection fails after retries
        """
        if self._settings is None:
            raise RedisError("Redis settings not initialized")
        
        logger.info(f"Connecting to Redis in {self._settings.mode} mode...")
        
        for attempt in range(self._settings.retry_attempts):
            try:
                if self._settings.mode == 'single':
                    await self._connect_single()
                elif self._settings.mode == 'sentinel':
                    await self._connect_sentinel()
                elif self._settings.mode == 'cluster':
                    await self._connect_cluster()
                else:
                    raise ValueError(f"Unsupported Redis mode: {self._settings.mode}")
                
                # Test connection
                await self._test_connection()
                self._is_connected = True
                
                # Start health check task
                if self._health_check_task is None:
                    self._health_check_task = asyncio.create_task(
                        self._health_check_loop()
                    )
                
                logger.info(f"Successfully connected to Redis (attempt {attempt + 1})")
                return
                
            except (ConnectionError, AuthenticationError, TimeoutError) as e:
                logger.warning(
                    f"Redis connection attempt {attempt + 1} failed: {str(e)}"
                )
                
                if attempt < self._settings.retry_attempts - 1:
                    await asyncio.sleep(self._settings.retry_delay)
                else:
                    logger.error(f"Failed to connect to Redis after {self._settings.retry_attempts} attempts")
                    raise RedisError(f"Redis connection failed: {str(e)}")
    
    async def _connect_single(self) -> None:
        """Connect to a single Redis instance."""
        if self._settings is None:
            return
        
        # Create connection pool
        self._connection_pool = ConnectionPool(
            host=self._settings.host,
            port=self._settings.port,
            password=self._settings.password,
            db=self._settings.db,
            max_connections=self._settings.max_connections,
            socket_connect_timeout=self._settings.timeout,
            socket_timeout=self._settings.timeout,
            health_check_interval=self._settings.health_check_interval,
            ssl=self._settings.ssl,
            ssl_cert_reqs=self._settings.ssl_cert_reqs,
            decode_responses=self._settings.decode_responses,
            retry_on_timeout=True,
            retry_on_error=[ConnectionError, TimeoutError],
        )
        
        # Create Redis client
        self._client = Redis(
            connection_pool=cast(ConnectionPool, self._connection_pool),
            decode_responses=self._settings.decode_responses,
        )
    
    async def _connect_sentinel(self) -> None:
        """Connect to Redis Sentinel cluster."""
        if self._settings is None:
            return
        
        if not self._settings.sentinel_master or not self._settings.sentinel_nodes:
            raise ValueError("Sentinel mode requires master name and nodes configuration")
        
        # Parse sentinel nodes
        sentinel_nodes = self._settings.parse_sentinel_nodes(
            self._settings.sentinel_nodes, {'mode': 'sentinel'}
        )
        
        if not sentinel_nodes:
            raise ValueError("Invalid sentinel nodes configuration")
        
        # Create Sentinel client
        sentinel = Sentinel(
            sentinel_nodes,
            socket_timeout=self._settings.timeout,
            password=self._settings.password,
            ssl=self._settings.ssl,
            ssl_cert_reqs=self._settings.ssl_cert_reqs,
            decode_responses=self._settings.decode_responses,
        )
        
        # Get master connection
        self._client = sentinel.master_for(
            self._settings.sentinel_master,
            socket_timeout=self._settings.timeout,
            password=self._settings.password,
            db=self._settings.db,
            decode_responses=self._settings.decode_responses,
        )
    
    async def _connect_cluster(self) -> None:
        """Connect to Redis Cluster."""
        if self._settings is None:
            return
        
        # Create Redis Cluster client
        self._client = RedisCluster(
            host=self._settings.host,
            port=self._settings.port,
            password=self._settings.password,
            socket_timeout=self._settings.timeout,
            socket_connect_timeout=self._settings.timeout,
            max_connections=self._settings.max_connections,
            decode_responses=self._settings.decode_responses,
            ssl=self._settings.ssl,
            ssl_cert_reqs=self._settings.ssl_cert_reqs,
            skip_full_coverage_check=True,
        )
    
    async def _test_connection(self) -> None:
        """Test Redis connection with a simple PING command."""
        if self._client is None:
            raise RedisError("Redis client not initialized")
        
        try:
            response = await self._client.ping()
            if response != True:  # noqa: E712
                raise RedisError(f"Unexpected PING response: {response}")
        except Exception as e:
            raise RedisError(f"Redis connection test failed: {str(e)}")
    
    async def _health_check_loop(self) -> None:
        """Background task to periodically check Redis connection health."""
        if self._settings is None:
            return
        
        while True:
            try:
                await asyncio.sleep(self._settings.health_check_interval)
                
                if self._client is None:
                    logger.warning("Redis client is None, attempting to reconnect...")
                    await self.reconnect()
                    continue
                
                # Perform health check
                try:
                    await self._client.ping()
                    if not self._is_connected:
                        self._is_connected = True
                        logger.info("Redis connection restored")
                except (ConnectionError, TimeoutError) as e:
                    if self._is_connected:
                        self._is_connected = False
                        logger.error(f"Redis connection lost: {str(e)}")
                    
                    # Attempt reconnection
                    await self.reconnect()
                    
            except asyncio.CancelledError:
                logger.info("Redis health check loop cancelled")
                break
            except Exception as e:
                logger.error(f"Error in Redis health check loop: {str(e)}")
                await asyncio.sleep(5)  # Prevent tight error loop
    
    async def reconnect(self) -> None:
        """
        Force reconnection to Redis.
        
        This method closes existing connections and establishes new ones.
        """
        async with self._connection_lock:
            logger.info("Attempting Redis reconnection...")
            
            # Close existing connections
            await self.close()
            
            # Clear client reference
            self._client = None
            self._connection_pool = None
            self._is_connected = False
            
            # Reconnect
            try:
                await self._connect()
                logger.info("Redis reconnection successful")
            except Exception as e:
                logger.error(f"Redis reconnection failed: {str(e)}")
                raise
    
    async def close(self) -> None:
        """Close Redis connections and cleanup resources."""
        async with self._connection_lock:
            # Cancel health check task
            if self._health_check_task:
                self._health_check_task.cancel()
                try:
                    await self._health_check_task
                except asyncio.CancelledError:
                    pass
                self._health_check_task = None
            
            # Close client
            if self._client:
                try:
                    await self._client.close()
                    logger.info("Redis client closed")
                except Exception as e:
                    logger.error(f"Error closing Redis client: {str(e)}")
                finally:
                    self._client = None
            
            # Close connection pool
            if self._connection_pool:
                try:
                    await self._connection_pool.disconnect()
                    logger.info("Redis connection pool disconnected")
                except Exception as e:
                    logger.error(f"Error disconnecting Redis pool: {str(e)}")
                finally:
                    self._connection_pool = None
            
            self._is_connected = False
    
    def is_connected(self) -> bool:
        """Check if Redis is currently connected."""
        return self._is_connected
    
    def get_settings(self) -> Optional[RedisSettings]:
        """Get current Redis settings."""
        return self._settings
    
    async def execute_command(self, *args: Any, **kwargs: Any) -> Any:
        """
        Execute a Redis command with automatic reconnection.
        
        Args:
            *args: Command arguments
            **kwargs: Command keyword arguments
            
        Returns:
            Command response
            
        Raises:
            RedisError: If command execution fails
        """
        client = await self.get_client()
        
        try:
            return await client.execute_command(*args, **kwargs)
        except (ConnectionError, TimeoutError) as e:
            logger.warning(f"Redis command failed, attempting reconnection: {str(e)}")
            await self.reconnect()
            
            # Retry with reconnected client
            client = await self.get_client()
            return await client.execute_command(*args, **kwargs)
        except Exception as e:
            logger.error(f"Redis command execution error: {str(e)}")
            raise RedisError(f"Redis command failed: {str(e)}")


# Global Redis connection manager instance
_redis_manager: Optional[RedisConnectionManager] = None


async def get_redis() -> Union[Redis, RedisCluster]:
    """
    Get Redis client instance (async context manager compatible).
    
    Example:
        redis_client = await get_redis()
        await redis_client.set("key", "value")
    
    Returns:
        Redis or RedisCluster client
    """
    global _redis_manager
    
    if _redis_manager is None:
        _redis_manager = RedisConnectionManager()
    
    return await _redis_manager.get_client()


async def init_redis() -> None:
    """Initialize Redis connection on application startup."""
    global _redis_manager
    
    if _redis_manager is None:
        _redis_manager = RedisConnectionManager()
    
    try:
        await _redis_manager.get_client()
        logger.info("Redis initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize Redis: {str(e)}")
        raise


async def close_redis() -> None:
    """Close Redis connection on application shutdown."""
    global _redis_manager
    
    if _redis_manager:
        await _redis_manager.close()
        _redis_manager = None
        logger.info("Redis connections closed")


def get_redis_manager() -> RedisConnectionManager:
    """
    Get the Redis connection manager instance.
    
    Returns:
        RedisConnectionManager instance
    """
    global _redis_manager
    
    if _redis_manager is None:
        _redis_manager = RedisConnectionManager()
    
    return _redis_manager


# Convenience functions for common operations
async def redis_ping() -> bool:
    """Check if Redis is responsive."""
    try:
        client = await get_redis()
        return await client.ping()
    except Exception:
        return False


async def redis_info() -> Dict[str, Any]:
    """
    Get Redis server information.
    
    Returns:
        Dictionary with Redis server info
        
    Raises:
        RedisError: If info command fails
    """
    client = await get_redis()
    
    try:
        info = await client.info()
        return cast(Dict[str, Any], info)
    except Exception as e:
        raise RedisError(f"Failed to get Redis info: {str(e)}")


async def redis_flushdb(async_mode: bool = True) -> bool:
    """
    Flush the current Redis database.
    
    Args:
        async_mode: Use asynchronous flush (default: