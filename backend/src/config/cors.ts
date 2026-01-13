/**
 * CORS Configuration Module
 * 
 * Configures Cross-Origin Resource Sharing for the backend API.
 * Provides secure, flexible CORS policies for development and production.
 */

import { CorsOptions } from 'cors';

/**
 * Environment-based CORS configuration
 */
export interface CorsConfig {
  /**
   * Array of allowed origins (wildcards supported)
   */
  allowedOrigins: string[];
  
  /**
   * Whether to allow credentials (cookies, authorization headers)
   */
  allowCredentials: boolean;
  
  /**
   * Maximum age for preflight requests cache (in seconds)
   */
  maxAge: number;
  
  /**
   * Array of allowed HTTP methods
   */
  allowedMethods: string[];
  
  /**
   * Array of allowed HTTP headers
   */
  allowedHeaders: string[];
  
  /**
   * Array of exposed headers to the client
   */
  exposedHeaders: string[];
  
  /**
   * Whether to enable CORS for all routes
   */
  enableForAllRoutes: boolean;
}

/**
 * Default CORS configuration
 */
const DEFAULT_CORS_CONFIG: CorsConfig = {
  allowedOrigins: [],
  allowCredentials: true,
  maxAge: 86400, // 24 hours
  allowedMethods: ['GET', 'POST', 'PUT', 'PATCH', 'DELETE', 'OPTIONS'],
  allowedHeaders: [
    'Origin',
    'X-Requested-With',
    'Content-Type',
    'Accept',
    'Authorization',
    'X-Api-Key',
    'X-Client-Version',
    'X-Client-Platform',
    'X-Session-ID',
    'X-CSRF-Token',
    'X-Request-ID',
  ],
  exposedHeaders: [
    'X-RateLimit-Limit',
    'X-RateLimit-Remaining',
    'X-RateLimit-Reset',
    'X-Request-ID',
    'X-Response-Time',
    'X-Total-Count',
    'X-Page-Count',
  ],
  enableForAllRoutes: true,
};

/**
 * Development-specific CORS configuration
 */
const DEVELOPMENT_CORS_CONFIG: CorsConfig = {
  ...DEFAULT_CORS_CONFIG,
  allowedOrigins: [
    'http://localhost:3000',
    'http://localhost:3001',
    'http://localhost:5173',
    'http://localhost:8080',
    'http://127.0.0.1:3000',
    'http://127.0.0.1:3001',
    'http://127.0.0.1:5173',
    'http://127.0.0.1:8080',
  ],
  allowCredentials: true,
};

/**
 * Production-specific CORS configuration
 */
const PRODUCTION_CORS_CONFIG: CorsConfig = {
  ...DEFAULT_CORS_CONFIG,
  allowedOrigins: [], // Should be explicitly set via environment variables
  allowCredentials: true,
  maxAge: 86400, // 24 hours
};

/**
 * Environment variable parser for CORS origins
 */
const parseCorsOriginsFromEnv = (): string[] => {
  const originsEnv = process.env.CORS_ALLOWED_ORIGINS;
  if (!originsEnv) {
    return [];
  }
  
  return originsEnv
    .split(',')
    .map(origin => origin.trim())
    .filter(origin => origin.length > 0);
};

/**
 * Environment variable parser for CORS methods
 */
const parseCorsMethodsFromEnv = (): string[] => {
  const methodsEnv = process.env.CORS_ALLOWED_METHODS;
  if (!methodsEnv) {
    return DEFAULT_CORS_CONFIG.allowedMethods;
  }
  
  return methodsEnv
    .split(',')
    .map(method => method.trim().toUpperCase())
    .filter(method => method.length > 0);
};

/**
 * Environment variable parser for CORS headers
 */
const parseCorsHeadersFromEnv = (): string[] => {
  const headersEnv = process.env.CORS_ALLOWED_HEADERS;
  if (!headersEnv) {
    return DEFAULT_CORS_CONFIG.allowedHeaders;
  }
  
  const headers = headersEnv
    .split(',')
    .map(header => header.trim())
    .filter(header => header.length > 0);
  
  // Always include essential headers
  const essentialHeaders = ['Origin', 'Content-Type', 'Accept', 'Authorization'];
  return [...new Set([...essentialHeaders, ...headers])];
};

/**
 * Get environment-specific CORS configuration
 */
