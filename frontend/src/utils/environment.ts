/**
 * Environment detection and URL helper utilities
 * Provides runtime environment detection, URL construction, and environment-specific configuration
 */

// ============================================================================
// TYPES AND INTERFACES
// ============================================================================

/**
 * Application environment types
 */
export type EnvironmentType = 
  | 'development'
  | 'staging'
  | 'production'
  | 'test'
  | 'preview';

/**
 * Environment configuration object
 */
export interface EnvironmentConfig {
  /** Current environment type */
  type: EnvironmentType;
  
  /** Base URL for API requests */
  apiBaseUrl: string;
  
  /** Base URL for WebSocket connections */
  wsBaseUrl: string;
  
  /** Application version */
  version: string;
  
  /** Build timestamp */
  buildTimestamp: string;
  
  /** Feature flags */
  features: {
    /** Enable debug mode with additional logging */
    debugMode: boolean;
    
    /** Enable performance monitoring */
    performanceMonitoring: boolean;
    
    /** Enable experimental features */
    experimentalFeatures: boolean;
    
    /** Enable analytics */
    analytics: boolean;
  };
  
  /** Third-party service configurations */
  services: {
    /** Sentry error tracking configuration */
    sentry: {
      dsn: string;
      enabled: boolean;
      environment: string;
    };
    
    /** Analytics service configuration */
    analytics: {
      trackingId: string;
      enabled: boolean;
    };
    
    /** Feature flag service */
    featureFlags: {
      endpoint: string;
      enabled: boolean;
    };
  };
}

/**
 * URL construction options
 */
export interface UrlOptions {
  /** URL protocol (defaults to current protocol) */
  protocol?: string;
  
  /** Hostname (defaults to current hostname) */
  hostname?: string;
  
  /** Port number */
  port?: number | string;
  
  /** Path segments to join */
  path?: string | string[];
  
  /** Query parameters as key-value pairs */
  query?: Record<string, string | number | boolean | null | undefined>;
  
  /** Hash fragment */
  hash?: string;
  
  /** Whether to include trailing slash */
  trailingSlash?: boolean;
}

/**
 * Parsed URL components
 */
export interface ParsedUrl {
  protocol: string;
  hostname: string;
  port: string;
  pathname: string;
  search: string;
  hash: string;
  origin: string;
  href: string;
}

// ============================================================================
// CONSTANTS
// ============================================================================

/**
 * Default environment configurations
 */
