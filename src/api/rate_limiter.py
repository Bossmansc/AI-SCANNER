"""
Fixed window rate limiter implementation with Redis backend.
Provides thread-safe rate limiting for API endpoints and distributed systems.
"""

import time
import asyncio
import logging
from typing import Optional, Dict, Any, Tuple, Union, Callable
from functools import wraps
import json
import hashlib
import uuid

# Try to import Redis, but provide fallback for development
try:
    import redis.asyncio as redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    logging.warning("Redis not available. Using in-memory fallback for rate limiting.")

from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timedelta
import threading
from collections import defaultdict


class RateLimitExceeded(Exception):
    """Exception raised when rate limit is exceeded."""
    
    def __init__(self, retry_after: float, limit: int, window: int, 
                 identifier: str, message: str = "Rate limit exceeded"):
        self.retry_after = retry_after
        self.limit = limit
        self.window = window
        self.identifier = identifier
        self.message = message
        super().__init__(self.message)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert exception to dictionary for API responses."""
        return {
            "error": "rate_limit_exceeded",
            "message": self.message,
            "retry_after": self.retry_after,
            "limit": self.limit,
            "window": self.window,
            "identifier": self.identifier,
            "timestamp": datetime.utcnow().isoformat()
        }


class RateLimitStrategy(Enum):
    """Strategy for handling rate limit exceeded scenarios."""
    REJECT = "reject"           # Immediately reject with 429
    QUEUE = "queue"            # Queue request for later processing
    SLOW_DOWN = "slow_down"    # Add increasing delays
    BURST = "burst"            # Allow temporary bursts


@dataclass
class RateLimitConfig:
    """Configuration for rate limiting."""
    requests_per_window: int = 100
    window_seconds: int = 60
    identifier: Optional[str] = None
    strategy: RateLimitStrategy = RateLimitStrategy.REJECT
    burst_factor: float = 1.5  # For BURST strategy
    queue_timeout: int = 30    # For QUEUE strategy
    cost: int = 1              # Cost of this request
    namespace: str = "ratelimit"
    
    def __post_init__(self):
        if self.requests_per_window <= 0:
            raise ValueError("requests_per_window must be positive")
        if self.window_seconds <= 0:
            raise ValueError("window_seconds must be positive")
        if self.cost <= 0:
            raise ValueError("cost must be positive")


@dataclass
class RateLimitResult:
    """Result of a rate limit check."""
    allowed: bool
    limit: int
    remaining: int
    reset_time: float
    retry_after: float = 0
    cost: int = 1
    identifier: str = ""
    window_key: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for HTTP headers."""
        return {
            "X-RateLimit-Limit": str(self.limit),
            "X-RateLimit-Remaining": str(self.remaining),
            "X-RateLimit-Reset": str(int(self.reset_time)),
            "X-RateLimit-Retry-After": str(int(self.retry_after)) if self.retry_after > 0 else "0",
            "X-RateLimit-Cost": str(self.cost),
            "X-RateLimit-Identifier": self.identifier
        }


class BaseRateLimiter:
    """Base class for rate limiters."""
    
    async def check_rate_limit(self, identifier: str, config: RateLimitConfig) -> RateLimitResult:
        """Check if request is allowed."""
        raise NotImplementedError
    
    async def get_usage(self, identifier: str, config: RateLimitConfig) -> RateLimitResult:
        """Get current usage without incrementing counter."""
        raise NotImplementedError
    
    async def reset(self, identifier: str, config: RateLimitConfig) -> None:
        """Reset rate limit for identifier."""
        raise NotImplementedError
    
    async def cleanup(self, older_than: Optional[float] = None) -> int:
        """Clean up old rate limit data."""
        raise NotImplementedError


