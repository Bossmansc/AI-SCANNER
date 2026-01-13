import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App.jsx'
import './index.css'

// Locate the root element in the HTML document
const rootElement = document.getElementById('root')

// Safety check to ensure the root element exists before attempting to render
if (!rootElement) {
  throw new Error('Failed to find the root element. Ensure there is a <div id="root"></div> in your index.html.')
}

// Create the React root using the new Concurrent Mode API (React 18+)
const root = ReactDOM.createRoot(rootElement)

// Render the application wrapped in StrictMode for development checks
root.render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
)
