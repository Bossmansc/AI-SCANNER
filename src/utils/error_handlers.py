"""
Error Handling and Logging Consistency Module

This module provides standardized error handling, logging, and exception management
for high-concurrency applications. It ensures consistent error reporting, structured
logging, and proper error propagation across the system.
"""

import logging
import sys
import traceback
import json
import time
from datetime import datetime
from typing import Any, Dict, Optional, Union, Callable, Type, Tuple, List
from dataclasses import dataclass, asdict
from enum import Enum
import inspect
from contextlib import contextmanager
import asyncio
from functools import wraps

# Configure root logger
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('app_errors.log')
    ]
)

logger = logging.getLogger(__name__)


class ErrorSeverity(Enum):
    """Error severity levels for classification and routing."""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"
    FATAL = "FATAL"


class ErrorCategory(Enum):
    """Categorization of error types for better handling and monitoring."""
    VALIDATION = "VALIDATION"
    AUTHENTICATION = "AUTHENTICATION"
    AUTHORIZATION = "AUTHORIZATION"
    NETWORK = "NETWORK"
    DATABASE = "DATABASE"
    EXTERNAL_SERVICE = "EXTERNAL_SERVICE"
    CONCURRENCY = "CONCURRENCY"
    RESOURCE = "RESOURCE"
    CONFIGURATION = "CONFIGURATION"
    BUSINESS_LOGIC = "BUSINESS_LOGIC"
    UNKNOWN = "UNKNOWN"


@dataclass
class ErrorContext:
    """Structured context information for errors."""
    request_id: Optional[str] = None
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    endpoint: Optional[str] = None
    method: Optional[str] = None
    timestamp: Optional[datetime] = None
    additional_context: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert context to dictionary for serialization."""
        result = {
            'request_id': self.request_id,
            'user_id': self.user_id,
            'session_id': self.session_id,
            'endpoint': self.endpoint,
            'method': self.method,
            'timestamp': self.timestamp.isoformat() if self.timestamp else None,
        }
        if self.additional_context:
            result['additional_context'] = self.additional_context
        return {k: v for k, v in result.items() if v is not None}


@dataclass
class StructuredError:
    """Standardized error structure for consistent error reporting."""
    error_code: str
    message: str
    severity: ErrorSeverity
    category: ErrorCategory
    context: Optional[ErrorContext] = None
    stack_trace: Optional[str] = None
    root_cause: Optional[str] = None
    timestamp: Optional[datetime] = None
    metadata: Optional[Dict[str, Any]] = None
    
    def __post_init__(self):
        """Initialize timestamp if not provided."""
        if self.timestamp is None:
            self.timestamp = datetime.utcnow()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert structured error to dictionary."""
        result = {
            'error_code': self.error_code,
            'message': self.message,
            'severity': self.severity.value,
            'category': self.category.value,
            'timestamp': self.timestamp.isoformat(),
        }
        
        if self.context:
            result['context'] = self.context.to_dict()
        if self.stack_trace:
            result['stack_trace'] = self.stack_trace
        if self.root_cause:
            result['root_cause'] = self.root_cause
        if self.metadata:
            result['metadata'] = self.metadata
            
        return result
    
    def to_json(self) -> str:
        """Convert structured error to JSON string."""
        return json.dumps(self.to_dict(), indent=2, default=str)
    
    def log(self, logger_instance: Optional[logging.Logger] = None):
        """Log the error with appropriate severity."""
        log_func = {
            ErrorSeverity.DEBUG: logger.debug,
            ErrorSeverity.INFO: logger.info,
            ErrorSeverity.WARNING: logger.warning,
            ErrorSeverity.ERROR: logger.error,
            ErrorSeverity.CRITICAL: logger.critical,
            ErrorSeverity.FATAL: logger.critical,
        }.get(self.severity, logger.error)
        
        log_instance = logger_instance or logger
        log_msg = f"[{self.error_code}] {self.message}"
        
        if self.context:
            log_msg += f" | Context: {self.context.to_dict()}"
        
        log_func(log_msg, exc_info=self.stack_trace is not None)
        
        if self.stack_trace and self.severity in [ErrorSeverity.ERROR, ErrorSeverity.CRITICAL, ErrorSeverity.FATAL]:
            log_instance.debug(f"Full stack trace for {self.error_code}:\n{self.stack_trace}")


