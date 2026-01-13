"""
Application Configuration Module

This module provides centralized configuration management for the application.
It supports multiple environments (development, testing, staging, production)
and loads configuration from environment variables with sensible defaults.

Features:
- Environment-specific configuration
- Type-safe configuration validation using Pydantic
- Secret management with .env file support
- Database configuration
- API configuration
- Logging configuration
- CORS configuration
- Rate limiting configuration
- Cache configuration
"""

import os
import secrets
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from pydantic import AnyHttpUrl, BaseSettings, EmailStr, PostgresDsn, validator


class Settings(BaseSettings):
    """
    Application settings class.
    
    All configuration values are loaded from environment variables.
    Environment variables should be prefixed with 'APP_' to avoid conflicts.
    """
    
    # ==================== BASIC APPLICATION CONFIG ====================
    APP_NAME: str = "CodeCraft AI"
    APP_VERSION: str = "1.0.0"
    APP_DESCRIPTION: str = "High-concurrency architectural engine"
    APP_DEBUG: bool = False
    
    # ==================== ENVIRONMENT CONFIG ====================
    ENVIRONMENT: str = "development"
    
    @validator("ENVIRONMENT")
    def validate_environment(cls, v: str) -> str:
        """Validate environment value."""
        allowed = ["development", "testing", "staging", "production"]
        if v not in allowed:
            raise ValueError(f"ENVIRONMENT must be one of {allowed}")
        return v
    
    # ==================== SECURITY CONFIG ====================
    SECRET_KEY: str = secrets.token_urlsafe(32)
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    
    # ==================== API CONFIG ====================
    API_V1_STR: str = "/api/v1"
    API_PREFIX: str = "/api"
    PROJECT_NAME: str = "CodeCraft AI API"
    
    # ==================== SERVER CONFIG ====================
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    WORKERS: int = 4
    BACKLOG: int = 2048
    TIMEOUT: int = 120
    
    # ==================== DATABASE CONFIG ====================
    POSTGRES_SERVER: str = "localhost"
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = ""
    POSTGRES_DB: str = "codecraft"
    POSTGRES_PORT: str = "5432"
    
    # Construct database URL
    SQLALCHEMY_DATABASE_URI: Optional[PostgresDsn] = None
    
    @validator("SQLALCHEMY_DATABASE_URI", pre=True)
    def assemble_db_connection(cls, v: Optional[str], values: Dict[str, Any]) -> Any:
        """Assemble database connection URI from components."""
        if isinstance(v, str):
            return v
        
        return PostgresDsn.build(
            scheme="postgresql",
            user=values.get("POSTGRES_USER"),
            password=values.get("POSTGRES_PASSWORD"),
            host=values.get("POSTGRES_SERVER"),
            port=values.get("POSTGRES_PORT"),
            path=f"/{values.get('POSTGRES_DB') or ''}",
        )
    
    # ==================== REDIS CONFIG ====================
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_PASSWORD: Optional[str] = None
    REDIS_DB: int = 0
    REDIS_SSL: bool = False
    
    @property
    def redis_url(self) -> str:
        """Construct Redis connection URL."""
        auth = f":{self.REDIS_PASSWORD}@" if self.REDIS_PASSWORD else ""
        scheme = "rediss" if self.REDIS_SSL else "redis"
        return f"{scheme}://{auth}{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"
    
    # ==================== CACHE CONFIG ====================
    CACHE_DEFAULT_TIMEOUT: int = 300  # 5 minutes
    CACHE_KEY_PREFIX: str = "codecraft:"
    CACHE_ENABLED: bool = True
    
    # ==================== RATE LIMITING CONFIG ====================
    RATE_LIMIT_ENABLED: bool = True
    RATE_LIMIT_DEFAULT: str = "100/minute"
    RATE_LIMIT_STORAGE_URL: Optional[str] = None
    
    @property
    def rate_limit_storage_url(self) -> str:
        """Get rate limit storage URL (defaults to Redis URL)."""
        if self.RATE_LIMIT_STORAGE_URL:
            return self.RATE_LIMIT_STORAGE_URL
        return self.redis_url
    
    # ==================== CORS CONFIG ====================
    CORS_ORIGINS: List[AnyHttpUrl] = []
    
    @validator("CORS_ORIGINS", pre=True)
    def parse_cors_origins(cls, v: Union[str, List[str]]) -> Union[List[str], str]:
        """Parse CORS origins from string or list."""
        if isinstance(v, str) and not v.startswith("["):
            return [i.strip() for i in v.split(",")]
        elif isinstance(v, (list, str)):
            return v
        raise ValueError(v)
    
    # ==================== EMAIL CONFIG ====================
    SMTP_TLS: bool = True
    SMTP_PORT: Optional[int] = None
    SMTP_HOST: Optional[str] = None
    SMTP_USER: Optional[str] = None
    SMTP_PASSWORD: Optional[str] = None
    EMAILS_FROM_EMAIL: Optional[EmailStr] = None
    EMAILS_FROM_NAME: Optional[str] = None
    
    @validator("EMAILS_FROM_NAME")
    def get_project_name(cls, v: Optional[str], values: Dict[str, Any]) -> str:
        """Get email from name from project name if not set."""
        if not v:
            return values.get("PROJECT_NAME", "")
        return v
    
    # ==================== LOGGING CONFIG ====================
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "json"  # json or text
    LOG_FILE: Optional[str] = None
    LOG_ROTATION: str = "1 day"
    LOG_RETENTION: str = "30 days"
    
    # ==================== FILE STORAGE CONFIG ====================
    UPLOAD_DIR: str = "uploads"
    MAX_UPLOAD_SIZE: int = 10 * 1024 * 1024  # 10MB
    ALLOWED_EXTENSIONS: List[str] = [".txt", ".pdf", ".png", ".jpg", ".jpeg", ".gif"]
    
    # ==================== MONITORING CONFIG ====================
    SENTRY_DSN: Optional[str] = None
    METRICS_ENABLED: bool = True
    HEALTH_CHECK_ENABLED: bool = True
    
    # ==================== QUEUE CONFIG ====================
    QUEUE_BROKER_URL: Optional[str] = None
    QUEUE_RESULT_BACKEND: Optional[str] = None
    
    @property
    def celery_broker_url(self) -> str:
        """Get Celery broker URL (defaults to Redis URL)."""
        if self.QUEUE_BROKER_URL:
            return self.QUEUE_BROKER_URL
        return self.redis_url
    
    @property
    def celery_result_backend(self) -> str:
        """Get Celery result backend URL (defaults to Redis URL)."""
        if self.QUEUE_RESULT_BACKEND:
            return self.QUEUE_RESULT_BACKEND
        return self.redis_url
    
    # ==================== AI/ML CONFIG ====================
    OPENAI_API_KEY: Optional[str] = None
    AI_MODEL: str = "gpt-3.5-turbo"
    AI_MAX_TOKENS: int = 8192
    AI_TEMPERATURE: float = 0.7
    
    # ==================== FEATURE FLAGS ====================
    FEATURE_WEBSOCKETS: bool = True
    FEATURE_GRAPHQL: bool = False
    FEATURE_JOBS: bool = True
    FEATURE_NOTIFICATIONS: bool = True
    
    # ==================== PATHS ====================
    BASE_DIR: Path = Path(__file__).resolve().parent.parent.parent
    
    @property
    def upload_dir(self) -> Path:
        """Get upload directory path."""
        return self.BASE_DIR / self.UPLOAD_DIR
    
    @property
    def log_dir(self) -> Path:
        """Get log directory path."""
        return self.BASE_DIR / "logs"
    
    @property
    def temp_dir(self) -> Path:
        """Get temporary directory path."""
        return self.BASE_DIR / "tmp"
    
    # ==================== VALIDATION ====================
    @validator("LOG_LEVEL")
    def validate_log_level(cls, v: str) -> str:
        """Validate log level."""
        allowed = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if v.upper() not in allowed:
            raise ValueError(f"LOG_LEVEL must be one of {allowed}")
        return v.upper()
    
    @validator("LOG_FORMAT")
    def validate_log_format(cls, v: str) -> str:
        """Validate log format."""
        allowed = ["json", "text"]
        if v.lower() not in allowed:
            raise ValueError(f"LOG_FORMAT must be one of {allowed}")
        return v.lower()
    
    # ==================== PYDANTIC CONFIG ====================
    class Config:
        """Pydantic configuration."""
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True
        
        # Allow environment variables with or without APP_ prefix
        @classmethod
        def customise_sources(
            cls,
            init_settings,
            env_settings,
            file_secret_settings,
        ):
            """Customize environment variable sources."""
            # First try with APP_ prefix, then without
            from pydantic.config import EnvSettingsSource, SettingsSourceCallable
            
            class PrefixedEnvSettings(EnvSettingsSource):
                def __call__(self, settings: BaseSettings) -> Dict[str, Any]:
                    data = super().__call__(settings)
                    # Remove APP_ prefix for matching
                    prefixed_data = {}
                    for key, value in data.items():
                        if key.startswith("APP_"):
                            prefixed_data[key[4:]] = value
                    return {**data, **prefixed_data}
            
            return (
                init_settings,
                PrefixedEnvSettings(env_file=cls.env_file, env_file_encoding=cls.env_file_encoding),
                file_secret_settings,
            )


