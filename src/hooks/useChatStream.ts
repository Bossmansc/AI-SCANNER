import { useState, useCallback, useRef } from 'react'
import axios from 'axios'
import { useToast } from '@/components/ui/use-toast'

export interface Message {
  id: string
  role: 'user' | 'assistant' | 'system'
  content: string
  timestamp: string
  metadata?: {
    book_ids?: string[]
    context_depth?: string
    document_chunks_used?: number
    model_used?: string
  }
}

interface ChatRequest {
  message: string
  conversation_id?: string
  book_ids?: string[]
  context_depth: 'shallow' | 'medium' | 'deep'
}

interface ChatResponse {
  chunk: string
  complete: boolean
  error?: string
}

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'https://ai-scanner-j2c9.onrender.com/api/v1'

export function useChatStream() {
  const [messages, setMessages] = useState([])
  const [conversationId, setConversationId] = useState()
  const [isLoading, setIsLoading] = useState(false)
  const [isStreaming, setIsStreaming] = useState(false)
  const abortControllerRef = useRef(null)
  const { toast } = useToast()

  // Send message with streaming
  const sendMessage = useCallback(async (
    message: string,
    bookIds: string[] = [],
    contextDepth: 'shallow' | 'medium' | 'deep' = 'medium'
  ) => {
    // Cancel any ongoing request
    if (abortControllerRef.current) {
      abortControllerRef.current.abort()
    }

    // Create new abort controller
    abortControllerRef.current = new AbortController()

    // Add user message immediately
    const userMessage: Message = {
      id: Date.now().toString(),
      role: 'user',
      content: message,
      timestamp: new Date().toISOString(),
    }

    setMessages(prev => [...prev, userMessage])
    setIsLoading(true)
    setIsStreaming(true)

    // Create assistant placeholder message
    const assistantMessageId = (Date.now() + 1).toString()
    const assistantMessage: Message = {
      id: assistantMessageId,
      role: 'assistant',
      content: '',
      timestamp: new Date().toISOString(),
      metadata: {
        book_ids: bookIds,
        context_depth: contextDepth
      }
    }

    setMessages(prev => [...prev, assistantMessage])

    try {
      const requestPayload: ChatRequest = {
        message,
        conversation_id: conversationId,
        book_ids: bookIds,
        context_depth: contextDepth,
      }

      // Use native fetch for streaming support
      const response = await fetch(`${API_BASE_URL}/chat/stream`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(requestPayload),
        signal: abortControllerRef.current.signal,
      })

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`)
      }

      const reader = response.body?.getReader()
      if (!reader) {
        throw new Error('No response body')
      }

      let accumulatedContent = ''
      let newConversationId = conversationId

      // Process stream
      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        const text = new TextDecoder().decode(value)
        const lines = text.split('\n')

        for (const line of lines) {
          if (!line.trim() || !line.startsWith('data: ')) continue

          try {
            const jsonStr = line.replace('data: ', '')
            const data: ChatResponse = JSON.parse(jsonStr)

            if (data.error) {
              throw new Error(data.error)
            }

            if (data.chunk) {
              accumulatedContent += data.chunk

              // Update the assistant message with accumulated content
              setMessages(prev => prev.map(msg =>
                msg.id === assistantMessageId
                  ? { ...msg, content: accumulatedContent }
                  : msg
              ))
            }

            if (data.complete) {
              // Finalize the message
              const finalMessage: Message = {
                ...assistantMessage,
                content: accumulatedContent,
                metadata: {
                  ...assistantMessage.metadata,
                  model_used: 'deepseek-chat',
                },
              }

              setMessages(prev => prev.map(msg =>
                msg.id === assistantMessageId ? finalMessage : msg
              ))

              setIsLoading(false)
              setIsStreaming(false)
              return {
                success: true,
                message: accumulatedContent,
              }
            }
          } catch (error) {
            console.error('Error parsing stream chunk:', error, 'Line:', line)
          }
        }
      }
    } catch (error: any) {
      // Only show error if not an abort error
      if (error.name !== 'AbortError') {
        console.error('Chat stream error:', error)

        // Update assistant message with error state
        setMessages(prev => prev.map(msg =>
          msg.id === assistantMessageId
            ? {
                ...msg,
                content: msg.content + (msg.content ? '\n\n' : '') + `[Error: ${error.message || 'Failed to get response'}]`,
              }
            : msg
        ))

        toast({
          title: 'Chat Error',
          description: error.message || 'Failed to get response',
          variant: 'destructive',
        })
      }

      setIsLoading(false)
      setIsStreaming(false)
      return {
        success: false,
        error: error.message || 'Failed to get response',
      }
    } finally {
      setIsLoading(false)
      setIsStreaming(false)
      abortControllerRef.current = null
    }
  }, [conversationId, toast])

  // Stop streaming
  const stopStreaming = useCallback(() => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort()
      setIsStreaming(false)
      setIsLoading(false)
    }
  }, [])

  // Load conversation
  const loadConversation = useCallback(async (id: string) => {
    try {
      setIsLoading(true)
      const response = await axios.get(
        `${API_BASE_URL}/chat/conversations/${id}`
      )

      const loadedMessages: Message[] = response.data.map((msg: any) => ({
        id: msg.message_id,
        role: msg.role as 'user' | 'assistant' | 'system',
        content: msg.content,
        timestamp: msg.created_at,
        metadata: {
          book_ids: msg.book_ids_used,
          model_used: msg.model_used,
        },
      }))

      setMessages(loadedMessages)
      setConversationId(id)

      return { success: true, messages: loadedMessages }
    } catch (error: any) {
      console.error('Error loading conversation:', error)
      toast({
        title: 'Load Error',
        description: 'Failed to load conversation history',
        variant: 'destructive',
      })
      return { success: false, error: error.message }
    } finally {
      setIsLoading(false)
    }
  }, [toast])

  // Clear conversation
  const clearConversation = useCallback(() => {
    setMessages([])
    setConversationId(undefined)
  }, [])

  // Delete conversation
  const deleteConversation = useCallback(async (id: string) => {
    try {
      await axios.delete(`${API_BASE_URL}/chat/conversations/${id}`)

      if (id === conversationId) {
        clearConversation()
      }

      toast({
        title: 'Conversation Deleted',
        description: 'Conversation has been removed',
      })

      return { success: true }
    } catch (error: any) {
      console.error('Error deleting conversation:', error)
      toast({
        title: 'Delete Error',
        description: 'Failed to delete conversation',
        variant: 'destructive',
      })
      return { success: false, error: error.message }
    }
  }, [conversationId, clearConversation, toast])

  return {
    messages,
    conversationId,
    isLoading,
    isStreaming,
    sendMessage,
    stopStreaming,
    loadConversation,
    clearConversation,
    deleteConversation,
    setConversationId,
    setMessages,
  }
}