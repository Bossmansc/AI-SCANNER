"""
Main FastAPI application for CodeCraft AI - High-Concurrency Architectural Engine
Core application with REST API endpoints and WebSocket handling for real-time collaboration
"""

import asyncio
import json
import logging
import uuid
from datetime import datetime
from typing import Dict, List, Optional, Any, Set
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, validator
import redis.asyncio as redis
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import declarative_base
from sqlalchemy import Column, String, Text, DateTime, JSON, Integer, Boolean
import aioredis

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Database configuration
DATABASE_URL = "sqlite+aiosqlite:///./codecraft.db"
engine = create_async_engine(DATABASE_URL, echo=True, future=True)
AsyncSessionLocal = async_sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)
Base = declarative_base()

# Redis configuration for pub/sub and caching
REDIS_URL = "redis://localhost:6379"
redis_pool = None

# Pydantic models for request/response
class ProjectCreate(BaseModel):
    """Model for creating a new project"""
    name: str = Field(..., min_length=1, max_length=100, description="Project name")
    description: Optional[str] = Field(None, max_length=500, description="Project description")
    language: str = Field(..., description="Primary programming language")
    architecture_type: str = Field(..., description="Architecture type (microservices, monolith, etc.)")

class FileCreate(BaseModel):
    """Model for creating a new file"""
    path: str = Field(..., description="File path including filename")
    content: str = Field("", description="File content")
    purpose: str = Field(..., description="Purpose/description of the file")

class FileUpdate(BaseModel):
    """Model for updating file content"""
    content: str = Field(..., description="Updated file content")
    version: int = Field(..., ge=0, description="File version for optimistic locking")

class WebSocketMessage(BaseModel):
    """Model for WebSocket messages"""
    type: str = Field(..., description="Message type (edit, cursor, join, leave)")
    project_id: str = Field(..., description="Project identifier")
    user_id: str = Field(..., description="User identifier")
    data: Dict[str, Any] = Field(default_factory=dict, description="Message payload")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Message timestamp")

class ProjectResponse(BaseModel):
    """Response model for project data"""
    id: str
    name: str
    description: Optional[str]
    language: str
    architecture_type: str
    created_at: datetime
    updated_at: datetime
    file_count: int = 0

class FileResponse(BaseModel):
    """Response model for file data"""
    id: str
    path: str
    content: str
    purpose: str
    version: int
    project_id: str
    created_at: datetime
    updated_at: datetime

