import React, { useState, useEffect } from 'react'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { FileUpload } from '@/components/FileUpload'
import { BookList } from '@/components/BookList'
import { Button } from '@/components/ui/button'
import { Upload, BookOpen, Search, FileQuestion } from 'lucide-react'
import { useSearchParams } from 'react-router-dom'

export default function BooksPage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const initialTab = searchParams.get('tab') || 'library'
  const [activeTab, setActiveTab] = useState(initialTab)

  useEffect(() => {
    setSearchParams({ tab: activeTab })
  }, [activeTab, setSearchParams])

  return (
    
      
        
          Books
          
            Upload and manage your documents for AI-powered analysis
          
        
        
           setActiveTab('upload')}
            className="flex items-center gap-2"
          >
            
            Upload
          
           setActiveTab('library')}
            className="flex items-center gap-2"
          >
            
            Library
          
        
      

      
        
          
            
            Library
          
          
            
            Upload
          
        

        
          
        

        
           setActiveTab('library')} />
          
          {/* Upload Tips */}
          
            
              
                
                  
                
                Supported Formats
              
              
                • PDF Documents (.pdf)
                • EPUB E-books (.epub)
                • Text Files (.txt)
                • Word Documents (.docx)
                • Markdown (.md)
              
            

            
              
                
                  
                
                Scan Depth
              
              
                
                  Shallow: Fast, less detailed
                
                
                  Medium: Balanced speed & detail
                
                
                  Deep: Slow, most detailed
                
              
            

            
              
                
                  
                
                Processing
              
              
                Files are chunked, embedded, and added to the vector database.
                Processing time depends on file size and scan depth.
                You'll be notified when your documents are ready for chat.
              
            
          
        
      
    
  )
}