const DEFAULT_CONFIGS: Record<EnvironmentType, Omit<EnvironmentConfig, 'type'>> = {
  development: {
    apiBaseUrl: 'http://localhost:3000/api',
    wsBaseUrl: 'ws://localhost:3000',
    version: process.env.REACT_APP_VERSION || '0.0.0-dev',
    buildTimestamp: process.env.REACT_APP_BUILD_TIMESTAMP || new Date().toISOString(),
    features: {
      debugMode: true,
      performanceMonitoring: true,
      experimentalFeatures: true,
      analytics: false,
    },
    services: {
      sentry: {
        dsn: process.env.REACT_APP_SENTRY_DSN || '',
        enabled: false,
        environment: 'development',
      },
      analytics: {
        trackingId: process.env.REACT_APP_ANALYTICS_ID || '',
        enabled: false,
      },
      featureFlags: {
        endpoint: 'http://localhost:3000/api/flags',
        enabled: true,
      },
    },
  },
  
  test: {
    apiBaseUrl: 'http://localhost:3000/api',
    wsBaseUrl: 'ws://localhost:3000',
    version: '0.0.0-test',
    buildTimestamp: new Date().toISOString(),
    features: {
      debugMode: true,
      performanceMonitoring: false,
      experimentalFeatures: false,
      analytics: false,
    },
    services: {
      sentry: {
        dsn: '',
        enabled: false,
        environment: 'test',
      },
      analytics: {
        trackingId: '',
        enabled: false,
      },
      featureFlags: {
        endpoint: 'http://localhost:3000/api/flags',
        enabled: false,
      },
    },
  },
  
  staging: {
    apiBaseUrl: 'https://staging-api.example.com/api',
    wsBaseUrl: 'wss://staging-ws.example.com',
    version: process.env.REACT_APP_VERSION || '0.0.0-staging',
    buildTimestamp: process.env.REACT_APP_BUILD_TIMESTAMP || new Date().toISOString(),
    features: {
      debugMode: true,
      performanceMonitoring: true,
      experimentalFeatures: true,
      analytics: true,
    },
    services: {
      sentry: {
        dsn: process.env.REACT_APP_SENTRY_DSN || '',
        enabled: true,
        environment: 'staging',
      },
      analytics: {
        trackingId: process.env.REACT_APP_ANALYTICS_ID || '',
        enabled: true,
      },
      featureFlags: {
        endpoint: 'https://staging-api.example.com/api/flags',
        enabled: true,
      },
    },
  },
  
  production: {
    apiBaseUrl: 'https://api.example.com/api',
    wsBaseUrl: 'wss://ws.example.com',
    version: process.env.REACT_APP_VERSION || '1.0.0',
    buildTimestamp: process.env.REACT_APP_BUILD_TIMESTAMP || new Date().toISOString(),
    features: {
      debugMode: false,
      performanceMonitoring: true,
      experimentalFeatures: false,
      analytics: true,
    },
    services: {
      sentry: {
        dsn: process.env.REACT_APP_SENTRY_DSN || '',
        enabled: true,
        environment: 'production',
      },
      analytics: {
        trackingId: process.env.REACT_APP_ANALYTICS_ID || '',
        enabled: true,
      },
      featureFlags: {
        endpoint: 'https://api.example.com/api/flags',
        enabled: true,
      },
    },
  },
  
  preview: {
    apiBaseUrl: 'https://preview-api.example.com/api',
    wsBaseUrl: 'wss://preview-ws.example.com',
    version: process.env.REACT_APP_VERSION || '0.0.0-preview',
    buildTimestamp: process.env.REACT_APP_BUILD_TIMESTAMP || new Date().toISOString(),
    features: {
      debugMode: true,
      performanceMonitoring: true,
      experimentalFeatures: true,
      analytics: true,
    },
    services: {
      sentry: {
        dsn: process.env.REACT_APP_SENTRY_DSN || '',
        enabled: true,
        environment: 'preview',
      },
      analytics: {
        trackingId: process.env.REACT_APP_ANALYTICS_ID || '',
        enabled: true,
      },
      featureFlags: {
        endpoint: 'https://preview-api.example.com/api/flags',
        enabled: true,
      },
    },
  },
};

/**
 * Environment detection patterns
 */
const ENVIRONMENT_PATTERNS: Array<{
  pattern: RegExp;
  type: EnvironmentType;
}> = [
  { pattern: /localhost|127\.0\.0\.1|^192\.168|^10\./, type: 'development' },
  { pattern: /\.test\.|\.testing\.|test\./, type: 'test' },
  { pattern: /staging|stage|preprod/, type: 'staging' },
  { pattern: /preview|pr-/, type: 'preview' },
  { pattern: /.*/, type: 'production' }, // Default fallback
];

/**
 * Common ports for development
 */
export const COMMON_PORTS = {
  HTTP: 80,
  HTTPS: 443,
  DEV_SERVER: 3000,
  API_DEV: 3001,
  JSON_SERVER: 3002,
  WEB_SOCKET: 8080,
} as const;

// ============================================================================
// ENVIRONMENT DETECTION
// ============================================================================

/**
 * Detect the current environment based on hostname and URL
 * @returns Detected environment type
 */
export function detectEnvironment(): EnvironmentType {
  // Check for explicit environment variable (highest priority)
  const envFromVar = process.env.REACT_APP_ENV || process.env.NODE_ENV;
  
  if (envFromVar === 'production') return 'production';
  if (envFromVar === 'staging') return 'staging';
  if (envFromVar === 'test' || envFromVar === 'testing') return 'test';
  if (envFromVar === 'development') return 'development';
  
  // Detect from hostname
  const hostname = window.location.hostname;
  const href = window.location.href;
  
  // Check against patterns
  for (const { pattern, type } of ENVIRONMENT_PATTERNS) {
    if (pattern.test(hostname) || pattern.test(href)) {
      return type;
    }
  }
  
  // Default based on NODE_ENV
  return process.env.NODE_ENV === 'production' ? 'production' : 'development';
}

/**
 * Check if running in development environment
 * @returns True if in development
 */
