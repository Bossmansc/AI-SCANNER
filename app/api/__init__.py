"""
app/api/__init__.py

API Namespace Initialization Module.

This module serves as the central aggregation point for the application's API routes.
It initializes the primary `APIRouter` and is responsible for composing different
API versions and domain-specific sub-routers.

Architectural Note:
    In a high-concurrency environment, keeping the route registration centralized
    here allows for easier introspection, versioning strategies, and global
    dependency injection (e.g., authentication guards) at the router level.
"""

from fastapi import APIRouter

# -----------------------------------------------------------------------------
# Router Initialization
# -----------------------------------------------------------------------------

# The main API router that will be included in the FastAPI application instance.
# This router acts as the root for all API endpoints defined within the `app.api` namespace.
api_router = APIRouter()

# -----------------------------------------------------------------------------
# System Endpoints
# -----------------------------------------------------------------------------

@api_router.get(
    "/health",
    tags=["System"],
    summary="System Health Check",
    response_description="Returns the operational status of the API service."
)
async def health_check() -> dict:
    """
    **Health Check Endpoint**

    Performs a lightweight status check of the API service.
    
    Usage:
    - **Load Balancers**: To determine if traffic should be routed to this instance.
    - **Orchestrators (K8s)**: To determine liveness/readiness probes.
    - **Monitoring**: To verify basic service availability.

    Returns:
        dict: A JSON object containing the service status and version.
    """
    return {
        "status": "active",
        "service": "CodeCraft High-Concurrency API",
        "component": "api_gateway"
    }

# -----------------------------------------------------------------------------
# Route Aggregation (Blueprint)
# -----------------------------------------------------------------------------

# NOTE: As the synthesis engine generates specific domain modules (e.g., auth, users),
# they should be imported and included here.
#
# Example Architecture:
#
# from app.api.v1 import api as api_v1
# from app.api.auth import router as auth_router
#
# api_router.include_router(auth_router, prefix="/auth", tags=["Authentication"])
# api_router.include_router(api_v1.router, prefix="/v1")

# -----------------------------------------------------------------------------
# Module Exports
# -----------------------------------------------------------------------------

__all__ = ["api_router"]
