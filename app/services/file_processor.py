import os
import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union
import PyPDF2
from ebooklib import epub
from docx import Document
import aiofiles
import hashlib
import re

logger = logging.getLogger(__name__)

class FileProcessor:
    """Processes uploaded files and extracts text content."""
    
    SUPPORTED_EXTENSIONS = {
        '.pdf': 'PDF',
        '.epub': 'EPUB',
        '.txt': 'Text',
        '.docx': 'Word',
        '.md': 'Markdown',
    }
    
    @staticmethod
    def is_supported_file(filename: str) -> bool:
        """Check if file extension is supported."""
        ext = Path(filename).suffix.lower()
        return ext in FileProcessor.SUPPORTED_EXTENSIONS
    
    @staticmethod
    def get_file_hash(file_path: Path) -> str:
        """Generate MD5 hash of file for deduplication."""
        with open(file_path, 'rb') as f:
            file_hash = hashlib.md5(f.read()).hexdigest()
        return file_hash
    
    @staticmethod
    async def save_uploaded_file(upload_file, upload_dir: Path) -> Tuple[Path, str]:
        """Save uploaded file and return its path and hash."""
        upload_dir.mkdir(exist_ok=True)
        file_path = upload_dir / upload_file.filename
        
        # Save file asynchronously
        async with aiofiles.open(file_path, 'wb') as out_file:
            content = await upload_file.read()
            await out_file.write(content)
        
        # Generate file hash
        file_hash = FileProcessor.get_file_hash(file_path)
        
        return file_path, file_hash
    
    @staticmethod
    def extract_text_from_pdf(file_path: Path) -> str:
        """Extract text from PDF file."""
        text = ""
        try:
            with open(file_path, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)
                for page_num, page in enumerate(pdf_reader.pages):
                    page_text = page.extract_text()
                    if page_text:
                        text += f"--- Page {page_num + 1} ---\n{page_text}\n\n"
        except Exception as e:
            logger.error(f"Error extracting text from PDF {file_path}: {e}")
            raise ValueError(f"Failed to process PDF: {str(e)}")
        return text
    
    @staticmethod
    def extract_text_from_epub(file_path: Path) -> str:
        """Extract text from EPUB file."""
        text = ""
        try:
            book = epub.read_epub(str(file_path))
            for item in book.get_items():
                if item.get_type() == epub.ITEM_DOCUMENT:
                    # Clean HTML tags (simple approach)
                    content = item.get_content().decode('utf-8', errors='ignore')
                    clean_text = re.sub(r']*>', '', content)
                    clean_text = re.sub(r'\s+', ' ', clean_text).strip()
                    if clean_text:
                        text += clean_text + "\n\n"
        except Exception as e:
            logger.error(f"Error extracting text from EPUB {file_path}: {e}")
            raise ValueError(f"Failed to process EPUB: {str(e)}")
        return text
    
    @staticmethod
    def extract_text_from_txt(file_path: Path) -> str:
        """Extract text from plain text file."""
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as file:
                text = file.read()
        except UnicodeDecodeError:
            # Try different encoding
            with open(file_path, 'r', encoding='latin-1', errors='ignore') as file:
                text = file.read()
        except Exception as e:
            logger.error(f"Error extracting text from TXT {file_path}: {e}")
            raise ValueError(f"Failed to process text file: {str(e)}")
        return text
    
    @staticmethod
    def extract_text_from_docx(file_path: Path) -> str:
        """Extract text from Word document."""
        text = ""
        try:
            doc = Document(file_path)
            for paragraph in doc.paragraphs:
                if paragraph.text.strip():
                    text += paragraph.text + "\n"
        except Exception as e:
            logger.error(f"Error extracting text from DOCX {file_path}: {e}")
            raise ValueError(f"Failed to process Word document: {str(e)}")
        return text
    
    @staticmethod
    def extract_text_from_markdown(file_path: Path) -> str:
        """Extract text from Markdown file."""
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as file:
                text = file.read()
        except Exception as e:
            logger.error(f"Error extracting text from Markdown {file_path}: {e}")
            raise ValueError(f"Failed to process Markdown file: {str(e)}")
        return text
    
    @staticmethod
    def process_file(file_path: Path) -> Dict[str, Union[str, int]]:
        """
        Main method to process a file and extract text.
        Returns dictionary with text content and metadata.
        """
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        
        ext = file_path.suffix.lower()
        
        # Dispatch to appropriate extractor
        if ext == '.pdf':
            text = FileProcessor.extract_text_from_pdf(file_path)
        elif ext == '.epub':
            text = FileProcessor.extract_text_from_epub(file_path)
        elif ext == '.txt':
            text = FileProcessor.extract_text_from_txt(file_path)
        elif ext == '.docx':
            text = FileProcessor.extract_text_from_docx(file_path)
        elif ext == '.md':
            text = FileProcessor.extract_text_from_markdown(file_path)
        else:
            raise ValueError(f"Unsupported file type: {ext}")
        
        # Get file stats
        file_size = file_path.stat().st_size
        file_hash = FileProcessor.get_file_hash(file_path)
        
        return {
            'text': text,
            'file_path': str(file_path),
            'file_name': file_path.name,
            'file_extension': ext,
            'file_size': file_size,
            'file_hash': file_hash,
            'character_count': len(text),
            'word_count': len(text.split())
        }

# Singleton instance for easy import
file_processor = FileProcessor()