class BaseAppError(Exception):
    """Base exception class for all application errors."""
    
    def __init__(
        self,
        message: str,
        error_code: str = "APP_ERROR",
        severity: ErrorSeverity = ErrorSeverity.ERROR,
        category: ErrorCategory = ErrorCategory.UNKNOWN,
        context: Optional[ErrorContext] = None,
        root_cause: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        cause: Optional[Exception] = None
    ):
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.severity = severity
        self.category = category
        self.context = context
        self.root_cause = root_cause
        self.metadata = metadata
        self.cause = cause
        self.timestamp = datetime.utcnow()
        self.stack_trace = self._capture_stack_trace()
    
    def _capture_stack_trace(self) -> str:
        """Capture current stack trace."""
        return ''.join(traceback.format_exception(*sys.exc_info())) if sys.exc_info()[0] else traceback.format_stack()
    
    def to_structured_error(self) -> StructuredError:
        """Convert exception to structured error."""
        return StructuredError(
            error_code=self.error_code,
            message=self.message,
            severity=self.severity,
            category=self.category,
            context=self.context,
            stack_trace=self.stack_trace,
            root_cause=self.root_cause,
            timestamp=self.timestamp,
            metadata=self.metadata
        )
    
    def log(self, logger_instance: Optional[logging.Logger] = None):
        """Log the exception as structured error."""
        self.to_structured_error().log(logger_instance)


class ValidationError(BaseAppError):
    """Error for data validation failures."""
    
    def __init__(
        self,
        message: str,
        field: Optional[str] = None,
        value: Any = None,
        validation_rule: Optional[str] = None,
        **kwargs
    ):
        error_code = kwargs.pop('error_code', 'VALIDATION_ERROR')
        metadata = kwargs.get('metadata', {})
        
        if field:
            metadata['field'] = field
        if value is not None:
            metadata['invalid_value'] = str(value)
        if validation_rule:
            metadata['validation_rule'] = validation_rule
        
        kwargs['metadata'] = metadata
        kwargs.setdefault('category', ErrorCategory.VALIDATION)
        
        super().__init__(message, error_code=error_code, **kwargs)


class AuthenticationError(BaseAppError):
    """Error for authentication failures."""
    
    def __init__(self, message: str, auth_method: Optional[str] = None, **kwargs):
        error_code = kwargs.pop('error_code', 'AUTHENTICATION_ERROR')
        metadata = kwargs.get('metadata', {})
        
        if auth_method:
            metadata['auth_method'] = auth_method
        
        kwargs['metadata'] = metadata
        kwargs.setdefault('category', ErrorCategory.AUTHENTICATION)
        kwargs.setdefault('severity', ErrorSeverity.WARNING)
        
        super().__init__(message, error_code=error_code, **kwargs)


class AuthorizationError(BaseAppError):
    """Error for authorization failures."""
    
    def __init__(
        self,
        message: str,
        required_permission: Optional[str] = None,
        user_permissions: Optional[List[str]] = None,
        **kwargs
    ):
        error_code = kwargs.pop('error_code', 'AUTHORIZATION_ERROR')
        metadata = kwargs.get('metadata', {})
        
        if required_permission:
            metadata['required_permission'] = required_permission
        if user_permissions:
            metadata['user_permissions'] = user_permissions
        
        kwargs['metadata'] = metadata
        kwargs.setdefault('category', ErrorCategory.AUTHORIZATION)
        kwargs.setdefault('severity', ErrorSeverity.WARNING)
        
        super().__init__(message, error_code=error_code, **kwargs)


