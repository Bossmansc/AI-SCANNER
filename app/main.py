"""
Main FastAPI application entry point with ASGI app definition.
This module serves as the central hub for the application, configuring
the FastAPI instance, middleware, routing, and lifecycle events.
"""

import asyncio
import logging
import os
import sys
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any, Dict, List, Optional

import sentry_sdk
from fastapi import FastAPI, Request, Response, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from prometheus_fastapi_instrumentator import Instrumentator
from sentry_sdk.integrations.asgi import SentryAsgiMiddleware
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.starlette import StarletteIntegration

from app.api.v1.api import api_router as v1_router
from app.core.config import settings
from app.core.exceptions import (
    AppException,
    BadRequestException,
    ForbiddenException,
    NotFoundException,
    UnauthorizedException,
    ValidationException,
)
from app.core.logging import configure_logging
from app.core.metrics import metrics_router
from app.core.version import get_version
from app.middleware.request_id import RequestIDMiddleware
from app.middleware.request_logging import RequestLoggingMiddleware
from app.middleware.response_time import ResponseTimeMiddleware

# Configure logging
configure_logging()
logger = logging.getLogger(__name__)

# Configure Sentry if DSN is provided
if settings.SENTRY_DSN:
    sentry_sdk.init(
        dsn=settings.SENTRY_DSN,
        environment=settings.ENVIRONMENT,
        release=get_version(),
        integrations=[
            FastApiIntegration(),
            StarletteIntegration(),
        ],
        traces_sample_rate=settings.SENTRY_TRACES_SAMPLE_RATE,
        profiles_sample_rate=settings.SENTRY_PROFILES_SAMPLE_RATE,
        send_default_pii=settings.SENTRY_SEND_DEFAULT_PII,
    )
    logger.info("Sentry SDK initialized for error tracking")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan context manager for application startup and shutdown events.
    
    Args:
        app: The FastAPI application instance.
    
    Yields:
        Control to the application runtime.
    """
    startup_time = datetime.utcnow()
    
    # Startup logic
    logger.info("Application starting up...")
    logger.info(f"Environment: {settings.ENVIRONMENT}")
    logger.info(f"Debug mode: {settings.DEBUG}")
    logger.info(f"Version: {get_version()}")
    
    # Initialize database connections, caches, etc.
    # Example: await database.connect()
    
    # Register startup complete
    app.state.startup_time = startup_time
    app.state.ready = True
    
    logger.info("Application startup complete")
    
    yield
    
    # Shutdown logic
    logger.info("Application shutting down...")
    
    # Clean up resources
    # Example: await database.disconnect()
    
    logger.info("Application shutdown complete")


def create_application() -> FastAPI:
    """
    Create and configure the FastAPI application instance.
    
    Returns:
        Configured FastAPI application instance.
    """
    # Determine application title and description
    app_title = settings.PROJECT_NAME
    app_description = f"""
    {settings.PROJECT_NAME} API
    
    Environment: {settings.ENVIRONMENT}
    Version: {get_version()}
    
    This API provides the backend services for the application.
    """
    
    # Create FastAPI instance with lifespan
    app = FastAPI(
        title=app_title,
        description=app_description,
        version=get_version(),
        docs_url="/docs" if settings.DOCS_ENABLED else None,
        redoc_url="/redoc" if settings.DOCS_ENABLED else None,
        openapi_url="/openapi.json" if settings.OPENAPI_ENABLED else None,
        lifespan=lifespan,
    )
    
    # Add application state
    app.state.settings = settings
    app.state.version = get_version()
    app.state.startup_time = None
    app.state.ready = False
    
    # Configure middleware
    configure_middleware(app)
    
    # Configure exception handlers
    configure_exception_handlers(app)
    
    # Configure routing
    configure_routing(app)
    
    # Configure health checks
    configure_health_checks(app)
    
    # Configure metrics if enabled
    if settings.METRICS_ENABLED:
        configure_metrics(app)
    
    return app


def configure_middleware(app: FastAPI) -> None:
    """
    Configure middleware for the FastAPI application.
    
    Args:
        app: FastAPI application instance.
    """
    # CORS middleware
    if settings.CORS_ORIGINS:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.CORS_ORIGINS,
            allow_credentials=settings.CORS_ALLOW_CREDENTIALS,
            allow_methods=settings.CORS_ALLOW_METHODS,
            allow_headers=settings.CORS_ALLOW_HEADERS,
            expose_headers=settings.CORS_EXPOSE_HEADERS,
            max_age=settings.CORS_MAX_AGE,
        )
        logger.info(f"CORS configured with origins: {settings.CORS_ORIGINS}")
    
    # Trusted Host middleware
    if settings.ALLOWED_HOSTS:
        app.add_middleware(
            TrustedHostMiddleware,
            allowed_hosts=settings.ALLOWED_HOSTS,
        )
        logger.info(f"TrustedHost middleware configured with hosts: {settings.ALLOWED_HOSTS}")
    
    # GZip middleware for responses
    if settings.GZIP_ENABLED:
        app.add_middleware(
            GZipMiddleware,
            minimum_size=settings.GZIP_MINIMUM_SIZE,
        )
        logger.info("GZip middleware enabled")
    
    # Custom middleware
    app.add_middleware(RequestIDMiddleware)
    app.add_middleware(RequestLoggingMiddleware)
    app.add_middleware(ResponseTimeMiddleware)
    
    # Sentry middleware (if enabled)
    if settings.SENTRY_DSN:
        app.add_middleware(SentryAsgiMiddleware)
        logger.info("Sentry ASGI middleware enabled")
    
    logger.info("Middleware configuration complete")


def configure_exception_handlers(app: FastAPI) -> None:
    """
    Configure global exception handlers for the application.
    
    Args:
        app: FastAPI application instance.
    """
    
    @app.exception_handler(AppException)
    async def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
        """
        Handle custom application exceptions.
        
        Args:
            request: The incoming request.
            exc: The application exception.
            
        Returns:
            JSONResponse with error details.
        """
        logger.error(
            f"Application exception: {exc.__class__.__name__} - {exc.message}",
            extra={
                "request_id": request.state.request_id,
                "status_code": exc.status_code,
                "error_code": exc.error_code,
            },
            exc_info=exc if settings.DEBUG else None,
        )
        
        response_data = {
            "error": {
                "code": exc.error_code,
                "message": exc.message,
                "details": exc.details,
            }
        }
        
        # Include traceback in debug mode
        if settings.DEBUG and exc.__cause__:
            import traceback
            response_data["error"]["traceback"] = traceback.format_exception(
                type(exc.__cause__), exc.__cause__, exc.__cause__.__traceback__
            )
        
        return JSONResponse(
            status_code=exc.status_code,
            content=response_data,
            headers=exc.headers,
        )
    
    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        """
        Handle FastAPI request validation errors.
        
        Args:
            request: The incoming request.
            exc: The validation exception.
            
        Returns:
            JSONResponse with validation error details.
        """
        logger.warning(
            f"Request validation error: {exc}",
            extra={"request_id": request.state.request_id},
        )
        
        # Format validation errors
        errors = []
        for error in exc.errors():
            error_detail = {
                "loc": error["loc"],
                "msg": error["msg"],
                "type": error["type"],
            }
            if "ctx" in error:
                error_detail["ctx"] = error["ctx"]
            errors.append(error_detail)
        
        response_data = {
            "error": {
                "code": "VALIDATION_ERROR",
                "message": "Request validation failed",
                "details": {"errors": errors},
            }
        }
        
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=response_data,
        )
    
    @app.exception_handler(Exception)
    async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        """
        Handle all other unhandled exceptions.
        
        Args:
            request: The incoming request.
            exc: The exception.
            
        Returns:
            JSONResponse with error details.
        """
        logger.error(
            f"Unhandled exception: {exc.__class__.__name__} - {str(exc)}",
            extra={"request_id": request.state.request_id},
            exc_info=exc,
        )
        
        response_data = {
            "error": {
                "code": "INTERNAL_SERVER_ERROR",
                "message": "An internal server error occurred",
            }
        }
        
        # Include more details in debug mode
        if settings.DEBUG:
            import traceback
            response_data["error"]["details"] = {
                "exception_type": exc.__class__.__name__,
                "exception_message": str(exc),
                "traceback": traceback.format_exception(
                    type(exc), exc, exc.__traceback__
                ),
            }
        
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=response_data,
        )
    
    logger.info("Exception handlers configured")


def configure_routing(app: FastAPI) -> None:
    """
    Configure API routing for the application.
    
    Args:
        app: FastAPI application instance.
    """
    # Include API routers
    app.include_router(v1_router, prefix="/api/v1")
    
    # Include metrics router if enabled
    if settings.METRICS_ENABLED:
        app.include_router(metrics_router, prefix="/metrics", tags=["metrics"])
    
    logger.info("Routing configuration complete")


def configure_health_checks(app: FastAPI) -> None:
    """
    Configure health check endpoints.
    
    Args:
        app: FastAPI application instance.
    """
    
    @app.get("/health", tags=["health"])
    async def health_check() -> Dict[str, Any]:
        """
        Basic health check endpoint.
        
        Returns:
            Health status information.
        """
        return {
            "status": "healthy",
            "timestamp": datetime.utcnow().isoformat(),
            "version": get_version(),
            "environment": settings.ENVIRONMENT,
        }
    
    @app.get("/health/ready", tags=["health"])
    async def readiness_check(request: Request) -> Dict[str, Any]:
        """
        Readiness check endpoint for Kubernetes/container orchestration.
        
        Args:
            request: The incoming request.
            
        Returns:
            Readiness status information.
        """
        # Check application readiness
        is_ready = request.app.state.ready
        
        # Add additional readiness checks here
        # Example: database connectivity, cache connectivity, etc.
        checks = {
            "app_ready": is_ready,
            # "database_connected": await database.is_connected(),
        }
        
        all_ready = all(checks.values())
        
        status_code = status.HTTP_200_OK if all_ready else status.HTTP_503_SERVICE_UNAVAILABLE
        
        response_data = {
            "status": "ready" if all_ready else "not_ready",
            "timestamp": datetime.utcnow().isoformat(),
            "checks": checks,
            "version": get_version(),
        }
        
        return JSONResponse(
            status_code=status_code,
            content=response_data,
        )
    
    @app.get("/health/live", tags=["health"])
    async def liveness_check() -> Dict[str, Any]:
        """
        Liveness check endpoint for Kubernetes/container orchestration.
        
        Returns:
            Liveness status information.
        """
        return {
            "status": "alive",
            "timestamp": datetime.utcnow().isoformat(),
        }
    
    logger.info("Health check endpoints configured")


def configure_metrics(app: FastAPI) -> None:
    """
    Configure Prometheus metrics instrumentation.
    
    Args:
        app: FastAPI application instance.
    """
    try:
        # Instrument the application
        instrumentator = Instrumentator(
            should_group_status_codes=False,
            should_ignore_untemplated=True,
            should_respect_env_var=True,
            should_instrument_requests_inprogress=True,
            excluded_handlers=["/metrics", "/health", "/docs", "/redoc", "/openapi.json"],
            env_var_name="ENABLE_METRICS",
            inprogress_name="http_requests_inprogress",
            inprogress_labels=True,
        )
        
        # Instrument the app
        instrumentator.instrument(app).expose(
            app,
            endpoint="/metrics",
            include_in_schema=settings.METRICS_INCLUDE_IN_SCHEMA,
        )
        
        logger.info("Prometheus metrics instrumentation configured")
    except Exception as e:
        logger.error(f"Failed to configure metrics instrumentation: {e}")
        if settings.DEBUG:
            raise


# Create the application instance
app = create_application()


# Main entry point for ASGI servers
async def main() -> None:
    """
    Main entry point for running the application directly.
    
    This is used when running with: python -m app.main
    """
    import uvicorn
    
    # Get server configuration
    host = settings.HOST
    port = settings.PORT
    reload = settings.DEBUG and settings.AUTO_RELOAD
    
    logger.info(f"Starting server on {host}:{port}")
    logger.info(f"Auto-reload: {reload}")
    
    # Run the server
    uvicorn.run(
        "app.main:app",
        host=host,
        port=port,
        reload=reload,
        log_level=settings.LOG_LEVEL.lower(),
        access_log=settings.ACCESS_LOG,
    )


if __name__ == "__main__":
    # Run the application
    asyncio.run(main())