# Global settings instance
settings = Settings()


def get_settings() -> Settings:
    """
    Get settings instance (for dependency injection).
    
    Returns:
        Settings: Application settings instance
    """
    return settings


def is_development() -> bool:
    """
    Check if running in development environment.
    
    Returns:
        bool: True if development environment
    """
    return settings.ENVIRONMENT == "development"


def is_testing() -> bool:
    """
    Check if running in testing environment.
    
    Returns:
        bool: True if testing environment
    """
    return settings.ENVIRONMENT == "testing"


def is_staging() -> bool:
    """
    Check if running in staging environment.
    
    Returns:
        bool: True if staging environment
    """
    return settings.ENVIRONMENT == "staging"


def is_production() -> bool:
    """
    Check if running in production environment.
    
    Returns:
        bool: True if production environment
    """
    return settings.ENVIRONMENT == "production"


def get_database_url() -> str:
    """
    Get database URL as string.
    
    Returns:
        str: Database connection URL
    """
    if settings.SQLALCHEMY_DATABASE_URI:
        return str(settings.SQLALCHEMY_DATABASE_URI)
    raise ValueError("Database URL not configured")


def get_redis_config() -> Dict[str, Any]:
    """
    Get Redis configuration as dictionary.
    
    Returns:
        Dict[str, Any]: Redis configuration
    """
    return {
        "host": settings.REDIS_HOST,
        "port": settings.REDIS_PORT,
        "password": settings.REDIS_PASSWORD,
        "db": settings.REDIS_DB,
        "ssl": settings.REDIS_SSL,
        "url": settings.redis_url,
    }


