"""
Database Connection Pool with Leak Detection and Health Monitoring
High-concurrency, production-ready connection pooling with automatic leak detection,
connection validation, and graceful degradation.
"""

import asyncio
import logging
import threading
import time
import weakref
from collections import deque
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple, Union
from uuid import uuid4

import asyncpg
from asyncpg import Connection, Pool
from asyncpg.exceptions import TooManyConnectionsError, PostgresConnectionError
from prometheus_client import Counter, Gauge, Histogram

# Configure logging
logger = logging.getLogger(__name__)


class ConnectionState(Enum):
    """Connection lifecycle states"""
    IDLE = "idle"
    ACTIVE = "active"
    RESERVED = "reserved"
    VALIDATING = "validating"
    BROKEN = "broken"
    LEAKED = "leaked"


@dataclass
class PoolMetrics:
    """Pool performance metrics"""
    total_connections: int = 0
    active_connections: int = 0
    idle_connections: int = 0
    waiting_requests: int = 0
    connection_creates: int = 0
    connection_closes: int = 0
    connection_timeouts: int = 0
    connection_errors: int = 0
    leak_detections: int = 0
    avg_acquire_time_ms: float = 0.0
    max_acquire_time_ms: float = 0.0


@dataclass
class TrackedConnection:
    """Connection with tracking metadata"""
    connection: Connection
    connection_id: str
    state: ConnectionState = ConnectionState.IDLE
    created_at: float = field(default_factory=time.time)
    last_used_at: float = field(default_factory=time.time)
    last_validated_at: float = field(default_factory=time.time)
    usage_count: int = 0
    transaction_depth: int = 0
    leak_detected: bool = False
    thread_id: Optional[int] = None
    task_name: Optional[str] = None


class ConnectionLeakError(Exception):
    """Raised when a connection leak is detected"""
    pass


class PoolExhaustedError(Exception):
    """Raised when connection pool is exhausted"""
    pass


