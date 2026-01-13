"""
Pydantic schemas for request/response validation.
Organized by domain/resource type.
"""

from datetime import datetime, date
from typing import Optional, List, Dict, Any, Union
from uuid import UUID
from pydantic import BaseModel, Field, EmailStr, validator, root_validator
from enum import Enum


# ==================== BASE SCHEMAS ====================

class BaseResponse(BaseModel):
    """Base response schema with common fields."""
    id: UUID
    created_at: datetime
    updated_at: datetime
    
    class Config:
        orm_mode = True
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            UUID: lambda v: str(v)
        }


class PaginatedResponse(BaseModel):
    """Base schema for paginated responses."""
    items: List[Any]
    total: int
    page: int
    per_page: int
    total_pages: int


class ErrorResponse(BaseModel):
    """Error response schema."""
    detail: str
    error_code: Optional[str] = None
    field: Optional[str] = None


# ==================== AUTH SCHEMAS ====================

class TokenType(str, Enum):
    """Token type enumeration."""
    BEARER = "bearer"
    REFRESH = "refresh"


class Token(BaseModel):
    """Token response schema."""
    access_token: str
    refresh_token: str
    token_type: TokenType = TokenType.BEARER
    expires_in: int


class TokenPayload(BaseModel):
    """Token payload schema."""
    sub: str  # subject (user ID)
    exp: int  # expiration time
    iat: int  # issued at
    type: TokenType


class LoginRequest(BaseModel):
    """Login request schema."""
    email: EmailStr
    password: str
    remember_me: bool = False


class RegisterRequest(BaseModel):
    """User registration request schema."""
    email: EmailStr
    password: str
    confirm_password: str
    first_name: str = Field(..., min_length=1, max_length=50)
    last_name: str = Field(..., min_length=1, max_length=50)
    
    @validator('confirm_password')
    def passwords_match(cls, v, values):
        if 'password' in values and v != values['password']:
            raise ValueError('passwords do not match')
        return v
    
    @validator('password')
    def password_strength(cls, v):
        if len(v) < 8:
            raise ValueError('password must be at least 8 characters')
        # Add more password strength checks as needed
        return v


class PasswordResetRequest(BaseModel):
    """Password reset request schema."""
    email: EmailStr


class PasswordResetConfirm(BaseModel):
    """Password reset confirmation schema."""
    token: str
    new_password: str
    confirm_password: str
    
    @validator('confirm_password')
    def passwords_match(cls, v, values):
        if 'new_password' in values and v != values['new_password']:
            raise ValueError('passwords do not match')
        return v


# ==================== USER SCHEMAS ====================

class UserRole(str, Enum):
    """User role enumeration."""
    ADMIN = "admin"
    USER = "user"
    MODERATOR = "moderator"


class UserBase(BaseModel):
    """Base user schema."""
    email: EmailStr
    first_name: str
    last_name: str
    is_active: bool = True
    is_verified: bool = False


class UserCreate(UserBase):
    """User creation schema."""
    password: str


class UserUpdate(BaseModel):
    """User update schema."""
    email: Optional[EmailStr] = None
    first_name: Optional[str] = Field(None, min_length=1, max_length=50)
    last_name: Optional[str] = Field(None, min_length=1, max_length=50)
    is_active: Optional[bool] = None
    is_verified: Optional[bool] = None


class UserResponse(UserBase, BaseResponse):
    """User response schema."""
    role: UserRole = UserRole.USER
    
    class Config:
        schema_extra = {
            "example": {
                "id": "123e4567-e89b-12d3-a456-426614174000",
                "email": "user@example.com",
                "first_name": "John",
                "last_name": "Doe",
                "is_active": True,
                "is_verified": True,
                "role": "user",
                "created_at": "2023-01-01T00:00:00",
                "updated_at": "2023-01-01T00:00:00"
            }
        }


class UserProfileResponse(BaseModel):
    """User profile response schema."""
    user: UserResponse
    stats: Optional[Dict[str, Any]] = None


# ==================== FILE SCHEMAS ====================

class FileType(str, Enum):
    """File type enumeration."""
    IMAGE = "image"
    DOCUMENT = "document"
    AUDIO = "audio"
    VIDEO = "video"
    ARCHIVE = "archive"
    OTHER = "other"


class FileBase(BaseModel):
    """Base file schema."""
    filename: str
    content_type: str
    file_type: FileType
    size_bytes: int
    description: Optional[str] = None
    is_public: bool = False


class FileCreate(FileBase):
    """File creation schema."""
    pass


class FileUpdate(BaseModel):
    """File update schema."""
    filename: Optional[str] = None
    description: Optional[str] = None
    is_public: Optional[bool] = None


class FileResponse(FileBase, BaseResponse):
    """File response schema."""
    url: str
    uploader_id: UUID
    
    class Config:
        schema_extra = {
            "example": {
                "id": "123e4567-e89b-12d3-a456-426614174000",
                "filename": "example.jpg",
                "content_type": "image/jpeg",
                "file_type": "image",
                "size_bytes": 102400,
                "description": "Example image",
                "is_public": True,
                "url": "https://example.com/files/example.jpg",
                "uploader_id": "123e4567-e89b-12d3-a456-426614174001",
                "created_at": "2023-01-01T00:00:00",
                "updated_at": "2023-01-01T00:00:00"
            }
        }


class FileUploadResponse(BaseModel):
    """File upload response schema."""
    file: FileResponse
    upload_url: Optional[str] = None  # For presigned URLs


# ==================== AUDIT LOG SCHEMAS ====================

class AuditAction(str, Enum):
    """Audit action enumeration."""
    CREATE = "create"
    READ = "read"
    UPDATE = "update"
    DELETE = "delete"
    LOGIN = "login"
    LOGOUT = "logout"
    PASSWORD_CHANGE = "password_change"
    PERMISSION_CHANGE = "permission_change"


