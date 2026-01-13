"""
API v1 Router Configuration
Main router that aggregates all v1 API endpoints and middleware.
"""

from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.responses import JSONResponse
from typing import List, Optional, Dict, Any
import logging
import time
from contextlib import asynccontextmanager

from app.api.v1.endpoints import (
    auth,
    users,
    projects,
    datasets,
    models,
    predictions,
    monitoring,
    system
)
from app.core.config import settings
from app.core.security import get_current_active_user, get_current_active_superuser
from app.schemas.user import User
from app.middleware.rate_limiter import rate_limit_middleware
from app.middleware.request_logger import log_request_middleware
from app.utils.metrics import api_metrics_middleware

# Configure logger
logger = logging.getLogger(__name__)

# Create main API v1 router
api_router = APIRouter(
    prefix="/api/v1",
    tags=["api-v1"],
    dependencies=[
        Depends(rate_limit_middleware),
        Depends(log_request_middleware),
        Depends(api_metrics_middleware)
    ],
    responses={
        400: {"description": "Bad Request"},
        401: {"description": "Unauthorized"},
        403: {"description": "Forbidden"},
        404: {"description": "Not Found"},
        422: {"description": "Validation Error"},
        429: {"description": "Too Many Requests"},
        500: {"description": "Internal Server Error"},
        503: {"description": "Service Unavailable"}
    }
)

# Include all endpoint routers with their specific configurations
api_router.include_router(
    auth.router,
    prefix="/auth",
    tags=["authentication"]
)

api_router.include_router(
    users.router,
    prefix="/users",
    tags=["users"]
)

api_router.include_router(
    projects.router,
    prefix="/projects",
    tags=["projects"]
)

api_router.include_router(
    datasets.router,
    prefix="/datasets",
    tags=["datasets"]
)

api_router.include_router(
    models.router,
    prefix="/models",
    tags=["models"]
)

api_router.include_router(
    predictions.router,
    prefix="/predictions",
    tags=["predictions"]
)

api_router.include_router(
    monitoring.router,
    prefix="/monitoring",
    tags=["monitoring"]
)

api_router.include_router(
    system.router,
    prefix="/system",
    tags=["system"]
)

# Health check endpoint (no authentication required)
@api_router.get(
    "/health",
    response_model=Dict[str, Any],
    status_code=status.HTTP_200_OK,
    summary="Health check",
    description="Check if the API is running and healthy",
    tags=["system"]
)
async def health_check() -> Dict[str, Any]:
    """
    Health check endpoint for load balancers and monitoring systems.
    Returns basic system status information.
    """
    from app.core.health import check_database, check_cache, check_storage
    from app.utils.system_info import get_system_info
    
    try:
        # Run basic health checks
        db_status = await check_database()
        cache_status = await check_cache()
        storage_status = await check_storage()
        
        # Get system info
        system_info = get_system_info()
        
        # Determine overall health status
        all_healthy = all([
            db_status["healthy"],
            cache_status["healthy"],
            storage_status["healthy"]
        ])
        
        status_code = status.HTTP_200_OK if all_healthy else status.HTTP_503_SERVICE_UNAVAILABLE
        
        response_data = {
            "status": "healthy" if all_healthy else "unhealthy",
            "timestamp": time.time(),
            "version": settings.API_VERSION,
            "environment": settings.ENVIRONMENT,
            "components": {
                "database": db_status,
                "cache": cache_status,
                "storage": storage_status
            },
            "system": system_info
        }
        
        return JSONResponse(
            content=response_data,
            status_code=status_code
        )
        
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}", exc_info=True)
        return JSONResponse(
            content={
                "status": "unhealthy",
                "timestamp": time.time(),
                "error": str(e),
                "version": settings.API_VERSION,
                "environment": settings.ENVIRONMENT
            },
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE
        )

# API info endpoint
@api_router.get(
    "/info",
    response_model=Dict[str, Any],
    status_code=status.HTTP_200_OK,
    summary="API information",
    description="Get information about the API including available endpoints",
    tags=["system"]
)
async def api_info(
    current_user: User = Depends(get_current_active_user)
) -> Dict[str, Any]:
    """
    Returns information about the API including version, available endpoints,
    and user-specific information.
    """
    from app.core.config import settings
    from app.utils.endpoint_discovery import get_available_endpoints
    
    try:
        # Get available endpoints for the current user
        endpoints = await get_available_endpoints(current_user)
        
        response_data = {
            "api": {
                "name": settings.PROJECT_NAME,
                "version": settings.API_VERSION,
                "description": settings.PROJECT_DESCRIPTION,
                "environment": settings.ENVIRONMENT,
                "docs_url": "/api/v1/docs",
                "redoc_url": "/api/v1/redoc"
            },
            "user": {
                "id": str(current_user.id),
                "email": current_user.email,
                "is_active": current_user.is_active,
                "is_superuser": current_user.is_superuser,
                "permissions": current_user.permissions
            },
            "endpoints": endpoints,
            "limits": {
                "rate_limit": settings.RATE_LIMIT_PER_MINUTE,
                "max_file_size": settings.MAX_UPLOAD_SIZE,
                "max_request_size": settings.MAX_REQUEST_SIZE
            },
            "features": {
                "authentication": True,
                "file_upload": True,
                "real_time_predictions": settings.REAL_TIME_PREDICTIONS,
                "batch_processing": settings.BATCH_PROCESSING_ENABLED,
                "model_training": settings.MODEL_TRAINING_ENABLED,
                "monitoring": settings.MONITORING_ENABLED
            }
        }
        
        return response_data
        
    except Exception as e:
        logger.error(f"API info endpoint failed: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve API information"
        )

