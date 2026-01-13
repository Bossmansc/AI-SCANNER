from fastapi import APIRouter

from app.api.v1.endpoints import (
    login,
    users,
    utils,
    tasks,
    websockets,
)

# Initialize the main API router for Version 1
api_router = APIRouter()

# -----------------------------------------------------------------------------
# Authentication & Security
# -----------------------------------------------------------------------------
api_router.include_router(
    login.router, 
    tags=["login"],
    responses={404: {"description": "Not found"}}
)

# -----------------------------------------------------------------------------
# Core Resources
# -----------------------------------------------------------------------------
api_router.include_router(
    users.router, 
    prefix="/users", 
    tags=["users"]
)

api_router.include_router(
    tasks.router, 
    prefix="/tasks", 
    tags=["tasks"]
)

# -----------------------------------------------------------------------------
# Real-time & Utilities
# -----------------------------------------------------------------------------
api_router.include_router(
    websockets.router,
    prefix="/ws",
    tags=["websockets"]
)

api_router.include_router(
    utils.router, 
    prefix="/utils", 
    tags=["utils"]
)
