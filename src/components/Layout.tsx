import React, { useState } from 'react'
import { Outlet, Link, useLocation } from 'react-router-dom'
import { 
  Home, 
  MessageSquare, 
  BookOpen, 
  Settings, 
  Upload, 
  Menu, 
  Bot,
  User
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Separator } from '@/components/ui/separator'
import { cn } from '@/lib/utils'

const navigation = [
  { name: 'Dashboard', href: '/dashboard', icon: Home },
  { name: 'Chat', href: '/chat', icon: MessageSquare },
  { name: 'Books', href: '/books', icon: BookOpen },
  { name: 'Settings', href: '/settings', icon: Settings },
]

export default function Layout() {
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const location = useLocation()

  return (
    
      {/* Mobile sidebar backdrop */}
      {sidebarOpen && (
         setSidebarOpen(false)}
        />
      )}

      {/* Sidebar */}
      
        
          {/* Logo */}
          
             setSidebarOpen(false)}>
              
              
                Document
                Engine
              
            
          

          {/* Navigation */}
          
            {navigation.map((item) => {
              const isActive = location.pathname.startsWith(item.href)
              return (
                 setSidebarOpen(false)}
                  className={cn(
                    'flex items-center gap-3 rounded-lg px-3 py-2.5   transition-colors',
                    isActive
                      ? 'bg-primary '
                      : 'hover:bg-accent hover:'
                  )}
                >
                  
                  {item.name}
                
              )
            })}
            
            
            
            {/* Quick Upload */}
             setSidebarOpen(false)}
              className="flex items-center gap-3 rounded-lg px-3 py-2.5   bg-primary/10  hover:bg-primary/20 transition-colors"
            >
              
              Quick Upload
            
          

          {/* User Section */}
          
            
              
                
              
              
                Guest User
                Free Plan
              
            
          
        
      

      {/* Main Content */}
      
        {/* Top Bar */}
        
           setSidebarOpen(true)}
          >
            
          
          
          
            
              
                {navigation.find(item => location.pathname.startsWith(item.href))?.name || 'Document Engine'}
              
            
            
            
              
                
                  
                  Upload
                
              
            
          
        

        {/* Page Content */}
        
          
        
      
    
  )
}