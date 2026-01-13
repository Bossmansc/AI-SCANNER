"""
Redis connection manager with serialization, connection pooling, and health monitoring.
Provides thread-safe Redis client management with automatic reconnection and serialization.
"""

import json
import pickle
import logging
import threading
import time
from typing import Any, Optional, Union, Dict, List, Tuple, Callable
from enum import Enum
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
import hashlib
import zlib

import redis
from redis import Redis, ConnectionPool, RedisError
from redis.retry import Retry
from redis.backoff import ExponentialBackoff
from redis.exceptions import (
    ConnectionError,
    TimeoutError,
    AuthenticationError,
    ResponseError,
    BusyLoadingError
)

# Configure module logger
logger = logging.getLogger(__name__)


class SerializationMethod(Enum):
    """Supported serialization methods."""
    JSON = "json"
    PICKLE = "pickle"
    MSGPACK = "msgpack"
    COMPRESSED_JSON = "compressed_json"
    COMPRESSED_PICKLE = "compressed_pickle"


class RedisKeyType(Enum):
    """Redis key types for type checking."""
    STRING = "string"
    HASH = "hash"
    LIST = "list"
    SET = "set"
    ZSET = "zset"
    STREAM = "stream"


@dataclass
class RedisConnectionConfig:
    """Redis connection configuration."""
    host: str = "localhost"
    port: int = 6379
    db: int = 0
    username: Optional[str] = None
    password: Optional[str] = None
    socket_timeout: float = 5.0
    socket_connect_timeout: float = 5.0
    socket_keepalive: bool = True
    retry_on_timeout: bool = True
    max_connections: int = 50
    health_check_interval: int = 30
    decode_responses: bool = False
    ssl: bool = False
    ssl_cert_reqs: Optional[str] = None
    ssl_ca_certs: Optional[str] = None
    ssl_keyfile: Optional[str] = None
    ssl_certfile: Optional[str] = None


@dataclass
class CacheStats:
    """Cache statistics."""
    hits: int = 0
    misses: int = 0
    sets: int = 0
    deletes: int = 0
    errors: int = 0
    reconnects: int = 0
    total_operations: int = 0
    avg_response_time: float = 0.0
    
    def hit_rate(self) -> float:
        """Calculate cache hit rate."""
        total = self.hits + self.misses
        return self.hits / total if total > 0 else 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "hits": self.hits,
            "misses": self.misses,
            "sets": self.sets,
            "deletes": self.deletes,
            "errors": self.errors,
            "reconnects": self.reconnects,
            "total_operations": self.total_operations,
            "avg_response_time": self.avg_response_time,
            "hit_rate": self.hit_rate()
        }


class RedisSerializationError(Exception):
    """Custom exception for serialization errors."""
    pass


class RedisConnectionError(Exception):
    """Custom exception for connection errors."""
    pass


