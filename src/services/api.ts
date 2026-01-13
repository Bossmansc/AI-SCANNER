import axios from 'axios'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api/v1'

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
})

// Request interceptor for adding auth token
api.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('auth_token')
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  },
  (error) => {
    return Promise.reject(error)
  }
)

// Response interceptor for error handling
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      // Handle unauthorized access
      localStorage.removeItem('auth_token')
      window.location.href = '/login'
    }
    return Promise.reject(error)
  }
)

// Books API
export const booksApi = {
  // Get all books
  getAll: () => api.get('/books'),
  
  // Get book by ID
  getById: (bookId: string) => api.get(`/books/${bookId}`),
  
  // Upload book
  upload: (formData: FormData) => 
    api.post('/books/upload', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    }),
  
  // Delete book
  delete: (bookId: string) => api.delete(`/books/${bookId}`),
  
  // Get processing status
  getStatus: (bookId: string) => api.get(`/books/${bookId}/status`),
  
  // Search in book
  search: (bookId: string, query: string, k: number = 5, scoreThreshold: number = 0.5) =>
    api.post(`/books/search/${bookId}`, { query, k, score_threshold: scoreThreshold }),
}

// Chat API
export const chatApi = {
  // Stream chat (Note: Use fetch directly for streaming consumption in hooks)
  stream: (data: {
    message: string
    conversation_id?: string
    book_ids?: string[]
    context_depth?: string
  }) => api.post('/chat/stream', data),
  
  // Regular chat (non-streaming)
  chat: (data: {
    message: string
    conversation_id?: string
    book_ids?: string[]
    context_depth?: string
  }) => api.post('/chat', data),
  
  // Get conversations
  getConversations: (skip: number = 0, limit: number = 50) =>
    api.get('/chat/conversations', { params: { skip, limit } }),
  
  // Get conversation messages
  getConversationMessages: (conversationId: string, limit: number = 100) =>
    api.get(`/chat/conversations/${conversationId}`, { params: { limit } }),
  
  // Delete conversation
  deleteConversation: (conversationId: string) =>
    api.delete(`/chat/conversations/${conversationId}`),
  
  // Get available books for chat
  getAvailableBooks: () => api.get('/chat/books/available'),
  
  // Health check
  health: () => api.get('/chat/health'),
}

// Auth API (future use)
export const authApi = {
  login: (username: string, password: string) =>
    api.post('/auth/token', { username, password }),
  
  register: (email: string, username: string, password: string) =>
    api.post('/auth/register', { email, username, password }),
  
  getProfile: () => api.get('/auth/me'),
}

export default api