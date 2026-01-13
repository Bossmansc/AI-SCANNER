import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { Toaster } from '@/components/ui/toaster'
import { TooltipProvider } from '@/components/ui/tooltip'
import Layout from '@/components/Layout'
import Dashboard from '@/pages/Dashboard'
import ChatPage from '@/pages/ChatPage'
import BooksPage from '@/pages/BooksPage'
import SettingsPage from '@/pages/SettingsPage'
import NotFound from '@/pages/NotFound'

// Create a client
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: false,
      retry: 1,
      staleTime: 5 * 60 * 1000, // 5 minutes
    },
  },
})

function App() {
  return (
    
      
        
          
            
              }>
                } />
                } />
                } />
                } />
                } />
                } />
                } />
              
            
            
          
        
      
    
  )
}

export default App