import React, { useState, useEffect } from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Label } from '@/components/ui/label'
import { Switch } from '@/components/ui/switch'
import { Separator } from '@/components/ui/separator'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Slider } from '@/components/ui/slider'
import { Save, Trash2, RefreshCw, Download, Upload } from 'lucide-react'
import { useToast } from '@/components/ui/use-toast'

export default function SettingsPage() {
  const { toast } = useToast()
  const [isSaving, setIsSaving] = useState(false)
  
  const [settings, setSettings] = useState({
    defaultContextDepth: 'medium',
    maxTokens: 8192,
    temperature: 0.7,
    streamingEnabled: true,
    theme: 'light',
    compactMode: false,
    animationsEnabled: true,
    autoSaveConversations: true,
    conversationRetentionDays: 30,
    autoClearUploads: true,
  })

  // Load settings from local storage on mount
  useEffect(() => {
    const saved = localStorage.getItem('document-engine-settings')
    if (saved) {
      try {
        setSettings(JSON.parse(saved))
      } catch (e) {
        console.error('Failed to parse settings', e)
      }
    }
  }, [])

  const handleSave = async () => {
    setIsSaving(true)
    try {
      // Simulate API call delay
      await new Promise(resolve => setTimeout(resolve, 800))
      
      localStorage.setItem('document-engine-settings', JSON.stringify(settings))
      
      toast({
        title: 'Settings Saved',
        description: 'Your preferences have been updated',
      })
    } catch (error) {
      toast({
        title: 'Save Failed',
        description: 'Failed to save settings',
        variant: 'destructive',
      })
    } finally {
      setIsSaving(false)
    }
  }

  const handleReset = () => {
    setSettings({
      defaultContextDepth: 'medium',
      maxTokens: 8192,
      temperature: 0.7,
      streamingEnabled: true,
      theme: 'light',
      compactMode: false,
      animationsEnabled: true,
      autoSaveConversations: true,
      conversationRetentionDays: 30,
      autoClearUploads: true,
    })
    
    toast({
      title: 'Settings Reset',
      description: 'All settings have been reset to defaults',
    })
  }

  return (
    
      
        Settings
        
          Configure your Document Engine experience
        
      

      
        {/* Left Column - Settings Forms */}
        
          {/* Chat Settings */}
          
            
              Chat Settings
              
                Configure how the AI interacts with your documents
              
            
            
              
                Default Context Depth
                 setSettings({ ...settings, defaultContextDepth: value })}
                >
                  
                    
                  
                  
                    Shallow (Fast, less detailed)
                    Medium (Balanced)
                    Deep (Slow, most detailed)
                  
                
              

              
                
                  Creativity (Temperature)
                  {settings.temperature.toFixed(1)}
                
                 setSettings({ ...settings, temperature: value })}
                  min={0}
                  max={1}
                  step={0.1}
                />
                
                  More Precise
                  More Creative
                
              

              
                
                  Streaming Responses
                  
                    Show responses as they're generated
                  
                
                 setSettings({ ...settings, streamingEnabled: checked })}
                />
              
            
          

          {/* UI Settings */}
          
            
              Interface Settings
              
                Customize the look and feel of the application
              
            
            
              
                Theme
                 setSettings({ ...settings, theme: value })}
                >
                  
                    
                  
                  
                    Light
                    Dark
                    System
                  
                
              

              
                
                  Compact Mode
                  
                    Reduce spacing for more content
                  
                
                 setSettings({ ...settings, compactMode: checked })}
                />
              
            
          

          {/* Data Management */}
          
            
              Data Management
              
                Control how your data is stored and managed
              
            
            
              
                
                  Auto-save Conversations
                  
                    Automatically save chat history
                  
                
                 setSettings({ ...settings, autoSaveConversations: checked })}
                />
              
              
              

              
                
                  
                  Reset to Defaults
                
              
            
          
        

        {/* Right Column - Actions */}
        
          
            
              Save Changes
              
                Apply your settings configuration
              
            
            
              
                {isSaving ? (
                  
                    
                    Saving...
                  
                ) : (
                  
                    
                    Save All Changes
                  
                )}
              
              
                Settings are saved to your browser's local storage
              
            
          
        
      
    
  )
}