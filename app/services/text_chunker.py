import logging
from typing import Dict, List, Any
import re

logger = logging.getLogger(__name__)

class TextChunker:
    """Splits text into overlapping chunks for embedding."""

    def __init__(
        self,
        chunk_size: int = 1000,
        chunk_overlap: int = 200,
        separators: List[str] = None
    ):
        """
        Initialize chunker with configuration.

        Args:
            chunk_size: Maximum characters per chunk
            chunk_overlap: Overlap between chunks
            separators: List of separators to split on (in order of preference)
        """
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

        if separators is None:
            self.separators = [
                "\n\n",  # Double newlines (paragraphs)
                "\n",    # Single newlines
                ". ",    # Sentences
                "? ",    # Questions
                "! ",    # Exclamations
                "; ",    # Semicolons
                ", ",    # Commas
                " ",     # Spaces
                ""       # No separator (character level)
            ]
        else:
            self.separators = separators

    def _split_text_with_separator(self, text: str, separator: str) -> List[str]:
        """Split text using a specific separator."""
        if separator:
            splits = text.split(separator)
        else:
            splits = list(text)

        # Combine the separator back into each split (except the last one)
        if separator and len(splits) > 1:
            splits = [split + separator for split in splits[:-1]] + [splits[-1]]

        return splits

    def create_chunks(
        self, 
        text: str, 
        metadata: Dict[str, Any],
        depth_level: str = "medium"
    ) -> List[Dict[str, Any]]:
        """
        Create chunks from text with configurable depth.

        Args:
            text: The text to chunk
            metadata: Metadata to attach to each chunk
            depth_level: "shallow", "medium", or "deep" (affects chunk size)

        Returns:
            List of chunk dictionaries with text and metadata
        """
        # Adjust chunk size based on depth level
        depth_config = {
            "shallow": {"chunk_size": 2000, "chunk_overlap": 100},
            "medium": {"chunk_size": 1000, "chunk_overlap": 200},
            "deep": {"chunk_size": 500, "chunk_overlap": 100},
        }

        config = depth_config.get(depth_level, depth_config["medium"])
        effective_chunk_size = config["chunk_size"]
        effective_overlap = config["chunk_overlap"]

        # Clean text
        text = self._clean_text(text)
        if not text:
            return []

        final_chunks = []
        
        # Recursive splitting logic
        def split_text(text_segment: str, separator_index: int = 0) -> List[str]:
            # If we ran out of separators, just return the text as is (or force split if needed)
            if separator_index >= len(self.separators):
                return [text_segment]

            separator = self.separators[separator_index]
            
            # If text is small enough, return it
            if len(text_segment)  effective_chunk_size:
                    # Recurse with next separator
                    result_splits.extend(split_text(split, separator_index + 1))
                else:
                    result_splits.append(split)
                    
            return result_splits

        # Generate raw text chunks
        raw_chunks = split_text(text)

        # Apply overlap and format
        processed_chunks = []
        
        for i, chunk_text in enumerate(raw_chunks):
            chunk_text = chunk_text.strip()
            if not chunk_text:
                continue
                
            chunk_metadata = {
                **metadata,
                "text": chunk_text,
                "chunk_index": i,
                "total_chunks": len(raw_chunks),
                "depth_level": depth_level,
                "char_count": len(chunk_text),
                "word_count": len(chunk_text.split())
            }

            # Add source location if available
            if "page_number" in metadata:
                chunk_metadata["page_number"] = metadata["page_number"]

            processed_chunks.append(chunk_metadata)

        logger.info(f"Created {len(processed_chunks)} chunks from text (depth: {depth_level})")
        return processed_chunks

    def _clean_text(self, text: str) -> str:
        """Clean and normalize text before chunking."""
        # Remove excessive whitespace
        text = re.sub(r'\s+', ' ', text)

        # Remove control characters (except newlines and tabs)
        text = re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]', '', text)

        # Normalize unicode spaces
        text = text.replace('\u200b', '')  # Zero-width space
        text = text.replace('\u00a0', ' ')  # Non-breaking space

        return text.strip()

    def chunk_document(
        self, 
        document_data: Dict[str, Any], 
        depth_level: str = "medium"
    ) -> List[Dict[str, Any]]:
        """
        Convenience method to chunk a document from file processor output.

        Args:
            document_data: Output from FileProcessor.process_file()
            depth_level: Chunking depth level

        Returns:
            List of chunks with combined metadata
        """
        metadata = {
            "file_name": document_data["file_name"],
            "file_path": document_data["file_path"],
            "file_extension": document_data["file_extension"],
            "file_hash": document_data["file_hash"],
        }

        chunks = self.create_chunks(
            text=document_data["text"],
            metadata=metadata,
            depth_level=depth_level
        )

        return chunks

# Default chunker instance
default_chunker = TextChunker()