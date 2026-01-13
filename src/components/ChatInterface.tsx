import React, { useState, useRef, useEffect } from 'react'
import { Send, Bot, BookOpen, Trash2, StopCircle, Loader2 } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { CardContent, CardFooter, CardHeader, CardTitle } from '@/components/ui/card'
import { Textarea } from '@/components/ui/textarea'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Badge } from '@/components/ui/badge'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip'
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from '@/components/ui/alert-dialog'
import { BookList } from '@/components/BookList'
import { MessageList } from '@/components/MessageList'
import { useChatStream } from '@/hooks/useChatStream'
import { useToast } from '@/components/ui/use-toast'

interface ChatInterfaceProps {
  initialBookIds?: string[]
  conversationId?: string
}

export function ChatInterface({ initialBookIds = [], conversationId }: ChatInterfaceProps) {
  const [input, setInput] = useState('')
  const [selectedBooks, setSelectedBooks] = useState(initialBookIds)
  const [contextDepth, setContextDepth] = useState('medium')
  const [showBookSelector, setShowBookSelector] = useState(false)
  const [isClearing, setIsClearing] = useState(false)
  
  const messagesEndRef = useRef(null)
  const textareaRef = useRef(null)
  
  const {
    messages,
    isLoading,
    isStreaming,
    sendMessage,
    stopStreaming,
    clearConversation,
    loadConversation,
  } = useChatStream()
  
  const { toast } = useToast()

  // Load conversation if ID provided
  useEffect(() => {
    if (conversationId) {
      loadConversation(conversationId)
    }
  }, [conversationId, loadConversation])

  // Auto-scroll to bottom
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  // Auto-resize textarea
  useEffect(() => {
    const textarea = textareaRef.current
    if (textarea) {
      textarea.style.height = 'auto'
      textarea.style.height = `${Math.min(textarea.scrollHeight, 200)}px`
    }
  }, [input])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!input.trim() || isLoading) return

    const message = input.trim()
    setInput('')

    try {
      await sendMessage(message, selectedBooks, contextDepth)
    } catch (error) {
      console.error('Error sending message:', error)
    }
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSubmit(e)
    }
  }

  const handleClearConversation = async () => {
    setIsClearing(true)
    try {
      clearConversation()
      toast({
        title: 'Conversation Cleared',
        description: 'Chat history has been cleared',
      })
    } catch (error) {
      console.error('Error clearing conversation:', error)
    } finally {
      setIsClearing(false)
    }
  }

  const toggleBookSelection = (bookId: string) => {
    setSelectedBooks(prev =>
      prev.includes(bookId)
        ? prev.filter(id => id !== bookId)
        : [...prev, bookId]
    )
  }

  const getBookCountText = () => {
    if (selectedBooks.length === 0) return 'No books selected'
    if (selectedBooks.length === 1) return '1 book selected'
    return `${selectedBooks.length} books selected`
  }

  return (
    
      {/* Header */}
      
        
          
            
            Document Engine Chat
          
          
            {/* Context Depth Selector */}
             setContextDepth(value)}>
              
                
              
              
                Shallow
                Medium
                Deep
              
            

            {/* Book Selector Button */}
            
              
                
                   0 ? "secondary" : "outline"}
                    size="sm"
                    onClick={() => setShowBookSelector(!showBookSelector)}
                    className="flex items-center gap-2 h-8"
                  >
                    
                    {getBookCountText()}
                    {selectedBooks.length > 0 && (
                      
                        {selectedBooks.length}
                      
                    )}
                  
                
                
                  Select books for context
                
              
            

            {/* Clear Chat Button */}
            
              
                
                  
                
              
              
                
                  Clear Conversation
                  
                    Are you sure you want to clear this conversation? This action cannot be undone.
                  
                
                
                  Cancel
                  
                    {isClearing ? (
                      
                    ) : null}
                    Clear
                  
                
              
            
          
        

        {/* Book Selector Panel */}
        {showBookSelector && (
          
            
              Select Books for Context
               setShowBookSelector(false)}
                className="h-6 "
              >
                Close
              
            
            
              
            
          
        )}
      

      {/* Messages Area */}
      
        
          
          
        
      

      {/* Input Area */}
      
        
          {/* Selected Books Indicator */}
          {selectedBooks.length > 0 && (
            
              
              Context:
              
                {selectedBooks.map((bookId, index) => (
                   toggleBookSelection(bookId)}
                  >
                    Book {index + 1} &times;
                  
                ))}
              
            
          )}

          
             setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder={selectedBooks.length === 0 ? "Ask a general question..." : "Ask about your documents..."}
              className="min-h-[50px] max-h-[200px] resize-none flex-1 bg-background focus-visible:ring-1"
              disabled={isLoading && !isStreaming}
            />
            
              {isStreaming ? (
                
                  
                
              ) : (
                
                  
                
              )}
            
          

          
            
              Press Enter to send, Shift + Enter for new line
            
            {messages.length} messages
          
        
      
    
  )
}