"""
Environment Configuration Module

This module provides a robust, type-safe environment configuration loader with
validation, default values, and support for different deployment environments.
It uses Pydantic for validation and python-dotenv for .env file support.

Features:
- Type-safe configuration with Pydantic BaseSettings
- Environment-specific configuration (development, testing, production)
- Validation of required environment variables
- Sensitive data protection (passwords, API keys)
- Support for .env files with environment-specific overrides
- Singleton pattern to ensure single configuration instance
- Runtime environment detection
"""

import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Union, Literal
from enum import Enum

from pydantic import (
    BaseSettings,
    Field,
    SecretStr,
    validator,
    root_validator,
    HttpUrl,
    PostgresDsn,
    RedisDsn,
    AmqpDsn,
    AnyUrl
)
from pydantic.error_wrappers import ValidationError
from dotenv import load_dotenv

# Load environment variables from .env file if it exists
# This must happen before any configuration class is instantiated
env_path = Path(__file__).parent.parent.parent.parent / '.env'
if env_path.exists():
    load_dotenv(dotenv_path=env_path)
else:
    # Try to load environment-specific .env files
    env_name = os.getenv('ENVIRONMENT', 'development').lower()
    env_specific_path = Path(__file__).parent.parent.parent.parent / f'.env.{env_name}'
    if env_specific_path.exists():
        load_dotenv(dotenv_path=env_specific_path)


class EnvironmentType(str, Enum):
    """Enumeration of supported environment types."""
    DEVELOPMENT = "development"
    TESTING = "testing"
    STAGING = "staging"
    PRODUCTION = "production"
    LOCAL = "local"


class LogLevel(str, Enum):
    """Enumeration of supported log levels."""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class DatabaseType(str, Enum):
    """Enumeration of supported database types."""
    POSTGRESQL = "postgresql"
    MYSQL = "mysql"
    SQLITE = "sqlite"
    MONGODB = "mongodb"


class CacheType(str, Enum):
    """Enumeration of supported cache types."""
    REDIS = "redis"
    MEMCACHED = "memcached"
    IN_MEMORY = "in_memory"


class BaseConfig(BaseSettings):
    """Base configuration class with common settings."""
    
    class Config:
        env_file = '.env'
        env_file_encoding = 'utf-8'
        case_sensitive = False
        validate_assignment = True
        arbitrary_types_allowed = True


class DatabaseConfig(BaseConfig):
    """Database configuration settings."""
    
    # Database type and connection
    database_type: DatabaseType = Field(
        default=DatabaseType.POSTGRESQL,
        description="Type of database to use"
    )
    
    database_host: str = Field(
        default="localhost",
        description="Database server hostname or IP address"
    )
    
    database_port: int = Field(
        default=5432,
        ge=1,
        le=65535,
        description="Database server port"
    )
    
    database_name: str = Field(
        default="app_db",
        min_length=1,
        description="Database name"
    )
    
    database_user: str = Field(
        default="postgres",
        min_length=1,
        description="Database username"
    )
    
    database_password: SecretStr = Field(
        default=SecretStr("postgres"),
        description="Database password"
    )
    
    # Connection pool settings
    database_pool_min_size: int = Field(
        default=1,
        ge=0,
        description="Minimum number of connections in the pool"
    )
    
    database_pool_max_size: int = Field(
        default=10,
        ge=1,
        description="Maximum number of connections in the pool"
    )
    
    database_pool_timeout: int = Field(
        default=30,
        ge=1,
        description="Connection pool timeout in seconds"
    )
    
    # SSL/TLS settings
    database_ssl: bool = Field(
        default=False,
        description="Enable SSL/TLS for database connections"
    )
    
    database_ssl_ca: Optional[str] = Field(
        default=None,
        description="Path to SSL CA certificate file"
    )
    
    # Migration settings
    database_migrate_on_startup: bool = Field(
        default=False,
        description="Run database migrations on application startup"
    )
    
    database_migration_dir: str = Field(
        default="migrations",
        description="Directory containing database migration files"
    )
    
    @property
    def database_url(self) -> str:
        """Generate database connection URL."""
        if self.database_type == DatabaseType.SQLITE:
            return f"sqlite:///{self.database_name}.db"
        
        password = self.database_password.get_secret_value()
        
        if self.database_type == DatabaseType.POSTGRESQL:
            scheme = "postgresql"
        elif self.database_type == DatabaseType.MYSQL:
            scheme = "mysql"
        else:
            scheme = str(self.database_type.value)
        
        ssl_param = "?sslmode=require" if self.database_ssl else ""
        return f"{scheme}://{self.database_user}:{password}@{self.database_host}:{self.database_port}/{self.database_name}{ssl_param}"
    
    @validator('database_ssl_ca')
    def validate_ssl_ca(cls, v, values):
        """Validate SSL CA certificate path."""
        if values.get('database_ssl') and v:
            ca_path = Path(v)
            if not ca_path.exists():
                raise ValueError(f"SSL CA certificate file not found: {v}")
            if not ca_path.is_file():
                raise ValueError(f"SSL CA certificate path is not a file: {v}")
        return v