export const getCorsConfig = (): CorsConfig => {
  const nodeEnv = process.env.NODE_ENV || 'development';
  
  let config: CorsConfig;
  
  switch (nodeEnv) {
    case 'production':
      config = { ...PRODUCTION_CORS_CONFIG };
      break;
    case 'development':
    default:
      config = { ...DEVELOPMENT_CORS_CONFIG };
      break;
  }
  
  // Override with environment variables if present
  const envOrigins = parseCorsOriginsFromEnv();
  if (envOrigins.length > 0) {
    config.allowedOrigins = envOrigins;
  }
  
  const envMethods = parseCorsMethodsFromEnv();
  if (envMethods.length > 0) {
    config.allowedMethods = envMethods;
  }
  
  const envHeaders = parseCorsHeadersFromEnv();
  if (envHeaders.length > 0) {
    config.allowedHeaders = envHeaders;
  }
  
  // Parse boolean environment variables
  if (process.env.CORS_ALLOW_CREDENTIALS) {
    config.allowCredentials = process.env.CORS_ALLOW_CREDENTIALS.toLowerCase() === 'true';
  }
  
  if (process.env.CORS_MAX_AGE) {
    const maxAge = parseInt(process.env.CORS_MAX_AGE, 10);
    if (!isNaN(maxAge) && maxAge > 0) {
      config.maxAge = maxAge;
    }
  }
  
  if (process.env.CORS_ENABLE_FOR_ALL_ROUTES) {
    config.enableForAllRoutes = process.env.CORS_ENABLE_FOR_ALL_ROUTES.toLowerCase() === 'true';
  }
  
  // Add exposed headers from environment if present
  if (process.env.CORS_EXPOSED_HEADERS) {
    const exposedHeaders = process.env.CORS_EXPOSED_HEADERS
      .split(',')
      .map(header => header.trim())
      .filter(header => header.length > 0);
    
    if (exposedHeaders.length > 0) {
      config.exposedHeaders = [...new Set([...config.exposedHeaders, ...exposedHeaders])];
    }
  }
  
  return config;
};

/**
 * Origin validation function
 * 
 * @param origin - The origin to validate
 * @param allowedOrigins - Array of allowed origins
 * @returns boolean indicating if origin is allowed
 */
export const validateOrigin = (
  origin: string | undefined,
  allowedOrigins: string[]
): boolean => {
  // Allow requests with no origin (e.g., same-origin, mobile apps, curl)
  if (!origin) {
    return true;
  }
  
  // If no origins are specified, deny all cross-origin requests
  if (allowedOrigins.length === 0) {
    return false;
  }
  
  // Check against allowed origins
  return allowedOrigins.some(allowedOrigin => {
    // Exact match
    if (allowedOrigin === origin) {
      return true;
    }
    
    // Wildcard subdomain matching (e.g., *.example.com)
    if (allowedOrigin.startsWith('*.')) {
      const domain = allowedOrigin.substring(2);
      const originUrl = new URL(origin);
      const originHostname = originUrl.hostname;
      
      // Match subdomains of the specified domain
      if (originHostname === domain || originHostname.endsWith(`.${domain}`)) {
        return true;
      }
    }
    
    // Protocol-relative matching (e.g., //example.com)
    if (allowedOrigin.startsWith('//')) {
      const domain = allowedOrigin.substring(2);
      const originUrl = new URL(origin);
      const originHost = originUrl.host;
      
      if (originHost === domain) {
        return true;
      }
    }
    
    return false;
  });
};

/**
 * Create CORS options for the cors middleware
 * 
 * @param config - CORS configuration
 * @returns CorsOptions for the cors middleware
 */
export const createCorsOptions = (config: CorsConfig = getCorsConfig()): CorsOptions => {
  return {
    origin: (origin, callback) => {
      const isValidOrigin = validateOrigin(origin, config.allowedOrigins);
      
      if (isValidOrigin) {
        callback(null, true);
      } else {
        console.warn(`CORS: Blocked request from origin: ${origin}`);
        callback(new Error(`Origin ${origin} not allowed by CORS policy`));
      }
    },
    credentials: config.allowCredentials,
    maxAge: config.maxAge,
    methods: config.allowedMethods,
    allowedHeaders: config.allowedHeaders,
    exposedHeaders: config.exposedHeaders,
    preflightContinue: false,
    optionsSuccessStatus: 204,
  };
};

