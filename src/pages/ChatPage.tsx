import React from 'react'
import { ChatInterface } from '@/components/ChatInterface'
import { useSearchParams } from 'react-router-dom'

export default function ChatPage() {
  const [searchParams] = useSearchParams()
  const bookId = searchParams.get('book')
  
  return (
    
      
        Chat
        
          Ask questions about your uploaded documents. Select books from the header to include as context.
        
      
      
      
        
      
    
  )
}