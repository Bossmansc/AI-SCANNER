"""
SQLAlchemy model definitions for the application.

This module centralizes all database models and provides the Base class
for SQLAlchemy declarative base. Models are organized by domain and
include proper relationships, constraints, and type annotations.
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
from sqlalchemy import (
    Column,
    Integer,
    String,
    Text,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    UniqueConstraint,
    Index,
    CheckConstraint,
    Enum,
    JSON,
    LargeBinary,
    Numeric,
    Date,
    Time,
    Interval,
    BigInteger,
    SmallInteger,
    ARRAY,
    func,
    event,
    DDL
)
from sqlalchemy.orm import (
    declarative_base,
    relationship,
    backref,
    validates,
    Session,
    sessionmaker,
    scoped_session,
    deferred,
    column_property,
    composite
)
from sqlalchemy.ext.hybrid import hybrid_property, hybrid_method
from sqlalchemy.ext.associationproxy import association_proxy
from sqlalchemy.ext.mutable import MutableDict, MutableList
from sqlalchemy.dialects.postgresql import UUID, JSONB, ARRAY as PG_ARRAY, INET, CIDR
import enum
import uuid

# Base class for all models
Base = declarative_base()

# Enable mutable JSON for SQLAlchemy
MutableDict.associate_with(JSON)
MutableList.associate_with(PG_ARRAY)


class UserRole(enum.Enum):
    """Enumeration for user roles."""
    ADMIN = "admin"
    MANAGER = "manager"
    USER = "user"
    GUEST = "guest"
    MODERATOR = "moderator"


class AccountStatus(enum.Enum):
    """Enumeration for account status."""
    ACTIVE = "active"
    INACTIVE = "inactive"
    SUSPENDED = "suspended"
    PENDING = "pending"
    BANNED = "banned"


class ContentType(enum.Enum):
    """Enumeration for content types."""
    ARTICLE = "article"
    BLOG_POST = "blog_post"
    TUTORIAL = "tutorial"
    DOCUMENTATION = "documentation"
    NEWS = "news"
    REVIEW = "review"
    COMMENT = "comment"
    FORUM_POST = "forum_post"


class NotificationType(enum.Enum):
    """Enumeration for notification types."""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    SUCCESS = "success"
    SYSTEM = "system"
    MESSAGE = "message"
    ALERT = "alert"


class User(Base):
    """
    User model representing application users.
    
    Stores user authentication, profile, and preference data.
    """
    __tablename__ = "users"
    __table_args__ = (
        UniqueConstraint("email", name="uq_users_email"),
        UniqueConstraint("username", name="uq_users_username"),
        Index("idx_users_email_lower", func.lower("email")),
        Index("idx_users_username_lower", func.lower("username")),
        Index("idx_users_created_at", "created_at"),
        Index("idx_users_status_role", "status", "role"),
        CheckConstraint("email ~* '^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\\.[A-Za-z]{2,}$'", name="chk_users_email_format"),
    )
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, nullable=False)
    email = Column(String(255), nullable=False, index=True)
    username = Column(String(50), nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    first_name = Column(String(100))
    last_name = Column(String(100))
    display_name = Column(String(150))
    avatar_url = Column(String(500))
    bio = Column(Text)
    role = Column(Enum(UserRole), default=UserRole.USER, nullable=False)
    status = Column(Enum(AccountStatus), default=AccountStatus.PENDING, nullable=False)
    email_verified = Column(Boolean, default=False, nullable=False)
    two_factor_enabled = Column(Boolean, default=False, nullable=False)
    last_login_at = Column(DateTime(timezone=True))
    login_count = Column(Integer, default=0, nullable=False)
    failed_login_attempts = Column(Integer, default=0, nullable=False)
    locale = Column(String(10), default="en-US")
    timezone = Column(String(50), default="UTC")
    preferences = Column(JSONB, default=dict, nullable=False)
    metadata = Column(JSONB, default=dict, nullable=False)
    created_at = Column(DateTime(timezone=True), default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=func.now(), onupdate=func.now(), nullable=False)
    deleted_at = Column(DateTime(timezone=True))
    
    # Relationships
    sessions = relationship("UserSession", back_populates="user", cascade="all, delete-orphan")
    profiles = relationship("UserProfile", back_populates="user", cascade="all, delete-orphan")
    posts = relationship("Post", back_populates="author")
    comments = relationship("Comment", back_populates="author")
    notifications = relationship("Notification", back_populates="user", cascade="all, delete-orphan")
    user_groups = relationship("UserGroupMembership", back_populates="user", cascade="all, delete-orphan")
    activities = relationship("UserActivity", back_populates="user", cascade="all, delete-orphan")
    
    # Association proxies
    groups = association_proxy("user_groups", "group")
    
    @hybrid_property
    def full_name(self) -> Optional[str]:
        """Return the user's full name."""
        if self.first_name and self.last_name:
            return f"{self.first_name} {self.last_name}"
        return self.display_name or self.username
    
    @full_name.expression
    def full_name(cls):
        """SQL expression for full name."""
        return func.coalesce(
            func.concat(cls.first_name, ' ', cls.last_name),
            cls.display_name,
            cls.username
        )
    
    @hybrid_property
    def is_active(self) -> bool:
        """Check if user account is active."""
        return self.status == AccountStatus.ACTIVE
    
    @is_active.expression
    def is_active(cls):
        """SQL expression for active status."""
        return cls.status == AccountStatus.ACTIVE.value
    
    @hybrid_property
    def is_admin(self) -> bool:
        """Check if user has admin role."""
        return self.role == UserRole.ADMIN
    
    @validates("email")
    def validate_email(self, key: str, email: str) -> str:
        """Validate email format."""
        if "@" not in email:
            raise ValueError("Invalid email address")
        return email.lower()
    
    @validates("username")
    def validate_username(self, key: str, username: str) -> str:
        """Validate username format."""
        if not username or len(username) < 3:
            raise ValueError("Username must be at least 3 characters")
        if not username.isalnum() and "_" not in username:
            raise ValueError("Username can only contain alphanumeric characters and underscores")
        return username.lower()
    
    def __repr__(self) -> str:
        return f"<User(id={self.id}, username='{self.username}', email='{self.email}')>"


