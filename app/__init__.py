"""
App Package Initialization

This module initializes the app package and exposes the core application
components for external import. It serves as the main entry point for
the application's public API.

Key Responsibilities:
- Package-level initialization and metadata
- Centralized export of public classes and functions
- Version management
- Application lifecycle hooks
"""

import os
import sys
from pathlib import Path
from typing import Optional, Dict, Any, List, Union

# Add the parent directory to the Python path for module resolution
# This ensures that imports work correctly regardless of execution context
_parent_dir = Path(__file__).parent.parent
if str(_parent_dir) not in sys.path:
    sys.path.insert(0, str(_parent_dir))

# Package metadata
__version__ = "1.0.0"
__author__ = "CodeCraft AI"
__license__ = "MIT"
__copyright__ = "Copyright 2024 CodeCraft AI"

# Application configuration defaults
DEFAULT_CONFIG = {
    "debug": False,
    "environment": "production",
    "log_level": "INFO",
    "max_workers": 4,
    "timeout": 30,
    "cache_ttl": 3600,
    "database_url": "sqlite:///./app.db",
    "redis_url": "redis://localhost:6379/0",
    "api_prefix": "/api/v1",
    "cors_origins": ["*"],
    "rate_limit": 100,
    "secret_key": "change-this-in-production",
    "session_ttl": 86400,
}

# Public API exports
# These imports are lazy-loaded to avoid circular dependencies
# and improve startup performance

__all__ = [
    # Core application
    "create_app",
    "get_app",
    "run_app",
    
    # Configuration
    "Config",
    "load_config",
    "validate_config",
    
    # Utilities
    "logger",
    "cache",
    "database",
    "redis_client",
    
    # Decorators
    "route",
    "middleware",
    "validator",
    "background_task",
    
    # Exceptions
    "AppError",
    "ValidationError",
    "NotFoundError",
    "RateLimitError",
    
    # Types
    "Request",
    "Response",
    "JSONType",
    
    # Constants
    "DEFAULT_CONFIG",
    "__version__",
    "__author__",
]

# Lazy import proxies
# These will be initialized on first access to avoid import overhead

class _LazyImporter:
    """Lazy importer for application components to optimize startup."""
    
    _modules = {}
    
    @classmethod
    def _import_core(cls):
        """Import core application module."""
        if "core" not in cls._modules:
            from .core.application import Application
            cls._modules["core"] = Application
        return cls._modules["core"]
    
    @classmethod
    def _import_config(cls):
        """Import configuration module."""
        if "config" not in cls._modules:
            from .core.config import Config, load_config, validate_config
            cls._modules["config"] = {
                "Config": Config,
                "load_config": load_config,
                "validate_config": validate_config,
            }
        return cls._modules["config"]
    
    @classmethod
    def _import_utils(cls):
        """Import utility modules."""
        if "utils" not in cls._modules:
            from .utils.logging import get_logger
            from .utils.cache import CacheManager
            from .database.connection import DatabaseManager
            from .cache.redis import RedisClient
            
            cls._modules["utils"] = {
                "logger": get_logger("app"),
                "cache": CacheManager(),
                "database": DatabaseManager(),
                "redis_client": RedisClient(),
            }
        return cls._modules["utils"]
    
    @classmethod
    def _import_decorators(cls):
        """Import decorator modules."""
        if "decorators" not in cls._modules:
            from .core.decorators import (
                route, 
                middleware, 
                validator, 
                background_task
            )
            cls._modules["decorators"] = {
                "route": route,
                "middleware": middleware,
                "validator": validator,
                "background_task": background_task,
            }
        return cls._modules["decorators"]
    
    @classmethod
    def _import_exceptions(cls):
        """Import exception classes."""
        if "exceptions" not in cls._modules:
            from .core.exceptions import (
                AppError,
                ValidationError,
                NotFoundError,
                RateLimitError,
            )
            cls._modules["exceptions"] = {
                "AppError": AppError,
                "ValidationError": ValidationError,
                "NotFoundError": NotFoundError,
                "RateLimitError": RateLimitError,
            }
        return cls._modules["exceptions"]
    
    @classmethod
    def _import_types(cls):
        """Import type definitions."""
        if "types" not in cls._modules:
            from typing import Dict, List, Union, Any
            from .core.types import Request, Response, JSONType
            cls._modules["types"] = {
                "Request": Request,
                "Response": Response,
                "JSONType": JSONType,
            }
        return cls._modules["types"]

