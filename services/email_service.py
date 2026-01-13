"""
Email Service Abstraction Layer with Version Compatibility

This module provides a unified interface for sending emails across multiple
backend providers (SMTP, SendGrid, AWS SES) with automatic fallback,
template rendering, and comprehensive error handling.

Features:
- Multi-provider support with priority-based fallback
- Template engine abstraction (Jinja2, Mako, or plain text)
- Async and sync operation modes
- Attachment handling with MIME encoding
- Rate limiting and retry logic
- Comprehensive logging and metrics
- Email tracking (open/click) when supported
- Batch sending with chunking
"""

import asyncio
import base64
import json
import logging
import mimetypes
import os
import smtplib
import time
from abc import ABC, abstractmethod
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager, contextmanager
from dataclasses import dataclass, field
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union, Callable
from urllib.parse import urlparse

import aiohttp
from pydantic import BaseModel, EmailStr, Field, validator

# Optional imports with graceful degradation
try:
    import jinja2
    JINJA2_AVAILABLE = True
except ImportError:
    JINJA2_AVAILABLE = False
    jinja2 = None

try:
    import boto3
    from botocore.exceptions import ClientError
    BOTO3_AVAILABLE = True
except ImportError:
    BOTO3_AVAILABLE = False
    boto3 = None

try:
    from sendgrid import SendGridAPIClient
    from sendgrid.helpers.mail import (
        Mail, Attachment, Personalization, Content,
        From as SGFrom, To as SGTo, Cc as SGCc, Bcc as SGBcc
    )
    SENDGRID_AVAILABLE = True
except ImportError:
    SENDGRID_AVAILABLE = False
    SendGridAPIClient = None

logger = logging.getLogger(__name__)


class EmailProvider(str, Enum):
    """Supported email providers"""
    SMTP = "smtp"
    SENDGRID = "sendgrid"
    AWS_SES = "aws_ses"
    CONSOLE = "console"  # For development/testing


class TemplateEngine(str, Enum):
    """Supported template engines"""
    JINJA2 = "jinja2"
    MAKO = "mako"
    PLAIN = "plain"
    NONE = "none"


class EmailPriority(str, Enum):
    """Email priority levels"""
    HIGH = "high"
    NORMAL = "normal"
    LOW = "low"


@dataclass
class EmailAttachment:
    """Represents an email attachment"""
    content: bytes
    filename: str
    content_type: Optional[str] = None
    content_id: Optional[str] = None  # For inline images
    
    @classmethod
    def from_file(
        cls,
        filepath: Union[str, Path],
        filename: Optional[str] = None,
        content_id: Optional[str] = None
    ) -> "EmailAttachment":
        """Create attachment from file"""
        path = Path(filepath)
        if not path.exists():
            raise FileNotFoundError(f"Attachment file not found: {filepath}")
        
        with open(path, "rb") as f:
            content = f.read()
        
        if filename is None:
            filename = path.name
        
        # Guess content type
        content_type, _ = mimetypes.guess_type(str(path))
        
        return cls(
            content=content,
            filename=filename,
            content_type=content_type,
            content_id=content_id
        )
    
    @classmethod
    def from_base64(
        cls,
        base64_content: str,
        filename: str,
        content_type: Optional[str] = None,
        content_id: Optional[str] = None
    ) -> "EmailAttachment":
        """Create attachment from base64 encoded string"""
        content = base64.b64decode(base64_content)
        return cls(
            content=content,
            filename=filename,
            content_type=content_type,
            content_id=content_id
        )


class EmailAddress(BaseModel):
    """Validated email address with optional name"""
    email: EmailStr
    name: Optional[str] = None
    
    def formatted(self) -> str:
        """Format as 'Name <email@example.com>' or just email"""
        if self.name:
            return f"{self.name} <{self.email}>"
        return self.email
    
    @classmethod
    def parse(cls, address: str) -> "EmailAddress":
        """Parse email address from string"""
        from email.utils import parseaddr
        name, email = parseaddr(address)
        if not email:
            raise ValueError(f"Invalid email address: {address}")
        return cls(email=email, name=name if name else None)


