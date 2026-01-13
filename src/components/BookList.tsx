import React, { useEffect, useState } from 'react'
import { BookOpen, FileText, Trash2, Search, Clock, CheckCircle, AlertCircle, Loader2 } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Input } from '@/components/ui/input'
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
import { formatFileSize, formatDate, truncateText } from '@/lib/utils'
import { useFileUpload } from '@/hooks/useFileUpload'

interface BookListProps {
  onBookSelect?: (bookId: string) => void
  selectedBooks?: string[]
}

export function BookList({ onBookSelect, selectedBooks = [] }: BookListProps) {
  const [searchQuery, setSearchQuery] = useState('')
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(null)
  const { books, isLoading, deleteBook, fetchBooks } = useFileUpload()

  useEffect(() => {
    fetchBooks()
    
    // Set up polling for book list updates (e.g., if processing completes while viewing list)
    const interval = setInterval(() => {
      fetchBooks()
    }, 15000)
    
    return () => clearInterval(interval)
  }, [fetchBooks])

  const filteredBooks = books.filter(book =>
    book.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
    book.file_name.toLowerCase().includes(searchQuery.toLowerCase())
  )

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'completed':
        return (
          
            
            Ready
          
        )
      case 'processing':
        return (
          
            
            Processing
          
        )
      case 'failed':
        return (
          
            
            Failed
          
        )
      default:
        return (
          
            
            Pending
          
        )
    }
  }

  const getFileIcon = (fileType: string) => {
    const type = fileType ? fileType.toLowerCase() : ''
    if (type.includes('pdf')) return 
    if (type.includes('epub')) return 
    if (type.includes('word') || type.includes('docx')) return 
    return 
  }

  const handleDelete = async (bookId: string) => {
    try {
      await deleteBook(bookId)
      setDeleteDialogOpen(null)
    } catch (error) {
      console.error('Delete failed:', error)
    }
  }

  const handleBookSelect = (bookId: string) => {
    if (onBookSelect) {
      onBookSelect(bookId)
    }
  }

  if (isLoading && books.length === 0) {
    return (
      
        
          
        
      
    )
  }

  return (
    
      {/* Search Bar */}
      
        
         setSearchQuery(e.target.value)}
          className="pl-10"
        />
      

      {/* Stats */}
      
        
          
            
              
                Total Books
                {books.length}
              
              
            
          
        
        
          
            
              
                Ready for Chat
                
                  {books.filter(b => b.upload_status === 'completed').length}
                
              
              
            
          
        
        
          
            
              
                Total Chunks
                
                  {books.reduce((sum, book) => sum + (book.chunk_count || 0), 0)}
                
              
              
            
          
        
      

      {/* Book List */}
      
        
          Uploaded Books
          
            {books.length === 0
              ? 'No books uploaded yet. Upload some documents to get started.'
              : `Showing ${filteredBooks.length} of ${books.length} books`}
          
        
        
          {filteredBooks.length === 0 ? (
            
              {searchQuery ? 'No books match your search' : 'No books uploaded yet'}
            
          ) : (
            
              {filteredBooks.map((book) => (
                 onBookSelect && handleBookSelect(book.book_id)}
                >
                  
                    
                      
                        {getFileIcon(book.file_type)}
                      
                      
                        
                          {book.title}
                          {getStatusBadge(book.upload_status)}
                        
                        
                          {book.file_name} • {formatFileSize(book.file_size)}
                        
                        
                          
                            
                            {book.chunk_count} chunks
                          
                          •
                          
                            
                            {book.scan_depth} scan
                          
                          •
                          
                            
                            {formatDate(book.uploaded_at)}
                          
                        
                        {book.upload_status === 'failed' && book.processing_error && (
                          
                            Error: {truncateText(book.processing_error, 100)}
                          
                        )}
                      
                    
                    
                      {onBookSelect && (
                         {
                            e.stopPropagation()
                            handleBookSelect(book.book_id)
                          }}
                        >
                          {selectedBooks.includes(book.book_id) ? 'Selected' : 'Select'}
                        
                      )}
                       setDeleteDialogOpen(open ? book.book_id : null)}>
                        
                           e.stopPropagation()}
                          >
                            
                          
                        
                        
                          
                            Delete Book
                            
                              Are you sure you want to delete "{book.title}"? This action cannot be undone.
                              All associated chunks and vector data will be permanently removed.
                            
                          
                          
                            Cancel
                             handleDelete(book.book_id)}
                              className="bg-red-500 hover:bg-red-600"
                            >
                              Delete
                            
                          
                        
                      
                    
                  
                
              ))}
            
          )}
        
      
    
  )
}