# Public API accessors
# These functions provide access to lazy-loaded components

def create_app(config: Optional[Dict[str, Any]] = None) -> Any:
    """
    Create and configure a new application instance.
    
    Args:
        config: Optional configuration dictionary to override defaults
        
    Returns:
        Application instance
        
    Example:
        >>> app = create_app({"debug": True, "environment": "development"})
        >>> app.run()
    """
    Application = _LazyImporter._import_core()
    config_module = _LazyImporter._import_config()
    
    # Merge provided config with defaults
    app_config = DEFAULT_CONFIG.copy()
    if config:
        app_config.update(config)
    
    # Validate configuration
    config_module["validate_config"](app_config)
    
    # Create application instance
    return Application(config=app_config)

def get_app() -> Optional[Any]:
    """
    Get the current application instance if one exists.
    
    Returns:
        Current application instance or None if not initialized
        
    Example:
        >>> app = get_app()
        >>> if app:
        ...     app.logger.info("Application is running")
    """
    try:
        from .core.application import _current_app
        return _current_app
    except (ImportError, AttributeError):
        return None

def run_app(
    host: str = "127.0.0.1",
    port: int = 8000,
    debug: Optional[bool] = None,
    **kwargs
) -> None:
    """
    Run the application server.
    
    Args:
        host: Server host address
        port: Server port
        debug: Enable debug mode (overrides config if provided)
        **kwargs: Additional arguments passed to the application runner
        
    Example:
        >>> run_app(host="0.0.0.0", port=8080, debug=True)
    """
    app = get_app()
    if not app:
        # Create default app if none exists
        config = {"debug": debug} if debug is not None else {}
        app = create_app(config)
    
    # Override debug mode if specified
    if debug is not None:
        app.config["debug"] = debug
    
    # Run the application
    app.run(host=host, port=port, **kwargs)

# Configuration accessors
class Config:
    """Configuration class proxy for lazy loading."""
    
    @staticmethod
    def load(config_path: Optional[str] = None) -> Dict[str, Any]:
        """
        Load configuration from file or environment.
        
        Args:
            config_path: Optional path to configuration file
            
        Returns:
            Configuration dictionary
        """
        config_module = _LazyImporter._import_config()
        return config_module["load_config"](config_path)
    
    @staticmethod
    def validate(config: Dict[str, Any]) -> bool:
        """
        Validate configuration dictionary.
        
        Args:
            config: Configuration dictionary to validate
            
        Returns:
            True if configuration is valid
            
        Raises:
            ValidationError: If configuration is invalid
        """
        config_module = _LazyImporter._import_config()
        return config_module["validate_config"](config)

def load_config(config_path: Optional[str] = None) -> Dict[str, Any]:
    """Alias for Config.load()."""
    return Config.load(config_path)

def validate_config(config: Dict[str, Any]) -> bool:
    """Alias for Config.validate()."""
    return Config.validate(config)

# Utility accessors
@property
def logger():
    """Get the application logger."""
    utils = _LazyImporter._import_utils()
    return utils["logger"]

@property
def cache():
    """Get the cache manager."""
    utils = _LazyImporter._import_utils()
    return utils["cache"]

@property
def database():
    """Get the database manager."""
    utils = _LazyImporter._import_utils()
    return utils["database"]

@property
def redis_client():
    """Get the Redis client."""
    utils = _LazyImporter._import_utils()
    return utils["redis_client"]

# Decorator accessors
@property
def route():
    """Get the route decorator."""
    decorators = _LazyImporter._import_decorators()
    return decorators["route"]

@property
def middleware():
    """Get the middleware decorator."""
    decorators = _LazyImporter._import_decorators()
    return decorators["middleware"]