# Root endpoint redirects to docs
@api_router.get(
    "/",
    status_code=status.HTTP_307_TEMPORARY_REDIRECT,
    include_in_schema=False
)
async def root_redirect():
    """
    Redirect root API endpoint to documentation.
    """
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/api/v1/docs")

# Global exception handler for the API router
@api_router.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """
    Global HTTP exception handler for consistent error responses.
    """
    error_detail = exc.detail
    
    # Log the error
    logger.warning(
        f"HTTP Exception: {exc.status_code} - {error_detail}",
        extra={
            "path": request.url.path,
            "method": request.method,
            "status_code": exc.status_code
        }
    )
    
    # Structure error response
    error_response = {
        "error": {
            "code": exc.status_code,
            "message": error_detail,
            "path": request.url.path,
            "timestamp": time.time(),
            "request_id": request.state.get("request_id", "unknown")
        }
    }
    
    # Add validation errors if available
    if hasattr(exc, 'errors'):
        error_response["error"]["validation_errors"] = exc.errors
    
    return JSONResponse(
        status_code=exc.status_code,
        content=error_response
    )

@api_router.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """
    Global exception handler for unhandled exceptions.
    """
    # Log the full exception
    logger.error(
        f"Unhandled exception: {str(exc)}",
        exc_info=True,
        extra={
            "path": request.url.path,
            "method": request.method,
            "client": request.client.host if request.client else "unknown"
        }
    )
    
    # Don't expose internal errors in production
    if settings.ENVIRONMENT == "production":
        error_message = "Internal server error"
    else:
        error_message = str(exc)
    
    error_response = {
        "error": {
            "code": status.HTTP_500_INTERNAL_SERVER_ERROR,
            "message": error_message,
            "path": request.url.path,
            "timestamp": time.time(),
            "request_id": request.state.get("request_id", "unknown")
        }
    }
    
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=error_response
    )

# Middleware registration functions (called from main app)
def register_api_middleware(app):
    """
    Register API-specific middleware.
    This function is called from the main FastAPI application.
    """
    from app.middleware.cors import setup_cors
    from app.middleware.trusted_host import TrustedHostMiddleware
    from app.middleware.gzip import GZipMiddleware
    
    # Setup CORS
    setup_cors(app)
    
    # Add trusted host middleware
    if settings.ALLOWED_HOSTS:
        app.add_middleware(
            TrustedHostMiddleware,
            allowed_hosts=settings.ALLOWED_HOSTS
        )
    
    # Add GZip compression for responses
    app.add_middleware(GZipMiddleware, minimum_size=1000)

# API lifespan context manager
@asynccontextmanager
async def api_lifespan(app):
    """
    API lifespan context manager for startup and shutdown events.
    """
    from app.core.database import init_database, close_database
    from app.core.cache import init_cache, close_cache
    from app.core.storage import init_storage, close_storage
    from app.services.model_registry import init_model_registry
    from app.services.prediction_engine import init_prediction_engine
    from app.monitoring.metrics import init_metrics
    
    # Startup
    logger.info("Starting API v1 lifespan...")
    
    try:
        # Initialize core components
        await init_database()
        await init_cache()
        await init_storage()
        
        # Initialize services
        await init_model_registry()
        await init_prediction_engine()
        
        # Initialize monitoring
        await init_metrics()
        
        logger.info("API v1 lifespan started successfully")
        yield
        
    except Exception as e:
        logger.error(f"Failed to start API lifespan: {str(e)}", exc_info=True)
        raise
        
    finally:
        # Shutdown
        logger.info("Shutting down API v1 lifespan...")
        
        try:
            await close_prediction_engine()
            await close_model_registry()
            await close_storage()
            await close_cache()
            await close_database()
            
            logger.info("API v1 lifespan shut down successfully")
            
        except Exception as e:
            logger.error(f"Error during API shutdown: {str(e)}", exc_info=True)

# Helper function to get all registered routes
def get_registered_routes() -> List[Dict[str, Any]]:
    """
    Returns a list of all registered routes in the API.
    Useful for documentation and testing.
    """
    routes = []
    
    for route in api_router.routes:
        route_info = {
            "path": route.path,
            "name": route.name,
            "methods": list(route.methods) if hasattr(route, 'methods') else [],
            "tags": route.tags if hasattr(route, 'tags') else [],
            "summary": route.summary if hasattr(route, 'summary') else "",
            "description": route.description if hasattr(route, 'description') else ""
        }
        routes.append(route_info)
    
    return routes

# Export the main router
__all__ = [
    "api_router",
    "register_api_middleware",
    "api_lifespan",
    "get_registered_routes"
]
