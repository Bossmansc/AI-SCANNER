"""
Email Configuration Module for FastAPI Mail

This module provides a robust, version-aware email configuration system with:
1. Support for both FastAPI-Mail 0.3.3+ and legacy 0.2.0+ versions
2. Environment-based configuration with validation
3. Connection pooling and retry mechanisms
4. Template support for HTML emails
5. Comprehensive error handling and logging
"""

import os
import sys
import logging
from typing import Dict, Any, Optional, List, Union, Literal
from enum import Enum
from pydantic import BaseModel, Field, validator, root_validator
from pydantic_settings import BaseSettings
from functools import lru_cache

# Configure logging
logger = logging.getLogger(__name__)


class EmailBackend(str, Enum):
    """Supported email backends"""
    SMTP = "smtp"
    CONSOLE = "console"  # For development/testing
    FILE = "file"  # Write emails to files
    NULL = "null"  # Discard emails (testing)


class EmailSecurity(str, Enum):
    """SSL/TLS security options"""
    NONE = "none"
    SSL = "ssl"
    TLS = "tls"
    STARTTLS = "starttls"


class EmailTemplateConfig(BaseModel):
    """Configuration for email templates"""
    folder: str = Field(default="templates/email", description="Template folder path")
    jinja_extensions: List[str] = Field(
        default=["jinja2.ext.i18n", "jinja2.ext.do"],
        description="Jinja2 extensions to load"
    )
    auto_reload: bool = Field(default=False, description="Reload templates on change")
    encoding: str = Field(default="utf-8", description="Template file encoding")


class EmailConnectionPoolConfig(BaseModel):
    """Connection pooling configuration"""
    enabled: bool = Field(default=True, description="Enable connection pooling")
    max_connections: int = Field(default=10, ge=1, le=100, description="Max pool size")
    idle_timeout: int = Field(default=300, ge=60, description="Idle timeout in seconds")
    recycle_interval: int = Field(default=3600, ge=300, description="Recycle interval")


class EmailRetryConfig(BaseModel):
    """Retry configuration for failed email sends"""
    enabled: bool = Field(default=True, description="Enable retry mechanism")
    max_attempts: int = Field(default=3, ge=1, le=10, description="Max retry attempts")
    initial_delay: float = Field(default=1.0, ge=0.1, description="Initial delay in seconds")
    backoff_factor: float = Field(default=2.0, ge=1.0, le=5.0, description="Exponential backoff factor")
    max_delay: float = Field(default=60.0, ge=1.0, description="Maximum delay in seconds")


