import React from 'react'
import { Bot, User, BookOpen, Clock } from 'lucide-react'
import { Avatar, AvatarFallback } from '@/components/ui/avatar'
import { Badge } from '@/components/ui/badge'
import { Separator } from '@/components/ui/separator'
import { cn, formatDate } from '@/lib/utils'
import { Message } from '@/hooks/useChatStream'

interface MessageListProps {
  messages: Message[]
  isLoading?: boolean
  className?: string
}

export function MessageList({ messages, isLoading, className }: MessageListProps) {
  if (messages.length === 0 && !isLoading) {
    return (
      
        
          
            
          
          
            Document Engine Chat
            
              Ask questions about your uploaded documents. Select books from the top menu to include them as context.
            
          
          
          
            
              "Summarize the main concepts in this document."
            
            
              "What does the author say about [Topic]?"
            
          
        
      
    )
  }

  return (
    
      {messages.map((message) => (
        
          {/* Avatar */}
          
            
              {message.role === 'user' ? (
                
              ) : (
                
              )}
            
          

          {/* Message Content */}
          
            {/* Message Bubble */}
            
              
                {message.content}
              
            

            {/* Metadata */}
            
              
                
                {formatDate(message.timestamp)}
              

              {message.metadata?.book_ids && message.metadata.book_ids.length > 0 && (
                
                  
                  
                    
                    
                      {message.metadata.book_ids.length} book
                      {message.metadata.book_ids.length > 1 ? 's' : ''}
                    
                  
                
              )}

              {message.metadata?.context_depth && message.role === 'assistant' && (
                
                  
                  
                    {message.metadata.context_depth} context
                  
                
              )}
            
          
        
      ))}

      {/* Loading Indicator */}
      {isLoading && (
        
          
            
              
            
          
          
            
              
                
                
                
              
              Thinking...
            
          
        
      )}
    
  )
}