import sys
import os
import logging
import uvicorn
from contextlib import asynccontextmanager
from typing import AsyncGenerator

# ------------------------------------------------------------------------------
# PATH VERIFICATION & SETUP
# ------------------------------------------------------------------------------
# Ensure the project root is in sys.path so that imports work correctly 
# whether running via 'python app/main.py' or 'uvicorn app.main:app'.
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

# Now we can safely import third-party libraries and internal modules
from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

# ------------------------------------------------------------------------------
# LOGGING CONFIGURATION
# ------------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger("CodeCraftAI")

# ------------------------------------------------------------------------------
# LIFESPAN MANAGEMENT
# ------------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator:
    """
    Handle application startup and shutdown events.
    Initialize database connections, caches, or background tasks here.
    """
    logger.info("System initializing... [STARTUP]")
    
    # Placeholder: Initialize DB connection
    # await db.connect()
    
    # Placeholder: Initialize Redis cache
    # await cache.connect()
    
    yield
    
    logger.info("System shutting down... [SHUTDOWN]")
    
    # Placeholder: Close resources
    # await db.disconnect()
    # await cache.disconnect()

# ------------------------------------------------------------------------------
# APPLICATION FACTORY
# ------------------------------------------------------------------------------
def create_application() -> FastAPI:
    """
    Factory function to create and configure the FastAPI application instance.
    """
    application = FastAPI(
        title="CodeCraft AI Engine",
        description="High-concurrency architectural engine API.",
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan
    )

    # --------------------------------------------------------------------------
    # MIDDLEWARE
    # --------------------------------------------------------------------------
    # Configure CORS (Cross-Origin Resource Sharing)
    # In production, replace ["*"] with specific allowed origins.
    origins = [
        "http://localhost",
        "http://localhost:3000",
        "http://localhost:8000",
    ]

    application.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Permissive for development
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    return application

# Initialize the application instance
app = create_application()

# ------------------------------------------------------------------------------
# GLOBAL EXCEPTION HANDLERS
# ------------------------------------------------------------------------------
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """
    Catch-all exception handler to ensure all errors return JSON.
    """
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": "Internal Server Error",
            "message": str(exc) if os.getenv("DEBUG") == "true" else "An unexpected error occurred."
        },
    )

# ------------------------------------------------------------------------------
# CORE ENDPOINTS
# ------------------------------------------------------------------------------
@app.get("/", tags=["System"])
async def root():
    """
    Root endpoint to verify the API is reachable.
    """
    return {
        "system": "CodeCraft AI",
        "status": "online",
        "version": "1.0.0"
    }

@app.get("/health", tags=["System"])
async def health_check():
    """
    Health check endpoint for load balancers and monitoring tools.
    """
    return {
        "status": "healthy",
        "components": {
            "database": "unknown", # To be implemented with actual checks
            "cache": "unknown"     # To be implemented with actual checks
        }
    }

# ------------------------------------------------------------------------------
# ENTRY POINT
# ------------------------------------------------------------------------------
if __name__ == "__main__":
    """
    Entry point for running the application directly via Python.
    Example: python app/main.py
    """
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8000"))
    reload = os.getenv("ENV", "development") == "development"

    logger.info(f"Starting server on {host}:{port} (Reload: {reload})")
    
    uvicorn.run(
        "app.main:app",
        host=host,
        port=port,
        reload=reload,
        log_level="info"
    )