@property
def validator():
    """Get the validator decorator."""
    decorators = _LazyImporter._import_decorators()
    return decorators["validator"]

@property
def background_task():
    """Get the background task decorator."""
    decorators = _LazyImporter._import_decorators()
    return decorators["background_task"]

# Exception accessors
@property
def AppError():
    """Get the base application error class."""
    exceptions = _LazyImporter._import_exceptions()
    return exceptions["AppError"]

@property
def ValidationError():
    """Get the validation error class."""
    exceptions = _LazyImporter._import_exceptions()
    return exceptions["ValidationError"]

@property
def NotFoundError():
    """Get the not found error class."""
    exceptions = _LazyImporter._import_exceptions()
    return exceptions["NotFoundError"]

@property
def RateLimitError():
    """Get the rate limit error class."""
    exceptions = _LazyImporter._import_exceptions()
    return exceptions["RateLimitError"]

# Type accessors
@property
def Request():
    """Get the Request type."""
    types = _LazyImporter._import_types()
    return types["Request"]

@property
def Response():
    """Get the Response type."""
    types = _LazyImporter._import_types()
    return types["Response"]

@property
def JSONType():
    """Get the JSONType type alias."""
    types = _LazyImporter._import_types()
    return types["JSONType"]

# Package initialization
def _initialize_package():
    """Initialize package-level resources."""
    # Set up package logging
    import logging
    
    # Configure root logger if not already configured
    root_logger = logging.getLogger()
    if not root_logger.handlers:
        handler = logging.StreamHandler()
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        handler.setFormatter(formatter)
        root_logger.addHandler(handler)
        root_logger.setLevel(logging.INFO)
    
    # Log package initialization
    package_logger = logging.getLogger(__name__)
    package_logger.debug(
        f"Initializing app package v{__version__} by {__author__}"
    )
    
    # Check environment
    env = os.getenv("APP_ENVIRONMENT", "production")
    package_logger.info(f"Application environment: {env}")
    
    # Validate critical dependencies
    try:
        import sqlalchemy
        import redis
        import pydantic
        package_logger.debug("All dependencies are available")
    except ImportError as e:
        package_logger.warning(f"Missing dependency: {e}")
    
    return True

# Run package initialization
_package_initialized = _initialize_package()

# Clean up module namespace
del _LazyImporter
del _initialize_package
del _parent_dir

# Export package metadata
__docformat__ = "restructuredtext"
__status__ = "Production"
__maintainer__ = "dev@codecraft.ai"
__email__ = "dev@codecraft.ai"
__url__ = "https://github.com/codecraft-ai/app"
__download_url__ = "https://pypi.org/project/codecraft-app/"
__keywords__ = ["web", "application", "framework", "async", "high-concurrency"]
__classifiers__ = [
    "Development Status :: 5 - Production/Stable",
    "Intended Audience :: Developers",
    "License :: OSI Approved :: MIT License",
    "Operating System :: OS Independent",
    "Programming Language :: Python :: 3",
    "Programming Language :: Python :: 3.8",
    "Programming Language :: Python :: 3.9",
    "Programming Language :: Python :: 3.10",
    "Programming Language :: Python :: 3.11",
    "Programming Language :: Python :: 3.12",
    "Topic :: Internet :: WWW/HTTP",
    "Topic :: Software Development :: Libraries :: Application Frameworks",
]

# Package entry points (for setuptools compatibility)
if __name__ == "__main__":
    # Allow running the package as a module
    # python -m app
    import argparse
    
    parser = argparse.ArgumentParser(description="CodeCraft AI Application Framework")
    parser.add_argument(
        "--version", 
        action="version", 
        version=f"CodeCraft AI App v{__version__}"
    )
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Server host address (default: 127.0.0.1)"
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Server port (default: 8000)"
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug mode"
    )
    
    args = parser.parse_args()
    
    print(f"Starting CodeCraft AI Application v{__version__}")
    print(f"Server: {args.host}:{args.port}")
    print(f"Debug mode: {args.debug}")
    print("Press Ctrl+C to stop")
    
    # Run the application
    run_app(host=args.host, port=args.port, debug=args.debug)