export function isDevelopment(): boolean {
  return detectEnvironment() === 'development';
}

/**
 * Check if running in production environment
 * @returns True if in production
 */
export function isProduction(): boolean {
  return detectEnvironment() === 'production';
}

/**
 * Check if running in staging environment
 * @returns True if in staging
 */
export function isStaging(): boolean {
  return detectEnvironment() === 'staging';
}

/**
 * Check if running in test environment
 * @returns True if in test
 */
export function isTest(): boolean {
  return detectEnvironment() === 'test';
}

/**
 * Check if running in preview environment (PR deployments, etc.)
 * @returns True if in preview
 */
export function isPreview(): boolean {
  return detectEnvironment() === 'preview';
}

/**
 * Check if running on localhost
 * @returns True if on localhost
 */
export function isLocalhost(): boolean {
  const hostname = window.location.hostname;
  return hostname === 'localhost' || 
         hostname === '127.0.0.1' || 
         hostname.startsWith('192.168.') ||
         hostname.startsWith('10.');
}

/**
 * Check if running on mobile device
 * @returns True if on mobile device
 */
export function isMobile(): boolean {
  return /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(
    navigator.userAgent
  );
}

/**
 * Check if running on iOS device
 * @returns True if on iOS
 */
export function isIOS(): boolean {
  return /iPad|iPhone|iPod/.test(navigator.userAgent) && !(window as any).MSStream;
}

/**
 * Check if running on Android device
 * @returns True if on Android
 */
export function isAndroid(): boolean {
  return /Android/.test(navigator.userAgent);
}

/**
 * Check if running in iframe
 * @returns True if in iframe
 */
export function isInIframe(): boolean {
  try {
    return window.self !== window.top;
  } catch (e) {
    return true;
  }
}

// ============================================================================
// ENVIRONMENT CONFIGURATION
// ============================================================================

/**
 * Get the complete environment configuration
 * @returns Environment configuration object
 */
export function getEnvironmentConfig(): EnvironmentConfig {
  const envType = detectEnvironment();
  const baseConfig = DEFAULT_CONFIGS[envType];
  
  // Merge with environment variables for override capability
  const config: EnvironmentConfig = {
    type: envType,
    apiBaseUrl: process.env.REACT_APP_API_URL || baseConfig.apiBaseUrl,
    wsBaseUrl: process.env.REACT_APP_WS_URL || baseConfig.wsBaseUrl,
    version: process.env.REACT_APP_VERSION || baseConfig.version,
    buildTimestamp: process.env.REACT_APP_BUILD_TIMESTAMP || baseConfig.buildTimestamp,
    features: {
      debugMode: process.env.REACT_APP_DEBUG === 'true' ? true : 
                process.env.REACT_APP_DEBUG === 'false' ? false : 
                baseConfig.features.debugMode,
      performanceMonitoring: baseConfig.features.performanceMonitoring,
      experimentalFeatures: baseConfig.features.experimentalFeatures,
      analytics: baseConfig.features.analytics,
    },
    services: {
      sentry: {
        dsn: process.env.REACT_APP_SENTRY_DSN || baseConfig.services.sentry.dsn,
        enabled: process.env.REACT_APP_SENTRY_ENABLED === 'true' ? true :
                process.env.REACT_APP_SENTRY_ENABLED === 'false' ? false :
                baseConfig.services.sentry.enabled,
        environment: process.env.REACT_APP_SENTRY_ENV || baseConfig.services.sentry.environment,
      },
      analytics: {
        trackingId: process.env.REACT_APP_ANALYTICS_ID || baseConfig.services.analytics.trackingId,
        enabled: process.env.REACT_APP_ANALYTICS_ENABLED === 'true' ? true :
                process.env.REACT_APP_ANALYTICS_ENABLED === 'false' ? false :
                baseConfig.services.analytics.enabled,
      },
      featureFlags: {
        endpoint: process.env.REACT_APP_FEATURE_FLAGS_URL || baseConfig.services.featureFlags.endpoint,
        enabled: process.env.REACT_APP_FEATURE_FLAGS_ENABLED === 'true' ? true :
                process.env.REACT_APP_FEATURE_FLAGS_ENABLED === 'false' ? false :
                baseConfig.services.featureFlags.enabled,
      },
    },
  };
  
  return config;
}