class DatabaseError(BaseAppError):
    """Error for database operation failures."""
    
    def __init__(
        self,
        message: str,
        operation: Optional[str] = None,
        query: Optional[str] = None,
        table: Optional[str] = None,
        **kwargs
    ):
        error_code = kwargs.pop('error_code', 'DATABASE_ERROR')
        metadata = kwargs.get('metadata', {})
        
        if operation:
            metadata['operation'] = operation
        if query:
            metadata['query'] = query
        if table:
            metadata['table'] = table
        
        kwargs['metadata'] = metadata
        kwargs.setdefault('category', ErrorCategory.DATABASE)
        
        super().__init__(message, error_code=error_code, **kwargs)


class ExternalServiceError(BaseAppError):
    """Error for external service failures."""
    
    def __init__(
        self,
        message: str,
        service_name: Optional[str] = None,
        endpoint: Optional[str] = None,
        status_code: Optional[int] = None,
        response_body: Optional[str] = None,
        **kwargs
    ):
        error_code = kwargs.pop('error_code', 'EXTERNAL_SERVICE_ERROR')
        metadata = kwargs.get('metadata', {})
        
        if service_name:
            metadata['service_name'] = service_name
        if endpoint:
            metadata['endpoint'] = endpoint
        if status_code is not None:
            metadata['status_code'] = status_code
        if response_body:
            metadata['response_body'] = response_body
        
        kwargs['metadata'] = metadata
        kwargs.setdefault('category', ErrorCategory.EXTERNAL_SERVICE)
        
        super().__init__(message, error_code=error_code, **kwargs)


class ConcurrencyError(BaseAppError):
    """Error for concurrency-related failures."""
    
    def __init__(
        self,
        message: str,
        resource: Optional[str] = None,
        lock_type: Optional[str] = None,
        timeout: Optional[float] = None,
        **kwargs
    ):
        error_code = kwargs.pop('error_code', 'CONCURRENCY_ERROR')
        metadata = kwargs.get('metadata', {})
        
        if resource:
            metadata['resource'] = resource
        if lock_type:
            metadata['lock_type'] = lock_type
        if timeout is not None:
            metadata['timeout'] = timeout
        
        kwargs['metadata'] = metadata
        kwargs.setdefault('category', ErrorCategory.CONCURRENCY)
        
        super().__init__(message, error_code=error_code, **kwargs)


class ResourceError(BaseAppError):
    """Error for resource-related failures."""
    
    def __init__(
        self,
        message: str,
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        limit: Optional[Any] = None,
        current_usage: Optional[Any] = None,
        **kwargs
    ):
        error_code = kwargs.pop('error_code', 'RESOURCE_ERROR')
        metadata = kwargs.get('metadata', {})
        
        if resource_type:
            metadata['resource_type'] = resource_type
        if resource_id:
            metadata['resource_id'] = resource_id
        if limit is not None:
            metadata['limit'] = str(limit)
        if current_usage is not None:
            metadata['current_usage'] = str(current_usage)
        
        kwargs['metadata'] = metadata
        kwargs.setdefault('category', ErrorCategory.RESOURCE)
        
        super().__init__(message, error_code=error_code, **kwargs)