class EmailConfig(BaseSettings):
    """
    Main email configuration class with environment variable support.
    Uses pydantic-settings for automatic environment variable loading.
    """
    
    # Backend configuration
    backend: EmailBackend = Field(default=EmailBackend.SMTP, description="Email backend to use")
    
    # SMTP Configuration
    smtp_host: str = Field(default="localhost", description="SMTP server hostname")
    smtp_port: int = Field(default=587, ge=1, le=65535, description="SMTP server port")
    smtp_user: str = Field(default="", description="SMTP username")
    smtp_password: str = Field(default="", description="SMTP password")
    smtp_security: EmailSecurity = Field(default=EmailSecurity.TLS, description="Security protocol")
    
    # Sender configuration
    default_sender_name: str = Field(default="System", description="Default sender name")
    default_sender_email: str = Field(default="noreply@example.com", description="Default sender email")
    
    # Connection settings
    timeout: int = Field(default=30, ge=5, le=300, description="Connection timeout in seconds")
    use_tls: bool = Field(default=True, description="Use TLS (legacy option)")
    use_ssl: bool = Field(default=False, description="Use SSL (legacy option)")
    validate_certs: bool = Field(default=True, description="Validate SSL certificates")
    
    # Template configuration
    templates: EmailTemplateConfig = Field(default_factory=EmailTemplateConfig)
    
    # Advanced features
    connection_pool: EmailConnectionPoolConfig = Field(default_factory=EmailConnectionPoolConfig)
    retry_config: EmailRetryConfig = Field(default_factory=EmailRetryConfig)
    
    # Development/testing
    suppress_send: bool = Field(default=False, description="Suppress actual email sending")
    debug_level: int = Field(default=0, ge=0, le=2, description="Debug level: 0=off, 1=basic, 2=verbose")
    
    # FastAPI-Mail version compatibility
    fastapi_mail_version: str = Field(default="0.3.3", description="FastAPI-Mail version")
    
    class Config:
        env_prefix = "EMAIL_"
        env_nested_delimiter = "__"
        case_sensitive = False
        extra = "ignore"
    
    @validator("smtp_password", pre=True)
    def validate_password(cls, v):
        """Mask password in logs"""
        if v and len(v) > 0:
            logger.debug("Email password configured (masked for security)")
            return v
        return v
    
    @root_validator
    def validate_security_settings(cls, values):
        """Validate and normalize security settings"""
        security = values.get("smtp_security")
        use_tls = values.get("use_tls")
        use_ssl = values.get("use_ssl")
        
        # Backward compatibility: map legacy flags to new security enum
        if security == EmailSecurity.NONE:
            values["use_tls"] = False
            values["use_ssl"] = False
        elif security == EmailSecurity.SSL:
            values["use_tls"] = False
            values["use_ssl"] = True
        elif security == EmailSecurity.TLS:
            values["use_tls"] = True
            values["use_ssl"] = False
        elif security == EmailSecurity.STARTTLS:
            values["use_tls"] = True
            values["use_ssl"] = False
        
        # If security is not set but legacy flags are, infer security
        elif not security and (use_tls or use_ssl):
            if use_ssl:
                values["smtp_security"] = EmailSecurity.SSL
            elif use_tls:
                values["smtp_security"] = EmailSecurity.TLS
        
        return values
    
    @property
    def sender_tuple(self) -> tuple:
        """Get sender as (name, email) tuple for FastAPI-Mail"""
        return (self.default_sender_name, self.default_sender_email)
    
    @property
    def is_secure_connection(self) -> bool:
        """Check if connection uses SSL/TLS"""
        return self.smtp_security in [EmailSecurity.SSL, EmailSecurity.TLS, EmailSecurity.STARTTLS]
    
    @property
    def supports_connection_pooling(self) -> bool:
        """Check if current FastAPI-Mail version supports connection pooling"""
        try:
            from packaging import version
            return version.parse(self.fastapi_mail_version) >= version.parse("0.3.3")
        except ImportError:
            # If packaging not available, assume no pooling for safety
            return False
    
    def get_fastapi_mail_config(self) -> Dict[str, Any]:
        """
        Generate configuration dictionary compatible with FastAPI-Mail.
        Handles version differences between 0.2.x and 0.3.x.
        """
        config = {
            "MAIL_USERNAME": self.smtp_user,
            "MAIL_PASSWORD": self.smtp_password,
            "MAIL_FROM": self.sender_tuple,
            "MAIL_PORT": self.smtp_port,
            "MAIL_SERVER": self.smtp_host,
            "MAIL_FROM_NAME": self.default_sender_name,
            "MAIL_STARTTLS": self.smtp_security == EmailSecurity.STARTTLS,
            "MAIL_SSL_TLS": self.smtp_security == EmailSecurity.SSL,
            "MAIL_USE_CREDENTIALS": bool(self.smtp_user and self.smtp_password),
            "MAIL_VALIDATE_CERTS": self.validate_certs,
            "USE_CREDENTIALS": bool(self.smtp_user and self.smtp_password),
        }
        
        # Version-specific adjustments
        try:
            from packaging import version
            current_version = version.parse(self.fastapi_mail_version)
            
            if current_version >= version.parse("0.3.0"):
                # 0.3.x uses different field names
                config.update({
                    "MAIL_TLS": self.smtp_security == EmailSecurity.TLS,
                    "MAIL_SSL": self.smtp_security == EmailSecurity.SSL,
                })
                
                # Remove old field names to avoid conflicts
                config.pop("MAIL_STARTTLS", None)
                config.pop("MAIL_SSL_TLS", None)
                
            elif current_version >= version.parse("0.2.0"):
                # 0.2.x compatibility
                config.update({
                    "MAIL_TLS": self.use_tls,
                    "MAIL_SSL": self.use_ssl,
                })
        
        except ImportError:
            # Fallback to conservative defaults
            logger.warning("packaging module not found, using conservative email config")
        
        # Add template configuration if templates are enabled
        if os.path.exists(self.templates.folder):
            config["MAIL_TEMPLATE_FOLDER"] = self.templates.folder
        
        # Filter out empty values
        return {k: v for k, v in config.items() if v not in (None, "", False) or k in ["MAIL_TLS", "MAIL_SSL"]}
    
    def get_connection_config(self) -> Dict[str, Any]:
        """Get connection-specific configuration"""
        return {
            "host": self.smtp_host,
            "port": self.smtp_port,
            "username": self.smtp_user,
            "password": self.smtp_password,
            "use_tls": self.smtp_security in [EmailSecurity.TLS, EmailSecurity.STARTTLS],
            "use_ssl": self.smtp_security == EmailSecurity.SSL,
            "timeout": self.timeout,
            "validate_certs": self.validate_certs,
        }
    
    def validate_configuration(self) -> List[str]:
        """
        Validate configuration and return list of warnings/errors.
        Returns empty list if configuration is valid.
        """
        warnings = []
        
        # Check SMTP configuration if using SMTP backend
        if self.backend == EmailBackend.SMTP:
            if not self.smtp_host:
                warnings.append("SMTP host is not configured")
            
            if self.smtp_security == EmailSecurity.SSL and self.smtp_port != 465:
                warnings.append(f"SSL typically uses port 465, but configured port is {self.smtp_port}")
            
            if self.smtp_security == EmailSecurity.STARTTLS and self.smtp_port != 587:
                warnings.append(f"STARTTLS typically uses port 587, but configured port is {self.smtp_port}")
        
        # Check template folder
        if not os.path.exists(self.templates.folder):
            warnings.append(f"Template folder '{self.templates.folder}' does not exist")
        
        # Check FastAPI-Mail version compatibility
        try:
            from packaging import version
            current_version = version.parse(self.fastapi_mail_version)
            
            if current_version < version.parse("0.2.0"):
                warnings.append(f"FastAPI-Mail version {self.fastapi_mail_version} is very old, consider upgrading")
            
            if current_version >= version.parse("0.3.0") and self.connection_pool.enabled:
                if not self.supports_connection_pooling:
                    warnings.append("Connection pooling requires FastAPI-Mail 0.3.3+")
        
        except ImportError:
            warnings.append("Cannot validate FastAPI-Mail version without 'packaging' module")
        
        return warnings