class EmailMessage(BaseModel):
    """Complete email message definition"""
    to: List[EmailAddress]
    subject: str
    body: str
    html_body: Optional[str] = None
    from_addr: EmailAddress
    cc: List[EmailAddress] = Field(default_factory=list)
    bcc: List[EmailAddress] = Field(default_factory=list)
    reply_to: Optional[EmailAddress] = None
    attachments: List[EmailAttachment] = Field(default_factory=list)
    priority: EmailPriority = EmailPriority.NORMAL
    headers: Dict[str, str] = Field(default_factory=dict)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    template_id: Optional[str] = None
    template_data: Dict[str, Any] = Field(default_factory=dict)
    
    class Config:
        arbitrary_types_allowed = True
    
    @validator('to', 'cc', 'bcc')
    def validate_recipients(cls, v):
        """Ensure at least one recipient"""
        if not v:
            raise ValueError("Recipient list cannot be empty")
        return v
    
    def add_attachment(self, attachment: EmailAttachment) -> None:
        """Add attachment to message"""
        self.attachments.append(attachment)
    
    def add_header(self, key: str, value: str) -> None:
        """Add custom header"""
        self.headers[key] = value


class EmailTemplate(BaseModel):
    """Email template definition"""
    name: str
    subject: str
    body_template: str
    html_template: Optional[str] = None
    engine: TemplateEngine = TemplateEngine.JINJA2
    variables: List[str] = Field(default_factory=list)
    
    def render(
        self,
        context: Dict[str, Any],
        engine_override: Optional[TemplateEngine] = None
    ) -> Tuple[str, Optional[str]]:
        """Render template with context"""
        engine = engine_override or self.engine
        
        if engine == TemplateEngine.PLAIN or engine == TemplateEngine.NONE:
            return self.body_template, self.html_template
        
        if engine == TemplateEngine.JINJA2:
            if not JINJA2_AVAILABLE:
                raise RuntimeError("Jinja2 is not installed")
            
            # Create Jinja2 environment
            from jinja2 import Environment, BaseLoader
            env = Environment(loader=BaseLoader())
            
            # Render templates
            body_template = env.from_string(self.body_template)
            body = body_template.render(**context)
            
            html = None
            if self.html_template:
                html_template = env.from_string(self.html_template)
                html = html_template.render(**context)
            
            return body, html
        
        elif engine == TemplateEngine.MAKO:
            try:
                from mako.template import Template
            except ImportError:
                raise RuntimeError("Mako is not installed")
            
            body_template = Template(self.body_template)
            body = body_template.render(**context)
            
            html = None
            if self.html_template:
                html_template = Template(self.html_template)
                html = html_template.render(**context)
            
            return body, html
        
        else:
            raise ValueError(f"Unsupported template engine: {engine}")


class ProviderConfig(BaseModel):
    """Base configuration for email providers"""
    provider: EmailProvider
    priority: int = 1  # Lower number = higher priority
    enabled: bool = True
    timeout: int = 30
    max_retries: int = 3
    retry_delay: float = 1.0


class SMTPConfig(ProviderConfig):
    """SMTP provider configuration"""
    provider: EmailProvider = EmailProvider.SMTP
    host: str = "localhost"
    port: int = 587
    username: Optional[str] = None
    password: Optional[str] = None
    use_tls: bool = True
    use_ssl: bool = False
    from_addr: Optional[EmailAddress] = None
    
    @validator('port')
    def validate_port(cls, v):
        if not 1 <= v <= 65535:
            raise ValueError("Port must be between 1 and 65535")
        return v