class ConnectionPool:
    """
    High-performance async connection pool with leak detection and health monitoring.
    
    Features:
    - Configurable min/max connections
    - Connection validation and health checks
    - Automatic leak detection with stack trace capture
    - Graceful degradation under load
    - Prometheus metrics integration
    - Connection recycling
    - Transaction-aware tracking
    """
    
    # Prometheus metrics
    _METRICS_CONNECTION_TOTAL = Gauge(
        'db_pool_connections_total',
        'Total number of connections in pool',
        ['state']
    )
    _METRICS_CONNECTION_ACTIVE = Gauge(
        'db_pool_connections_active',
        'Number of active connections'
    )
    _METRICS_CONNECTION_IDLE = Gauge(
        'db_pool_connections_idle',
        'Number of idle connections'
    )
    _METRICS_WAITING_REQUESTS = Gauge(
        'db_pool_waiting_requests',
        'Number of requests waiting for connections'
    )
    _METRICS_ACQUIRE_TIME = Histogram(
        'db_pool_acquire_time_seconds',
        'Time taken to acquire connection',
        buckets=(0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1.0, 5.0)
    )
    _METRICS_CONNECTION_ERRORS = Counter(
        'db_pool_connection_errors_total',
        'Total connection errors',
        ['error_type']
    )
    _METRICS_LEAK_DETECTIONS = Counter(
        'db_pool_leak_detections_total',
        'Total connection leak detections'
    )
    
    def __init__(
        self,
        dsn: str,
        min_connections: int = 2,
        max_connections: int = 20,
        max_lifetime: int = 3600,  # 1 hour
        idle_timeout: int = 600,   # 10 minutes
        validation_interval: int = 30,  # 30 seconds
        leak_detection_threshold: int = 30,  # 30 seconds
        connection_timeout: float = 5.0,
        acquire_timeout: float = 10.0,
        enable_metrics: bool = True,
        application_name: Optional[str] = None
    ):
        """
        Initialize connection pool.
        
        Args:
            dsn: PostgreSQL connection string
            min_connections: Minimum number of connections to maintain
            max_connections: Maximum number of connections allowed
            max_lifetime: Maximum lifetime of a connection in seconds
            idle_timeout: Time before idle connection is closed (seconds)
            validation_interval: How often to validate connections (seconds)
            leak_detection_threshold: Time before connection is considered leaked (seconds)
            connection_timeout: Timeout for establishing new connection
            acquire_timeout: Timeout for acquiring connection from pool
            enable_metrics: Enable Prometheus metrics collection
            application_name: Application name for PostgreSQL connection
        """
        self.dsn = dsn
        self.min_connections = min_connections
        self.max_connections = max_connections
        self.max_lifetime = max_lifetime
        self.idle_timeout = idle_timeout
        self.validation_interval = validation_interval
        self.leak_detection_threshold = leak_detection_threshold
        self.connection_timeout = connection_timeout
        self.acquire_timeout = acquire_timeout
        self.enable_metrics = enable_metrics
        self.application_name = application_name or f"app-{uuid4().hex[:8]}"
        
        # Core pool state
        self._pool: Optional[Pool] = None
        self._tracked_connections: Dict[str, TrackedConnection] = {}
        self._idle_connections: deque = deque()
        self._active_connections: Set[str] = set()
        self._reserved_connections: Set[str] = set()
        
        # Request management
        self._waiting_requests: deque = deque()
        self._connection_semaphore: Optional[asyncio.Semaphore] = None
        
        # Health monitoring
        self._health_check_task: Optional[asyncio.Task] = None
        self._leak_detection_task: Optional[asyncio.Task] = None
        self._metrics_task: Optional[asyncio.Task] = None
        
        # Synchronization
        self._lock = asyncio.Lock()
        self._condition = asyncio.Condition()
        
        # Statistics
        self._metrics = PoolMetrics()
        self._start_time = time.time()
        
        # Cleanup tracking
        self._cleanup_callbacks: List[weakref.ReferenceType] = []
        
        # Thread safety
        self._thread_local = threading.local()
        
        logger.info(
            f"Initializing connection pool: "
            f"min={min_connections}, max={max_connections}, "
            f"app={self.application_name}"
        )
    
    async def initialize(self) -> None:
        """Initialize the connection pool and start background tasks."""
        async with self._lock:
            if self._pool is not None:
                return
            
            # Create asyncpg pool
            self._pool = await asyncpg.create_pool(
                dsn=self.dsn,
                min_size=self.min_connections,
                max_size=self.max_connections,
                max_queries=50000,  # Recycle connections periodically
                max_inactive_connection_lifetime=self.idle_timeout,
                timeout=self.connection_timeout,
                command_timeout=None,  # No command timeout at pool level
                init=self._init_connection,
                setup=self._setup_connection,
                statement_cache_size=100,
                max_cached_statement_lifetime=0,  # Disable statement cache timeout
                connection_class=None,  # Use default connection class
                loop=asyncio.get_event_loop()
            )
            
            # Initialize semaphore for connection limiting
            self._connection_semaphore = asyncio.Semaphore(self.max_connections)
            
            # Start background tasks
            self._health_check_task = asyncio.create_task(
                self._health_check_loop(),
                name="connection_pool_health_check"
            )
            self._leak_detection_task = asyncio.create_task(
                self._leak_detection_loop(),
                name="connection_pool_leak_detection"
            )
            self._metrics_task = asyncio.create_task(
                self._metrics_update_loop(),
                name="connection_pool_metrics"
            )
            
            # Register cleanup
            self._register_cleanup()
            
            logger.info("Connection pool initialized successfully")
    
    async def _init_connection(self, conn: Connection) -> None:
        """Initialize a new connection."""
        connection_id = str(uuid4())
        
        # Set application name for connection tracking in PostgreSQL
        await conn.execute(
            f"SET application_name TO '{self.application_name}-{connection_id[:8]}'"
        )
        
        # Set reasonable timeouts and settings
        await conn.execute("SET statement_timeout = 30000")  # 30 second statement timeout
        await conn.execute("SET idle_in_transaction_session_timeout = 60000")  # 60 second idle timeout
        
        tracked = TrackedConnection(
            connection=conn,
            connection_id=connection_id,
            state=ConnectionState.IDLE,
            created_at=time.time(),
            last_used_at=time.time(),
            last_validated_at=time.time(),
            thread_id=threading.get_ident(),
            task_name=asyncio.current_task().get_name() if asyncio.current_task() else None
        )
        
        async with self._lock:
            self._tracked_connections[connection_id] = tracked
            self._idle_connections.append(connection_id)
            self._metrics.connection_creates += 1
        
        if self.enable_metrics:
            self._METRICS_CONNECTION_TOTAL.labels(state='total').inc()
            self._METRICS_CONNECTION_IDLE.inc()
        
        logger.debug(f"Initialized new connection: {connection_id}")
    
    async def _setup_connection(self, conn: Connection) -> None:
        """Setup connection before use (called on acquire)."""
        connection_id = await self._get_connection_id(conn)
        
        async with self._lock:
            if connection_id in self._tracked_connections:
                tracked = self._tracked_connections[connection_id]
                tracked.last_used_at = time.time()
                tracked.usage_count += 1
                tracked.task_name = asyncio.current_task().get_name() if asyncio.current_task() else None
                
                # Validate connection if needed
                if time.time() - tracked.last_validated_at > self.validation_interval:
                    if await self._validate_connection(conn):
                        tracked.last_validated_at = time.time()
                    else:
                        # Connection is broken, remove it
                        await self._remove_connection(connection_id, ConnectionState.BROKEN)
                        raise PostgresConnectionError("Connection validation failed")
    
    async def _get_connection_id(self, conn: Connection) -> Optional[str]:
        """Extract connection ID from PostgreSQL application_name."""
        try:
            row = await conn.fetchrow("SHOW application_name")
            if row and row[0]:
                app_name = row[0]
                if '-' in app_name:
                    return app_name.split('-')[-1]
        except Exception:
            pass
        return None
    
    async def _validate_connection(self, conn: Connection) -> bool:
        """Validate connection health with a simple query."""
        try:
            await conn.execute("SELECT 1")
            return True
        except Exception as e:
            logger.warning(f"Connection validation failed: {e}")
            if self.enable_metrics:
                self._METRICS_CONNECTION_ERRORS.labels(error_type='validation').inc()
            return False
    
    async def acquire(self) -> Connection:
        """
        Acquire a connection from the pool with timeout and leak detection.
        
        Returns:
            Connection: A healthy database connection
            
        Raises:
            PoolExhaustedError: If pool is exhausted and timeout is reached
            ConnectionLeakError: If potential leak is detected
            PostgresConnectionError: If connection cannot be established
        """
        if self._pool is None:
            await self.initialize()
        
        start_time = time.time()
        
        try:
            # Try to acquire with timeout
            async with self._METRICS_ACQUIRE_TIME.time():
                conn = await asyncio.wait_for(
                    self._acquire_with_tracking(),
                    timeout=self.acquire_timeout
                )
            
            acquire_time = (time.time() - start_time) * 1000
            self._metrics.avg_acquire_time_ms = (
                (self._metrics.avg_acquire_time_ms * self._metrics.total_connections + acquire_time)
                / (self._metrics.total_connections + 1)
            )
            self._metrics.max_acquire_time_ms = max(
                self._metrics.max_acquire_time_ms,
                acquire_time
            )
            
            return conn
            
        except asyncio.TimeoutError:
            self._metrics.connection_timeouts += 1
            if self.enable_metrics:
                self._METRICS_CONNECTION_ERRORS.labels(error_type='timeout').inc()
            
            logger.error(
                f"Connection acquisition timeout after {self.acquire_timeout}s. "
                f"Active: {len(self._active_connections)}, "
                f"Idle: {len(self._idle_connections)}, "
                f"Waiting: {len(self._waiting_requests)}"
            )
            
            raise PoolExhaustedError(
                f"Connection pool exhausted. Could not acquire connection within "
                f"{self.acquire_timeout} seconds. Consider increasing max_connections "
                f"or optimizing query performance."
            )
    
    async def _acquire_with_tracking(self) -> Connection:
        """Acquire connection with detailed tracking."""
        if self._pool is None:
            raise RuntimeError("Pool not initialized")
        
        # Get connection from asyncpg pool
        conn = await self._pool.acquire()
        
        # Track the connection
        connection_id = await self._get_connection_id(conn)
        if connection_id:
            async with self._lock:
                if connection_id in self._tracked_connections:
                    tracked = self._tracked_connections[connection_id]
                    
                    # Update tracking
                    if connection_id in self._idle_connections:
                        self._idle_connections.remove(connection_id)
                    
                    self._active_connections.add(connection_id)
                    tracked.state = ConnectionState.ACTIVE
                    tracked.last_used_at = time.time()
                    tracked.thread_id = threading.get_ident()
                    
                    # Update metrics
                    self._metrics.active_connections = len(self._active_connections)
                    self._metrics.idle_connections = len(self._idle_connections)
                    
                    if self.enable_metrics:
                        self._METRICS_CONNECTION_ACTIVE.inc()
                        self._METRICS_CONNECTION_IDLE.dec()
        
        # Add cleanup callback for leak detection
        task = asyncio.current_task()
        if task:
            # Store connection ID in task context for leak detection
            if not hasattr(task, '_db_connections'):
                task._db_connections = []
            task._db_connections.append((connection_id, time.time()))
            
            # Add done callback to ensure connection is released
            task.add_done_callback(
                lambda t: asyncio.create_task(
                    self._check_task_cleanup(t, connection_id)
                )
            )
        
        return conn
    
    async def release(self, connection: Connection) -> None:
        """
        Release a connection back to the pool.
        
        Args:
            connection: Connection to release
        """
        if self._pool is None:
            logger.error("Attempted to release connection on uninitialized pool")
            return
        
        connection_id = await self._get_connection_id(connection)
        
        async with self._lock:
            if connection_id and connection_id in self._tracked_connections:
                tracked = self._tracked_connections[connection_id]
                
                # Remove from active set
                if connection_id in self._active_connections:
                    self._active_connections.remove(connection_id)
                
                # Check if connection should be recycled
                current_time = time.time()
                age = current_time - tracked.created_at
                idle_time = current_time - tracked.last_used_at
                
                if (age > self.max_lifetime or 
                    tracked.usage_count > 50000 or
                    tracked.leak_detected):
                    
                    # Connection is too old or has been used too much, close it
                    await self._remove_connection(connection_id, ConnectionState.BROKEN)
                    await self._pool.release(connection, timeout=5.0)
                    
                    logger.debug(
                        f"Recycled connection {connection_id}: "
                        f"age={age:.1f}s, uses={tracked.usage_count}"
                    )
                    return
                
                # Return to idle pool
                tracked.state = ConnectionState.IDLE
                self._idle_connections.append(connection_id)
                
                # Update metrics
                self._metrics.active_connections = len(self._active_connections)
                self._metrics.idle_connections = len(self._idle_connections)
                
                if self.enable_metrics:
                    self._METRICS_CONNECTION_ACTIVE.dec()
                    self._METRICS_CONNECTION_IDLE.inc()
                
                # Notify waiting requests
                if self._waiting_requests:
                    self._condition.notify(1)
        
        # Release back to asyncpg pool
        try:
            await self._pool.release(connection, timeout=5.0)
        except Exception as e:
            logger.error(f"Error releasing connection: {e}")
            if connection_id:
                async with self._lock:
                    await self._remove_connection(connection_id, ConnectionState.BROKEN)
    
    async def _remove_connection(
        self, 
        connection_id: str, 
        state: ConnectionState
    ) ->