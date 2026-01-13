import asyncio
import logging
from typing import List, Optional, Dict, Any
from datetime import datetime
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, BackgroundTasks, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel
import shutil
from pathlib import Path

from app.database import get_db
from app.models import Book
from app.config import settings
from app.services.file_processor import file_processor
from app.services.text_chunker import default_chunker
from app.services.vector_store import vector_store_manager

router = APIRouter(prefix="/books", tags=["books"])
logger = logging.getLogger(__name__)

# Pydantic models
class BookResponse(BaseModel):
    id: int
    book_id: str
    title: str
    file_name: str
    file_size: int
    file_type: str
    chunk_count: int
    scan_depth: str
    upload_status: str
    uploaded_at: datetime
    processed_at: Optional[datetime]
    character_count: int
    word_count: int
    book_metadata: Optional[Dict[str, Any]] = {}

    class Config:
        from_attributes = True

class UploadResponse(BaseModel):
    message: str
    book_id: str
    task_id: str

class ProcessingStatus(BaseModel):
    book_id: str
    status: str
    progress: float
    message: Optional[str]

# Helper function for background processing
async def process_uploaded_file(
    file_path: Path,
    file_hash: str,
    book_id: str,
    scan_depth: str,
    db: Session
):
    """Background task to process uploaded file."""
    try:
        # Update book status
        book = db.query(Book).filter(Book.book_id == book_id).first()
        if not book:
            logger.error(f"Book {book_id} not found in database")
            return

        book.upload_status = "processing"
        db.commit()

        # Process file
        logger.info(f"Processing file: {file_path}")
        document_data = file_processor.process_file(file_path)

        # Update book with metadata
        book.title = Path(file_path).stem
        book.file_type = document_data['file_extension']
        book.file_size = document_data['file_size']
        book.character_count = document_data['character_count']
        book.word_count = document_data['word_count']

        # Create chunks
        chunks = default_chunker.chunk_document(document_data, scan_depth)
        book.chunk_count = len(chunks)

        # Add to vector store
        chunk_ids = vector_store_manager.add_document(
            collection_name=book_id,
            chunks=chunks,
            batch_size=50
        )

        # Update book status
        book.upload_status = "completed"
        book.processed_at = datetime.utcnow()
        db.commit()

        logger.info(f"Successfully processed book {book_id} with {len(chunks)} chunks")

    except Exception as e:
        logger.error(f"Error processing file {file_path}: {e}")

        # Update book status with error
        book = db.query(Book).filter(Book.book_id == book_id).first()
        if book:
            book.upload_status = "failed"
            book.processing_error = str(e)
            db.commit()

# Routes
@router.post("/upload", response_model=UploadResponse)
async def upload_book(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    scan_depth: str = Form("medium"),
    title: Optional[str] = Form(None),
    db: Session = Depends(get_db)
):
    """Upload and process a book/document."""

    # Validate file type
    if not file_processor.is_supported_file(file.filename):
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type. Supported types: {', '.join(file_processor.SUPPORTED_EXTENSIONS.keys())}"
        )

    # Check file size (50MB limit)
    max_size = settings.MAX_FILE_SIZE_MB * 1024 * 1024
    file.file.seek(0, 2)  # Seek to end
    file_size = file.file.tell()
    file.file.seek(0)  # Reset to beginning

    if file_size > max_size:
        raise HTTPException(
            status_code=400,
            detail=f"File too large. Maximum size is {settings.MAX_FILE_SIZE_MB}MB"
        )

    try:
        # Save uploaded file
        file_path, file_hash = await file_processor.save_uploaded_file(
            file, settings.UPLOAD_DIR
        )

        # Check for duplicate files
        existing_book = db.query(Book).filter(Book.file_hash == file_hash).first()
        if existing_book:
            # Clean up duplicate file
            file_path.unlink(missing_ok=True)
            raise HTTPException(
                status_code=400,
                detail="This file has already been uploaded",
                headers={"X-Book-ID": existing_book.book_id}
            )

        # Create book record
        book_title = title or Path(file.filename).stem
        db_book = Book(
            title=book_title,
            file_name=file.filename,
            file_path=str(file_path),
            file_hash=file_hash,
            file_size=file_size,
            scan_depth=scan_depth,
            upload_status="pending"
        )

        db.add(db_book)
        db.commit()
        db.refresh(db_book)

        # Start background processing
        background_tasks.add_task(
            process_uploaded_file,
            file_path,
            file_hash,
            db_book.book_id,
            scan_depth,
            db
        )

        return UploadResponse(
            message="File uploaded successfully. Processing started.",
            book_id=db_book.book_id,
            task_id=db_book.book_id
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Upload error: {e}")
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")

@router.get("/", response_model=List[BookResponse])
async def list_books(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """List all uploaded books."""
    books = db.query(Book).order_by(Book.uploaded_at.desc()).offset(skip).limit(limit).all()
    return books

@router.get("/{book_id}", response_model=BookResponse)
async def get_book(book_id: str, db: Session = Depends(get_db)):
    """Get book details by ID."""
    book = db.query(Book).filter(Book.book_id == book_id).first()
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")
    return book

@router.get("/{book_id}/status", response_model=ProcessingStatus)
async def get_processing_status(book_id: str, db: Session = Depends(get_db)):
    """Get processing status of a book."""
    book = db.query(Book).filter(Book.book_id == book_id).first()
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")

    progress = 0.0
    if book.upload_status == "completed":
        progress = 1.0
    elif book.upload_status == "processing":
        progress = 0.5

    return ProcessingStatus(
        book_id=book.book_id,
        status=book.upload_status,
        progress=progress,
        message=book.processing_error
    )

@router.delete("/{book_id}")
async def delete_book(book_id: str, db: Session = Depends(get_db)):
    """Delete a book and its vector store."""
    book = db.query(Book).filter(Book.book_id == book_id).first()
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")

    try:
        # Delete from vector store
        vector_store_manager.delete_collection(book_id)

        # Delete file
        if book.file_path:
            file_path = Path(book.file_path)
            if file_path.exists():
                file_path.unlink()

        # Delete from database
        db.delete(book)
        db.commit()

        return {"message": "Book deleted successfully"}

    except Exception as e:
        logger.error(f"Error deleting book {book_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to delete book: {str(e)}")

@router.post("/search/{book_id}")
async def search_in_book(
    book_id: str,
    query: str,
    k: int = 5,
    score_threshold: float = 0.5
):
    """Search within a specific book."""
    # Verify book exists in vector store
    stats = vector_store_manager.get_collection_stats(book_id)
    if not stats:
        raise HTTPException(status_code=404, detail="Book not found or not processed")

    results = vector_store_manager.search(
        collection_name=book_id,
        query=query,
        k=k,
        score_threshold=score_threshold
    )

    return {
        "book_id": book_id,
        "query": query,
        "results": results,
        "total_found": len(results)
    }