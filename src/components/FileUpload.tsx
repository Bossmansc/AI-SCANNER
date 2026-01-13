import React, { useCallback, useState } from 'react'
import { useDropzone } from 'react-dropzone'
import { Upload, FileText, BookOpen, AlertCircle, Loader2, Check } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Progress } from '@/components/ui/progress'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Badge } from '@/components/ui/badge'
import { Separator } from '@/components/ui/separator'
import { formatFileSize } from '@/lib/utils'
import { useFileUpload } from '@/hooks/useFileUpload'

interface FileUploadProps {
  onUploadComplete?: () => void
}

export function FileUpload({ onUploadComplete }: FileUploadProps) {
  const [scanDepth, setScanDepth] = useState('medium')
  const [customTitle, setCustomTitle] = useState('')
  const [isDragging, setIsDragging] = useState(false)

  const {
    uploadFilesList,
    uploadMultipleFiles,
    clearCompletedUploads,
    getUploadStats,
  } = useFileUpload()

  const onDrop = useCallback(
    (acceptedFiles: File[]) => {
      setIsDragging(false)
      if (acceptedFiles.length > 0) {
        uploadMultipleFiles(acceptedFiles, {
          scanDepth,
          title: customTitle || undefined,
        })
        setCustomTitle('') // Reset title after upload
        if (onUploadComplete) {
          onUploadComplete()
        }
      }
    },
    [scanDepth, customTitle, uploadMultipleFiles, onUploadComplete]
  )

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    onDragEnter: () => setIsDragging(true),
    onDragLeave: () => setIsDragging(false),
    accept: {
      'application/pdf': ['.pdf'],
      'application/epub+zip': ['.epub'],
      'text/plain': ['.txt'],
      'application/vnd.openxmlformats-officedocument.wordprocessingml.document': ['.docx'],
      'text/markdown': ['.md'],
    },
    multiple: true,
    maxSize: 50 * 1024 * 1024, // 50MB
  })

  const stats = getUploadStats()

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'completed':
        return 
      case 'error':
        return 
      case 'processing':
      case 'uploading':
        return 
      default:
        return 
    }
  }

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'completed':
        return 'bg-green-100  border-green-200 dark:bg-green-900/30 dark: dark:border-green-800'
      case 'error':
        return 'bg-red-100  border-red-200 dark:bg-red-900/30 dark: dark:border-red-800'
      case 'processing':
      case 'uploading':
        return 'bg-blue-100  border-blue-200 dark:bg-blue-900/30 dark: dark:border-blue-800'
      default:
        return 'bg-gray-100  border-gray-200 dark:bg-gray-800 dark: dark:border-gray-700'
    }
  }

  return (
    
      
        
          Upload Documents
          
            Upload PDF, EPUB, TXT, DOCX, or MD files. Maximum size: 50MB per file.
          
        
        
          {/* Upload Stats */}
          {stats.total > 0 && (
            
              
                
                Completed: {stats.completed}
              
              
                
                Processing: {stats.processing}
              
              
                
                Errors: {stats.errors}
              
              
                Clear Completed
              
            
          )}

          {/* Upload Options */}
          
            
              Scan Depth
               setScanDepth(value)}>
                
                  
                
                
                  
                    
                      
                      Shallow (Fast, less detailed)
                    
                  
                  
                    
                      
                      Medium (Balanced)
                    
                  
                  
                    
                      
                      Deep (Slow, most detailed)
                    
                  
                
              
            

            
              Custom Title (Optional)
               setCustomTitle(e.target.value)}
              />
            
          

          {/* Drop Zone */}
          
            
            
              
                
              
              
                
                  {isDragActive ? 'Drop files here' : 'Drag & drop files here'}
                
                
                  or click to browse files
                
                
                  Supports: PDF, EPUB, TXT, DOCX, MD • Max 50MB
                
              
              
                Select Files
              
            
          

          {/* Upload Progress List */}
          {uploadFilesList.length > 0 && (
            
              
              Upload Progress
              
                {uploadFilesList.map((file) => (
                  
                    
                      
                        
                          {getStatusIcon(file.status)}
                          
                            {file.file.name}
                            
                              {formatFileSize(file.file.size)} • {file.status}
                            
                          
                        
                        
                          {file.status}
                        
                      
                      
                      {file.error && (
                        {file.error}
                      )}
                      {file.bookId && file.status === 'completed' && (
                        
                          ID: {file.bookId.substring(0, 8)}...
                        
                      )}
                    
                  
                ))}
              
            
          )}
        
      
    
  )
}