"""
File processing service for handling document uploads, validation, and processing.
Centralizes file operations with robust error handling and import structure.
"""

import os
import io
import hashlib
import mimetypes
import tempfile
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union, BinaryIO, Any
from concurrent.futures import ThreadPoolExecutor, as_completed

from werkzeug.datastructures import FileStorage
from werkzeug.utils import secure_filename

from app.core.config import settings
from app.core.exceptions import (
    FileProcessingError,
    ValidationError,
    StorageError,
    UnsupportedFileTypeError,
    FileSizeExceededError,
    FileCorruptionError
)
from app.core.logging import get_logger
from app.models.file_metadata import FileMetadata
from app.services.storage.base import StorageService
from app.services.storage.factory import get_storage_service
from app.services.validator import FileValidator
from app.utils.file_utils import (
    calculate_file_hash,
    get_file_extension,
    normalize_filename,
    sanitize_filepath,
    ensure_directory_exists
)

logger = get_logger(__name__)


class FileProcessor:
    """
    Main file processing service that orchestrates file validation,
    storage, and metadata management.
    """
    
    def __init__(self, storage_service: Optional[StorageService] = None):
        """
        Initialize the file processor.
        
        Args:
            storage_service: Optional storage service instance. If not provided,
                           uses the default from factory.
        """
        self.storage_service = storage_service or get_storage_service()
        self.validator = FileValidator()
        self._executor = ThreadPoolExecutor(
            max_workers=settings.FILE_PROCESSING_MAX_WORKERS
        )
        
        # Ensure temp directory exists
        self.temp_dir = Path(settings.TEMP_FILE_DIRECTORY)
        ensure_directory_exists(self.temp_dir)
    
    def process_upload(
        self,
        file_storage: FileStorage,
        user_id: str,
        collection_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        process_async: bool = False
    ) -> Union[FileMetadata, str]:
        """
        Process a file upload from a FileStorage object.
        
        Args:
            file_storage: The uploaded file from request
            user_id: ID of the user uploading the file
            collection_id: Optional collection ID for grouping files
            metadata: Additional metadata to attach to the file
            process_async: If True, returns a job ID for async processing
            
        Returns:
            FileMetadata object if synchronous, job ID string if async
            
        Raises:
            ValidationError: If file validation fails
            FileProcessingError: If processing fails
            StorageError: If storage operations fail
        """
        try:
            # Validate input
            if not file_storage:
                raise ValidationError("No file provided")
            
            if not user_id:
                raise ValidationError("User ID is required")
            
            # Start processing
            logger.info(
                f"Processing upload for user {user_id}, "
                f"filename: {file_storage.filename}"
            )
            
            if process_async:
                # Queue for async processing
                job_id = self._queue_async_processing(
                    file_storage, user_id, collection_id, metadata
                )
                return job_id
            
            # Synchronous processing
            return self._process_file_sync(
                file_storage, user_id, collection_id, metadata
            )
            
        except (ValidationError, UnsupportedFileTypeError, FileSizeExceededError) as e:
            logger.warning(f"Upload validation failed: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error during upload processing: {str(e)}")
            raise FileProcessingError(f"Failed to process upload: {str(e)}")
    
    def _process_file_sync(
        self,
        file_storage: FileStorage,
        user_id: str,
        collection_id: Optional[str],
        metadata: Optional[Dict[str, Any]]
    ) -> FileMetadata:
        """
        Synchronously process a file.
        
        Args:
            file_storage: The uploaded file
            user_id: User ID
            collection_id: Optional collection ID
            metadata: Additional metadata
            
        Returns:
            FileMetadata object
        """
        # Create temporary file for processing
        temp_file_path = None
        try:
            # Save to temp file for validation and processing
            temp_file_path = self._save_to_temp(file_storage)
            
            # Validate file
            self.validator.validate_file(
                file_path=temp_file_path,
                filename=file_storage.filename,
                content_type=file_storage.content_type
            )
            
            # Calculate file hash
            file_hash = calculate_file_hash(temp_file_path)
            
            # Check for duplicate files
            existing_file = self._check_duplicate(file_hash, user_id)
            if existing_file:
                logger.info(f"Duplicate file found: {existing_file.id}")
                # Update metadata if needed
                if metadata:
                    self._update_file_metadata(existing_file.id, metadata)
                return existing_file
            
            # Generate secure filename and path
            original_filename = secure_filename(file_storage.filename)
            storage_filename = self._generate_storage_filename(
                original_filename, user_id
            )
            storage_path = self._generate_storage_path(
                user_id, collection_id, storage_filename
            )
            
            # Extract additional metadata
            extracted_metadata = self._extract_file_metadata(
                temp_file_path, original_filename
            )
            
            # Merge with provided metadata
            final_metadata = self._merge_metadata(
                extracted_metadata, metadata or {}
            )
            
            # Upload to storage
            with open(temp_file_path, 'rb') as f:
                file_size = os.path.getsize(temp_file_path)
                storage_url = self.storage_service.upload(
                    file_obj=f,
                    file_path=storage_path,
                    content_type=file_storage.content_type,
                    metadata=final_metadata
                )
            
            # Create file metadata record
            file_metadata = FileMetadata(
                id=str(uuid.uuid4()),
                user_id=user_id,
                original_filename=original_filename,
                storage_filename=storage_filename,
                storage_path=storage_path,
                storage_url=storage_url,
                file_size=file_size,
                content_type=file_storage.content_type or mimetypes.guess_type(original_filename)[0],
                file_hash=file_hash,
                collection_id=collection_id,
                metadata=final_metadata,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            
            # Save to database
            self._save_metadata_to_db(file_metadata)
            
            logger.info(
                f"File processed successfully: {file_metadata.id}, "
                f"size: {file_size} bytes"
            )
            
            return file_metadata
            
        finally:
            # Clean up temp file
            if temp_file_path and os.path.exists(temp_file_path):
                try:
                    os.unlink(temp_file_path)
                except Exception as e:
                    logger.warning(f"Failed to delete temp file {temp_file_path}: {e}")
    
    def process_multiple(
        self,
        files: List[FileStorage],
        user_id: str,
        collection_id: Optional[str] = None,
        metadata_list: Optional[List[Dict[str, Any]]] = None,
        parallel: bool = True
    ) -> List[FileMetadata]:
        """
        Process multiple files.
        
        Args:
            files: List of FileStorage objects
            user_id: User ID
            collection_id: Optional collection ID
            metadata_list: Optional list of metadata dicts (one per file)
            parallel: Whether to process files in parallel
            
        Returns:
            List of FileMetadata objects
        """
        if not files:
            return []
        
        if metadata_list and len(metadata_list) != len(files):
            raise ValidationError(
                "metadata_list must have same length as files if provided"
            )
        
        results = []
        
        if parallel:
            # Process files in parallel
            futures = {}
            for i, file_storage in enumerate(files):
                metadata = metadata_list[i] if metadata_list else None
                future = self._executor.submit(
                    self._process_file_sync,
                    file_storage,
                    user_id,
                    collection_id,
                    metadata
                )
                futures[future] = i
            
            # Collect results
            for future in as_completed(futures):
                try:
                    result = future.result()
                    results.append(result)
                except Exception as e:
                    idx = futures[future]
                    filename = files[idx].filename if idx < len(files) else "unknown"
                    logger.error(f"Failed to process file {filename}: {e}")
                    raise FileProcessingError(
                        f"Failed to process file {filename}: {str(e)}"
                    )
        else:
            # Process files sequentially
            for i, file_storage in enumerate(files):
                try:
                    metadata = metadata_list[i] if metadata_list else None
                    result = self._process_file_sync(
                        file_storage, user_id, collection_id, metadata
                    )
                    results.append(result)
                except Exception as e:
                    filename = file_storage.filename
                    logger.error(f"Failed to process file {filename}: {e}")
                    # Optionally continue with other files or re-raise
                    raise FileProcessingError(
                        f"Failed to process file {filename}: {str(e)}"
                    )
        
        return results
    
    def get_file(
        self,
        file_id: str,
        user_id: Optional[str] = None,
        include_content: bool = False
    ) -> Union[FileMetadata, Tuple[FileMetadata, bytes]]:
        """
        Retrieve a file by ID.
        
        Args:
            file_id: File ID
            user_id: Optional user ID for authorization check
            include_content: Whether to include file content
            
        Returns:
            FileMetadata or tuple of (FileMetadata, content bytes)
            
        Raises:
            FileProcessingError: If file not found or access denied
        """
        try:
            # Get metadata from database
            file_metadata = self._get_metadata_from_db(file_id)
            
            if not file_metadata:
                raise FileProcessingError(f"File not found: {file_id}")
            
            # Check authorization if user_id provided
            if user_id and file_metadata.user_id != user_id:
                raise FileProcessingError(
                    f"Access denied to file: {file_id}"
                )
            
            if include_content:
                # Download file content
                content = self.storage_service.download(file_metadata.storage_path)
                return file_metadata, content
            
            return file_metadata
            
        except Exception as e:
            logger.error(f"Failed to get file {file_id}: {str(e)}")
            raise FileProcessingError(f"Failed to retrieve file: {str(e)}")
    
    def delete_file(
        self,
        file_id: str,
        user_id: Optional[str] = None,
        soft_delete: bool = True
    ) -> bool:
        """
        Delete a file.
        
        Args:
            file_id: File ID
            user_id: Optional user ID for authorization
            soft_delete: If True, only marks as deleted in DB
            
        Returns:
            True if successful
            
        Raises:
            FileProcessingError: If deletion fails
        """
        try:
            # Get file metadata
            file_metadata = self._get_metadata_from_db(file_id)
            
            if not file_metadata:
                raise FileProcessingError(f"File not found: {file_id}")
            
            # Check authorization if user_id provided
            if user_id and file_metadata.user_id != user_id:
                raise FileProcessingError(
                    f"Access denied to delete file: {file_id}"
                )
            
            if soft_delete:
                # Soft delete - mark as deleted in DB
                self._soft_delete_metadata(file_id)
                logger.info(f"File soft deleted: {file_id}")
            else:
                # Hard delete - remove from storage and DB
                # Delete from storage
                self.storage_service.delete(file_metadata.storage_path)
                
                # Delete from database
                self._hard_delete_metadata(file_id)
                
                logger.info(f"File hard deleted: {file_id}")
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to delete file {file_id}: {str(e)}")
            raise FileProcessingError(f"Failed to delete file: {str(e)}")
    
    def update_file_metadata(
        self,
        file_id: str,
        metadata_updates: Dict[str, Any],
        user_id: Optional[str] = None
    ) -> FileMetadata:
        """
        Update file metadata.
        
        Args:
            file_id: File ID
            metadata_updates: Metadata fields to update
            user_id: Optional user ID for authorization
            
        Returns:
            Updated FileMetadata
            
        Raises:
            FileProcessingError: If update fails
        """
        try:
            # Get current metadata
            file_metadata = self._get_metadata_from_db(file_id)
            
            if not file_metadata:
                raise FileProcessingError(f"File not found: {file_id}")
            
            # Check authorization if user_id provided
            if user_id and file_metadata.user_id != user_id:
                raise FileProcessingError(
                    f"Access denied to update file: {file_id}"
                )
            
            # Update metadata
            updated_metadata = self._update_metadata_in_db(
                file_id, metadata_updates
            )
            
            logger.info(f"File metadata updated: {file_id}")
            
            return updated_metadata
            
        except Exception as e:
            logger.error(f"Failed to update file metadata {file_id}: {str(e)}")
            raise FileProcessingError(f"Failed to update file metadata: {str(e)}")
    
    def _save_to_temp(self, file_storage: FileStorage) -> str:
        """
        Save FileStorage to temporary file.
        
        Args:
            file_storage: FileStorage object
            
        Returns:
            Path to temporary file
        """
        try:
            # Create temp file
            temp_fd, temp_path = tempfile.mkstemp(
                dir=self.temp_dir,
                prefix='upload_',
                suffix=get_file_extension(file_storage.filename)
            )
            
            # Write content
            with os.fdopen(temp_fd, 'wb') as f:
                chunk_size = 8192  # 8KB chunks
                while True:
                    chunk = file_storage.read(chunk_size)
                    if not chunk:
                        break
                    f.write(chunk)
            
            # Reset file pointer
            file_storage.seek(0)
            
            return temp_path
            
        except Exception as e:
            logger.error(f"Failed to save file to temp: {str(e)}")
            raise FileProcessingError(f"Failed to save temporary file: {str(e)}")
    
    def _generate_storage_filename(
        self,
        original_filename: str,
        user_id: str
    ) -> str:
        """
        Generate a secure storage filename.
        
        Args:
            original_filename: Original filename
            user_id: User ID
            
        Returns:
            Generated filename
        """
        # Get file extension
        ext = get_file_extension(original_filename)
        
        # Generate unique filename
        unique_id = str(uuid.uuid4())
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        
        # Create base name without extension
        base_name = Path(original_filename).stem
        safe_base_name = secure_filename(base_name)[:50]  # Limit length
        
        # Construct final filename
        filename = f"{user_id}_{timestamp}_{unique_id}_{safe_base_name}{ext}"
        
        return normalize_filename(filename)
    
    def _generate_storage_path(
        self,
        user_id: str,
        collection_id: Optional[str],
        filename: str
    ) -> str:
        """
        Generate storage path for a file.
        
        Args:
            user_id: User ID
            collection_id: Optional collection ID
            filename: Filename
            
        Returns:
            Storage path
        """
        # Base user directory
        path_parts = [settings.STORAGE_BASE_PATH, user_id]
        
        # Add collection directory if provided
        if collection_id:
            path_parts.append(collection_id)
        
        # Add filename
        path_parts.append(filename)
        
        # Join and sanitize
        path = os.path.join(*path_parts)
        return sanitize_filepath(path)
    
    def _extract_file_metadata(
        self,
        file_path: str,
        filename: str
    ) -> Dict[str, Any]:
        """
        Extract metadata from a file.
        
        Args:
            file_path: Path to the file
            filename: Original filename
            
        Returns:
            Dictionary of extracted metadata
        """
        metadata = {
            'filename': filename,
            'file_size': os.path.getsize(file_path),
            'file_extension': get_file_extension(filename),
            'last_modified': datetime.utcnow().isoformat()
        }
        
        try:
            # Try to extract more metadata based on file type
            file_ext = metadata['file_extension'].lower()
            
            if file_ext in ['.txt', '.md', '.csv', '.json', '.xml']:
                # Text files - try to get encoding and line count
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                        metadata['character_count'] = len(content)
                        metadata['line_count'] = content.count('\n') + 1
                except:
                    pass  # Skip if can't read as text
            
            elif file_ext in ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff']:
                # Image files
                try:
                    from PIL import Image
                    with Image.open(file_path) as img:
                        metadata['image_width'] = img.width
                        metadata['image_height'] = img.height
                        metadata['image_mode'] = img.mode
                        metadata['image_format'] = img.format
                except ImportError:
                    logger.warning("PIL not installed, skipping image metadata")
                except Exception:
                    pass  # Skip if can't extract image metadata
            
        except Exception as e:
            logger.warning(f"Failed to extract additional metadata: {e}")
        
        return metadata
    
    def _merge_metadata(
        self,
        extracted: Dict[str, Any],
        provided: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Merge extracted and provided metadata.
        
        Args:
            extracted: Extracted metadata
            provided: User-provided metadata
            
        Returns:
            Merged metadata
        """
        #