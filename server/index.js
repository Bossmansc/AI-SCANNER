/**
 * CodeCraft AI - High-Concurrency Express Backend Entry Point
 * 
 * This module initializes the Express application, configures middleware,
 * establishes database connections, and handles server lifecycle events.
 * 
 * Features:
 * - Security (Helmet, CORS, Rate Limiting)
 * - Logging (Morgan)
 * - Body Parsing (JSON, URL-encoded)
 * - Global Error Handling
 * - Graceful Shutdown
 * - Uncaught Exception/Rejection Handling
 */

import express from 'express';
import http from 'http';
import cors from 'cors';
import helmet from 'helmet';
import morgan from 'morgan';
import dotenv from 'dotenv';
import rateLimit from 'express-rate-limit';
import compression from 'compression';
import mongoose from 'mongoose'; // Assuming MongoDB for persistence
import path from 'path';
import { fileURLToPath } from 'url';

// --- Configuration & Environment Setup ---
dotenv.config();

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const PORT = process.env.PORT || 5000;
const NODE_ENV = process.env.NODE_ENV || 'development';
const MONGO_URI = process.env.MONGO_URI || 'mongodb://localhost:27017/codecraft_db';
const CORS_ORIGIN = process.env.CORS_ORIGIN || '*';

// --- Application Initialization ---
const app = express();
const server = http.createServer(app);

// --- Middleware Layer ---

// 1. Security Headers
app.use(helmet());

// 2. Cross-Origin Resource Sharing
app.use(cors({
  origin: CORS_ORIGIN,
  methods: ['GET', 'POST', 'PUT', 'DELETE', 'PATCH'],
  allowedHeaders: ['Content-Type', 'Authorization'],
  credentials: true,
}));

// 3. Request Logging
if (NODE_ENV === 'development') {
  app.use(morgan('dev'));
} else {
  app.use(morgan('combined'));
}

// 4. Body Parsing
app.use(express.json({ limit: '10mb' })); // Limit payload size for security
app.use(express.urlencoded({ extended: true, limit: '10mb' }));

// 5. Compression (Gzip)
app.use(compression());

// 6. Rate Limiting (DDoS Protection)
const apiLimiter = rateLimit({
  windowMs: 15 * 60 * 1000, // 15 minutes
  max: 100, // Limit each IP to 100 requests per windowMs
  standardHeaders: true, // Return rate limit info in the `RateLimit-*` headers
  legacyHeaders: false, // Disable the `X-RateLimit-*` headers
  message: {
    status: 429,
    error: 'Too Many Requests',
    message: 'You have exceeded the request limit. Please try again later.'
  }
});

// Apply rate limiter to API routes only
app.use('/api', apiLimiter);

// --- Database Connection ---
const connectDB = async () => {
  try {
    const conn = await mongoose.connect(MONGO_URI, {
      // Mongoose 6+ defaults these to true, but explicit is better for clarity in older docs
      autoIndex: NODE_ENV === 'development', 
      serverSelectionTimeoutMS: 5000,
    });
    console.log(`[Database] MongoDB Connected: ${conn.connection.host}`);
  } catch (error) {
    console.error(`[Database] Error: ${error.message}`);
    process.exit(1); // Exit process with failure
  }
};

// --- Route Definitions ---

// Health Check Endpoint
app.get('/health', (req, res) => {
  res.status(200).json({
    status: 'UP',
    timestamp: new Date().toISOString(),
    uptime: process.uptime(),
    environment: NODE_ENV
  });
});

// API Routes Placeholder
// In a real architecture, these would be imported from ./routes/index.js
// app.use('/api/v1/auth', authRoutes);
// app.use('/api/v1/users', userRoutes);

// Mock API Route for demonstration
app.get('/api/v1/demo', (req, res) => {
  res.json({ message: 'CodeCraft AI Server is operational.' });
});

// Static Files (if serving frontend from same server)
if (NODE_ENV === 'production') {
  app.use(express.static(path.join(__dirname, '../client/dist')));
  
  // SPA Fallback
  app.get('*', (req, res) => {
    // Skip API routes
    if (req.path.startsWith('/api')) {
      return res.status(404).json({ error: 'API Endpoint Not Found' });
    }
    res.sendFile(path.resolve(__dirname, '../client/dist', 'index.html'));
  });
} else {
  app.get('/', (req, res) => {
    res.send('API is running in Development Mode...');
  });
}

// --- Error Handling Middleware ---

// 404 Handler for undefined API routes
app.use((req, res, next) => {
  const error = new Error(`Not Found - ${req.originalUrl}`);
  res.status(404);
  next(error);
});

// Global Error Handler
app.use((err, req, res, next) => {
  const statusCode = res.statusCode === 200 ? 500 : res.statusCode;
  
  // Log error stack in development
  if (NODE_ENV === 'development') {
    console.error(err.stack);
  }

  res.status(statusCode).json({
    success: false,
    error: statusCode === 500 ? 'Internal Server Error' : err.name,
    message: err.message,
    stack: NODE_ENV === 'production' ? '🥞' : err.stack,
  });
});

// --- Server Startup & Lifecycle ---

const startServer = async () => {
  // Connect to DB first
  await connectDB();

  server.listen(PORT, () => {
    console.log(`\n[Server] CodeCraft AI Engine running in ${NODE_ENV} mode on port ${PORT}`);
    console.log(`[Server] Health Check: http://localhost:${PORT}/health`);
  });
};

// Handle Unhandled Promise Rejections
process.on('unhandledRejection', (err, promise) => {
  console.error(`[Process] Unhandled Rejection at:`, promise, `reason:`, err);
  // Close server & exit process
  server.close(() => process.exit(1));
});

// Handle Uncaught Exceptions
process.on('uncaughtException', (err) => {
  console.error(`[Process] Uncaught Exception: ${err.message}`);
  console.error(err.stack);
  process.exit(1);
});

// Graceful Shutdown (SIGTERM/SIGINT)
const gracefulShutdown = (signal) => {
  console.log(`\n[Process] ${signal} received. Shutting down gracefully...`);
  server.close(() => {
    console.log('[Server] HTTP server closed.');
    mongoose.connection.close(false, () => {
      console.log('[Database] MongoDB connection closed.');
      process.exit(0);
    });
  });
};

process.on('SIGTERM', () => gracefulShutdown('SIGTERM'));
process.on('SIGINT', () => gracefulShutdown('SIGINT'));

// Ignite
startServer();
