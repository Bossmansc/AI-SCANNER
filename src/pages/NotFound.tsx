import React from 'react'
import { useNavigate } from 'react-router-dom'
import { Button } from '@/components/ui/button'
import { Home, ArrowLeft } from 'lucide-react'

export default function NotFound() {
  const navigate = useNavigate()

  return (
    
      
        
          404
          
            Page Not Found
          
        

        Oops! Lost in the documents?
        
        
          The page you're looking for doesn't exist or has been moved. 
          Don't worry, your documents are safe.
        

        
           navigate('/')}
            className="w-full flex items-center justify-center gap-2"
            size="lg"
          >
            
            Go to Dashboard
          

           navigate(-1)}
            variant="outline"
            className="w-full flex items-center justify-center gap-2"
          >
            
            Go Back
          
        
      
    
  )
}