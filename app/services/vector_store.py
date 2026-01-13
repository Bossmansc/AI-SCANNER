import logging
import numpy as np
import faiss
import pickle
import json
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
import uuid
from datetime import datetime

from app.config import settings
from app.services.embeddings import embedding_service

logger = logging.getLogger(__name__)

class VectorStore:
    """Manages FAISS vector stores for different document collections."""
    
    def __init__(self, collection_name: str):
        """
        Initialize a vector store for a specific collection.
        
        Args:
            collection_name: Name of the collection (usually book/file identifier)
        """
        self.collection_name = collection_name
        self.collection_id = str(uuid.uuid4())[:8]
        self.index = None
        self.metadata = []
        self.dimension = embedding_service.dimension
        self.is_trained = False
        self.total_chunks = 0
        
        # File paths for persistence
        self.base_dir = settings.VECTOR_STORE_DIR / collection_name
        self.base_dir.mkdir(parents=True, exist_ok=True)
        
        self.index_file = self.base_dir / "faiss_index.bin"
        self.metadata_file = self.base_dir / "metadata.pkl"
        self.info_file = self.base_dir / "info.json"
    
    def create_index(self, use_gpu: bool = False):
        """Create a new FAISS index."""
        try:
            # Use IndexFlatIP for inner product (cosine similarity with normalized vectors)
            self.index = faiss.IndexFlatIP(self.dimension)
            
            # Add ID mapping
            self.index = faiss.IndexIDMap2(self.index)
            
            self.is_trained = True
            logger.info(f"Created new FAISS index for collection: {self.collection_name}")
            
        except Exception as e:
            logger.error(f"Failed to create FAISS index: {e}")
            raise RuntimeError(f"Could not create vector index: {str(e)}")
    
    def add_texts(
        self, 
        chunks: List[Dict[str, Any]], 
        batch_size: int = 100
    ) -> List[str]:
        """
        Add text chunks to the vector store.
        
        Args:
            chunks: List of chunk dictionaries with 'text' and metadata
            batch_size: Number of chunks to process at once
            
        Returns:
            List of chunk IDs
        """
        if not chunks:
            return []
        
        # Create index if it doesn't exist
        if self.index is None:
            self.create_index()
        
        chunk_ids = []
        texts_to_embed = []
        
        # Prepare texts and metadata
        for chunk in chunks:
            chunk_id = str(uuid.uuid4())
            chunk["chunk_id"] = chunk_id
            chunk["collection_name"] = self.collection_name
            chunk["added_at"] = datetime.utcnow().isoformat()
            
            texts_to_embed.append(chunk["text"])
            self.metadata.append(chunk)
            chunk_ids.append(chunk_id)
        
        # Embed in batches to avoid memory issues
        for i in range(0, len(texts_to_embed), batch_size):
            batch_texts = texts_to_embed[i:i + batch_size]
            batch_ids = chunk_ids[i:i + batch_size]
            
            # Generate embeddings
            embeddings = embedding_service.embed_texts(batch_texts)
            
            if len(embeddings) == 0:
                continue
            
            # Convert IDs to numpy array
            id_array = np.array([int(id_hash[:8], 16) for id_hash in batch_ids], dtype=np.int64)
            
            # Add to index
            self.index.add_with_ids(embeddings, id_array)
            
            self.total_chunks += len(batch_texts)
            logger.debug(f"Added batch of {len(batch_texts)} chunks to vector store")
        
        logger.info(f"Added {len(chunks)} chunks to collection: {self.collection_name}")
        return chunk_ids
    
    def similarity_search(
        self, 
        query: str, 
        k: int = 5,
        score_threshold: float = 0.5
    ) -> List[Dict[str, Any]]:
        """
        Search for similar chunks to the query.
        
        Args:
            query: Search query string
            k: Number of results to return
            score_threshold: Minimum similarity score (0-1)
            
        Returns:
            List of matching chunks with similarity scores
        """
        if self.index is None or self.total_chunks == 0:
            return []
        
        # Limit k to available chunks
        k = min(k, self.total_chunks)
        
        try:
            # Generate query embedding
            query_embedding = embedding_service.embed_single(query)
            
            # Search
            scores, indices = self.index.search(query_embedding, k)
            
            results = []
            for score, idx in zip(scores[0], indices[0]):
                if idx == -1 or score  List[Dict[str, Any]]:
        """
        Search with metadata filters.
        
        Args:
            query: Search query string
            k: Number of results
            filters: Dictionary of metadata filters
            score_threshold: Minimum similarity score
            
        Returns:
            Filtered search results
        """
        # First get regular search results
        results = self.similarity_search(query, k * 2, score_threshold)
        
        if not filters or not results:
            return results[:k]
        
        # Apply filters
        filtered_results = []
        for result in results:
            match = True
            for key, value in filters.items():
                if key in result and result[key] != value:
                    match = False
                    break
            
            if match:
                filtered_results.append(result)
        
        return filtered_results[:k]
    
    def delete_chunks(self, chunk_ids: List[str]) -> int:
        """
        Delete specific chunks from the index.
        
        Args:
            chunk_ids: List of chunk IDs to delete
            
        Returns:
            Number of chunks deleted
        """
        if not self.index or not chunk_ids:
            return 0
        
        # Get IDs to remove
        ids_to_remove = []
        for chunk_id in chunk_ids:
            try:
                faiss_id = int(chunk_id[:8], 16)
                ids_to_remove.append(faiss_id)
            except:
                continue
        
        if not ids_to_remove:
            return 0
        
        # Remove from index
        id_array = np.array(ids_to_remove, dtype=np.int64)
        self.index.remove_ids(id_array)
        
        # Remove from metadata
        initial_count = len(self.metadata)
        self.metadata = [
            meta for meta in self.metadata 
            if meta.get("chunk_id") not in chunk_ids
        ]
        
        deleted_count = initial_count - len(self.metadata)
        self.total_chunks -= deleted_count
        
        logger.info(f"Deleted {deleted_count} chunks from collection: {self.collection_name}")
        return deleted_count
    
    def save(self):
        """Save the vector store to disk."""
        try:
            # Save FAISS index
            if self.index:
                faiss.write_index(self.index, str(self.index_file))
            
            # Save metadata
            with open(self.metadata_file, 'wb') as f:
                pickle.dump(self.metadata, f)
            
            # Save collection info
            info = {
                "collection_name": self.collection_name,
                "collection_id": self.collection_id,
                "dimension": self.dimension,
                "total_chunks": self.total_chunks,
                "created_at": datetime.utcnow().isoformat(),
                "updated_at": datetime.utcnow().isoformat()
            }
            
            with open(self.info_file, 'w') as f:
                json.dump(info, f, indent=2)
            
            logger.info(f"Saved vector store for collection: {self.collection_name}")
            
        except Exception as e:
            logger.error(f"Failed to save vector store: {e}")
            raise RuntimeError(f"Could not save vector store: {str(e)}")
    
    def load(self) -> bool:
        """
        Load the vector store from disk.
        
        Returns:
            True if loaded successfully, False otherwise
        """
        try:
            if not self.index_file.exists():
                return False
            
            # Load FAISS index
            self.index = faiss.read_index(str(self.index_file))
            
            # Load metadata
            if self.metadata_file.exists():
                with open(self.metadata_file, 'rb') as f:
                    self.metadata = pickle.load(f)
            
            # Load info
            if self.info_file.exists():
                with open(self.info_file, 'r') as f:
                    info = json.load(f)
                    self.total_chunks = info.get("total_chunks", 0)
            
            self.is_trained = True
            logger.info(f"Loaded vector store for collection: {self.collection_name}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to load vector store: {e}")
            return False
    
    def get_stats(self) -> Dict[str, Any]:
        """Get statistics about the vector store."""
        return {
            "collection_name": self.collection_name,
            "collection_id": self.collection_id,
            "total_chunks": self.total_chunks,
            "dimension": self.dimension,
            "index_size": self.index.ntotal if self.index else 0,
            "is_trained": self.is_trained
        }