class AuditLogBase(BaseModel):
    """Base audit log schema."""
    action: AuditAction
    resource_type: str
    resource_id: Optional[str] = None
    details: Optional[Dict[str, Any]] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None


class AuditLogCreate(AuditLogBase):
    """Audit log creation schema."""
    user_id: Optional[UUID] = None


class AuditLogResponse(AuditLogBase, BaseResponse):
    """Audit log response schema."""
    user_id: Optional[UUID]
    user_email: Optional[str] = None
    
    class Config:
        schema_extra = {
            "example": {
                "id": "123e4567-e89b-12d3-a456-426614174000",
                "action": "create",
                "resource_type": "user",
                "resource_id": "123e4567-e89b-12d3-a456-426614174001",
                "details": {"email": "new@example.com"},
                "ip_address": "192.168.1.1",
                "user_agent": "Mozilla/5.0",
                "user_id": "123e4567-e89b-12d3-a456-426614174002",
                "user_email": "admin@example.com",
                "created_at": "2023-01-01T00:00:00",
                "updated_at": "2023-01-01T00:00:00"
            }
        }


# ==================== NOTIFICATION SCHEMAS ====================

class NotificationType(str, Enum):
    """Notification type enumeration."""
    INFO = "info"
    SUCCESS = "success"
    WARNING = "warning"
    ERROR = "error"
    SYSTEM = "system"


class NotificationBase(BaseModel):
    """Base notification schema."""
    title: str
    message: str
    notification_type: NotificationType = NotificationType.INFO
    is_read: bool = False
    metadata: Optional[Dict[str, Any]] = None


class NotificationCreate(NotificationBase):
    """Notification creation schema."""
    user_id: UUID


class NotificationUpdate(BaseModel):
    """Notification update schema."""
    is_read: Optional[bool] = None


class NotificationResponse(NotificationBase, BaseResponse):
    """Notification response schema."""
    user_id: UUID
    
    class Config:
        schema_extra = {
            "example": {
                "id": "123e4567-e89b-12d3-a456-426614174000",
                "title": "Welcome!",
                "message": "Welcome to our platform!",
                "notification_type": "info",
                "is_read": False,
                "metadata": {"welcome": True},
                "user_id": "123e4567-e89b-12d3-a456-426614174001",
                "created_at": "2023-01-01T00:00:00",
                "updated_at": "2023-01-01T00:00:00"
            }
        }


# ==================== SETTINGS SCHEMAS ====================

class UserSettingsBase(BaseModel):
    """Base user settings schema."""
    email_notifications: bool = True
    push_notifications: bool = True
    theme: str = "light"
    language: str = "en"
    timezone: str = "UTC"
    preferences: Optional[Dict[str, Any]] = None


class UserSettingsCreate(UserSettingsBase):
    """User settings creation schema."""
    user_id: UUID


class UserSettingsUpdate(BaseModel):
    """User settings update schema."""
    email_notifications: Optional[bool] = None
    push_notifications: Optional[bool] = None
    theme: Optional[str] = None
    language: Optional[str] = None
    timezone: Optional[str] = None
    preferences: Optional[Dict[str, Any]] = None


class UserSettingsResponse(UserSettingsBase, BaseResponse):
    """User settings response schema."""
    user_id: UUID


# ==================== API RESPONSE SCHEMAS ====================

class SuccessResponse(BaseModel):
    """Generic success response schema."""
    success: bool = True
    message: Optional[str] = None
    data: Optional[Any] = None


class PaginationParams(BaseModel):
    """Pagination parameters schema."""
    page: int = Field(1, ge=1)
    per_page: int = Field(10, ge=1, le=100)
    sort_by: Optional[str] = None
    sort_order: Optional[str] = Field(None, regex="^(asc|desc)$")


class FilterParams(BaseModel):
    """Filter parameters schema."""
    search: Optional[str] = None
    filters: Optional[Dict[str, Any]] = None
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None


# ==================== HEALTH CHECK SCHEMAS ====================

class HealthCheckResponse(BaseModel):
    """Health check response schema."""
    status: str
    timestamp: datetime
    version: str
    dependencies: Dict[str, str]
    uptime: float


class ServiceStatus(BaseModel):
    """Service status schema."""
    service: str
    status: str
    response_time: Optional[float] = None
    error: Optional[str] = None


# ==================== EXPORT ALL SCHEMAS ====================

__all__ = [
    # Base schemas
    "BaseResponse",
    "PaginatedResponse",
    "ErrorResponse",
    
    # Auth schemas
    "TokenType",
    "Token",
    "TokenPayload",
    "LoginRequest",
    "RegisterRequest",
    "PasswordResetRequest",
    "PasswordResetConfirm",
    
    # User schemas
    "UserRole",
    "UserBase",
    "UserCreate",
    "UserUpdate",
    "UserResponse",
    "UserProfileResponse",
    
    # File schemas
    "FileType",
    "FileBase",
    "FileCreate",
    "FileUpdate",
    "FileResponse",
    "FileUploadResponse",
    
    # Audit log schemas
    "AuditAction",
    "AuditLogBase",
    "AuditLogCreate",
    "AuditLogResponse",
    
    # Notification schemas
    "NotificationType",
    "NotificationBase",
    "NotificationCreate",
    "NotificationUpdate",
    "NotificationResponse",
    
    # Settings schemas
    "UserSettingsBase",
    "UserSettingsCreate",
    "UserSettingsUpdate",
    "UserSettingsResponse",
    
    # API response schemas
    "SuccessResponse",
    "PaginationParams",
    "FilterParams",
    
    # Health check schemas
    "HealthCheckResponse",
    "ServiceStatus",
]