class CacheConfig(BaseConfig):
    """Cache configuration settings."""
    
    cache_type: CacheType = Field(
        default=CacheType.REDIS,
        description="Type of cache to use"
    )
    
    cache_host: str = Field(
        default="localhost",
        description="Cache server hostname or IP address"
    )
    
    cache_port: int = Field(
        default=6379,
        ge=1,
        le=65535,
        description="Cache server port"
    )
    
    cache_password: Optional[SecretStr] = Field(
        default=None,
        description="Cache server password (if required)"
    )
    
    cache_database: int = Field(
        default=0,
        ge=0,
        le=15,
        description="Cache database index"
    )
    
    cache_default_ttl: int = Field(
        default=300,
        ge=1,
        description="Default time-to-live for cache entries in seconds"
    )
    
    cache_max_connections: int = Field(
        default=10,
        ge=1,
        description="Maximum number of cache connections"
    )
    
    cache_key_prefix: str = Field(
        default="app",
        description="Prefix for all cache keys"
    )
    
    @property
    def cache_url(self) -> str:
        """Generate cache connection URL."""
        if self.cache_type == CacheType.REDIS:
            password_part = f":{self.cache_password.get_secret_value()}" if self.cache_password else ""
            auth_part = f"{password_part}@" if password_part else ""
            return f"redis://{auth_part}{self.cache_host}:{self.cache_port}/{self.cache_database}"
        elif self.cache_type == CacheType.MEMCACHED:
            return f"{self.cache_host}:{self.cache_port}"
        else:
            return "in_memory"


class SecurityConfig(BaseConfig):
    """Security configuration settings."""
    
    # JWT settings
    jwt_secret_key: SecretStr = Field(
        ...,
        min_length=32,
        description="Secret key for JWT token signing (minimum 32 characters)"
    )
    
    jwt_algorithm: str = Field(
        default="HS256",
        description="JWT signing algorithm"
    )
    
    jwt_access_token_expire_minutes: int = Field(
        default=30,
        ge=1,
        description="Access token expiration time in minutes"
    )
    
    jwt_refresh_token_expire_days: int = Field(
        default=7,
        ge=1,
        description="Refresh token expiration time in days"
    )
    
    # Password hashing
    password_hashing_algorithm: str = Field(
        default="bcrypt",
        description="Password hashing algorithm"
    )
    
    password_hashing_rounds: int = Field(
        default=12,
        ge=4,
        le=20,
        description="Number of rounds for password hashing"
    )
    
    # CORS settings
    cors_origins: List[str] = Field(
        default=["http://localhost:3000", "http://127.0.0.1:3000"],
        description="Allowed CORS origins"
    )
    
    cors_allow_credentials: bool = Field(
        default=True,
        description="Allow credentials in CORS requests"
    )
    
    cors_allow_methods: List[str] = Field(
        default=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
        description="Allowed HTTP methods for CORS"
    )
    
    cors_allow_headers: List[str] = Field(
        default=["*"],
        description="Allowed HTTP headers for CORS"
    )
    
    # Rate limiting
    rate_limit_enabled: bool = Field(
        default=True,
        description="Enable rate limiting"
    )
    
    rate_limit_default: str = Field(
        default="100/minute",
        description="Default rate limit string"
    )
    
    rate_limit_storage_uri: Optional[str] = Field(
        default=None,
        description="Storage URI for rate limiting (e.g., redis://localhost:6379)"
    )
    
    # API Key authentication
    api_key_header_name: str = Field(
        default="X-API-Key",
        description="HTTP header name for API key authentication"
    )
    
    api_keys: List[SecretStr] = Field(
        default=[],
        description="List of valid API keys"
    )