class RedisManager:
    """
    Thread-safe Redis connection manager with serialization and health monitoring.
    
    Features:
    - Connection pooling with configurable limits
    - Automatic reconnection on failure
    - Multiple serialization methods (JSON, Pickle, MsgPack)
    - Compression support
    - Health monitoring and statistics
    - Key expiration management
    - Batch operations
    - Type-safe operations
    """
    
    # Class-level lock for singleton pattern
    _instance_lock = threading.Lock()
    _instances = {}
    
    def __new__(cls, config: Optional[RedisConnectionConfig] = None, 
                instance_key: str = "default"):
        """Singleton pattern with instance key support."""
        with cls._instance_lock:
            if instance_key not in cls._instances:
                instance = super().__new__(cls)
                instance._initialize(config, instance_key)
                cls._instances[instance_key] = instance
            return cls._instances[instance_key]
    
    def _initialize(self, config: Optional[RedisConnectionConfig], instance_key: str):
        """Initialize the Redis manager instance."""
        self.instance_key = instance_key
        self.config = config or RedisConnectionConfig()
        self._connection_pool: Optional[ConnectionPool] = None
        self._redis_client: Optional[Redis] = None
        self._lock = threading.RLock()
        self._stats = CacheStats()
        self._response_times: List[float] = []
        self._max_response_time_samples = 1000
        self._last_health_check = 0
        self._is_healthy = True
        self._reconnect_attempts = 0
        self._max_reconnect_attempts = 3
        self._default_serialization = SerializationMethod.JSON
        self._default_ttl = 3600  # 1 hour default TTL
        
        # Initialize msgpack if available
        self._msgpack_available = False
        try:
            import msgpack
            self._msgpack_available = True
            self._msgpack = msgpack
        except ImportError:
            logger.warning("msgpack not installed. Using JSON as fallback.")
        
        # Initialize connection
        self._initialize_connection()
    
    def _initialize_connection(self) -> None:
        """Initialize Redis connection pool and client."""
        try:
            # Create connection pool with retry mechanism
            retry = Retry(ExponentialBackoff(), 3) if self.config.retry_on_timeout else None
            
            self._connection_pool = ConnectionPool(
                host=self.config.host,
                port=self.config.port,
                db=self.config.db,
                username=self.config.username,
                password=self.config.password,
                socket_timeout=self.config.socket_timeout,
                socket_connect_timeout=self.config.socket_connect_timeout,
                socket_keepalive=self.config.socket_keepalive,
                retry=retry,
                max_connections=self.config.max_connections,
                health_check_interval=self.config.health_check_interval,
                decode_responses=self.config.decode_responses,
                ssl=self.config.ssl,
                ssl_cert_reqs=self.config.ssl_cert_reqs,
                ssl_ca_certs=self.config.ssl_ca_certs,
                ssl_keyfile=self.config.ssl_keyfile,
                ssl_certfile=self.config.ssl_certfile
            )
            
            # Create Redis client
            self._redis_client = Redis(connection_pool=self._connection_pool)
            
            # Test connection
            self._test_connection()
            logger.info(f"Redis connection established for instance '{self.instance_key}': "
                       f"{self.config.host}:{self.config.port}/{self.config.db}")
            
        except Exception as e:
            logger.error(f"Failed to initialize Redis connection: {e}")
            self._is_healthy = False
            raise RedisConnectionError(f"Redis connection failed: {e}")
    
    def _test_connection(self) -> bool:
        """Test Redis connection with PING command."""
        try:
            if self._redis_client:
                response = self._redis_client.ping()
                self._is_healthy = response is True
                return self._is_healthy
            return False
        except Exception as e:
            logger.warning(f"Redis connection test failed: {e}")
            self._is_healthy = False
            return False
    
    def _ensure_connection(self) -> bool:
        """Ensure Redis connection is healthy, reconnect if necessary."""
        with self._lock:
            current_time = time.time()
            
            # Check health periodically
            if current_time - self._last_health_check > 30:  # 30 seconds
                self._test_connection()
                self._last_health_check = current_time
            
            # Reconnect if unhealthy and haven't exceeded max attempts
            if not self._is_healthy and self._reconnect_attempts < self._max_reconnect_attempts:
                try:
                    logger.info(f"Attempting Redis reconnection (attempt {self._reconnect_attempts + 1})")
                    self._initialize_connection()
                    self._reconnect_attempts = 0
                    self._stats.reconnects += 1
                    return True
                except Exception as e:
                    self._reconnect_attempts += 1
                    logger.error(f"Redis reconnection failed: {e}")
                    return False
            
            return self._is_healthy
    
    def _serialize(self, value: Any, method: SerializationMethod = None) -> bytes:
        """
        Serialize value to bytes.
        
        Args:
            value: Value to serialize
            method: Serialization method (defaults to instance default)
            
        Returns:
            Serialized bytes
            
        Raises:
            RedisSerializationError: If serialization fails
        """
        method = method or self._default_serialization
        
        try:
            if method == SerializationMethod.JSON:
                # Handle special types for JSON
                if isinstance(value, (datetime, timedelta)):
                    value = str(value)
                elif hasattr(value, "__dict__"):
                    value = asdict(value) if hasattr(value, "__dataclass_fields__") else value.__dict__
                
                serialized = json.dumps(value, default=str).encode('utf-8')
                
                if method == SerializationMethod.COMPRESSED_JSON:
                    serialized = zlib.compress(serialized)
                    
            elif method == SerializationMethod.PICKLE:
                serialized = pickle.dumps(value)
                
                if method == SerializationMethod.COMPRESSED_PICKLE:
                    serialized = zlib.compress(serialized)
                    
            elif method == SerializationMethod.MSGPACK:
                if not self._msgpack_available:
                    raise RedisSerializationError("msgpack not installed")
                
                # Convert special types for msgpack
                if isinstance(value, datetime):
                    value = value.isoformat()
                elif isinstance(value, timedelta):
                    value = value.total_seconds()
                
                serialized = self._msgpack.packb(value, use_bin_type=True)
                
            else:
                raise RedisSerializationError(f"Unsupported serialization method: {method}")
            
            return serialized
            
        except Exception as e:
            raise RedisSerializationError(f"Serialization failed: {e}")
    
    def _deserialize(self, data: bytes, method: SerializationMethod = None) -> Any:
        """
        Deserialize bytes to value.
        
        Args:
            data: Bytes to deserialize
            method: Serialization method (defaults to instance default)
            
        Returns:
            Deserialized value
            
        Raises:
            RedisSerializationError: If deserialization fails
        """
        if data is None:
            return None
        
        method = method or self._default_serialization
        
        try:
            if method == SerializationMethod.COMPRESSED_JSON:
                data = zlib.decompress(data)
                method = SerializationMethod.JSON
            elif method == SerializationMethod.COMPRESSED_PICKLE:
                data = zlib.decompress(data)
                method = SerializationMethod.PICKLE
            
            if method == SerializationMethod.JSON:
                return json.loads(data.decode('utf-8'))
            elif method == SerializationMethod.PICKLE:
                return pickle.loads(data)
            elif method == SerializationMethod.MSGPACK:
                if not self._msgpack_available:
                    raise RedisSerializationError("msgpack not installed")
                return self._msgpack.unpackb(data, raw=False)
            else:
                raise RedisSerializationError(f"Unsupported serialization method: {method}")
                
        except Exception as e:
            raise RedisSerializationError(f"Deserialization failed: {e}")
    
    def _record_response_time(self, start_time: float) -> None:
        """Record response time for statistics."""
        response_time = time.time() - start_time
        self._response_times.append(response_time)
        
        # Keep only last N samples
        if len(self._response_times) > self._max_response_time_samples:
            self._response_times.pop(0)
        
        # Update average
        self._stats.avg_response_time = sum(self._response_times) / len(self._response_times)
    
    def _execute_with_stats(self, operation: str, func: Callable, *args, **kwargs) -> Any:
        """
        Execute Redis operation with statistics and error handling.
        
        Args:
            operation: Operation name for logging
            func: Function to execute
            *args, **kwargs: Function arguments
            
        Returns:
            Function result
            
        Raises:
            RedisError: If Redis operation fails
        """
        if not self._ensure_connection():
            raise RedisConnectionError("Redis connection is not healthy")
        
        start_time = time.time()
        self._stats.total_operations += 1
        
        try:
            result = func(*args, **kwargs)
            
            # Update stats based on operation
            if operation == "get":
                if result is None:
                    self._stats.misses += 1
                else:
                    self._stats.hits += 1
            elif operation == "set":
                self._stats.sets += 1
            elif operation == "delete":
                self._stats.deletes += 1
            
            self._record_response_time(start_time)
            return result
            
        except (ConnectionError, TimeoutError, AuthenticationError, 
                ResponseError, BusyLoadingError) as e:
            self._stats.errors += 1
            self._is_healthy = False
            logger.error(f"Redis {operation} failed: {e}")
            raise RedisError(f"Redis {operation} failed: {e}")
        
        except Exception as e:
            self._stats.errors += 1
            logger.error(f"Unexpected error during Redis {operation}: {e}")
            raise
    
    # Public API Methods
    
    def get_client(self) -> Redis:
        """
        Get the Redis client instance.
        
        Returns:
            Redis client instance
            
        Raises:
            RedisConnectionError: If connection is not healthy
        """
        if not self._ensure_connection():
            raise RedisConnectionError("Redis connection is not healthy")
        
        return self._redis_client
    
    def is_healthy(self) -> bool:
        """Check if Redis connection is healthy."""
        return self._ensure_connection()
    
    def get_stats(self) -> CacheStats:
        """Get cache statistics."""
        return CacheStats(**self._stats.to_dict())
    
    def reset_stats(self) -> None:
        """Reset cache statistics."""
        with self._lock:
            self._stats = CacheStats()
            self._response_times = []
    
    # Key-Value Operations
    
    def set(self, key: str, value: Any, 
            ttl: Optional[int] = None,
            method: SerializationMethod = None,
            nx: bool = False,
            xx: bool = False) -> bool:
        """
        Set a key-value pair with optional TTL.
        
        Args:
            key: Redis key
            value: Value to store
            ttl: Time to live in seconds (defaults to instance default)
            method: Serialization method
            nx: Only set if key does not exist
            xx: Only set if key exists
            
        Returns:
            True if successful, False otherwise
        """
        serialized = self._serialize(value, method)
        ttl = ttl or self._default_ttl
        
        def _set():
            if ttl > 0:
                return self._redis_client.setex(key, ttl, serialized)
            else:
                if nx:
                    return self._redis_client.setnx(key, serialized)
                elif xx:
                    # For xx flag, we need to check existence first
                    if self._redis_client.exists(key):
                        return self._redis_client.set(key, serialized)
                    return False
                else:
                    return self._redis_client.set(key, serialized)
        
        result = self._execute_with_stats("set", _set)
        return result is True
    
    def get(self, key: str, method: SerializationMethod = None) -> Any:
        """
        Get value by key.
        
        Args:
            key: Redis key
            method: Serialization method
            
        Returns:
            Deserialized value or None if key doesn't exist
        """
        def _get():
            data = self._redis_client.get(key)
            return self._deserialize(data, method) if data else None
        
        return self._execute_with_stats("get", _get)
    
    def get_or_set(self, key: str, default_func: Callable[[], Any],
                   ttl: Optional[int] = None,
                   method: SerializationMethod = None) -> Any:
        """
        Get value by key, or set it using default_func if not exists.
        
        Args:
            key: Redis key
            default_func: Function that returns default value
            ttl: Time to live in seconds
            method: Serialization method
            
        Returns:
            Retrieved or newly set value
        """
        # Try to get existing value
        value = self.get(key, method)
        if value is not None:
            return value
        
        # Set default value
        default_value = default_func()
        self.set(key, default_value, ttl, method)
        return default_value
    
    def delete(self, *keys: str) -> int:
        """
        Delete one or more keys.
        
        Args:
            *keys: Keys to delete
            
        Returns:
            Number of keys deleted
        """
        def _delete():
            return self._redis_client.delete(*keys)
        
        return self._execute_with_stats("delete", _delete)
    
    def exists(self, *keys: str) -> int:
        """Check if one or more keys exist."""
        def _exists():
            return self._redis_client.exists(*keys)
        
        return self._execute_with_stats("exists", _exists)
    
    def expire(self, key: str, ttl: int) -> bool:
        """Set key expiration in seconds."""
        def _expire():
            return self._redis_client.expire(key, ttl)
        
        return self._execute_with_stats("expire", _expire)
    
    def ttl(self, key: str) -> int:
        """Get key time to live in seconds."""
        def _ttl():
            return self._redis_client.ttl(key)
        
       