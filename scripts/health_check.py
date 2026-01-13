#!/usr/bin/env python3
"""
Health Check Endpoint for High-Concurrency Monitoring System

This module provides a comprehensive health check endpoint for monitoring
the status of the application, its dependencies, and system resources.
It is designed to be lightweight, fast, and suitable for use by load
balancers, container orchestration systems (Kubernetes, Docker Swarm),
and external monitoring tools (Prometheus, Datadog, etc.).

Features:
- Dependency health checks (database, cache, external APIs)
- System resource monitoring (CPU, memory, disk)
- Application-specific health indicators
- Configurable check depth (basic, full, critical)
- Response caching for high-frequency polling
- Structured JSON output with status codes
- Optional metrics exposure in Prometheus format
"""

import asyncio
import json
import logging
import os
import platform
import psutil
import signal
import socket
import sys
import time
import threading
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Any, Optional, Tuple, Callable, Union
from dataclasses import dataclass, field, asdict
from functools import wraps
from concurrent.futures import ThreadPoolExecutor

# Third-party imports (with graceful degradation)
try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    redis = None

try:
    import pymongo
    MONGO_AVAILABLE = True
except ImportError:
    MONGO_AVAILABLE = False
    pymongo = None

try:
    import sqlalchemy
    from sqlalchemy import text
    SQLALCHEMY_AVAILABLE = True
except ImportError:
    SQLALCHEMY_AVAILABLE = False
    sqlalchemy = None

try:
    import aiohttp
    AIOHTTP_AVAILABLE = True
except ImportError:
    AIOHTTP_AVAILABLE = False
    aiohttp = None

# Configure logging
logger = logging.getLogger(__name__)