class SendGridConfig(ProviderConfig):
    """SendGrid provider configuration"""
    provider: EmailProvider = EmailProvider.SENDGRID
    api_key: str
    from_addr: Optional[EmailAddress] = None
    track_opens: bool = False
    track_clicks: bool = False
    sandbox_mode: bool = False


class SESConfig(ProviderConfig):
    """AWS SES provider configuration"""
    provider: EmailProvider = EmailProvider.AWS_SES
    aws_access_key_id: Optional[str] = None
    aws_secret_access_key: Optional[str] = None
    aws_region: str = "us-east-1"
    from_addr: Optional[EmailAddress] = None
    configuration_set: Optional[str] = None
    
    @validator('aws_region')
    def validate_region(cls, v):
        valid_regions = [
            'us-east-1', 'us-east-2', 'us-west-1', 'us-west-2',
            'eu-west-1', 'eu-west-2', 'eu-west-3', 'eu-central-1',
            'ap-south-1', 'ap-northeast-1', 'ap-northeast-2',
            'ap-southeast-1', 'ap-southeast-2', 'ca-central-1',
            'sa-east-1'
        ]
        if v not in valid_regions:
            logger.warning(f"Region {v} may not support SES")
        return v


class ConsoleConfig(ProviderConfig):
    """Console provider configuration (for development)"""
    provider: EmailProvider = EmailProvider.CONSOLE
    print_to_stdout: bool = True
    save_to_file: Optional[str] = None
    format_output: bool = True


class EmailServiceConfig(BaseModel):
    """Complete email service configuration"""
    providers: List[ProviderConfig] = Field(default_factory=list)
    default_from: EmailAddress
    template_dir: Optional[str] = None
    default_template_engine: TemplateEngine = TemplateEngine.JINJA2
    enable_async: bool = True
    max_workers: int = 10
    batch_size: int = 50
    rate_limit_per_minute: int = 100
    enable_metrics: bool = False
    metrics_prefix: str = "email_service"
    
    @validator('providers')
    def validate_providers(cls, v):
        if not v:
            raise ValueError("At least one provider must be configured")
        return sorted(v, key=lambda x: x.priority)
    
    def get_provider_config(self, provider: EmailProvider) -> Optional[ProviderConfig]:
        """Get configuration for specific provider"""
        for config in self.providers:
            if config.provider == provider and config.enabled:
                return config
        return None


class EmailMetrics:
    """Metrics collection for email service"""
    
    def __init__(self, prefix: str = "email_service"):
        self.prefix = prefix
        self.counters = defaultdict(int)
        self.timers = defaultdict(list)
        self.gauges = defaultdict(float)
    
    def increment(self, metric: str, value: int = 1, tags: Optional[Dict[str, str]] = None):
        """Increment counter metric"""
        key = self._format_metric(metric, tags)
        self.counters[key] += value
        logger.debug(f"Metric increment: {key} = {self.counters[key]}")
    
    def timer(self, metric: str, duration: float, tags: Optional[Dict[str, str]] = None):
        """Record timing metric"""
        key = self._format_metric(metric, tags)
        self.timers[key].append(duration)
        logger.debug(f"Metric timer: {key} = {duration:.3f}s")
    
    def gauge(self, metric: str, value: float, tags: Optional[Dict[str, str]] = None):
        """Set gauge metric"""
        key = self._format_metric(metric, tags)
        self.gauges[key] = value
        logger.debug(f"Metric gauge: {key} = {value}")
    
    def _format_metric(self, metric: str, tags: Optional[Dict[str, str]] = None) -> str:
        """Format metric name with tags"""
        if tags:
            tag_str = ",".join(f"{k}={v}" for k, v in sorted(tags.items()))
            return f"{self.prefix}.{metric}[{tag_str}]"
        return f"{self.prefix}.{metric}"
    
    def get_stats(self) -> Dict[str, Any]:
        """Get all metrics as dictionary"""
        return {
            "counters": dict(self.counters),
            "timers": {
                k: {
                    "count": len(v),
                    "min": min(v) if v else 0,
                    "max": max(v) if v else 0,
                    "avg": sum(v) / len(v) if v else 0,
                    "p95": sorted(v)[int(len(v) * 0.95)] if v else 0
                }
                for k, v in self.timers.items()
            },
            "gauges": dict(self.gauges)
        }