/**
 * CORS middleware factory
 * 
 * @param config - Optional custom CORS configuration
 * @returns CORS middleware function
 */
export const createCorsMiddleware = (config?: CorsConfig) => {
  const cors = require('cors');
  const corsOptions = createCorsOptions(config);
  return cors(corsOptions);
};

/**
 * Route-specific CORS middleware
 * Useful for applying different CORS policies to specific routes
 * 
 * @param config - CORS configuration for this route
 * @returns CORS middleware function
 */
export const createRouteSpecificCors = (config: Partial<CorsConfig> = {}) => {
  const cors = require('cors');
  const baseConfig = getCorsConfig();
  const routeConfig: CorsConfig = { ...baseConfig, ...config };
  const corsOptions = createCorsOptions(routeConfig);
  return cors(corsOptions);
};

/**
 * Preflight handler for manual CORS implementation
 * Useful for routes that need custom CORS handling
 * 
 * @param req - Express request object
 * @param res - Express response object
 * @param config - CORS configuration
 */
export const handlePreflight = (req: any, res: any, config: CorsConfig = getCorsConfig()) => {
  const origin = req.headers.origin;
  
  // Validate origin
  if (origin && !validateOrigin(origin, config.allowedOrigins)) {
    res.status(403).json({
      error: 'CORS policy violation',
      message: `Origin ${origin} not allowed`,
    });
    return;
  }
  
  // Set CORS headers
  if (origin) {
    res.setHeader('Access-Control-Allow-Origin', origin);
  }
  
  if (config.allowCredentials) {
    res.setHeader('Access-Control-Allow-Credentials', 'true');
  }
  
  res.setHeader('Access-Control-Allow-Methods', config.allowedMethods.join(', '));
  res.setHeader('Access-Control-Allow-Headers', config.allowedHeaders.join(', '));
  res.setHeader('Access-Control-Max-Age', config.maxAge.toString());
  
  if (config.exposedHeaders.length > 0) {
    res.setHeader('Access-Control-Expose-Headers', config.exposedHeaders.join(', '));
  }
  
  res.status(204).end();
};

/**
 * Apply CORS headers to response
 * Useful for manual CORS header injection
 * 
 * @param res - Express response object
 * @param config - CORS configuration
 * @param origin - Specific origin to allow (optional)
 */
export const applyCorsHeaders = (
  res: any,
  config: CorsConfig = getCorsConfig(),
  origin?: string
) => {
  const allowedOrigin = origin || (res.req?.headers?.origin as string);
  
  if (allowedOrigin && validateOrigin(allowedOrigin, config.allowedOrigins)) {
    res.setHeader('Access-Control-Allow-Origin', allowedOrigin);
  }
  
  if (config.allowCredentials) {
    res.setHeader('Access-Control-Allow-Credentials', 'true');
  }
  
  if (config.exposedHeaders.length > 0) {
    res.setHeader('Access-Control-Expose-Headers', config.exposedHeaders.join(', '));
  }
};

/**
 * CORS error handler middleware
 * Catches CORS errors and returns appropriate responses
 */
export const corsErrorHandler = (err: any, req: any, res: any, next: any) => {
  if (err && err.message && err.message.includes('CORS')) {
    res.status(403).json({
      error: 'CORS Error',
      message: err.message,
      timestamp: new Date().toISOString(),
      path: req.path,
    });
    return;
  }
  
  next(err);
};

/**
 * Health check endpoint with CORS
 * Useful for verifying CORS configuration
 */
export const corsHealthCheck = (req: any, res: any) => {
  const config = getCorsConfig();
  const origin = req.headers.origin;
  
  // Apply CORS headers
  applyCorsHeaders(res, config, origin);
  
  res.json({
    status: 'healthy',
    cors: {
      allowedOrigins: config.allowedOrigins,
      allowCredentials: config.allowCredentials,
      allowedMethods: config.allowedMethods,
      allowedHeaders: config.allowedHeaders,
      currentOrigin: origin,
      originAllowed: validateOrigin(origin, config.allowedOrigins),
    },
    timestamp: new Date().toISOString(),
    environment: process.env.NODE_ENV || 'development',
  });
};

/**
 * Export default CORS middleware for app-wide use
 */
export default createCorsMiddleware();

// Export types and utilities
export type { CorsOptions };
