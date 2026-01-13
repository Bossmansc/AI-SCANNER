"""
Redis Health Check and Version Validation Module

This module provides comprehensive Redis connection health monitoring,
version validation, and performance diagnostics. Designed for high-concurrency
environments with configurable thresholds and detailed reporting.

Features:
- Connection health validation with retry logic
- Redis version compatibility checking
- Performance benchmarking (latency, throughput)
- Memory usage monitoring
- Cluster and Sentinel support
- Detailed health reports with actionable insights
- Async and sync interfaces
- Configurable thresholds and timeouts
"""

import asyncio
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple, Union
from typing_extensions import TypedDict

import redis
import redis.asyncio as aioredis
from redis.exceptions import (
    AuthenticationError,
    ConnectionError,
    RedisError,
    ResponseError,
    TimeoutError,
)

# Configure module logger
logger = logging.getLogger(__name__)


class HealthStatus(Enum):
    """Health status enumeration."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


class RedisRole(Enum):
    """Redis server role enumeration."""
    MASTER = "master"
    REPLICA = "replica"
    SENTINEL = "sentinel"
    UNKNOWN = "unknown"


class HealthCheckResult(TypedDict, total=False):
    """Typed dictionary for health check results."""
    status: str
    timestamp: str
    latency_ms: float
    version: str
    role: str
    memory_used_mb: float
    memory_fragmentation_ratio: float
    connected_clients: int
    blocked_clients: int
    ops_per_second: float
    keyspace_hits: int
    keyspace_misses: int
    hit_rate: float
    uptime_days: float
    errors: List[str]
    warnings: List[str]
    recommendations: List[str]


@dataclass
class HealthCheckConfig:
    """Configuration for Redis health checks."""
    
    # Connection settings
    host: str = "localhost"
    port: int = 6379
    db: int = 0
    username: Optional[str] = None
    password: Optional[str] = None
    ssl: bool = False
    ssl_cert_reqs: str = "required"
    
    # Timeout settings (seconds)
    connection_timeout: float = 5.0
    socket_timeout: float = 5.0
    socket_connect_timeout: float = 5.0
    
    # Health check thresholds
    max_latency_ms: float = 100.0  # Maximum acceptable latency
    min_memory_available_mb: float = 100.0  # Minimum available memory
    max_memory_fragmentation: float = 1.5  # Maximum fragmentation ratio
    max_connected_clients_pct: float = 0.8  # 80% of max clients
    min_hit_rate: float = 0.9  # 90% cache hit rate
    
    # Performance test settings
    performance_test_iterations: int = 100
    performance_test_key_prefix: str = "health_check_"
    
    # Retry settings
    max_retries: int = 3
    retry_delay: float = 1.0
    
    # Cluster/Sentinel settings
    is_cluster: bool = False
    is_sentinel: bool = False
    sentinel_service_name: Optional[str] = None
    sentinel_nodes: List[Tuple[str, int]] = field(default_factory=list)
    
    # Monitoring settings
    collect_detailed_metrics: bool = True
    validate_version: bool = True
    min_redis_version: str = "6.0.0"


class RedisHealthChecker:
    """
    Redis health checker with comprehensive diagnostics.
    
    This class provides both synchronous and asynchronous methods
    for checking Redis health, validating versions, and monitoring
    performance metrics.
    """
    
    def __init__(self, config: Optional[HealthCheckConfig] = None):
        """
        Initialize the Redis health checker.
        
        Args:
            config: Health check configuration. If None, uses defaults.
        """
        self.config = config or HealthCheckConfig()
        self._sync_client: Optional[redis.Redis] = None
        self._async_client: Optional[aioredis.Redis] = None
        self._last_check_time: Optional[datetime] = None
        self._last_result: Optional[HealthCheckResult] = None
        
    def _create_sync_client(self) -> redis.Redis:
        """Create a synchronous Redis client."""
        if self.config.is_cluster:
            from redis.cluster import RedisCluster
            return RedisCluster(
                host=self.config.host,
                port=self.config.port,
                username=self.config.username,
                password=self.config.password,
                ssl=self.config.ssl,
                ssl_cert_reqs=self.config.ssl_cert_reqs,
                socket_timeout=self.config.socket_timeout,
                socket_connect_timeout=self.config.socket_connect_timeout,
                max_connections=10,
            )
        elif self.config.is_sentinel and self.config.sentinel_service_name:
            from redis.sentinel import Sentinel
            
            sentinel = Sentinel(
                self.config.sentinel_nodes or [(self.config.host, self.config.port)],
                socket_timeout=self.config.socket_timeout,
                sentinel_kwargs={
                    "username": self.config.username,
                    "password": self.config.password,
                    "ssl": self.config.ssl,
                }
            )
            return sentinel.master_for(self.config.sentinel_service_name)
        else:
            return redis.Redis(
                host=self.config.host,
                port=self.config.port,
                db=self.config.db,
                username=self.config.username,
                password=self.config.password,
                ssl=self.config.ssl,
                ssl_cert_reqs=self.config.ssl_cert_reqs,
                socket_timeout=self.config.socket_timeout,
                socket_connect_timeout=self.config.socket_connect_timeout,
                decode_responses=True,
                max_connections=10,
            )
    
    def _create_async_client(self) -> aioredis.Redis:
        """Create an asynchronous Redis client."""
        if self.config.is_cluster:
            from redis.asyncio.cluster import RedisCluster as AsyncRedisCluster
            return AsyncRedisCluster(
                host=self.config.host,
                port=self.config.port,
                username=self.config.username,
                password=self.config.password,
                ssl=self.config.ssl,
                ssl_cert_reqs=self.config.ssl_cert_reqs,
                socket_timeout=self.config.socket_timeout,
                socket_connect_timeout=self.config.socket_connect_timeout,
                max_connections=10,
            )
        elif self.config.is_sentinel and self.config.sentinel_service_name:
            from redis.asyncio.sentinel import Sentinel as AsyncSentinel
            
            sentinel = AsyncSentinel(
                self.config.sentinel_nodes or [(self.config.host, self.config.port)],
                socket_timeout=self.config.socket_timeout,
                sentinel_kwargs={
                    "username": self.config.username,
                    "password": self.config.password,
                    "ssl": self.config.ssl,
                }
            )
            return sentinel.master_for(self.config.sentinel_service_name)
        else:
            return aioredis.Redis(
                host=self.config.host,
                port=self.config.port,
                db=self.config.db,
                username=self.config.username,
                password=self.config.password,
                ssl=self.config.ssl,
                ssl_cert_reqs=self.config.ssl_cert_reqs,
                socket_timeout=self.config.socket_timeout,
                socket_connect_timeout=self.config.socket_connect_timeout,
                decode_responses=True,
                max_connections=10,
            )
    
    def _parse_version(self, version_str: str) -> Tuple[int, int, int]:
        """
        Parse Redis version string into major, minor, patch tuple.
        
        Args:
            version_str: Redis version string (e.g., "6.2.6")
            
        Returns:
            Tuple of (major, minor, patch)
        """
        try:
            # Remove non-numeric prefixes/suffixes
            version_str = version_str.split("-")[0].strip()
            parts = version_str.split(".")
            major = int(parts[0]) if len(parts) > 0 else 0
            minor = int(parts[1]) if len(parts) > 1 else 0
            patch = int(parts[2]) if len(parts) > 2 else 0
            return major, minor, patch
        except (ValueError, IndexError):
            logger.warning(f"Could not parse Redis version: {version_str}")
            return 0, 0, 0
    
    def _compare_versions(self, version1: str, version2: str) -> int:
        """
        Compare two version strings.
        
        Returns:
            -1 if version1 < version2
            0 if version1 == version2
            1 if version1 > version2
        """
        v1 = self._parse_version(version1)
        v2 = self._parse_version(version2)
        
        if v1 < v2:
            return -1
        elif v1 > v2:
            return 1
        else:
            return 0
    
    def _get_server_info(self, client: Union[redis.Redis, aioredis.Redis]) -> Dict[str, Any]:
        """Get Redis server information."""
        try:
            if isinstance(client, aioredis.Redis):
                # For async client, we need to handle this differently
                # In practice, this would be called from async context
                raise NotImplementedError("Async server info requires async context")
            else:
                return client.info()
        except (RedisError, AttributeError) as e:
            logger.warning(f"Failed to get server info: {e}")
            return {}
    
    def _check_connection(self, client: redis.Redis) -> Tuple[bool, float, Optional[str]]:
        """
        Check Redis connection with latency measurement.
        
        Returns:
            Tuple of (success, latency_ms, error_message)
        """
        try:
            start_time = time.perf_counter()
            response = client.ping()
            end_time = time.perf_counter()
            
            latency_ms = (end_time - start_time) * 1000
            
            if response is True:
                return True, latency_ms, None
            else:
                return False, latency_ms, "PING returned False"
                
        except AuthenticationError as e:
            return False, 0.0, f"Authentication failed: {e}"
        except ConnectionError as e:
            return False, 0.0, f"Connection failed: {e}"
        except TimeoutError as e:
            return False, 0.0, f"Connection timeout: {e}"
        except RedisError as e:
            return False, 0.0, f"Redis error: {e}"
        except Exception as e:
            return False, 0.0, f"Unexpected error: {e}"
    
    def _perform_performance_test(self, client: redis.Redis) -> Dict[str, Any]:
        """
        Perform basic performance test on Redis.
        
        Measures SET/GET operations per second and latency.
        """
        results = {
            "set_ops_per_sec": 0.0,
            "get_ops_per_sec": 0.0,
            "avg_set_latency_ms": 0.0,
            "avg_get_latency_ms": 0.0,
            "success_rate": 0.0,
        }
        
        iterations = self.config.performance_test_iterations
        key_prefix = self.config.performance_test_key_prefix
        test_value = "x" * 100  # 100 byte test value
        
        successful_ops = 0
        total_set_latency = 0.0
        total_get_latency = 0.0
        
        try:
            # Clean up any previous test keys
            pattern = f"{key_prefix}*"
            keys = client.keys(pattern)
            if keys:
                client.delete(*keys)
            
            # Perform SET operations
            set_start = time.perf_counter()
            for i in range(iterations):
                key = f"{key_prefix}_set_{i}"
                try:
                    op_start = time.perf_counter()
                    client.set(key, test_value, ex=60)  # 60 second expiry
                    op_end = time.perf_counter()
                    total_set_latency += (op_end - op_start) * 1000
                    successful_ops += 1
                except RedisError:
                    pass
            
            set_end = time.perf_counter()
            set_duration = set_end - set_start
            
            # Perform GET operations
            get_start = time.perf_counter()
            for i in range(iterations):
                key = f"{key_prefix}_set_{i}"
                try:
                    op_start = time.perf_counter()
                    client.get(key)
                    op_end = time.perf_counter()
                    total_get_latency += (op_end - op_start) * 1000
                except RedisError:
                    pass
            
            get_end = time.perf_counter()
            get_duration = get_end - get_start
            
            # Calculate results
            if set_duration > 0:
                results["set_ops_per_sec"] = iterations / set_duration
            if get_duration > 0:
                results["get_ops_per_sec"] = iterations / get_duration
            
            if iterations > 0:
                results["avg_set_latency_ms"] = total_set_latency / iterations
                results["avg_get_latency_ms"] = total_get_latency / iterations
                results["success_rate"] = successful_ops / iterations
            
            # Clean up test keys
            keys = client.keys(f"{key_prefix}*")
            if keys:
                client.delete(*keys)
                
        except RedisError as e:
            logger.warning(f"Performance test failed: {e}")
        
        return results
    
    def check_health(self) -> HealthCheckResult:
        """
        Perform comprehensive Redis health check.
        
        Returns:
            HealthCheckResult dictionary with detailed metrics and status.
        """
        result: HealthCheckResult = {
            "status": HealthStatus.UNKNOWN.value,
            "timestamp": datetime.utcnow().isoformat(),
            "latency_ms": 0.0,
            "version": "unknown",
            "role": RedisRole.UNKNOWN.value,
            "memory_used_mb": 0.0,
            "memory_fragmentation_ratio": 0.0,
            "connected_clients": 0,
            "blocked_clients": 0,
            "ops_per_second": 0.0,
            "keyspace_hits": 0,
            "keyspace_misses": 0,
            "hit_rate": 0.0,
            "uptime_days": 0.0,
            "errors": [],
            "warnings": [],
            "recommendations": [],
        }
        
        client = None
        try:
            # Create client with retry logic
            for attempt in range(self.config.max_retries + 1):
                try:
                    client = self._create_sync_client()
                    break
                except (ConnectionError, TimeoutError) as e:
                    if attempt == self.config.max_retries:
                        result["errors"].append(f"Failed to connect after {self.config.max_retries} retries: {e}")
                        result["status"] = HealthStatus.UNHEALTHY.value
                        self._last_result = result
                        return result
                    time.sleep(self.config.retry_delay)
            
            if client is None:
                result["errors"].append("Failed to create Redis client")
                result["status"] = HealthStatus.UNHEALTHY.value
                self._last_result = result
                return result
            
            # Check basic connection
            connected, latency, error = self._check_connection(client)
            result["latency_ms"] = latency
            
            if not connected:
                result["errors"].append(f"Connection check failed: {error}")
                result["status"] = HealthStatus.UNHEALTHY.value
                self._last_result = result
                return result
            
            # Get server info if detailed metrics are enabled
            if self.config.collect_detailed_metrics:
                try:
                    info = self._get_server_info(client)
                    
                    # Extract version
                    if "redis_version" in info:
                        result["version"] = info["redis_version"]
                        
                        # Validate version if configured
                        if self.config.validate_version:
                            current_version = info["redis_version"]
                            if self._compare_versions(current_version, self.config.min_redis_version) < 0:
                                result["warnings"].append(
                                    f"Redis version {current_version} is below minimum required {self.config.min_redis_version}"
                                )
                    
                    # Extract role
                    if "role" in info:
                        role = info["role"]
                        try:
                            result["role"] = RedisRole(role).value
                        except ValueError:
                            result["role"] = role
                    
                    # Extract memory info
                    if "used_memory" in info:
                        result["memory_used_mb"] = info["used_memory"] / (1024 * 1024)
                    
                    if "mem_fragmentation_ratio" in info:
                        result["memory_fragmentation_ratio"] = info["mem_fragmentation_ratio"]
                    
                    # Extract client info
                    if "connected_clients" in info:
                        result["connected_clients"] = info["connected_clients"]
                    
                    if "blocked_clients" in info:
                        result["blocked_clients"] = info["blocked_clients"]
                    
                    # Extract ops per second
                    if "instantaneous_ops_per_sec" in info:
                        result["ops_per_second"] = float(info["instantaneous_ops_per_sec"])
                    
                    # Extract keyspace stats
                    if "keyspace_hits" in info:
                        result["keyspace_hits"] = info["keyspace_hits"]
                    
                    if "keyspace_misses" in info:
                        result["keyspace_misses"] = info["keyspace_misses"]
                    
                    # Calculate hit rate
                    hits = result["keyspace_hits"]
                    misses = result["keyspace_misses"]
                    if hits + misses > 0:
                        result["hit_rate"] = hits / (hits + misses)
                    
                    # Extract uptime
                    if "uptime_in_seconds" in info:
                        result["uptime_days