"""
API V1 Namespace Initialization.

This module aggregates all sub-routers for the V1 API version.
It serves as the central registry for endpoints, ensuring modularity
and separation of concerns.

Architecture:
- Auth: Authentication and token management.
- Users: User profile and permission management.
- Tasks: Asynchronous background job management (High Concurrency).
- System: Health checks and system metrics.
"""

from fastapi import APIRouter

# Import endpoint modules from the endpoints package.
# These modules contain the actual route logic.
from app.api.v1.endpoints import (
    auth,
    users,
    tasks,
    system
)

# Initialize the main V1 router
api_router = APIRouter()

# -----------------------------------------------------------------------------
# Route Registration
# -----------------------------------------------------------------------------

# Authentication Routes
# Handles login, refresh tokens, and password recovery.
api_router.include_router(
    auth.router,
    prefix="/auth",
    tags=["Authentication"]
)

# User Management Routes
# Handles CRUD operations for users and role assignments.
api_router.include_router(
    users.router,
    prefix="/users",
    tags=["Users"]
)

# Task/Job Routes
# Handles submission and status checking of high-concurrency background tasks.
api_router.include_router(
    tasks.router,
    prefix="/tasks",
    tags=["Tasks"]
)

# System/Utility Routes
# Handles health checks, metrics, and system status.
api_router.include_router(
    system.router,
    prefix="/system",
    tags=["System"]
)
