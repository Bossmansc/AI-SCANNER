import json
import logging
from typing import List, Optional
from datetime import datetime
from fastapi import APIRouter, HTTPException, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.database import get_db
from app.models import Conversation, Message as MessageModel
from app.services.chat_engine import chat_engine
from app.services.conversation_memory import conversation_manager
from app.services.vector_store import vector_store_manager
from app.config import settings

router = APIRouter(prefix="/chat", tags=["chat"])
logger = logging.getLogger(__name__)

# Pydantic models
class ChatRequest(BaseModel):
    message: str
    conversation_id: Optional[str] = None
    book_ids: Optional[List[str]] = None
    context_depth: str = "medium"  # shallow, medium, deep

class ChatResponse(BaseModel):
    conversation_id: str
    message: str
    complete: bool

class ConversationResponse(BaseModel):
    conversation_id: str
    title: str
    message_count: int
    created_at: datetime
    updated_at: datetime
    last_message_at: Optional[datetime]
    book_ids: List[str]
    
    class Config:
        from_attributes = True

class MessageResponse(BaseModel):
    message_id: str
    role: str
    content: str
    created_at: str
    model_used: Optional[str]
    book_ids_used: Optional[List[str]]
    
    class Config:
        from_attributes = True

# Routes
@router.post("/stream", response_class=StreamingResponse)
async def chat_stream(request: ChatRequest):
    """
    Chat endpoint with Server-Sent Events streaming.
    Returns streaming response for real-time chat.
    """
    async def event_generator():
        try:
            # Generate streaming response
            async for chunk in chat_engine.generate_response(
                user_message=request.message,
                conversation_id=request.conversation_id,
                book_ids=request.book_ids,
                context_depth=request.context_depth,
                stream=True
            ):
                # Skip error messages wrapped in JSON
                if chunk.startswith('{"error":'):
                    error_data = json.loads(chunk)
                    # Send error as event
                    data = json.dumps({"error": error_data["error"], "complete": True})
                    yield f"data: {data}\n\n"
                    break
                
                # Send chunk as SSE event
                data = json.dumps({
                    "chunk": chunk,
                    "complete": False
                })
                yield f"data: {data}\n\n"
            
            # Send completion event
            completion_data = json.dumps({
                "chunk": "",
                "complete": True
            })
            yield f"data: {completion_data}\n\n"
            
        except Exception as e:
            logger.error(f"Error in chat stream: {e}")
            error_data = json.dumps({
                "error": str(e),
                "complete": True
            })
            yield f"data: {error_data}\n\n"
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"  # Disable buffering for nginx
        }
    )

@router.post("/", response_model=ChatResponse)
async def chat_complete(request: ChatRequest):
    """
    Chat endpoint without streaming (for testing or simple queries).
    Returns complete response at once.
    """
    try:
        full_response = ""
        
        async for chunk in chat_engine.generate_response(
            user_message=request.message,
            conversation_id=request.conversation_id,
            book_ids=request.book_ids,
            context_depth=request.context_depth,
            stream=False
        ):
            full_response += chunk
        
        return ChatResponse(
            conversation_id=request.conversation_id or "new",
            message=full_response,
            complete=True
        )
        
    except Exception as e:
        logger.error(f"Error in chat complete: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/conversations", response_model=List[ConversationResponse])
async def list_conversations(
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db)
):
    """List all conversations."""
    conversations = db.query(Conversation).order_by(
        Conversation.updated_at.desc()
    ).offset(skip).limit(limit).all()
    return conversations

@router.get("/conversations/{conversation_id}", response_model=List[MessageResponse])
async def get_conversation_messages(
    conversation_id: str,
    limit: int = Query(100, ge=1, le=1000)
):
    """Get messages from a specific conversation."""
    messages = chat_engine.get_conversation_history(conversation_id, last_n=limit)
    
    # Convert to response format
    response_messages = []
    for msg in messages:
        response_messages.append(MessageResponse(
            message_id=msg.get('id', ''),
            role=msg.get('role', ''),
            content=msg.get('content', ''),
            created_at=msg.get('timestamp', ''),
            model_used=msg.get('metadata', {}).get('model'),
            book_ids_used=msg.get('metadata', {}).get('book_ids', [])
        ))
    
    return response_messages

@router.delete("/conversations/{conversation_id}")
async def delete_conversation(conversation_id: str):
    """Delete a conversation."""
    success = chat_engine.clear_conversation(conversation_id)
    if not success:
        success = conversation_manager.delete_conversation(conversation_id)
    
    if not success:
        raise HTTPException(status_code=404, detail="Conversation not found")
    
    return {"message": "Conversation deleted successfully"}

@router.get("/books/available")
async def get_available_books():
    """Get list of books available for chat context."""
    stats = vector_store_manager.get_collection_stats()
    
    available_books = []
    for book_id, book_stats in stats.items():
        if book_stats.get('total_chunks', 0) > 0:
            available_books.append({
                "book_id": book_id,
                "chunk_count": book_stats.get('total_chunks', 0),
                "is_trained": book_stats.get('is_trained', False)
            })
    
    return {"books": available_books}

@router.get("/health")
async def chat_health():
    """Check chat service health."""
    try:
        # Quick test of OpenAI API
        test_response = await chat_engine.quick_chat(
            user_message="Hello",
            book_ids=[],
            context_depth="medium"
        )
        
        return {
            "status": "healthy",
            "openai": "connected" if not test_response.get("error") else "error",
            "vector_stores": len(vector_store_manager.stores),
            "active_conversations": len(conversation_manager.conversations)
        }
        
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {
            "status": "unhealthy",
            "error": str(e)
        }