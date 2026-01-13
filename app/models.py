from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, ForeignKey, JSON
from sqlalchemy.sql import func
from datetime import datetime
import uuid
from app.database import Base

def generate_uuid():
    return str(uuid.uuid4())

class User(Base):
    """User model for authentication (future use)."""
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    username = Column(String(100), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True)
    is_superuser = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

class Book(Base):
    """Book/document model."""
    __tablename__ = "books"

    id = Column(Integer, primary_key=True, index=True)
    book_id = Column(String(50), unique=True, index=True, default=generate_uuid)
    title = Column(String(500), nullable=False)
    file_name = Column(String(500), nullable=False)
    file_path = Column(String(1000))
    file_hash = Column(String(64), unique=True, index=True)  # MD5 hash
    file_size = Column(Integer)  # in bytes
    file_type = Column(String(50))
    chunk_count = Column(Integer, default=0)
    scan_depth = Column(String(50), default="medium")  # shallow, medium, deep
    upload_status = Column(String(50), default="pending")  # pending, processing, completed, failed
    processing_error = Column(Text)

    # Metadata
    uploader_id = Column(Integer, ForeignKey("users.id"), nullable=True)  # Future: link to user
    uploaded_at = Column(DateTime(timezone=True), server_default=func.now())
    processed_at = Column(DateTime(timezone=True), nullable=True)

    # Statistics
    character_count = Column(Integer, default=0)
    word_count = Column(Integer, default=0)
    page_count = Column(Integer, default=0)  # For PDFs

    # Additional metadata (Renamed from 'metadata' to avoid SQLAlchemy conflict)
    book_metadata = Column(JSON, default=dict)

class Conversation(Base):
    """Conversation model for database storage."""
    __tablename__ = "conversations"

    id = Column(Integer, primary_key=True, index=True)
    conversation_id = Column(String(50), unique=True, index=True, default=generate_uuid)
    title = Column(String(500), default="New Conversation")

    # User association (future)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)

    # Book associations (JSON list of book_ids)
    book_ids = Column(JSON, default=list)

    # Statistics
    message_count = Column(Integer, default=0)
    token_count = Column(Integer, default=0)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    last_message_at = Column(DateTime(timezone=True), nullable=True)

class Message(Base):
    """Message model for database storage."""
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, index=True)
    message_id = Column(String(50), unique=True, index=True, default=generate_uuid)
    conversation_id = Column(String(50), ForeignKey("conversations.conversation_id"), index=True)

    # Message content
    role = Column(String(20), nullable=False)  # user, assistant, system
    content = Column(Text, nullable=False)

    # Metadata
    token_count = Column(Integer, default=0)
    model_used = Column(String(100))

    # Context information
    book_ids_used = Column(JSON, default=list)
    chunk_count_used = Column(Integer, default=0)
    context_depth = Column(String(20), default="medium")

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class BookChunk(Base):
    """Store chunk metadata for faster retrieval."""
    __tablename__ = "book_chunks"

    id = Column(Integer, primary_key=True, index=True)
    chunk_id = Column(String(50), unique=True, index=True)
    book_id = Column(String(50), ForeignKey("books.book_id"), index=True)

    # Chunk content (partial for preview)
    text_preview = Column(String(500))
    text_length = Column(Integer)

    # Position in document
    chunk_index = Column(Integer)
    total_chunks = Column(Integer)

    # For PDFs
    page_number = Column(Integer, nullable=True)

    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now())