class VectorStoreManager:
    """Manages multiple vector stores (one per book/collection)."""
    
    def __init__(self):
        self.stores = {}  # collection_name -> VectorStore
        self.load_existing_stores()
    
    def load_existing_stores(self):
        """Load all existing vector stores from disk."""
        if not settings.VECTOR_STORE_DIR.exists():
            return
        
        for collection_dir in settings.VECTOR_STORE_DIR.iterdir():
            if collection_dir.is_dir():
                info_file = collection_dir / "info.json"
                if info_file.exists():
                    try:
                        with open(info_file, 'r') as f:
                            info = json.load(f)
                            collection_name = info.get("collection_name")
                            
                            if collection_name:
                                store = VectorStore(collection_name)
                                if store.load():
                                    self.stores[collection_name] = store
                                    logger.info(f"Loaded existing vector store: {collection_name}")
                    except Exception as e:
                        logger.error(f"Failed to load store from {collection_dir}: {e}")
    
    def get_store(self, collection_name: str) -> VectorStore:
        """
        Get or create a vector store for a collection.
        
        Args:
            collection_name: Name of the collection
            
        Returns:
            VectorStore instance
        """
        if collection_name not in self.stores:
            store = VectorStore(collection_name)
            store.create_index()
            self.stores[collection_name] = store
            logger.info(f"Created new vector store: {collection_name}")
        
        return self.stores[collection_name]
    
    def add_document(
        self,
        collection_name: str,
        chunks: List[Dict[str, Any]],
        batch_size: int = 100
    ) -> List[str]:
        """
        Add document chunks to a collection.
        
        Args:
            collection_name: Name of the collection
            chunks: List of chunk dictionaries
            batch_size: Batch size for embedding
            
        Returns:
            List of chunk IDs
        """
        store = self.get_store(collection_name)
        chunk_ids = store.add_texts(chunks, batch_size)
        store.save()
        return chunk_ids
    
    def search(
        self,
        collection_name: str,
        query: str,
        k: int = 5,
        filters: Optional[Dict[str, Any]] = None,
        score_threshold: float = 0.5
    ) -> List[Dict[str, Any]]:
        """
        Search within a specific collection.
        
        Args:
            collection_name: Collection to search in
            query: Search query
            k: Number of results
            filters: Metadata filters
            score_threshold: Minimum similarity score
            
        Returns:
            List of matching chunks
        """
        if collection_name not in self.stores:
            return []
        
        store = self.stores[collection_name]
        return store.search_with_filters(query, k, filters, score_threshold)
    
    def search_all(
        self,
        query: str,
        collection_names: Optional[List[str]] = None,
        k_per_collection: int = 3,
        score_threshold: float = 0.5
    ) -> List[Dict[str, Any]]:
        """
        Search across multiple collections.
        
        Args:
            query: Search query
            collection_names: List of collections to search (None for all)
            k_per_collection: Results per collection
            score_threshold: Minimum similarity score
            
        Returns:
            Combined results from all collections
        """
        if collection_names is None:
            collection_names = list(self.stores.keys())
        
        all_results = []
        for collection_name in collection_names:
            if collection_name in self.stores:
                results = self.stores[collection_name].similarity_search(
                    query, k_per_collection, score_threshold
                )
                all_results.extend(results)
        
        # Sort by similarity score
        all_results.sort(key=lambda x: x.get("similarity_score", 0), reverse=True)
        
        # Deduplicate by text content
        seen_texts = set()
        unique_results = []
        for result in all_results:
            text = result.get("text", "")
            if text and text not in seen_texts:
                seen_texts.add(text)
                unique_results.append(result)
        
        return unique_results
    
    def delete_collection(self, collection_name: str) -> bool:
        """
        Delete a collection and its vector store.
        
        Args:
            collection_name: Name of collection to delete
            
        Returns:
            True if deleted successfully
        """
        if collection_name not in self.stores:
            return False
        
        try:
            # Delete from memory
            store = self.stores.pop(collection_name)
            
            # Delete from disk
            store_dir = settings.VECTOR_STORE_DIR / collection_name
            if store_dir.exists():
                import shutil
                shutil.rmtree(store_dir)
            
            logger.info(f"Deleted collection: {collection_name}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to delete collection {collection_name}: {e}")
            return False
    
    def get_collection_stats(self, collection_name: str = None) -> Dict[str, Any]:
        """
        Get statistics for a specific collection or all collections.
        
        Args:
            collection_name: Specific collection or None for all
            
        Returns:
            Dictionary of statistics
        """
        if collection_name:
            if collection_name in self.stores:
                return self.stores[collection_name].get_stats()
            return {}
        
        # Return stats for all collections
        all_stats = {}
        for name, store in self.stores.items():
            all_stats[name] = store.get_stats()
        
        return all_stats
    
    def save_all(self):
        """Save all vector stores to disk."""
        for store in self.stores.values():
            try:
                store.save()
            except Exception as e:
                logger.error(f"Failed to save store {store.collection_name}: {e}")
        
        logger.info(f"Saved {len(self.stores)} vector stores")

# Global vector store manager
vector_store_manager = VectorStoreManager()