class HealthStatus(str, Enum):
    """Health status enumeration."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"

class CheckDepth(str, Enum):
    """Depth of health checks."""
    BASIC = "basic"      # Quick application status only
    FULL = "full"        # All dependencies and resources
    CRITICAL = "critical" # Only critical dependencies

@dataclass
class CheckResult:
    """Result of an individual health check."""
    name: str
    status: HealthStatus
    message: str = ""
    duration_ms: float = 0.0
    timestamp: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        result = asdict(self)
        result['timestamp'] = self.timestamp.isoformat()
        result['status'] = self.status.value
        return result

@dataclass
class HealthResponse:
    """Complete health check response."""
    status: HealthStatus
    timestamp: datetime = field(default_factory=datetime.utcnow)
    version: str = "1.0.0"
    service: str = "application"
    checks: Dict[str, CheckResult] = field(default_factory=dict)
    system: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            'status': self.status.value,
            'timestamp': self.timestamp.isoformat(),
            'version': self.version,
            'service': self.service,
            'checks': {name: check.to_dict() for name, check in self.checks.items()},
            'system': self.system
        }
    
    def to_prometheus(self) -> str:
        """Convert to Prometheus metrics format."""
        metrics = []
        metrics.append(f'# HELP health_check_status Overall health status (1=healthy, 0.5=degraded, 0=unhealthy)')
        metrics.append(f'# TYPE health_check_status gauge')
        
        status_value = {
            HealthStatus.HEALTHY: 1,
            HealthStatus.DEGRADED: 0.5,
            HealthStatus.UNHEALTHY: 0,
            HealthStatus.UNKNOWN: -1
        }.get(self.status, -1)
        
        metrics.append(f'health_check_status{{service="{self.service}"}} {status_value}')
        
        for check_name, check_result in self.checks.items():
            check_status_value = {
                HealthStatus.HEALTHY: 1,
                HealthStatus.DEGRADED: 0.5,
                HealthStatus.UNHEALTHY: 0,
                HealthStatus.UNKNOWN: -1
            }.get(check_result.status, -1)
            
            metrics.append(f'health_check_component_status{{service="{self.service}",check="{check_name}"}} {check_status_value}')
            metrics.append(f'health_check_duration_ms{{service="{self.service}",check="{check_name}"}} {check_result.duration_ms}')
        
        # System metrics
        for metric_name, metric_value in self.system.items():
            if isinstance(metric_value, (int, float)):
                metrics.append(f'health_system_{metric_name}{{service="{self.service}"}} {metric_value}')
        
        return '\n'.join(metrics)

class HealthCheckRegistry:
    """Registry for health check functions."""
    
    def __init__(self):
        self._checks: Dict[str, Callable] = {}
        self._critical_checks: List[str] = []
        self._check_timeout: float = 5.0  # Default timeout in seconds
    
    def register(self, name: str, check_func: Callable, critical: bool = False) -> None:
        """Register a health check function."""
        self._checks[name] = check_func
        if critical:
            self._critical_checks.append(name)
    
    def unregister(self, name: str) -> None:
        """Unregister a health check function."""
        self._checks.pop(name, None)
        if name in self._critical_checks:
            self._critical_checks.remove(name)
    
    def set_timeout(self, timeout: float) -> None:
        """Set timeout for all checks in seconds."""
        self._check_timeout = timeout
    
    async def run_check(self, name: str) -> CheckResult:
        """Run a single health check with timeout."""
        if name not in self._checks:
            return CheckResult(
                name=name,
                status=HealthStatus.UNKNOWN,
                message=f"Check '{name}' not registered",
                duration_ms=0.0
            )
        
        start_time = time.time()
        check_func = self._checks[name]
        
        try:
            # Run check with timeout
            if asyncio.iscoroutinefunction(check_func):
                # Async check
                try:
                    result = await asyncio.wait_for(check_func(), timeout=self._check_timeout)
                except asyncio.TimeoutError:
                    raise TimeoutError(f"Check '{name}' timed out after {self._check_timeout}s")
            else:
                # Sync check - run in thread pool
                loop = asyncio.get_event_loop()
                with ThreadPoolExecutor(max_workers=1) as executor:
                    try:
                        result = await asyncio.wait_for(
                            loop.run_in_executor(executor, check_func),
                            timeout=self._check_timeout
                        )
                    except asyncio.TimeoutError:
                        raise TimeoutError(f"Check '{name}' timed out after {self._check_timeout}s")
            
            # Process result
            if isinstance(result, CheckResult):
                result.duration_ms = (time.time() - start_time) * 1000
                return result
            elif isinstance(result, tuple) and len(result) == 2:
                status, message = result
                if isinstance(status, HealthStatus):
                    return CheckResult(
                        name=name,
                        status=status,
                        message=str(message),
                        duration_ms=(time.time() - start_time) * 1000
                    )
                elif isinstance(status, bool):
                    return CheckResult(
                        name=name,
                        status=HealthStatus.HEALTHY if status else HealthStatus.UNHEALTHY,
                        message=str(message),
                        duration_ms=(time.time() - start_time) * 1000
                    )
            elif isinstance(result, bool):
                return CheckResult(
                    name=name,
                    status=HealthStatus.HEALTHY if result else HealthStatus.UNHEALTHY,
                    duration_ms=(time.time() - start_time) * 1000
                )
            else:
                return CheckResult(
                    name=name,
                    status=HealthStatus.UNKNOWN,
                    message=f"Invalid return type from check '{name}'",
                    duration_ms=(time.time() - start_time) * 1000
                )
                
        except TimeoutError as e:
            return CheckResult(
                name=name,
                status=HealthStatus.UNHEALTHY,
                message=str(e),
                duration_ms=(time.time() - start_time) * 1000
            )
        except Exception as e:
            logger.error(f"Health check '{name}' failed: {e}", exc_info=True)
            return CheckResult(
                name=name,
                status=HealthStatus.UNHEALTHY,
                message=f"Check failed: {str(e)}",
                duration_ms=(time.time() - start_time) * 1000
            )
    
    async def run_checks(self, check_names: Optional[List[str]] = None) -> Dict[str, CheckResult]:
        """Run multiple health checks concurrently."""
        if check_names is None:
            check_names = list(self._checks.keys())
        
        # Run checks concurrently
        tasks = [self.run_check(name) for name in check_names]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Process results
        check_results = {}
        for name, result in zip(check_names, results):
            if isinstance(result, Exception):
                check_results[name] = CheckResult(
                    name=name,
                    status=HealthStatus.UNHEALTHY,
                    message=f"Check execution error: {str(result)}",
                    duration_ms=0.0
                )
            else:
                check_results[name] = result
        
        return check_results

class SystemMonitor:
    """Monitor system resources."""
    
    def __init__(self):
        self.process = psutil.Process(os.getpid())
        self._last_network_io = None
        self._last_disk_io = None
        self._last_check_time = None
    
    def get_system_info(self) -> Dict[str, Any]:
        """Get comprehensive system information."""
        try:
            # CPU
            cpu_percent = psutil.cpu_percent(interval=0.1)
            cpu_count = psutil.cpu_count()
            cpu_freq = psutil.cpu_freq()
            
            # Memory
            virtual_memory = psutil.virtual_memory()
            swap_memory = psutil.swap_memory()
            
            # Disk
            disk_usage = psutil.disk_usage('/')
            disk_io = psutil.disk_io_counters()
            
            # Network
            net_io = psutil.net_io_counters()
            
            # Process info
            process_memory = self.process.memory_info()
            process_cpu = self.process.cpu_percent(interval=0.1)
            process_threads = self.process.num_threads()
            process_open_files = len(self.process.open_files())
            process_connections = len(self.process.connections())
            
            # System info
            boot_time = datetime.fromtimestamp(psutil.boot_time())
            uptime = datetime.now() - boot_time
            
            # Calculate IO rates if we have previous measurements
            network_rates = {}
            disk_rates = {}
            
            current_time = time.time()
            if self._last_network_io and self._last_check_time:
                time_diff = current_time - self._last_check_time
                if time_diff > 0:
                    network_rates = {
                        'bytes_sent_per_sec': (net_io.bytes_sent - self._last_network_io.bytes_sent) / time_diff,
                        'bytes_recv_per_sec': (net_io.bytes_recv - self._last_network_io.bytes_recv) / time_diff,
                        'packets_sent_per_sec': (net_io.packets_sent - self._last_network_io.packets_sent) / time_diff,
                        'packets_recv_per_sec': (net_io.packets_recv - self._last_network_io.packets_recv) / time_diff,
                    }
            
            if self._last_disk_io and self._last_check_time:
                time_diff = current_time - self._last_check_time
                if time_diff > 0:
                    disk_rates = {
                        'read_bytes_per_sec': (disk_io.read_bytes - self._last_disk_io.read_bytes) / time_diff,
                        'write_bytes_per_sec': (disk_io.write_bytes - self._last_disk_io.write_bytes) / time_diff,
                        'read_count_per_sec': (disk_io.read_count - self._last_disk_io.read_count) / time_diff,
                        'write_count_per_sec': (disk_io.write_count - self._last_disk_io.write_count) / time_diff,
                    }
            
            # Update last measurements
            self._last_network_io = net_io
            self._last_disk_io = disk_io
            self._last_check_time = current_time
            
            return {
                'cpu': {
                    'percent': cpu_percent,
                    'count': cpu_count,
                    'frequency_current': cpu_freq.current if cpu_freq else None,
                    'frequency_min': cpu_freq.min if cpu_freq else None,
                    'frequency_max': cpu_freq.max if cpu_freq else None,
                },
                'memory': {
                    'total': virtual_memory.total,
                    'available': virtual_memory.available,
                    'percent': virtual_memory.percent,
                    'used': virtual_memory.used,
                    'free': virtual_memory.free,
                },
                'swap': {
                    'total': swap_memory.total,
                    'used': swap_memory.used,
                    'free': swap_memory.free,
                    'percent': swap_memory.percent,
                },
                'disk': {
                    'total': disk_usage.total,
                    'used': disk_usage.used,
                    'free': disk_usage.free,
                    'percent': disk_usage.percent,
                    'io': {
                        'read_bytes': disk_io.read_bytes,
                        'write_bytes': disk_io.write_bytes,
                        'read_count': disk_io.read_count,
                        'write_count': disk_io.write_count,
                        **disk_rates,
                    } if disk_io else None,
                },
                'network': {
                    'bytes_sent': net_io.bytes_sent,
                    'bytes_recv': net_io.bytes_recv,
                    'packets_sent': net_io.packets_sent,
                    'packets_recv': net_io.packets_recv,
                    **network_rates,
                } if net_io else None,
                'process': {
                    'memory_rss': process_memory.rss,
                    'memory_vms': process_memory.vms,
                    'cpu_percent': process_cpu,
                    'threads': process_threads,
                    'open_files': process_open_files,
                    'connections': process_connections,
                },
                'system': {
                    'boot_time': boot_time.isoformat(),
                    'uptime_seconds': uptime.total_seconds(),
                    'hostname': socket.gethostname(),
                    'platform': platform.platform(),
                    'python_version': platform.python_version(),
                }
            }
            
        except Exception as e:
            logger.error(f"Failed to get system info: {e}", exc_info=True)
            return {'error': str(e)}

class HealthCheckService:
    """Main health check service."""
    
    def __init__(self, service_name: str = "application", version: str = "1.0.0"):
        self.service_name = service_name
        self.version = version
        self.registry = HealthCheckRegistry()
        self.system_monitor = SystemMonitor()
        self._response_cache = None
        self._cache_ttl = 5.0  # Cache TTL in seconds
        self._last_cache_update = 0
        
        # Register built-in checks
        self._register_builtin_checks()
    
    def _register_builtin_checks(self) -> None:
        """Register built-in health checks."""
        
        # Application status check
        self.registry.register("application", self._check_application, critical=True)
        
        # System resource checks
        self.registry.register("system_resources", self._check_system_resources)
        
        # Python environment check
        self.registry.register("python_environment", self._check_python_environment)
        
        # Database checks (if available)
        if SQLALCHEMY_AVAILABLE:
            self.registry.register("database", self._check_database, critical=True)
        
        # Redis check (if available)
        if REDIS_AVAILABLE:
            self.registry.register("redis", self._check_redis)
        
        # MongoDB check (if available)
        if MONGO_AVAILABLE:
            self.registry.register("mongodb", self._check_mongodb)
        
        # External API check (if available)
        if AIOHTTP_AVAILABLE:
            self.registry.register("external_api", self._check_external_api)
    
    def set_cache_ttl(self, ttl_seconds: float) -> None:
        """Set cache TTL for health check responses."""
        self._cache_ttl = ttl_seconds
    
    def set_check_timeout(self, timeout_seconds: float) -> None:
        """Set timeout for individual health checks."""
        self.registry.set_timeout(timeout_seconds)
    
    def add_custom_check(self, name: str, check_func: Callable, critical: bool = False) -> None:
        """Add a custom health check."""
        self.registry.register(name, check_func, critical)
    
    # Built-in check implementations
    
    def _check_application(self) -> CheckResult:
        """Check basic application health."""
        try:
            # Check if we can import main application modules
            import __main__
            
            # Check if we're running in a valid Python environment
            if not sys.executable:
                return CheckResult(