class UserSession(Base):
    """
    User session model for tracking authenticated sessions.
    
    Stores session tokens, expiration, and device information.
    """
    __tablename__ = "user_sessions"
    __table_args__ = (
        Index("idx_user_sessions_user_id", "user_id"),
        Index("idx_user_sessions_expires_at", "expires_at"),
        Index("idx_user_sessions_token", "token"),
        Index("idx_user_sessions_refresh_token", "refresh_token"),
    )
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    token = Column(String(500), nullable=False, unique=True)
    refresh_token = Column(String(500), unique=True)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    refresh_expires_at = Column(DateTime(timezone=True))
    device_type = Column(String(50))
    device_name = Column(String(100))
    browser = Column(String(100))
    platform = Column(String(100))
    ip_address = Column(INET)
    user_agent = Column(Text)
    location = Column(JSONB)
    is_revoked = Column(Boolean, default=False, nullable=False)
    last_accessed_at = Column(DateTime(timezone=True), default=func.now(), nullable=False)
    created_at = Column(DateTime(timezone=True), default=func.now(), nullable=False)
    
    # Relationships
    user = relationship("User", back_populates="sessions")
    
    @hybrid_property
    def is_valid(self) -> bool:
        """Check if session is valid and not expired."""
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)
        return not self.is_revoked and self.expires_at > now
    
    @is_valid.expression
    def is_valid(cls):
        """SQL expression for valid session."""
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)
        return (cls.is_revoked.is_(False)) & (cls.expires_at > now)
    
    def __repr__(self) -> str:
        return f"<UserSession(id={self.id}, user_id={self.user_id}, expires_at={self.expires_at})>"


class UserProfile(Base):
    """
    Extended user profile information.
    
    Stores additional user details not in the main user table.
    """
    __tablename__ = "user_profiles"
    __table_args__ = (
        UniqueConstraint("user_id", name="uq_user_profiles_user_id"),
        Index("idx_user_profiles_location", "country", "city"),
    )
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)
    date_of_birth = Column(Date)
    gender = Column(String(20))
    phone_number = Column(String(30))
    website = Column(String(500))
    company = Column(String(200))
    job_title = Column(String(200))
    address_line1 = Column(String(255))
    address_line2 = Column(String(255))
    city = Column(String(100))
    state = Column(String(100))
    country = Column(String(100))
    postal_code = Column(String(20))
    latitude = Column(Float)
    longitude = Column(Float)
    social_links = Column(JSONB, default=dict, nullable=False)
    education = Column(JSONB, default=list, nullable=False)
    work_experience = Column(JSONB, default=list, nullable=False)
    skills = Column(PG_ARRAY(String), default=[], nullable=False)
    interests = Column(PG_ARRAY(String), default=[], nullable=False)
    languages = Column(JSONB, default=list, nullable=False)
    certifications = Column(JSONB, default=list, nullable=False)
    created_at = Column(DateTime(timezone=True), default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=func.now(), onupdate=func.now(), nullable=False)
    
    # Relationships
    user = relationship("User", back_populates="profiles")
    
    @hybrid_property
    def age(self) -> Optional[int]:
        """Calculate age from date of birth."""
        from datetime import date
        if not self.date_of_birth:
            return None
        today = date.today()
        return today.year - self.date_of_birth.year - (
            (today.month, today.day) < (self.date_of_birth.month, self.date_of_birth.day)
        )
    
    def __repr__(self) -> str:
        return f"<UserProfile(id={self.id}, user_id={self.user_id})>"


