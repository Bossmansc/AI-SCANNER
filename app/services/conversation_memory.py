import logging
import json
from datetime import datetime
from typing import Dict, List, Any, Optional
from uuid import uuid4
from pathlib import Path

logger = logging.getLogger(__name__)

class ConversationMemory:
    """Manages conversation history and context."""
    
    def __init__(self, conversation_id: Optional[str] = None, max_history: int = 20):
        """
        Initialize conversation memory.
        
        Args:
            conversation_id: Unique ID for the conversation
            max_history: Maximum number of messages to keep in memory
        """
        self.conversation_id = conversation_id or str(uuid4())
        self.max_history = max_history
        self.messages: List[Dict[str, Any]] = []
        self.created_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()
        self.document_contexts: Dict[str, List[Dict[str, Any]]] = {}  # book_id -> [chunks]
        
        # Try to load existing conversation
        self._load_from_disk()
    
    def _get_storage_path(self) -> Path:
        """Get file path for storing conversation."""
        storage_dir = Path("conversations")
        storage_dir.mkdir(exist_ok=True)
        return storage_dir / f"{self.conversation_id}.json"
    
    def _load_from_disk(self):
        """Load conversation from disk if it exists."""
        storage_path = self._get_storage_path()
        if storage_path.exists():
            try:
                with open(storage_path, 'r') as f:
                    data = json.load(f)
                    self.messages = data.get('messages', [])
                    self.document_contexts = data.get('document_contexts', {})
                    self.created_at = datetime.fromisoformat(data.get('created_at', self.created_at.isoformat()))
                    self.updated_at = datetime.fromisoformat(data.get('updated_at', self.updated_at.isoformat()))
                logger.info(f"Loaded conversation {self.conversation_id} from disk")
            except Exception as e:
                logger.error(f"Failed to load conversation from disk: {e}")
    
    def save_to_disk(self):
        """Save conversation to disk."""
        try:
            storage_path = self._get_storage_path()
            data = {
                'conversation_id': self.conversation_id,
                'messages': self.messages[-self.max_history:],  # Only save recent history
                'document_contexts': self.document_contexts,
                'created_at': self.created_at.isoformat(),
                'updated_at': self.updated_at.isoformat(),
                'max_history': self.max_history
            }
            with open(storage_path, 'w') as f:
                json.dump(data, f, indent=2)
            logger.debug(f"Saved conversation {self.conversation_id} to disk")
        except Exception as e:
            logger.error(f"Failed to save conversation to disk: {e}")
    
    def add_message(
        self, 
        role: str, 
        content: str, 
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Add a message to the conversation.
        
        Args:
            role: 'user' or 'assistant'
            content: Message content
            metadata: Additional metadata
            
        Returns:
            The message object
        """
        message = {
            'id': str(uuid4()),
            'role': role,
            'content': content,
            'timestamp': datetime.utcnow().isoformat(),
            'metadata': metadata or {}
        }
        
        self.messages.append(message)
        self.updated_at = datetime.utcnow()
        
        # Trim history if needed
        if len(self.messages) > self.max_history:
            self.messages = self.messages[-self.max_history:]
        
        # Auto-save to disk
        self.save_to_disk()
        
        return message
    
    def add_document_context(
        self, 
        book_id: str, 
        chunks: List[Dict[str, Any]],
        query: Optional[str] = None
    ):
        """
        Add document context from a book for the current conversation.
        
        Args:
            book_id: Identifier for the book
            chunks: Retrieved document chunks
            query: Original query that retrieved these chunks
        """
        if not chunks:
            return
        
        context_entry = {
            'chunks': chunks,
            'query': query,
            'retrieved_at': datetime.utcnow().isoformat(),
            'count': len(chunks)
        }
        
        if book_id not in self.document_contexts:
            self.document_contexts[book_id] = []
        
        self.document_contexts[book_id].append(context_entry)
        
        # Keep only recent context entries per book
        if len(self.document_contexts[book_id]) > 5:
            self.document_contexts[book_id] = self.document_contexts[book_id][-5:]
    
    def get_recent_context(
        self, 
        book_id: Optional[str] = None,
        max_chunks: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Get recent document context for the conversation.
        
        Args:
            book_id: Specific book or None for all books
            max_chunks: Maximum number of chunks to return
            
        Returns:
            List of recent document chunks
        """
        all_chunks = []
        
        if book_id:
            if book_id in self.document_contexts:
                for context in self.document_contexts[book_id][-3:]:  # Last 3 retrievals
                    all_chunks.extend(context['chunks'])
        else:
            for book_contexts in self.document_contexts.values():
                for context in book_contexts[-2:]:  # Last 2 retrievals per book
                    all_chunks.extend(context['chunks'])
        
        # Deduplicate by chunk text
        seen_texts = set()
        unique_chunks = []
        for chunk in all_chunks:
            text = chunk.get('text', '')
            if text and text not in seen_texts:
                seen_texts.add(text)
                unique_chunks.append(chunk)
        
        return unique_chunks[:max_chunks]
    
    def get_conversation_history(
        self, 
        include_system: bool = False,
        last_n: Optional[int] = None
    ) -> List[Dict[str, str]]:
        """
        Get conversation history in OpenAI format.
        
        Args:
            include_system: Whether to include system message
            last_n: Number of recent messages to return
            
        Returns:
            List of messages in OpenAI format
        """
        messages = []
        
        # Add system message if requested
        if include_system:
            messages.append({
                'role': 'system',
                'content': 'You are a helpful assistant with access to document context. Use the provided document context when relevant, but also use your general knowledge.'
            })
        
        # Add conversation history
        history = self.messages if last_n is None else self.messages[-last_n:]
        for msg in history:
            messages.append({
                'role': msg['role'],
                'content': msg['content']
            })
        
        return messages
    
    def clear(self):
        """Clear conversation memory."""
        self.messages = []
        self.document_contexts = {}
        self.updated_at = datetime.utcnow()
        self.save_to_disk()
    
    def get_stats(self) -> Dict[str, Any]:
        """Get conversation statistics."""
        return {
            'conversation_id': self.conversation_id,
            'message_count': len(self.messages),
            'user_messages': len([m for m in self.messages if m['role'] == 'user']),
            'assistant_messages': len([m for m in self.messages if m['role'] == 'assistant']),
            'books_referenced': list(self.document_contexts.keys()),
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }


class ConversationManager:
    """Manages multiple conversations."""
    
    def __init__(self):
        self.conversations: Dict[str, ConversationMemory] = {}
    
    def get_conversation(
        self, 
        conversation_id: Optional[str] = None,
        create_new: bool = True
    ) -> Optional[ConversationMemory]:
        """
        Get a conversation by ID.
        
        Args:
            conversation_id: Conversation ID or None for new
            create_new: Whether to create new conversation if not found
            
        Returns:
            ConversationMemory instance or None
        """
        if conversation_id and conversation_id in self.conversations:
            return self.conversations[conversation_id]
        
        if create_new:
            conv = ConversationMemory(conversation_id)
            self.conversations[conv.conversation_id] = conv
            return conv
        
        return None
    
    def delete_conversation(self, conversation_id: str) -> bool:
        """
        Delete a conversation.
        
        Args:
            conversation_id: ID of conversation to delete
            
        Returns:
            True if deleted successfully
        """
        if conversation_id in self.conversations:
            # Delete from memory
            del self.conversations[conversation_id]
            
            # Delete from disk
            storage_path = Path("conversations") / f"{conversation_id}.json"
            if storage_path.exists():
                storage_path.unlink()
            
            logger.info(f"Deleted conversation: {conversation_id}")
            return True
        
        return False
    
    def cleanup_old_conversations(self, max_age_hours: int = 24):
        """
        Clean up old conversations from disk.
        
        Args:
            max_age_hours: Maximum age in hours
        """
        conversations_dir = Path("conversations")
        if not conversations_dir.exists():
            return
        
        cutoff_time = datetime.utcnow().timestamp() - (max_age_hours * 3600)
        
        for file_path in conversations_dir.glob("*.json"):
            try:
                if file_path.stat().st_mtime