/**
 * Get a specific environment variable with fallback
 * @param key Environment variable key
 * @param defaultValue Default value if not found
 * @returns Environment variable value or default
 */
export function getEnvVar(key: string, defaultValue: string = ''): string {
  // Check React environment variables
  const reactKey = `REACT_APP_${key}`;
  if (process.env[reactKey] !== undefined) {
    return process.env[reactKey] as string;
  }
  
  // Check generic environment variables
  if (process.env[key] !== undefined) {
    return process.env[key] as string;
  }
  
  return defaultValue;
}

/**
 * Get the API base URL for the current environment
 * @returns API base URL
 */
export function getApiBaseUrl(): string {
  return getEnvironmentConfig().apiBaseUrl;
}

/**
 * Get the WebSocket base URL for the current environment
 * @returns WebSocket base URL
 */
export function getWebSocketBaseUrl(): string {
  return getEnvironmentConfig().wsBaseUrl;
}

// ============================================================================
// URL CONSTRUCTION AND PARSING
// ============================================================================

/**
 * Construct a URL from components
 * @param options URL construction options
 * @returns Constructed URL string
 */
export function constructUrl(options: UrlOptions): string {
  const {
    protocol = window.location.protocol,
    hostname = window.location.hostname,
    port,
    path = '',
    query = {},
    hash = '',
    trailingSlash = false,
  } = options;
  
  // Build protocol
  const normalizedProtocol = protocol.endsWith(':') ? protocol : `${protocol}:`;
  
  // Build host with port
  let host = hostname;
  if (port && port !== COMMON_PORTS.HTTP && port !== COMMON_PORTS.HTTPS) {
    host = `${hostname}:${port}`;
  }
  
  // Build path
  let pathStr = '';
  if (Array.isArray(path)) {
    pathStr = '/' + path.filter(Boolean).join('/');
  } else if (path) {
    pathStr = path.startsWith('/') ? path : `/${path}`;
  }
  
  // Add trailing slash if requested
  if (trailingSlash && !pathStr.endsWith('/')) {
    pathStr += '/';
  } else if (!trailingSlash && pathStr.endsWith('/') && pathStr.length > 1) {
    pathStr = pathStr.slice(0, -1);
  }
  
  // Build query string
  const queryParams = new URLSearchParams();
  Object.entries(query).forEach(([key, value]) => {
    if (value !== null && value !== undefined) {
      queryParams.append(key, String(value));
    }
  });
  const queryString = queryParams.toString();
  const search = queryString ? `?${queryString}` : '';
  
  // Build hash
  const normalizedHash = hash ? (hash.startsWith('#') ? hash : `#${hash}`) : '';
  
  // Construct full URL
  return `${normalizedProtocol}//${host}${pathStr}${search}${normalizedHash}`;
}

/**
 * Parse a URL string into its components
 * @param url URL string to parse
 * @returns Parsed URL components
 * @throws Error if URL is invalid
 */
export function parseUrl(url: string): ParsedUrl {
  try {
    const urlObj = new URL(url);
    
    return {
      protocol: urlObj.protocol,
      hostname: urlObj.hostname,
      port: urlObj.port,
      pathname: urlObj.pathname,
      search: urlObj.search,
      hash: urlObj.hash,
      origin: urlObj.origin,
      href: urlObj.href,
    };
  } catch (error) {
    throw new Error(`Invalid URL: ${url}`);
  }
}

/**
 * Join path segments into a single path
 * @param segments Path segments to join
 * @returns Joined path
 */
export function joinPath(...segments: string[]): string {
  return segments
    .map(segment => segment.replace(/^\/+|\/+$/g, ''))
    .filter(Boolean)
    .join('/');
}

/**
 * Normalize a URL by ensuring it has a protocol
 * @param url URL to normalize
 * @param defaultProtocol Default protocol to use if missing (defaults to current protocol)
 * @returns Normalized URL
 */
export function normalizeUrl(url: string, defaultProtocol: string = window.location.protocol): string {
  if (!url) return '';
  
  // If URL already has protocol, return as-is
  if (url.startsWith('http://') || url.startsWith('https://') || url.startsWith('ws://') || url.startsWith('wss://')) {
    return url;
 