class InMemoryRateLimiter(BaseRateLimiter):
    """In-memory rate limiter for development/testing."""
    
    def __init__(self):
        self._storage: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.RLock()
        self._cleanup_interval = 300  # 5 minutes
        self._last_cleanup = time.time()
    
    def _get_window_key(self, identifier: str, window_seconds: int) -> str:
        """Generate window key based on current time."""
        window_start = int(time.time() // window_seconds) * window_seconds
        return f"{identifier}:{window_start}"
    
    def _cleanup_old_windows(self):
        """Remove old windows from storage."""
        current_time = time.time()
        if current_time - self._last_cleanup < self._cleanup_interval:
            return
        
        with self._lock:
            keys_to_delete = []
            for key in self._storage:
                try:
                    window_start = int(key.split(":")[-1])
                    if current_time - window_start > 3600:  # Keep only last hour
                        keys_to_delete.append(key)
                except (ValueError, IndexError):
                    keys_to_delete.append(key)
            
            for key in keys_to_delete:
                del self._storage[key]
            
            self._last_cleanup = current_time
    
    async def check_rate_limit(self, identifier: str, config: RateLimitConfig) -> RateLimitResult:
        """Check and increment rate limit counter."""
        self._cleanup_old_windows()
        
        window_key = self._get_window_key(identifier, config.window_seconds)
        current_time = time.time()
        reset_time = (int(current_time // config.window_seconds) + 1) * config.window_seconds
        
        with self._lock:
            if window_key not in self._storage:
                self._storage[window_key] = {
                    "count": 0,
                    "created": current_time,
                    "identifier": identifier
                }
            
            window_data = self._storage[window_key]
            current_count = window_data["count"]
            
            if current_count + config.cost > config.requests_per_window:
                retry_after = reset_time - current_time
                return RateLimitResult(
                    allowed=False,
                    limit=config.requests_per_window,
                    remaining=max(0, config.requests_per_window - current_count),
                    reset_time=reset_time,
                    retry_after=retry_after,
                    cost=config.cost,
                    identifier=identifier,
                    window_key=window_key
                )
            
            # Increment counter
            window_data["count"] += config.cost
            window_data["last_updated"] = current_time
            
            return RateLimitResult(
                allowed=True,
                limit=config.requests_per_window,
                remaining=config.requests_per_window - window_data["count"],
                reset_time=reset_time,
                cost=config.cost,
                identifier=identifier,
                window_key=window_key
            )
    
    async def get_usage(self, identifier: str, config: RateLimitConfig) -> RateLimitResult:
        """Get current usage without incrementing."""
        self._cleanup_old_windows()
        
        window_key = self._get_window_key(identifier, config.window_seconds)
        current_time = time.time()
        reset_time = (int(current_time // config.window_seconds) + 1) * config.window_seconds
        
        with self._lock:
            if window_key not in self._storage:
                return RateLimitResult(
                    allowed=True,
                    limit=config.requests_per_window,
                    remaining=config.requests_per_window,
                    reset_time=reset_time,
                    cost=config.cost,
                    identifier=identifier,
                    window_key=window_key
                )
            
            window_data = self._storage[window_key]
            current_count = window_data["count"]
            
            return RateLimitResult(
                allowed=current_count < config.requests_per_window,
                limit=config.requests_per_window,
                remaining=max(0, config.requests_per_window - current_count),
                reset_time=reset_time,
                retry_after=reset_time - current_time if current_count >= config.requests_per_window else 0,
                cost=config.cost,
                identifier=identifier,
                window_key=window_key
            )
    
    async def reset(self, identifier: str, config: RateLimitConfig) -> None:
        """Reset rate limit for identifier."""
        with self._lock:
            # Remove all windows for this identifier
            keys_to_delete = [k for k in self._storage.keys() if k.startswith(f"{identifier}:")]
            for key in keys_to_delete:
                del self._storage[key]
    
    async def cleanup(self, older_than: Optional[float] = None) -> int:
        """Clean up old rate limit data."""
        if older_than is None:
            older_than = time.time() - 3600  # Default: older than 1 hour
        
        with self._lock:
            keys_to_delete = []
            for key, data in self._storage.items():
                if data.get("created", 0) < older_than:
                    keys_to_delete.append(key)
            
            for key in keys_to_delete:
                del self._storage[key]
            
            return len(keys_to_delete)


class RedisRateLimiter(BaseRateLimiter):
    """
    Redis-based rate limiter using fixed window algorithm.
    Thread-safe and suitable for distributed systems.
    """
    
    def __init__(self, redis_client: Optional[redis.Redis] = None, 
                 redis_url: Optional[str] = None,
                 connection_pool_size: int = 10):
        """
        Initialize Redis rate limiter.
        
        Args:
            redis_client: Existing Redis client
            redis_url: Redis connection URL
            connection_pool_size: Size of connection pool
        """
        if not REDIS_AVAILABLE:
            raise ImportError("Redis package not installed. Install with: pip install redis")
        
        if redis_client is not None:
            self.redis = redis_client
        else:
            redis_url = redis_url or "redis://localhost:6379/0"
            self.redis = redis.from_url(
                redis_url,
                max_connections=connection_pool_size,
                decode_responses=True
            )
        
        self._script_sha = None
        self._lock = asyncio.Lock()
        self._lua_script = """
        -- KEYS[1]: rate limit key
        -- ARGV[1]: window size in seconds
        -- ARGV[2]: max requests per window
        -- ARGV[3]: request cost
        -- ARGV[4]: current timestamp
        
        local key = KEYS[1]
        local window = tonumber(ARGV[1])
        local limit = tonumber(ARGV[2])
        local cost = tonumber(ARGV[3])
        local now = tonumber(ARGV[4])
        
        -- Calculate window start
        local window_start = math.floor(now / window) * window
        local window_key = key .. ":" .. window_start
        
        -- Get current count
        local current = redis.call("GET", window_key)
        current = current and tonumber(current) or 0
        
        -- Check if limit would be exceeded
        if current + cost > limit then
            local reset_time = window_start + window
            local retry_after = reset_time - now
            local remaining = math.max(0, limit - current)
            
            return {
                "allowed", "0",
                "limit", tostring(limit),
                "remaining", tostring(remaining),
                "reset_time", tostring(reset_time),
                "retry_after", tostring(retry_after),
                "current", tostring(current),
                "window_start", tostring(window_start)
            }
        end
        
        -- Increment counter
        redis.call("INCRBY", window_key, cost)
        redis.call("EXPIRE", window_key, window * 2)  -- Expire after 2 windows
        
        -- Get new count
        local new_count = current + cost
        local reset_time = window_start + window
        local remaining = limit - new_count
        
        return {
            "allowed", "1",
            "limit", tostring(limit),
            "remaining", tostring(remaining),
            "reset_time", tostring(reset_time),
            "retry_after", "0",
            "current", tostring(new_count),
            "window_start", tostring(window_start)
        }
        """
    
    async def _ensure_script_loaded(self) -> str:
        """Ensure Lua script is loaded in Redis."""
        if self._script_sha:
            return self._script_sha
        
        async with self._lock:
            if not self._script_sha:
                self._script_sha = await self.redis.script_load(self._lua_script)
        
        return self._script_sha
    
    def _generate_key(self, identifier: str, namespace: str) -> str:
        """Generate Redis key for rate limiting."""
        # Use hash for consistent key length
        key_hash = hashlib.md5(identifier.encode()).hexdigest()[:16]
        return f"{namespace}:{key_hash}"
    
    async def check_rate_limit(self, identifier: str, config: RateLimitConfig) -> RateLimitResult:
        """
        Check rate limit using Redis Lua script for atomic operations.
        
        Args:
            identifier: Client identifier (IP, user ID, API key, etc.)
            config: Rate limit configuration
            
        Returns:
            RateLimitResult with details
        """
        script_sha = await self._ensure_script_loaded()
        
        redis_key = self._generate_key(identifier, config.namespace)
        current_time = time.time()
        
        try:
            # Execute Lua script atomically
            result = await self.redis.evalsha(
                script_sha,
                1,  # Number of keys
                redis_key,
                config.window_seconds,
                config.requests_per_window,
                config.cost,
                current_time
            )
            
            # Parse result from Lua script
            # Result is a list of key-value pairs
            result_dict = {}
            for i in range(0, len(result), 2):
                result_dict[result[i]] = result[i + 1]
            
            allowed = result_dict.get("allowed") == "1"
            limit = int(result_dict.get("limit", config.requests_per_window))
            remaining = int(result_dict.get("remaining", 0))
            reset_time = float(result_dict.get("reset_time", 0))
            retry_after = float(result_dict.get("retry_after", 0))
            current = int(result_dict.get("current", 0))
            window_start = float(result_dict.get("window_start", 0))
            
            window_key = f"{redis_key}:{window_start}"
            
            return RateLimitResult(
                allowed=allowed,
                limit=limit,
                remaining=remaining,
                reset_time=reset_time,
                retry_after=retry_after,
                cost=config.cost,
                identifier=identifier,
                window_key=window_key
            )
            
        except redis.exceptions.NoScriptError:
            # Script not loaded, load it and retry
            self._script_sha = None
            return await self.check_rate_limit(identifier, config)
        
        except Exception as e:
            logging.error(f"Redis rate limit check failed: {e}")
            # Fallback: allow request if Redis fails
            return RateLimitResult(
                allowed=True,
                limit=config.requests_per_window,
                remaining=config.requests_per_window,
                reset_time=current_time + config.window_seconds,
                cost=config.cost,
                identifier=identifier,
                window_key="fallback"
            )
    
    async def get_usage(self, identifier: str, config: RateLimitConfig) -> RateLimitResult:
        """Get current usage without incrementing counter."""
        redis_key = self._generate_key(identifier, config.namespace)
        current_time = time.time()
        window_start = int(current_time // config.window_seconds) * config.window_seconds
        window_key = f"{redis_key}:{window_start}"
        
        try:
            current_count = await self.redis.get(window_key)
            current_count = int(current_count) if current_count else 0
            
            reset_time = window_start + config.window_seconds
            remaining = max(0, config.requests_per_window - current_count)
            retry_after = reset_time - current_time if current_count >= config.requests_per_window else 0
            
            return RateLimitResult(
                allowed=current_count < config.requests_per_window,
                limit=config.requests_per_window,
                remaining=remaining,
                reset_time=reset_time,
                retry_after=retry_after,
                cost=config.cost,
                identifier=identifier,
                window_key=window_key
            )
            
        except Exception as e:
            logging.error(f"Redis get usage failed: {e}")
            # Return optimistic result on failure
            return RateLimitResult(
                allowed=True,
                limit=config.requests_per_window,
                remaining=config.requests_per_window,
                reset_time=current_time + config.window_seconds,
                cost=config.cost,
                identifier=identifier,
                window_key="fallback"
            )
    
    async def reset(self, identifier: str, config: RateLimitConfig) -> None:
        """Reset rate limit for identifier."""
        redis_key = self._generate_key(identifier, config.namespace)
        
        try:
            # Find and delete all windows for this identifier
            pattern = f"{redis_key}:*"
            cursor = 0
            while True:
                cursor, keys = await self.redis.scan(cursor, match=pattern, count=100)
                if keys:
                    await self.redis.delete(*keys)
                if cursor == 0:
                    break
        except Exception as e:
            logging.error(f"Redis reset failed: {e}")
    
    async def cleanup(self, older_than: Optional[float] = None) -> int:
        """Clean up old rate limit data."""
        if older_than is None:
            older_than = time.time() - 86400  # Default: older than 24 hours
        
        try:
           