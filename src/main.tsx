import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App'
import './index.css'

// Initialize error boundary for better error handling
class ErrorBoundary extends React.Component {
  constructor(props: { children: React.ReactNode }) {
    super(props)
    this.state = { hasError: false }
  }

  static getDerivedStateFromError() {
    return { hasError: true }
  }

  componentDidCatch(error: Error, errorInfo: React.ErrorInfo) {
    console.error('React Error Boundary caught:', error, errorInfo)
  }

  render() {
    if (this.state.hasError) {
      return (
        
          
            
              Something went wrong
            
            
              The application encountered an error. Please refresh the page.
            
             window.location.reload()}
              className="px-4 py-2 bg-primary  rounded-md hover:bg-primary/90"
            >
              Refresh Page
            
          
        
      )
    }

    return this.props.children
  }
}

ReactDOM.createRoot(document.getElementById('root')!).render(
  
    
      
    
  
)