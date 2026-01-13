import React from 'react'
import { BookOpen, MessageSquare, Upload, Zap, Clock } from 'lucide-react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Separator } from '@/components/ui/separator'
import { useNavigate } from 'react-router-dom'
import { useFileUpload } from '@/hooks/useFileUpload'
import { formatFileSize } from '@/lib/utils'

export default function Dashboard() {
  const navigate = useNavigate()
  const { books, getUploadStats } = useFileUpload()
  
  const stats = getUploadStats()
  const completedBooks = books.filter(b => b.upload_status === 'completed')
  const totalChunks = books.reduce((sum, book) => sum + (book.chunk_count || 0), 0)
  const totalFileSize = books.reduce((sum, book) => sum + book.file_size, 0)

  const quickActions = [
    {
      title: 'New Chat',
      description: 'Start a conversation',
      icon: MessageSquare,
      action: () => navigate('/chat'),
      color: ' bg-blue-50 dark:bg-blue-900/20',
    },
    {
      title: 'Upload Documents',
      description: 'Add new files',
      icon: Upload,
      action: () => navigate('/books'),
      color: ' bg-green-50 dark:bg-green-900/20',
    },
    {
      title: 'View Books',
      description: 'Manage your library',
      icon: BookOpen,
      action: () => navigate('/books'),
      color: ' bg-purple-50 dark:bg-purple-900/20',
    },
  ]

  return (
    
      {/* Header */}
      
        Dashboard
        
          Welcome to Document Engine. Upload documents and chat with AI about their content.
        
      

      {/* Quick Stats */}
      
        
          
            
              
                Total Books
                {books.length}
              
              
                
              
            
          
        

        
          
            
              
                Ready for Chat
                {completedBooks.length}
              
              
                
              
            
          
        

        
          
            
              
                Total Chunks
                {totalChunks}
              
              
                
              
            
          
        

        
          
            
              
                Storage Used
                {formatFileSize(totalFileSize)}
              
              
                
              
            
          
        
      

      {/* Quick Actions */}
      
        
          Quick Actions
          
            Get started with these common actions
          
        
        
          
            {quickActions.map((action) => (
              
                
                  
                
                {action.title}
                {action.description}
              
            ))}
          
        
      

      {/* Recent Activity & System Status */}
      
        {/* Recent Books */}
        
          
            Recent Books
            
              Your most recently uploaded documents
            
          
          
            {books.length === 0 ? (
              
                
                No books uploaded yet
                 navigate('/books')}
                >
                  Upload Your First Book
                
              
            ) : (
              
                {books.slice(0, 5).map((book) => (
                  
                    
                      
                      
                        {book.title}
                        
                          {formatFileSize(book.file_size)} • {book.chunk_count} chunks
                        
                      
                    
                     navigate(`/chat?book=${book.book_id}`)}
                    >
                      Chat
                    
                  
                ))}
                {books.length > 5 && (
                  
                    
                     navigate('/books')}
                    >
                      View All Books
                    
                  
                )}
              
            )}
          
        

        {/* System Status */}
        
          
            System Status
            
              Current processing and upload status
            
          
          
            
              
                
                  Upload Processing
                  
                    {stats.processing} active
                  
                
                
                  
                
              

              
                
                  Completed Uploads
                  
                    {stats.completed} of {stats.total}
                  
                
                
                  
                
              

              
                Tips
                
                  
                    
                    Use "shallow" scan for faster processing of large documents
                  
                  
                    
                    Select multiple books for cross-document analysis
                  
                
              
            
          
        
      
    
  )
}