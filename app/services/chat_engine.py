import logging
import asyncio
from typing import Dict, List, Any, Optional, AsyncGenerator
import json
from openai import OpenAI
from openai.types.chat import ChatCompletionMessageParam

from app.config import settings
from app.services.vector_store import vector_store_manager
from app.services.conversation_memory import conversation_manager

logger = logging.getLogger(__name__)

class ChatEngine:
    """Main chat engine that handles document-aware conversations with streaming via DeepSeek."""

    def __init__(self):
        # Initialize DeepSeek Client
        self.client = OpenAI(
            api_key=settings.DEEPSEEK_API_KEY,
            base_url=settings.DEEPSEEK_BASE_URL
        )

        # Context retrieval strategies
        self.context_strategies = {
            "shallow": {
                "chunks_per_book": 3,
                "score_threshold": 0.7,
                "context_weight": 0.3
            },
            "medium": {
                "chunks_per_book": 5,
                "score_threshold": 0.6,
                "context_weight": 0.5
            },
            "deep": {
                "chunks_per_book": 8,
                "score_threshold": 0.5,
                "context_weight": 0.7
            }
        }

    def _format_document_context(
        self, 
        chunks: List[Dict[str, Any]], 
        strategy: str = "medium"
    ) -> str:
        """
        Format document chunks into context for the LLM.

        Args:
            chunks: Retrieved document chunks
            strategy: Context blending strategy

        Returns:
            Formatted context string
        """
        if not chunks:
            return ""

        strategy_config = self.context_strategies.get(strategy, self.context_strategies["medium"])
        max_chunks = strategy_config["chunks_per_book"] * 3  # Limit total chunks

        # Sort by similarity score
        sorted_chunks = sorted(
            chunks, 
            key=lambda x: x.get("similarity_score", 0), 
            reverse=True
        )[:max_chunks]

        context_parts = ["Relevant document excerpts:"]

        for i, chunk in enumerate(sorted_chunks, 1):
            source = chunk.get("file_name", "Unknown")
            text = chunk.get("text", "").strip()
            score = chunk.get("similarity_score", 0)

            if text:
                context_parts.append(
                    f"[Excerpt {i} from '{source}' (relevance: {score:.2f})]:\n{text}\n"
                )

        context_parts.append(
            "\nInstructions: Use the above document excerpts when they are relevant to answer the question. "
            "If the documents don't contain relevant information, use your general knowledge. "
            "Always cite which excerpt you're referencing when using document information."
        )

        return "\n".join(context_parts)

    def _build_messages(
        self,
        user_message: str,
        conversation_memory,
        document_context: str,
        strategy: str = "medium"
    ) -> List[ChatCompletionMessageParam]:
        """
        Build the message list for the LLM.

        Args:
            user_message: Current user message
            conversation_memory: ConversationMemory instance
            document_context: Formatted document context
            strategy: Context blending strategy

        Returns:
            List of messages in OpenAI/DeepSeek format
        """
        messages: List[ChatCompletionMessageParam] = []

        strategy_config = self.context_strategies.get(strategy, self.context_strategies["medium"])
        context_weight = strategy_config["context_weight"]

        system_content = f"""You are Document Engine, an AI assistant with access to uploaded documents.

{document_context if document_context else "No document context provided for this query."}

Guidelines:
1. Context Weight: {context_weight*100}% of your response should be guided by the provided documents when relevant
2. When using document information, cite the source (e.g., "According to excerpt 1 from 'book.pdf'...")
3. When documents don't contain relevant information, use your general knowledge
4. Be thorough but concise
5. If asked about document content, reference specific excerpts when possible
6. Maintain natural conversation flow

Current conversation context:"""

        messages.append({"role": "system", "content": system_content})

        # Add conversation history
        history = conversation_memory.get_conversation_history(
            include_system=False,
            last_n=10
        )
        messages.extend(history)  # type: ignore

        messages.append({"role": "user", "content": user_message})

        return messages

    async def generate_response(
        self,
        user_message: str,
        conversation_id: Optional[str] = None,
        book_ids: Optional[List[str]] = None,
        context_depth: str = "medium",
        stream: bool = True
    ) -> AsyncGenerator[str, None]:
        """
        Generate a response with document context using DeepSeek.

        Args:
            user_message: User's message
            conversation_id: Conversation ID for memory
            book_ids: List of book IDs to search in
            context_depth: "shallow", "medium", or "deep"
            stream: Whether to stream the response

        Yields:
            Response chunks as they're generated
        """
        # Get or create conversation memory
        conversation = conversation_manager.get_conversation(conversation_id)
        if not conversation:
            yield json.dumps({"error": "Failed to create conversation"})
            return

        # Add user message to memory
        conversation.add_message("user", user_message)

        # Retrieve relevant chunks
        document_chunks = []
        if book_ids:
            for book_id in book_ids:
                chunks = vector_store_manager.search(
                    collection_name=book_id,
                    query=user_message,
                    k=self.context_strategies[context_depth]["chunks_per_book"],
                    score_threshold=self.context_strategies[context_depth]["score_threshold"]
                )
                document_chunks.extend(chunks)

                # Store retrieval context
                if chunks:
                    conversation.add_document_context(book_id, chunks, user_message)

        # Add recent context from conversation history
        recent_context = conversation.get_recent_context(max_chunks=5)
        document_chunks.extend(recent_context)

        # Format context
        formatted_context = self._format_document_context(document_chunks, context_depth)

        # Build messages
        messages = self._build_messages(
            user_message=user_message,
            conversation_memory=conversation,
            document_context=formatted_context,
            strategy=context_depth
        )

        try:
            if stream:
                # Streaming response
                full_response = ""
                
                stream_response = self.client.chat.completions.create(
                    model=settings.DEEPSEEK_MODEL,
                    messages=messages,
                    stream=True,
                    max_tokens=settings.MAX_TOKENS,
                    temperature=0.7,
                )

                for chunk in stream_response:
                    if chunk.choices[0].delta.content:
                        content = chunk.choices[0].delta.content
                        full_response += content
                        yield content

                # Save assistant response to memory
                conversation.add_message("assistant", full_response, {
                    "book_ids": book_ids,
                    "context_depth": context_depth,
                    "document_chunks_used": len(document_chunks),
                    "model": settings.DEEPSEEK_MODEL
                })

            else:
                # Non-streaming response
                response = self.client.chat.completions.create(
                    model=settings.DEEPSEEK_MODEL,
                    messages=messages,
                    max_tokens=settings.MAX_TOKENS,
                    temperature=0.7,
                )

                full_response = response.choices[0].message.content or ""
                yield full_response

                conversation.add_message("assistant", full_response, {
                    "book_ids": book_ids,
                    "context_depth": context_depth,
                    "document_chunks_used": len(document_chunks),
                    "model": settings.DEEPSEEK_MODEL
                })

        except Exception as e:
            error_msg = f"Error generating response: {str(e)}"
            logger.error(error_msg)
            yield json.dumps({"error": error_msg})

    async def quick_chat(
        self,
        user_message: str,
        book_ids: Optional[List[str]] = None,
        context_depth: str = "medium"
    ) -> Dict[str, Any]:
        """
        Quick chat without conversation memory (for testing).
        """
        # Retrieve relevant chunks
        document_chunks = []
        if book_ids:
            for book_id in book_ids:
                chunks = vector_store_manager.search(
                    collection_name=book_id,
                    query=user_message,
                    k=self.context_strategies[context_depth]["chunks_per_book"],
                    score_threshold=self.context_strategies[context_depth]["score_threshold"]
                )
                document_chunks.extend(chunks)

        formatted_context = self._format_document_context(document_chunks, context_depth)

        messages: List[ChatCompletionMessageParam] = [
            {
                "role": "system",
                "content": f"You are a helpful assistant. {formatted_context}"
            },
            {"role": "user", "content": user_message}
        ]

        try:
            response = self.client.chat.completions.create(
                model=settings.DEEPSEEK_MODEL,
                messages=messages,
                max_tokens=2000,
                temperature=0.7,
            )

            return {
                "response": response.choices[0].message.content,
                "chunks_used": len(document_chunks),
                "context_depth": context_depth,
                "model": settings.DEEPSEEK_MODEL
            }

        except Exception as e:
            logger.error(f"Quick chat error: {e}")
            return {
                "response": f"Error: {str(e)}",
                "chunks_used": 0,
                "error": True
            }

    def get_conversation_history(
        self, 
        conversation_id: str,
        last_n: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """Get conversation history."""
        conversation = conversation_manager.get_conversation(
            conversation_id, 
            create_new=False
        )

        if not conversation:
            return []

        if last_n:
            return conversation.messages[-last_n:]

        return conversation.messages

    def clear_conversation(self, conversation_id: str) -> bool:
        """Clear a conversation."""
        conversation = conversation_manager.get_conversation(
            conversation_id, 
            create_new=False
        )

        if conversation:
            conversation.clear()
            return True

        return False

# Singleton instance
chat_engine = ChatEngine()