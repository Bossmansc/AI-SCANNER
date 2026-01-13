import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App';
import './index.css';

/**
 * Application Entry Point
 * 
 * This module initializes the React application by mounting the root component
 * to the DOM. It utilizes React 18's createRoot API for concurrent rendering features.
 */

// Locate the root DOM node
const rootElement = document.getElementById('root');

// Safety check to ensure the root element exists before attempting to mount
if (!rootElement) {
  const errorMessage = 'FATAL: Failed to find the root element. Ensure there is a <div id="root"></div> in your index.html.';
  console.error(errorMessage);
  throw new Error(errorMessage);
}

// Initialize the React root
const root = ReactDOM.createRoot(rootElement);

// Render the application wrapped in StrictMode for development checks
root.render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
