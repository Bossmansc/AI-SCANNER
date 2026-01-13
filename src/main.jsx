import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import { Provider } from 'react-redux'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { ReactQueryDevtools } from '@tanstack/react-query-devtools'
import { ThemeProvider } from '@mui/material/styles'
import CssBaseline from '@mui/material/CssBaseline'
import { LocalizationProvider } from '@mui/x-date-pickers'
import { AdapterDateFns } from '@mui/x-date-pickers/AdapterDateFns'
import { SnackbarProvider } from 'notistack'

import App from './App'
import { store } from './store/store'
import theme from './theme/theme'
import './index.css'
import { ErrorBoundary } from './components/ErrorBoundary/ErrorBoundary'
import { AuthProvider } from './contexts/AuthContext'
import { initializeAppMonitoring } from './utils/monitoring'
import { registerServiceWorker } from './utils/serviceWorker'

// Initialize application monitoring
initializeAppMonitoring()

// Create React Query client with default options
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 5 * 60 * 1000, // 5 minutes
      cacheTime: 10 * 60 * 1000, // 10 minutes
      retry: 1,
      refetchOnWindowFocus: false,
      refetchOnMount: true,
      refetchOnReconnect: true,
    },
    mutations: {
      retry: 0,
    },
  },
})

// Root container element
const container = document.getElementById('root')

if (!container) {
  throw new Error('Failed to find the root element. Please check your index.html file.')
}

// Create root instance
const root = ReactDOM.createRoot(container)

// Application bootstrap function
const bootstrapApp = () => {
  root.render(
    <React.StrictMode>
      <ErrorBoundary>
        <Provider store={store}>
          <QueryClientProvider client={queryClient}>
            <LocalizationProvider dateAdapter={AdapterDateFns}>
              <ThemeProvider theme={theme}>
                <CssBaseline />
                <SnackbarProvider
                  maxSnack={3}
                  anchorOrigin={{
                    vertical: 'bottom',
                    horizontal: 'right',
                  }}
                  autoHideDuration={5000}
                >
                  <BrowserRouter>
                    <AuthProvider>
                      <App />
                    </AuthProvider>
                  </BrowserRouter>
                </SnackbarProvider>
              </ThemeProvider>
            </LocalizationProvider>
            {process.env.NODE_ENV === 'development' && (
              <ReactQueryDevtools initialIsOpen={false} position="bottom-right" />
            )}
          </QueryClientProvider>
        </Provider>
      </ErrorBoundary>
    </React.StrictMode>
  )
}

// Register service worker for PWA capabilities
if ('serviceWorker' in navigator && process.env.NODE_ENV === 'production') {
  registerServiceWorker()
    .then(() => {
      console.log('Service Worker registered successfully')
      bootstrapApp()
    })
    .catch((error) => {
      console.error('Service Worker registration failed:', error)
      bootstrapApp()
    })
} else {
  bootstrapApp()
}

// Performance monitoring
if (process.env.NODE_ENV === 'development') {
  // Report web vitals in development
  const reportWebVitals = (onPerfEntry) => {
    if (onPerfEntry && onPerfEntry instanceof Function) {
      import('web-vitals').then(({ getCLS, getFID, getFCP, getLCP, getTTFB }) => {
        getCLS(onPerfEntry)
        getFID(onPerfEntry)
        getFCP(onPerfEntry)
        getLCP(onPerfEntry)
        getTTFB(onPerfEntry)
      })
    }
  }
  
  reportWebVitals(console.log)
}

// Global error handler for uncaught errors
window.addEventListener('error', (event) => {
  console.error('Uncaught error:', event.error)
  // Here you would typically send to your error tracking service
})

// Global promise rejection handler
window.addEventListener('unhandledrejection', (event) => {
  console.error('Unhandled promise rejection:', event.reason)
  // Here you would typically send to your error tracking service
})

// Export for testing purposes
export { queryClient }