class BaseEmailProvider(ABC):
    """Abstract base class for email providers"""
    
    def __init__(self, config: ProviderConfig, metrics: Optional[EmailMetrics] = None):
        self.config = config
        self.metrics = metrics
        self.retry_count = 0
        self.last_error = None
    
    @abstractmethod
    def send(self, message: EmailMessage) -> bool:
        """Send email synchronously"""
        pass
    
    @abstractmethod
    async def send_async(self, message: EmailMessage) -> bool:
        """Send email asynchronously"""
        pass
    
    def _record_metrics(self, success: bool, duration: float, message: EmailMessage):
        """Record metrics for send operation"""
        if self.metrics:
            tags = {
                "provider": self.config.provider.value,
                "success": str(success).lower(),
                "priority": message.priority.value
            }
            self.metrics.timer("send_duration", duration, tags)
            self.metrics.increment("send_total", 1, tags)
            if success:
                self.metrics.increment("send_success", 1, tags)
            else:
                self.metrics.increment("send_failure", 1, tags)
    
    def _should_retry(self, error: Exception) -> bool:
        """Determine if operation should be retried"""
        self.retry_count += 1
        self.last_error = error
        
        if self.retry_count >= self.config.max_retries:
            return False
        
        # Retry on network errors, timeouts, and rate limits
        retryable_errors = (
            ConnectionError,
            TimeoutError,
            smtplib.SMTPException,
            aiohttp.ClientError,
        )
        
        if isinstance(error, retryable_errors):
            return True
        
        # Check error message for retryable conditions
        error_msg = str(error).lower()
        retryable_phrases = [
            "timeout", "connection", "rate limit", "throttle",
            "temporary", "retry", "busy", "queue"
        ]
        
        return any(phrase in error_msg for phrase in retryable_phrases)


class SMTPProvider(BaseEmailProvider):
    """SMTP email provider"""
    
    def __init__(self, config: SMTPConfig, metrics: Optional[EmailMetrics] = None):
        if not isinstance(config, SMTPConfig):
            raise TypeError("config must be SMTPConfig")
        super().__init__(config, metrics)
        self.config: SMTPConfig = config
    
    def _create_mime_message(self, message: EmailMessage) -> MIMEMultipart:
        """Create MIME message from EmailMessage"""
        # Use provider's from_addr if specified, otherwise use message's
        from_addr = self.config.from_addr or message.from_addr
        
        # Create message
        mime_msg = MIMEMultipart('mixed')
        mime_msg['Subject'] = message.subject
        mime_msg['From'] = from_addr.formatted()
        mime_msg['To'] = ', '.join(addr.formatted() for addr in message.to)
        
        if message.cc:
            mime_msg['Cc'] = ', '.join(addr.formatted() for addr in message.cc)
        
        if message.bcc:
            mime_msg['Bcc'] = ', '.join(addr.formatted() for addr in message.bcc)
        
        if message.reply_to:
            mime_msg['Reply-To'] = message.reply_to.formatted()
        
        # Add custom headers
        for key, value in message.headers.items():
            mime_msg[key] = value
        
        # Add priority header
        if message.priority == EmailPriority.HIGH:
            mime_msg['X-Priority'] = '1'
            mime_msg['Importance'] = 'high'
        elif message.priority == EmailPriority.LOW:
            mime_msg['X-Priority'] = '5'
            mime_msg['Importance'] = 'low'
        
        # Create alternative part for text and HTML
        if message.html_body:
            alternative = MIMEMultipart('alternative')
            mime_msg.attach(alternative)
            
            # Add text part
            text_part = MIMEText(message.body, 'plain', 'utf-8')
           