def get_logging_config() -> Dict[str, Any]:
    """
    Get logging configuration as dictionary.
    
    Returns:
        Dict[str, Any]: Logging configuration
    """
    config = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "default": {
                "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            },
            "json": {
                "()": "pythonjsonlogger.jsonlogger.JsonFormatter",
                "format": "%(asctime)s %(name)s %(levelname)s %(message)s",
            },
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "formatter": "json" if settings.LOG_FORMAT == "json" else "default",
                "level": settings.LOG_LEVEL,
            },
        },
        "root": {
            "handlers": ["console"],
            "level": settings.LOG_LEVEL,
        },
        "loggers": {
            "uvicorn": {
                "handlers": ["console"],
                "level": settings.LOG_LEVEL,
                "propagate": False,
            },
            "uvicorn.access": {
                "handlers": ["console"],
                "level": "INFO",
                "propagate": False,
            },
            "uvicorn.error": {
                "handlers": ["console"],
                "level": settings.LOG_LEVEL,
                "propagate": False,
            },
        },
    }
    
    # Add file handler if LOG_FILE is specified
    if settings.LOG_FILE:
        config["handlers"]["file"] = {
            "class": "logging.handlers.RotatingFileHandler",
            "filename": str(settings.BASE_DIR / settings.LOG_FILE),
            "maxBytes": 10 * 1024 * 1024,  # 10MB
            "backupCount": 5,
            "formatter": "json" if settings.LOG_FORMAT == "json" else "default",
            "level": settings.LOG_LEVEL,
        }
        config["root"]["handlers"].append("file")
    
    return config


def validate_config() -> List[str]:
    """
    Validate configuration and return any warnings.
    
    Returns:
        List[str]: List of configuration warnings
    """
    warnings = []
    
    # Check for default secret key in production
    if is_production() and settings.SECRET_KEY == "changeme":
        warnings.append("SECRET_KEY is set to default value in production!")
    
    # Check for empty database password in production
    if is_production() and not settings.POSTGRES_PASSWORD:
        warnings.append("POSTGRES_PASSWORD is empty in production!")
    
    # Check for debug mode in production
    if is_production() and settings.APP_DEBUG:
        warnings.append("APP_DEBUG is True in production!")
    
    # Check for CORS origins in production
    if is_production() and not settings.CORS_ORIGINS:
        warnings.append("CORS_ORIGINS is empty in production!")
    
    # Check upload directory exists
    if not settings.upload_dir.exists():
        warnings.append(f"Upload directory does not exist: {settings.upload_dir}")
    
    return warnings


# Export commonly used functions and variables
__all__ = [
    "settings",
    "get_settings",
    "is_development",
    "is_testing",
    "is_staging",
    "is_production",
    "get_database_url",
    "get_redis_config",
    "get_logging_config",
    "validate_config",
]