class Post(Base):
    """
    Content post model.
    
    Stores blog posts, articles, tutorials, etc.
    """
    __tablename__ = "posts"
    __table_args__ = (
        Index("idx_posts_author_id", "author_id"),
        Index("idx_posts_slug", "slug"),
        Index("idx_posts_status_published_at", "status", "published_at"),
        Index("idx_posts_category_id", "category_id"),
        Index("idx_posts_created_at", "created_at"),
        Index("idx_posts_title_tsvector", func.to_tsvector("english", "title")),
        Index("idx_posts_content_tsvector", func.to_tsvector("english", "content")),
    )
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, nullable=False)
    author_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    category_id = Column(UUID(as_uuid=True), ForeignKey("categories.id", ondelete="SET NULL"), nullable=True, index=True)
    title = Column(String(500), nullable=False)
    slug = Column(String(500), nullable=False, unique=True)
    excerpt = Column(Text)
    content = Column(Text, nullable=False)
    content_type = Column(Enum(ContentType), default=ContentType.ARTICLE, nullable=False)
    status = Column(String(50), default="draft", nullable=False)
    featured_image = Column(String(500))
    meta_title = Column(String(500))
    meta_description = Column(Text)
    meta_keywords = Column(PG_ARRAY(String), default=[], nullable=False)
    reading_time = Column(Integer, default=0, nullable=False)
    word_count = Column(Integer, default=0, nullable=False)
    view_count = Column(Integer, default=0, nullable=False)
    like_count = Column(Integer, default=0, nullable=False)
    comment_count = Column(Integer, default=0, nullable=False)
    share_count = Column(Integer, default=0, nullable=False)
    is_featured = Column(Boolean, default=False, nullable=False)
    is_pinned = Column(Boolean, default=False, nullable=False)
    allow_comments = Column(Boolean, default=True, nullable=False)
    published_at = Column(DateTime(timezone=True))
    scheduled_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=func.now(), onupdate=func.now(), nullable=False)
    deleted_at = Column(DateTime(timezone=True))
    
    # Relationships
    author = relationship("User", back_populates="posts")
    category = relationship("Category", back_populates="posts")
    comments = relationship("Comment", back_populates="post", cascade="all, delete-orphan")
    tags = relationship("PostTag", back_populates="post", cascade="all, delete-orphan")
    attachments = relationship("PostAttachment", back_populates="post", cascade="all, delete-orphan")
    
    # Association proxies
    tag_names = association_proxy("tags", "tag_name")
    
    @hybrid_property
    def is_published(self) -> bool:
        """Check if post is published."""
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)
        return (
            self.status == "published" and 
            self.published_at is not None and 
            self.published_at <= now
        )
    
    @is_published.expression
    def is_published(cls):
        """SQL expression for published status."""
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)
        return (
            (cls.status == "published") & 
            (cls.published_at.isnot(None)) & 
            (cls.published_at <= now)
        )
    
    @validates("slug")
    def validate_slug(self, key: str, slug: str) -> str:
        """Validate and normalize slug."""
        import re
        # Convert to lowercase and replace spaces with hyphens
        slug = slug.lower().strip()
        slug = re.sub(r'[^\w\s-]', '', slug)
        slug = re.sub(r'[-\s]+', '-', slug)
        return slug
    
    def __repr__(self) -> str:
        return f"<Post(id={self.id}, title='{self.title}', status='{self.status}')>"


class Category(Base):
    """
    Content category model.
    
    Organizes posts into hierarchical categories.
    """
    __tablename__ = "categories"
    __table_args__ = (
        UniqueConstraint("slug", name="uq_categories_slug"),
        Index("idx_categories_parent_id", "parent_id"),
        Index("idx_categories_slug", "slug"),
    )
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, nullable=False)
    parent_id = Column(UUID(as_uuid=True), ForeignKey("categories.id", ondelete="SET NULL"), nullable=True, index=True)
    name = Column(String(200), nullable=False)
    slug = Column(String(200), nullable=False, unique=True)
    description = Column(Text)
    icon = Column(String(100))
    color = Column(String(7))
    sort_order = Column(Integer, default=0, nullable=False)
    post_count = Column(Integer, default=0, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    is_featured = Column(Boolean, default=False, nullable=False)
    meta_title = Column(String(500))
    meta_description = Column(Text)
    created_at = Column(DateTime(timezone=True), default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=func.now(), onupdate=func.now(), nullable=False)
    
    # Relationships
    parent = relationship("Category", remote_side=[id], backref=backref("children", cascade="all, delete-orphan"))
    posts = relationship("Post", back_populates="category")
    
    @hybrid_property
    def full_path(self) -> str:
        """Get full category path as string."""
        if