class LoggingConfig(BaseConfig):
    """Logging configuration settings."""
    
    log_level: LogLevel = Field(
        default=LogLevel.INFO,
        description="Default log level"
    )
    
    log_format: str = Field(
        default="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        description="Log message format"
    )
    
    log_date_format: str = Field(
        default="%Y-%m-%d %H:%M:%S",
        description="Date format in log messages"
    )
    
    log_file: Optional[str] = Field(
        default=None,
        description="Path to log file (if None, logs to console only)"
    )
    
    log_max_bytes: int = Field(
        default=10485760,  # 10MB
        ge=1024,
        description="Maximum size of log file in bytes before rotation"
    )
    
    log_backup_count: int = Field(
        default=5,
        ge=0,
        description="Number of backup log files to keep"
    )
    
    log_json_format: bool = Field(
        default=False,
        description="Use JSON format for logs (useful for structured logging)"
    )
    
    # Component-specific log levels
    log_level_overrides: Dict[str, LogLevel] = Field(
        default={},
        description="Component-specific log level overrides"
    )
    
    @validator('log_file')
    def validate_log_file(cls, v):
        """Validate log file path."""
        if v:
            log_path = Path(v)
            parent_dir = log_path.parent
            if not parent_dir.exists():
                try:
                    parent_dir.mkdir(parents=True, exist_ok=True)
                except (OSError, PermissionError) as e:
                    raise ValueError(f"Cannot create log directory: {e}")
            
            # Check if we can write to the directory
            if not os.access(parent_dir, os.W_OK):
                raise ValueError(f"No write permission for log directory: {parent_dir}")
        
        return v


class APIConfig(BaseConfig):
    """API server configuration settings."""
    
    api_host: str = Field(
        default="0.0.0.0",
        description="API server host address"
    )
    
    api_port: int = Field(
        default=8000,
        ge=1,
        le=65535,
        description="API server port"
    )
    
    api_workers: int = Field(
        default=1,
        ge=1,
        description="Number of worker processes"
    )
    
    api_reload: bool = Field(
        default=False,
        description="Enable auto-reload for development"
    )
    
    api_debug: bool = Field(
        default=False,
        description="Enable debug mode"
    )
    
    api_title: str = Field(
        default="Application API",
        description="API title for documentation"
    )
    
    api_description: str = Field(
        default="REST API for the application",
        description="API description for documentation"
    )
    
    api_version: str = Field(
        default="1.0.0",
        description="API version"
    )
    
    api_docs_url: Optional[str] = Field(
        default="/docs",
        description="URL path for Swagger documentation"
    )
    
    api_redoc_url: Optional[str] = Field(
        default="/redoc",
        description="URL path for ReDoc documentation"
    )
    
    api_openapi_url: Optional[str] = Field(
        default="/openapi.json",
        description="URL path for OpenAPI schema"
    )
    
    # Request/response settings
    api_max_request_size: int = Field(
        default=10485760,  # 10MB
        ge=1024,
        description="Maximum request size in bytes"
    )
    
    api_timeout: int = Field(
        default=30,
        ge=1,
        description="Request timeout in seconds"
    )
    
    @validator('api_reload')
    def validate_reload_for_production(cls, v, values):
        """Ensure auto-reload is disabled in production."""
        environment = values.get('environment', EnvironmentType.DEVELOPMENT)
        if environment == EnvironmentType.PRODUCTION and v:
            raise ValueError("Auto-reload should not be enabled in production")
        return v
    
    @validator('api_debug')
    def validate_debug_for_production(cls, v, values):
        """Ensure debug mode is disabled in production."""
        environment = values.get('environment', EnvironmentType.DEVELOPMENT)
        if environment == EnvironmentType.PRODUCTION and v:
            raise ValueError("Debug mode should not be enabled in production")
        return v