class EmailConfigManager:
    """
    Manager class for email configuration with caching and runtime adjustments.
    """
    
    def __init__(self):
        self._config: Optional[EmailConfig] = None
        self._config_cache: Dict[str, EmailConfig] = {}
        self._override_settings: Dict[str, Any] = {}
    
    def load_config(self, env_file: Optional[str] = None, **overrides) -> EmailConfig:
        """
        Load configuration from environment variables and optional .env file.
        
        Args:
            env_file: Path to .env file
            **overrides: Configuration overrides
        
        Returns:
            EmailConfig instance
        """
        cache_key = f"{env_file}:{str(sorted(overrides.items()))}"
        
        if cache_key in self._config_cache:
            return self._config_cache[cache_key]
        
        # Load base configuration
        config_kwargs = {}
        if env_file:
            config_kwargs["_env_file"] = env_file
        
        config = EmailConfig(**config_kwargs)
        
        # Apply overrides
        for key, value in overrides.items():
            if hasattr(config, key):
                setattr(config, key, value)
        
        # Apply runtime overrides
        for key, value in self._override_settings.items():
            if hasattr(config, key):
                setattr(config, key, value)
        
        # Validate configuration
        warnings = config.validate_configuration()
        if warnings:
            logger.warning("Email configuration warnings:")
            for warning in warnings:
                logger.warning(f"  - {warning}")
        
        self._config_cache[cache_key] = config
        self._config = config
        
        logger.info(f"Email configuration loaded for backend: {config.backend.value}")
        if config.backend == EmailBackend.SMTP:
            logger.info(f"SMTP Server: {config.smtp_host}:{config.smtp_port}")
            logger.info(f"Security: {config.smtp_security.value}")
        
        return config
    
    def get_config(self) -> EmailConfig:
        """Get current configuration, loading default if not already loaded"""
        if self._config is None:
            self._config = self.load_config()
        return self._config
    
    def update_config(self, **settings):
        """
        Update configuration at runtime.
        
        Args:
            **settings: Configuration settings to update
        """
        if self._config is None:
            self._config = self.load_config()
        
        for key, value in settings.items():
            if hasattr(self._config, key):
                setattr(self._config, key, value)
                logger.info(f"Updated email configuration: {key} = {value}")
            else:
                logger.warning(f"Ignoring unknown email configuration key: {key}")
        
        # Clear cache since configuration changed
        self._config_cache.clear()
    
    def set_override(self, key: str, value: Any):
        """
        Set a persistent override that applies to all future config loads.
        
        Args:
            key: Configuration key
            value: Value to override with
        """
        self._override_settings[key] = value
        logger.info(f"Set persistent email config override: {key} = {value}")
    
    def clear_overrides(self):
        """Clear all persistent overrides"""
        self._override_settings.clear()
        self._config_cache.clear()
        logger.info("Cleared all email configuration overrides")
    
    def get_fastapi_mail_config_dict(self) -> Dict[str, Any]:
        """Get FastAPI-Mail compatible configuration dictionary"""
        config = self.get_config()
        return config.get_fastapi_mail_config()
    
    def test_connection(self) -> bool:
        """
        Test email connection configuration.
        
        Returns:
            True if connection test passes, False otherwise
        """
        config = self.get_config()
        
        if config.backend != EmailBackend.SMTP:
            logger.info(f"Backend {config.backend.value} doesn't require connection test")
            return True
        
        if config.suppress_send:
            logger.info("Email sending suppressed, skipping connection test")
            return True
        
        try:
            import smtplib
            import socket
            
            logger.info(f"Testing SMTP connection to {config.smtp_host}:{config.smtp_port}")
            
            # Create SMTP connection based on security settings
            if config.smtp_security == EmailSecurity.SSL:
                server = smtplib.SMTP_SSL(
                    host=config.smtp_host,
                    port=config.smtp_port,
                    timeout=config.timeout
                )
            else:
                server = smtplib.SMTP(
                    host=config.smtp_host,
                    port=config.smtp_port,
                    timeout=config.timeout
                )
            
            # Enable debug if requested
            if config.debug_level >= 2:
                server.set_debuglevel(1)
            
            # Start TLS if needed
            if config.smtp_security == EmailSecurity.STARTTLS:
                server.starttls()
            
            # Login if credentials provided
            if config.smtp_user and config.smtp_password:
                server.login(config.smtp_user, config.smtp_password)
            
            server.quit()
            logger.info("SMTP connection test passed")
            return True
            
        except (smtplib.SMTPException, socket.error, socket.timeout) as e:
            logger.error(f"SMTP connection test failed: {str(e)}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error during connection test: {str(e)}")
            return False


# Global configuration manager instance
_config_manager: Optional[EmailConfigManager] = None


def get_email_config_manager() -> EmailConfigManager:
    """
    Get or create the global email configuration manager.
    
    Returns:
        EmailConfigManager instance
    """
    global _config_manager
    if _config_manager is None:
        _config_manager = EmailConfigManager()
    return _config_manager


@lru_cache(maxsize=1)
def get_email_config(env_file: Optional[str] = None, **overrides) -> EmailConfig:
    """
    Get email configuration with caching.
    
    Args:
        env_file: Path to .env file
        **overrides: Configuration overrides
    
    Returns:
        EmailConfig instance
    """
    manager = get