class ErrorHandler:
    """Central error handler for processing and managing errors."""
    
    def __init__(self, default_logger: Optional[logging.Logger] = None):
        self.logger = default_logger or logger
        self.error_handlers: Dict[Type[Exception], Callable] = {}
        self._register_default_handlers()
    
    def _register_default_handlers(self):
        """Register default error handlers."""
        self.register_handler(BaseAppError, self._handle_app_error)
        self.register_handler(ValidationError, self._handle_validation_error)
        self.register_handler(DatabaseError, self._handle_database_error)
        self.register_handler(ExternalServiceError, self._handle_external_service_error)
        self.register_handler(ConcurrencyError, self._handle_concurrency_error)
    
    def register_handler(
        self,
        exception_type: Type[Exception],
        handler: Callable[[Exception], Any]
    ):
        """Register a custom error handler for a specific exception type."""
        self.error_handlers[exception_type] = handler
    
    def handle_error(self, error: Exception, **context_kwargs) -> StructuredError:
        """
        Handle an error by finding appropriate handler and processing it.
        
        Args:
            error: The exception to handle
            **context_kwargs: Additional context for error
            
        Returns:
            StructuredError: The processed error information
        """
        # Create error context if provided
        context = None
        if context_kwargs:
            context = ErrorContext(**context_kwargs)
        
        # Check if it's already a structured error
        if isinstance(error, BaseAppError):
            if context and not error.context:
                error.context = context
            error.log(self.logger)
            return error.to_structured_error()
        
        # Find appropriate handler
        handler = None
        for exc_type in self.error_handlers:
            if isinstance(error, exc_type):
                handler = self.error_handlers[exc_type]
                break
        
        if handler:
            return handler(error, context)
        else:
            # Default handler for unregistered exceptions
            return self._handle_generic_error(error, context)
    
    def _handle_app_error(self, error: BaseAppError, context: Optional[ErrorContext]) -> StructuredError:
        """Handle BaseAppError instances."""
        if context and not error.context:
            error.context = context
        error.log(self.logger)
        return error.to_structured_error()
    
    def _handle_validation_error(self, error: ValidationError, context: Optional[ErrorContext]) -> StructuredError:
        """Handle ValidationError instances."""
        if context and not error.context:
            error.context = context
        error.log(self.logger)
        return error.to_structured_error()
    
    def _handle_database_error(self, error: DatabaseError, context: Optional[ErrorContext]) -> StructuredError:
        """Handle DatabaseError instances."""
        if context and not error.context:
            error.context = context
        error.log(self.logger)
        
        # Additional database-specific logging
        self.logger.error(f"Database operation failed: {error.operation if hasattr(error, 'operation') else 'Unknown'}")
        return error.to_structured_error()
    
    def _handle_external_service_error(
        self,
        error: ExternalServiceError,
        context: Optional[ErrorContext]
    ) -> StructuredError:
        """Handle ExternalServiceError instances."""
        if context and not error.context:
            error.context = context
        error.log(self.logger)
        
        # Log external service failure details
        if hasattr(error, 'service_name'):
            self.logger.warning(f"External service failure: {error.service_name}")
        
        return error.to_structured_error()
    
    def _handle_concurrency_error(self, error: ConcurrencyError, context: Optional[ErrorContext]) -> StructuredError:
        """Handle ConcurrencyError instances."""
        if context and not error.context:
            error.context = context
        error.log(self.logger)
        
        # Log concurrency issue details
        if hasattr(error, 'resource'):
            self.logger.warning(f"Concurrency issue with resource: {error.resource}")
        
        return error.to_structured_error()
    
    def _handle_generic_error(self, error: Exception, context: Optional[ErrorContext]) -> StructuredError:
        """Handle generic/unregistered exceptions."""
        structured_error = StructuredError(
            error_code="UNHANDLED_ERROR",
            message=str(error),
            severity=ErrorSeverity.ERROR,
            category=ErrorCategory.UNKNOWN,
            context=context,
            stack_trace=traceback.format_exc(),
            timestamp=datetime.utcnow()
        )
        
        structured_error.log(self.logger)
        return structured_error


# Global error handler instance
global_error_handler = ErrorHandler()


def error_handler(func: Callable) -> Callable:
    """
    Decorator for automatic error handling in synchronous functions.
    
    Args:
        func: The function to wrap with error handling
        
    Returns:
        Wrapped function with error handling
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            # Extract context from function signature
            context = ErrorContext(
                endpoint=func.__name__,
                additional_context={
                    'module': func.__module__,
                    'function': func.__name__,
                    'args_count': len(args),
                    'kwargs_keys': list(kwargs.keys())
                }
            )
            
            structured_error = global_error_handler.handle_error(e, **asdict(context))
            
            # Re-raise if it's a critical error
            if structured_error.severity in [ErrorSeverity.CRITICAL, ErrorSeverity.FATAL]:
                raise
            
            # Return error information for non-critical errors
            return {
                'error': structured_error.to_dict(),
                'success': False
            }
    
    return wrapper


def async_error_handler(func: Callable) -> Callable:
    """
    Decorator for automatic error handling in asynchronous functions.
    
    Args:
        func: The async function to wrap