class ExternalServicesConfig(BaseConfig):
    """External services configuration settings."""
    
    # Email service
    email_service_enabled: bool = Field(
        default=False,
        description="Enable email service"
    )
    
    email_host: Optional[str] = Field(
        default=None,
        description="Email server host"
    )
    
    email_port: Optional[int] = Field(
        default=None,
        ge=1,
        le=65535,
        description="Email server port"
    )
    
    email_username: Optional[str] = Field(
        default=None,
        description="Email server username"
    )
    
    email_password: Optional[SecretStr] = Field(
        default=None,
        description="Email server password"
    )
    
    email_use_tls: bool = Field(
        default=True,
        description="Use TLS for email connections"
    )
    
    email_from_address: Optional[str] = Field(
        default=None,
        description="Default 'from' email address"
    )
    
    # Storage service (S3-compatible)
    storage_service_enabled: bool = Field(
        default=False,
        description="Enable storage service"
    )
    
    storage_endpoint: Optional[str] = Field(
        default=None,
        description="Storage service endpoint URL"
    )
    
    storage_access_key: Optional[SecretStr] = Field(
        default=None,
        description="Storage service access key"
    )
    
    storage_secret_key: Optional[SecretStr] = Field(
        default=None,
        description="Storage service secret key"
    )
    
    storage_bucket: Optional[str] = Field(
        default=None,
        description="Default storage bucket"
    )
    
    storage_region: Optional[str] = Field(
        default=None,
        description="Storage service region"
    )
    
    # Message queue (RabbitMQ, etc.)
    message_queue_enabled: bool = Field(
        default=False,
        description="Enable message queue"
    )
    
    message_queue_url: Optional[str] = Field(
        default=None,
        description="Message queue connection URL"
    )
    
    message_queue_exchange: Optional[str] = Field(
        default=None,
        description="Default message queue exchange"
    )
    
    # Third-party APIs
    openai_api_key: Optional[SecretStr] = Field(
        default=None,
        description="OpenAI API key"
    )
    
    google_api_key: Optional[SecretStr] = Field(
        default=None,
        description="Google API key"
    )
    
    stripe_secret_key: Optional[SecretStr] = Field(
        default=None,
        description="Stripe secret key"
    )
    
    stripe_webhook_secret: Optional[SecretStr] = Field(
        default=None,
        description="Stripe webhook secret"
    )
    
    @validator('email_host')
    def validate_email_host(cls, v, values):
        """Validate email host when email service is enabled."""
        if values.get('email_service_enabled') and not v:
            raise ValueError("Email host is required when email service is enabled")
        return v
    
    @validator('storage_endpoint')
    def validate_storage_endpoint(cls, v, values):
        """Validate storage endpoint when storage service is enabled."""
        if values.get('storage_service_enabled') and not v:
            raise ValueError("Storage endpoint is required when storage service is enabled")
        return v


class ApplicationConfig(BaseConfig):
    """Main application configuration combining all sub-configurations."""
    
    # Core environment
    environment: EnvironmentType = Field(
        default=EnvironmentType.DEVELOPMENT,
        description="Application environment"
    )
    
    app_name: str = Field(
        default="My Application",
        min_length=1,
        description="Application name"
    )
    
   