# SQLAlchemy models
class Project(Base):
    """Project database model"""
    __tablename__ = "projects"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    language = Column(String(50), nullable=False)
    architecture_type = Column(String(50), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class File(Base):
    """File database model"""
    __tablename__ = "files"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    path = Column(String(500), nullable=False)
    content = Column(Text, nullable=False)
    purpose = Column(Text, nullable=False)
    version = Column(Integer, default=0, nullable=False)
    project_id = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class ConnectionManager:
    """Manager for WebSocket connections"""
    
    def __init__(self):
        self.active_connections: Dict[str, Dict[str, WebSocket]] = {}
        self.user_projects: Dict[str, Set[str]] = {}
        self.redis_pubsub = None
        
    async def connect(self, websocket: WebSocket, project_id: str, user_id: str):
        """Connect a user to a project room"""
        await websocket.accept()
        
        if project_id not in self.active_connections:
            self.active_connections[project_id] = {}
        
        self.active_connections[project_id][user_id] = websocket
        
        if user_id not in self.user_projects:
            self.user_projects[user_id] = set()
        self.user_projects[user_id].add(project_id)
        
        logger.info(f"User {user_id} connected to project {project_id}")
        
        # Notify others in the project
        await self.broadcast_to_project(
            project_id,
            {
                "type": "user_joined",
                "user_id": user_id,
                "project_id": project_id,
                "timestamp": datetime.utcnow().isoformat(),
                "active_users": list(self.active_connections[project_id].keys())
            },
            exclude_user=user_id
        )
        
        # Send current project state to the new user
        await self.send_personal_message(
            {
                "type": "project_state",
                "project_id": project_id,
                "active_users": list(self.active_connections[project_id].keys()),
                "timestamp": datetime.utcnow().isoformat()
            },
            websocket
        )
    
    def disconnect(self, project_id: str, user_id: str):
        """Disconnect a user from a project room"""
        if project_id in self.active_connections:
            if user_id in self.active_connections[project_id]:
                del self.active_connections[project_id][user_id]
                logger.info(f"User {user_id} disconnected from project {project_id}")
                
                # Clean up empty projects
                if not self.active_connections[project_id]:
                    del self.active_connections[project_id]
        
        if user_id in self.user_projects:
            self.user_projects[user_id].discard(project_id)
            if not self.user_projects[user_id]:
                del self.user_projects[user_id]
    
    async def send_personal_message(self, message: dict, websocket: WebSocket):
        """Send a message to a specific WebSocket connection"""
        try:
            await websocket.send_json(message)
        except Exception as e:
            logger.error(f"Error sending personal message: {e}")
    
    async def broadcast_to_project(self, project_id: str, message: dict, exclude_user: str = None):
        """Broadcast a message to all connections in a project"""
        if project_id not in self.active_connections:
            return
        
        disconnected_users = []
        
        for user_id, connection in self.active_connections[project_id].items():
            if user_id == exclude_user:
                continue
            
            try:
                await connection.send_json(message)
            except Exception as e:
                logger.error(f"Error broadcasting to user {user_id}: {e}")
                disconnected_users.append(user_id)
        
        # Clean up disconnected users
        for user_id in disconnected_users:
            self.disconnect(project_id, user_id)
    
    async def handle_edit(self, project_id: str, user_id: str, data: dict):
        """Handle file edit messages"""
        message = {
            "type": "file_edit",
            "project_id": project_id,
            "user_id": user_id,
            "data": data,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        await self.broadcast_to_project(project_id, message, exclude_user=user_id)
    
    async def handle_cursor(self, project_id: str, user_id: str, data: dict):
        """Handle cursor position updates"""
        message = {
            "type": "cursor_update",
            "project_id": project_id,
            "user_id": user_id,
            "data": data,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        await self.broadcast_to_project(project_id, message, exclude_user=user_id)

# Database dependency
async def get_db():
    """Dependency to get database session"""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()

# Redis dependency
async def get_redis():
    """Dependency to get Redis connection"""
    global redis_pool
    if redis_pool is None:
        redis_pool = await aioredis.from_url(REDIS_URL, decode_responses=True)
    return redis_pool

# Application lifespan
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Handle application startup and shutdown"""
    # Startup
    logger.info("Starting CodeCraft AI backend...")
    
    # Create database tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    # Initialize Redis
    await get_redis()
    
    logger.info("CodeCraft AI backend started successfully")
    
    yield
    
    # Shutdown
    logger.info("Shutting down CodeCraft AI backend...")
    
    if redis_pool:
        await redis_pool.close()
    
    await engine.dispose()
    
    logger.info("CodeCraft AI backend shutdown complete")

# Create FastAPI application
app = FastAPI(
    title="CodeCraft AI - High-Concurrency Architectural Engine",
    description="Backend API for real-time collaborative code architecture",
    version="1.0.0",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify actual origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize connection manager
connection_manager = ConnectionManager()

# REST API Endpoints
@app.get("/")
async def root():
    """Root endpoint with API information"""
    return {
        "service": "CodeCraft AI Backend",
        "version": "1.0.0",
        "status": "operational",
        "endpoints": {
            "projects": "/api/projects",
            "files": "/api/projects/{project_id}/files",
            "websocket": "/ws/{project_id}/{user_id}"
        }
    }

@app.get("/api/projects", response_model=List[ProjectResponse])
async def get_projects(db: AsyncSession = Depends(get_db)):
    """Get all projects"""
    try:
        result = await db.execute("""
            SELECT p.*, COUNT(f.id) as file_count
            FROM projects p
            LEFT JOIN files f ON p.id = f.project_id
            GROUP BY p.id
            ORDER BY p.updated_at DESC
        """)
        
        projects = []
        for row in result:
            project_data = dict(row)
            project_data["file_count"] = project_data.pop("COUNT(f.id)", 0)
            projects.append(project_data)
        
        return projects
    except Exception as e:
        logger.error(f"Error getting projects: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve projects"
        )

@app.post("/api/projects", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
async def create_project(project: ProjectCreate, db: AsyncSession = Depends(get_db)):
    """Create a new project"""
    try:
        db_project = Project(
            name=project.name,
            description=project.description,
            language=project.language,
            architecture_type=project.architecture_type
        )
        
        db.add(db_project)
        await db.commit()
        await db.refresh(db_project)
        
        # Convert to response model
        response = ProjectResponse(
            id=db_project.id,
            name=db_project.name,
            description=db_project.description,
            language=db_project.language,
            architecture_type=db_project.architecture_type,
            created_at=db_project.created_at,
            updated_at=db_project.updated_at,
            file_count=0
        )
        
        return response
    except Exception as e:
        await db.rollback()
        logger.error(f"Error creating project: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create project"
        )

@app.get("/api/projects/{project_id}", response_model=ProjectResponse)
async def get_project(project_id: str, db: AsyncSession = Depends(get_db)):
    """Get a specific project by ID"""
    try:
        # Get project
        result = await db.execute(
            "SELECT * FROM projects WHERE id = :id",
            {"id": project_id}
        )
        project = result.fetchone()
        
        if not project:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Project not found"
            )
        
        # Get file count
        result = await db.execute(
            "SELECT COUNT(*) as file_count FROM files WHERE project_id = :project_id",
            {"project_id": project_id}
        )
        file_count = result.scalar() or 0
        
        project_dict = dict(project)
        return ProjectResponse(
            **project_dict,
            file_count=file_count
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting project {project_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve project"
        )

@app.delete("/api/projects/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(project_id: str, db: AsyncSession = Depends(get_db)):
    """Delete a project and all its files"""
    try:
        # Check if project exists
        result = await db.execute(
            "SELECT id FROM projects WHERE id = :id",
            {"id": project_id}
        )
        if not result.fetchone():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Project not found"
            )
        
        # Delete files first (foreign key constraint)
        await db.execute(
            "DELETE FROM files WHERE project_id = :project_id",
            {"project_id": project_id}
        )
        
        # Delete project
        await db.execute(
            "DELETE FROM projects WHERE id = :id",
            {"id": project_id}
        )
        
        await db.commit()
        
        # Notify WebSocket connections
        if project_id in connection_manager.active_connections:
            message = {
                "type": "project_deleted",
                "project_id": project_id,
                "timestamp": datetime.utcnow().isoformat()
            }
            await connection_manager.broadcast_to_project(project_id, message)
            
            # Clean up connections
            for user_id in list(connection_manager.active_connections[project_id].keys()):
                connection_manager.disconnect(project_id, user_id)
        
        return None
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"Error deleting project {project_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete project"
        )

@app.get("/api/projects/{project_id}/files", response_model=List[FileResponse])
async def get_project_files(project_id: str, db: AsyncSession = Depends(get_db)):
    """Get all files for a project"""
    try:
        # Verify project exists
        result = await db.execute(
            "SELECT id FROM projects WHERE id = :id",
            {"id": project_id}
        )
        if not result.fetchone():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Project not found"
            )
        
        # Get files
        result = await db.execute(
            "SELECT * FROM files WHERE project_id = :project_id ORDER BY path",
            {"project_id": project_id}
        )
        
        files = [dict(row) for row in result]
        return files
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting files for project {project_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve files"
        )

@app.post("/api/projects/{project_id}/files", response_model=FileResponse, status_code=status.HTTP_201_CREATED)
async def create_file(
    project_id: str,
    file: FileCreate,
    db: AsyncSession = Depends(get_db)
):
    """Create a new file in a project"""
    try:
        # Verify project exists
        result = await db.execute(
            "SELECT id FROM projects WHERE id = :id",
            {"id": project_id}
        )
        if not result.fetchone():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Project not found"
            )
        
        # Check if file already exists
        result = await db.execute(
            "SELECT id FROM files WHERE project_id = :project_id AND path = :path",
            {"project_id": project_id, "path": file.path}
        )
        if result.fetchone():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="File with this path already exists in the project"
            )
        
        # Create file
        db_file = File(
            path=file.path,
            content=file.content,
            purpose=file.purpose,
            project_id=project_id,
            version=0
        )
        
        db