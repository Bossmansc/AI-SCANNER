import { useState, useCallback } from 'react'
import axios from 'axios'
import { useToast } from '@/components/ui/use-toast'

interface UploadFile {
  id: string
  file: File
  progress: number
  status: 'pending' | 'uploading' | 'processing' | 'completed' | 'error'
  error?: string
  bookId?: string
}

interface UploadOptions {
  scanDepth: 'shallow' | 'medium' | 'deep'
  title?: string
}

export interface Book {
  id: number
  book_id: string
  title: string
  file_name: string
  file_size: number
  file_type: string
  chunk_count: number
  scan_depth: string
  upload_status: string
  uploaded_at: string
  processed_at?: string
  character_count: number
  word_count: number
  processing_error?: string
}

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'https://ai-scanner-j2c9.onrender.com/api/v1'

export function useFileUpload() {
  const [uploadFiles, setUploadFiles] = useState([])
  const [books, setBooks] = useState([])
  const [isLoading, setIsLoading] = useState(false)
  const { toast } = useToast()

  // Fetch books from API
  const fetchBooks = useCallback(async () => {
    try {
      setIsLoading(true)
      const response = await axios.get(`${API_BASE_URL}/books/`)
      setBooks(response.data)
    } catch (error) {
      console.error('Error fetching books:', error)
      toast({
        title: 'Error',
        description: 'Failed to load books',
        variant: 'destructive',
      })
    } finally {
      setIsLoading(false)
    }
  }, [toast])

  // Poll processing status
  const pollProcessingStatus = useCallback(async (bookId: string, uploadId: string) => {
    const maxAttempts = 60 // 5 minutes at 5-second intervals
    let attempts = 0

    const checkStatus = async () => {
      try {
        const response = await axios.get(`${API_BASE_URL}/books/${bookId}/status`)
        const { status, progress, message } = response.data

        setUploadFiles(prev =>
          prev.map(f =>
            f.id === uploadId
              ? {
                  ...f,
                  progress: 95 + (progress * 5), // Map 0-1 backend progress to 95-100% UI progress
                  status: status === 'completed' ? 'completed' : 'processing',
                  error: status === 'failed' ? message : f.error,
                }
              : f
          )
        )

        if (status === 'completed') {
          toast({
            title: 'Upload Complete',
            description: 'File processed and ready for chat',
          })
          await fetchBooks() // Refresh book list
          return true
        }

        if (status === 'failed') {
          toast({
            title: 'Processing Failed',
            description: message || 'File processing failed',
            variant: 'destructive',
          })
          return true
        }

        attempts++
        return false
      } catch (error) {
        console.error('Status check error:', error)
        attempts++
        return attempts >= maxAttempts
      }
    }

    const poll = async () => {
      let done = false
      while (!done && attempts  setTimeout(resolve, 5000)) // 5 seconds
        }
      }

      if (attempts >= maxAttempts) {
        setUploadFiles(prev =>
          prev.map(f =>
            f.id === uploadId
              ? {
                  ...f,
                  status: 'error',
                  error: 'Processing timeout',
                  progress: 0,
                }
              : f
          )
        )
        toast({
          title: 'Processing Timeout',
          description: 'File processing took too long',
          variant: 'destructive',
        })
      }
    }

    poll()
  }, [toast, fetchBooks])

  // Upload single file
  const uploadFile = useCallback(async (file: File, options: UploadOptions) => {
    const formData = new FormData()
    formData.append('file', file)
    formData.append('scan_depth', options.scanDepth)
    if (options.title) {
      formData.append('title', options.title)
    }

    const uploadFileEntry: UploadFile = {
      id: Date.now().toString() + Math.random().toString(),
      file,
      progress: 0,
      status: 'pending',
    }

    setUploadFiles(prev => [...prev, uploadFileEntry])

    try {
      // Update status to uploading
      setUploadFiles(prev =>
        prev.map(f =>
          f.id === uploadFileEntry.id
            ? { ...f, status: 'uploading', progress: 10 }
            : f
        )
      )

      const response = await axios.post(
        `${API_BASE_URL}/books/upload`,
        formData,
        {
          headers: {
            'Content-Type': 'multipart/form-data',
          },
          onUploadProgress: progressEvent => {
            if (progressEvent.total) {
              const progress = Math.round(
                (progressEvent.loaded * 90) / progressEvent.total
              )
              setUploadFiles(prev =>
                prev.map(f =>
                  f.id === uploadFileEntry.id
                    ? { ...f, progress: 10 + progress }
                    : f
                )
              )
            }
          },
        }
      )

      const { book_id } = response.data

      // Update with book ID and set to processing
      setUploadFiles(prev =>
        prev.map(f =>
          f.id === uploadFileEntry.id
            ? { ...f, status: 'processing', progress: 95, bookId: book_id }
            : f
        )
      )

      // Start polling
      await pollProcessingStatus(book_id, uploadFileEntry.id)

    } catch (error: any) {
      console.error('Upload error:', error)
      const errorMessage = error.response?.data?.detail || 'Upload failed'

      setUploadFiles(prev =>
        prev.map(f =>
          f.id === uploadFileEntry.id
            ? {
                ...f,
                status: 'error',
                error: errorMessage,
                progress: 0,
              }
            : f
        )
      )

      toast({
        title: 'Upload Failed',
        description: errorMessage,
        variant: 'destructive',
      })
    }
  }, [toast, pollProcessingStatus])

  // Upload multiple files
  const uploadMultipleFiles = useCallback(async (files: File[], options: UploadOptions) => {
    for (const file of files) {
      await uploadFile(file, options)
      // Small delay between uploads to avoid overwhelming the server
      await new Promise(resolve => setTimeout(resolve, 500))
    }
  }, [uploadFile])

  // Delete book
  const deleteBook = useCallback(async (bookId: string) => {
    try {
      await axios.delete(`${API_BASE_URL}/books/${bookId}`)
      setBooks(prev => prev.filter(book => book.book_id !== bookId))
      toast({
        title: 'Book Deleted',
        description: 'Book has been removed',
      })
    } catch (error: any) {
      console.error('Delete error:', error)
      toast({
        title: 'Delete Failed',
        description: error.response?.data?.detail || 'Failed to delete book',
        variant: 'destructive',
      })
    }
  }, [toast])

  // Clear completed uploads
  const clearCompletedUploads = useCallback(() => {
    setUploadFiles(prev => prev.filter(file => file.status !== 'completed' && file.status !== 'error'))
  }, [])

  // Get upload statistics
  const getUploadStats = useCallback(() => {
    const total = uploadFiles.length
    const completed = uploadFiles.filter(f => f.status === 'completed').length
    const processing = uploadFiles.filter(f => f.status === 'processing' || f.status === 'uploading').length
    const errors = uploadFiles.filter(f => f.status === 'error').length
    const pending = uploadFiles.filter(f => f.status === 'pending').length

    return { total, completed, processing, errors, pending }
  }, [uploadFiles])

  return {
    uploadFilesList: uploadFiles,
    books,
    isLoading,
    uploadFile,
    uploadMultipleFiles,
    deleteBook,
    fetchBooks,
    clearCompletedUploads,
    getUploadStats,
  }
}