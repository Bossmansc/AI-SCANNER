/**
 * Shared TypeScript interfaces for API contracts
 * Centralized type definitions for all API requests and responses
 * Ensures type safety across frontend and backend
 */

// ==================== CORE API TYPES ====================

/**
 * Base API response wrapper for all endpoints
 * @template T - The type of the data payload
 */
export interface ApiResponse<T = unknown> {
  /** Indicates if the request was successful */
  success: boolean;
  /** The main data payload, type varies by endpoint */
  data?: T;
  /** Optional message for success/error context */
  message?: string;
  /** Error code if request failed */
  errorCode?: string;
  /** Validation errors for form submissions */
  validationErrors?: Record<string, string[]>;
  /** Server timestamp of response */
  timestamp: string;
  /** API version */
  version: string;
}

/**
 * Paginated API response for list endpoints
 * @template T - The type of items in the list
 */
export interface PaginatedResponse<T> {
  /** Array of items for current page */
  items: T[];
  /** Current page number (1-indexed) */
  page: number;
  /** Number of items per page */
  pageSize: number;
  /** Total number of items across all pages */
  totalItems: number;
  /** Total number of pages */
  totalPages: number;
  /** Whether there are more pages after this one */
  hasNextPage: boolean;
  /** Whether there are pages before this one */
  hasPreviousPage: boolean;
}

/**
 * Standard pagination parameters for list endpoints
 */
export interface PaginationParams {
  /** Page number (1-indexed) */
  page?: number;
  /** Number of items per page */
  pageSize?: number;
  /** Field to sort by */
  sortBy?: string;
  /** Sort direction: 'asc' or 'desc' */
  sortDirection?: 'asc' | 'desc';
  /** Search query string */
  search?: string;
}

/**
 * Standard filter parameters for list endpoints
 */
export interface FilterParams {
  /** Key-value pairs for exact matching */
  filters?: Record<string, string | number | boolean>;
  /** Key-value pairs for range filtering (min/max) */
  ranges?: Record<string, { min?: number; max?: number }>;
  /** Array of status values to include */
  statuses?: string[];
  /** Date range filter */
  dateRange?: {
    startDate?: string;
    endDate?: string;
  };
}

// ==================== AUTHENTICATION TYPES ====================

/**
 * User authentication request
 */
export interface LoginRequest {
  /** User's email address */
  email: string;
  /** User's password */
  password: string;
  /** Whether to remember the user (longer session) */
  rememberMe?: boolean;
}

/**
 * User registration request
 */
export interface RegisterRequest {
  /** User's full name */
  fullName: string;
  /** User's email address */
  email: string;
  /** User's password */
  password: string;
  /** Password confirmation */
  confirmPassword: string;
  /** Terms of service acceptance */
  acceptTerms: boolean;
  /** Optional referral code */
  referralCode?: string;
}

/**
 * Authentication response with tokens
 */
export interface AuthResponse {
  /** JWT access token for API authorization */
  accessToken: string;
  /** Refresh token for obtaining new access tokens */
  refreshToken: string;
  /** Token expiration time in seconds */
  expiresIn: number;
  /** Type of token (usually 'Bearer') */
  tokenType: string;
  /** Authenticated user information */
  user: UserProfile;
}

/**
 * Refresh token request
 */
export interface RefreshTokenRequest {
  /** Refresh token string */
  refreshToken: string;
}

/**
 * Password reset request
 */
export interface ResetPasswordRequest {
  /** User's email address */
  email: string;
}

/**
 * Confirm password reset request
 */
export interface ConfirmResetPasswordRequest {
  /** Reset token from email */
  token: string;
  /** New password */
  newPassword: string;
  /** Password confirmation */
  confirmPassword: string;
}

/**
 * Change password request (authenticated)
 */
export interface ChangePasswordRequest {
  /** Current password */
  currentPassword: string;
  /** New password */
  newPassword: string;
  /** Password confirmation */
  confirmPassword: string;
}

// ==================== USER PROFILE TYPES ====================

/**
 * User profile information
 */
export interface UserProfile {
  /** Unique user identifier */
  id: string;
  /** User's full name */
  fullName: string;
  /** User's email address */
  email: string;
  /** URL to user's profile picture */
  avatarUrl?: string;
  /** User's role/permissions */
  role: UserRole;
  /** Whether user's email is verified */
  emailVerified: boolean;
  /** Account creation timestamp */
  createdAt: string;
  /** Last profile update timestamp */
  updatedAt: string;
  /** Last login timestamp */
  lastLoginAt?: string;
  /** User preferences/settings */
  preferences?: UserPreferences;
  /** Account status */
  status: 'active' | 'suspended' | 'deactivated';
}

/**
 * User roles and permissions
 */
export type UserRole = 
  | 'admin' 
  | 'moderator' 
  | 'user' 
  | 'guest'
  | 'premium_user';

/**
 * User preferences and settings
 */
export interface UserPreferences {
  /** Language preference (ISO 639-1 code) */
  language: string;
  /** Timezone (IANA timezone database name) */
  timezone: string;
  /** Theme preference */
  theme: 'light' | 'dark' | 'auto';
  /** Email notification settings */
  notifications: {
    /** Receive marketing emails */
    marketing: boolean;
    /** Receive product updates */
    productUpdates: boolean;
    /** Receive security alerts */
    securityAlerts: boolean;
    /** Receive weekly digest */
    weeklyDigest: boolean;
  };
  /** Privacy settings */
  privacy: {
    /** Profile visibility */
    profileVisibility: 'public' | 'private' | 'friends_only';
    /** Show online status */
    showOnlineStatus: boolean;
    /** Allow search engine indexing */
    allowIndexing: boolean;
  };
}

/**
 * Update profile request
 */
export interface UpdateProfileRequest {
  /** Updated full name */
  fullName?: string;
  /** Updated avatar URL */
  avatarUrl?: string;
  /** Updated preferences */
  preferences?: Partial<UserPreferences>;
}

// ==================== FILE UPLOAD TYPES ====================

/**
 * File upload request metadata
 */
export interface FileUploadRequest {
  /** Original filename */
  fileName: string;
  /** File size in bytes */
  fileSize: number;
  /** MIME type */
  mimeType: string;
  /** Optional folder/path for organization */
  folder?: string;
  /** Optional tags for categorization */
  tags?: string[];
  /** Optional metadata */
  metadata?: Record<string, unknown>;
}

/**
 * File upload response
 */
export interface FileUploadResponse {
  /** Unique file identifier */
  fileId: string;
  /** Public URL for accessing the file */
  publicUrl: string;
  /** Secure URL for authenticated access */
  secureUrl?: string;
  /** Uploaded file metadata */
  metadata: {
    fileName: string;
    fileSize: number;
    mimeType: string;
    uploadedAt: string;
    dimensions?: {
      width: number;
      height: number;
    };
    duration?: number; // For audio/video files
  };
  /** Upload status */
  status: 'uploaded' | 'processing' | 'failed';
  /** Processing results (if applicable) */
  processingResults?: {
    thumbnailUrl?: string;
    optimizedUrl?: string;
    transcript?: string; // For audio/video
  };
}

/**
 * Presigned URL request for direct uploads
 */
export interface PresignedUrlRequest {
  /** File name */
  fileName: string;
  /** File size in bytes */
  fileSize: number;
  /** MIME type */
  mimeType: string;
  /** Optional metadata */
  metadata?: Record<string, string>;
}

/**
 * Presigned URL response
 */
export interface PresignedUrlResponse {
  /** URL for uploading the file */
  uploadUrl: string;
  /** HTTP method for upload (usually PUT) */
  method: string;
  /** Headers to include in upload request */
  headers: Record<string, string>;
  /** File identifier for reference */
  fileId: string;
  /** Expiration timestamp of the URL */
  expiresAt: string;
}

// ==================== NOTIFICATION TYPES ====================

/**
 * Notification message
 */
export interface Notification {
  /** Unique notification identifier */
  id: string;
  /** User ID of recipient */
  userId: string;
  /** Notification type/category */
  type: NotificationType;
  /** Notification title */
  title: string;
  /** Notification message/content */
  message: string;
  /** Optional data payload */
  data?: Record<string, unknown>;
  /** Whether notification has been read */
  read: boolean;
  /** Creation timestamp */
  createdAt: string;
  /** Optional expiration timestamp */
  expiresAt?: string;
  /** Optional action URL */
  actionUrl?: string;
  /** Priority level */
  priority: 'low' | 'medium' | 'high' | 'critical';
}

/**
 * Notification types
 */
export type NotificationType = 
  | 'system'
  | 'message'
  | 'alert'
  | 'reminder'
  | 'achievement'
  | 'warning'
  | 'info';

/**
 * Notification preferences update
 */
export interface NotificationPreferencesUpdate {
  /** Channel-specific preferences */
  channels: {
    /** In-app notifications */
    inApp: boolean;
    /** Email notifications */
    email: boolean;
    /** Push notifications */
    push: boolean;
    /** SMS notifications */
    sms: boolean;
  };
  /** Type-specific preferences */
  types: Record<NotificationType, boolean>;
}

// ==================== ANALYTICS & METRICS TYPES ====================

/**
 * Analytics event tracking request
 */
export interface AnalyticsEvent {
  /** Event name/category */
  eventName: string;
  /** Event action */
  eventAction: string;
  /** Event label/category */
  eventLabel?: string;
  /** Event value (numeric) */
  eventValue?: number;
  /** Custom properties */
  properties?: Record<string, unknown>;
  /** User ID (if authenticated) */
  userId?: string;
  /** Session ID */
  sessionId: string;
  /** Page URL */
  pageUrl: string;
  /** User agent */
  userAgent: string;
  /** Timestamp (client-side) */
  timestamp: string;
  /** Device information */
  device?: {
    type: 'desktop' | 'mobile' | 'tablet';
    platform: string;
    browser: string;
    browserVersion: string;
  };
}

/**
 * Analytics summary response
 */
export interface AnalyticsSummary {
  /** Total events in period */
  totalEvents: number;
  /** Unique users in period */
  uniqueUsers: number;
  /** Most common events */
  topEvents: Array<{
    eventName: string;
    count: number;
    percentage: number;
  }>;
  /** Event trends over time */
  trends: Array<{
    date: string;
    count: number;
  }>;
  /** Conversion rate (if applicable) */
  conversionRate?: number;
  /** Average session duration (seconds) */
  avgSessionDuration?: number;
  /** Bounce rate percentage */
  bounceRate?: number;
}

// ==================== ERROR & VALIDATION TYPES ====================

/**
 * Standard API error response
 */
export interface ApiError {
  /** Error code for programmatic handling */
  code: string;
  /** Human-readable error message */
  message: string;
  /** HTTP status code */
  statusCode: number;
  /** Detailed error information */
  details?: Record<string, unknown>;
  /** Stack trace (development only) */
  stack?: string;
  /** Timestamp of error */
  timestamp: string;
  /** Request ID for tracing */
  requestId: string;
}

/**
 * Validation error detail
 */
export interface ValidationError {
  /** Field that failed validation */
  field: string;
  /** Validation error message */
  message: string;
  /** Validation rule that failed */
  rule: string;
  /** Provided value that failed validation */
  value: unknown;
}

/**
 * Field-specific validation errors
 */
export interface FieldValidationErrors {
  [field: string]: string[];
}

// ==================== SEARCH TYPES ====================

/**
 * Search request parameters
 */
export interface SearchRequest {
  /** Search query string */
  query: string;
  /** Search filters */
  filters?: Record<string, (string | number | boolean)[]>;
  /** Sort options */
  sort?: {
    field: string;
    direction: 'asc' | 'desc';
  };
  /** Pagination */
  pagination?: {
    page: number;
    pageSize: number;
  };
  /** Fields to return in results */
  fields?: string[];
  /** Whether to include highlights */
  includeHighlights?: boolean;
  /** Search type/scope */
  searchType?: 'fulltext' | 'prefix' | 'fuzzy';
}

/**
 * Search result item
 */
export interface SearchResult<T = unknown> {
  /** Result item */
  item: T;
  /** Relevance score */
  score: number;
  /** Search highlights (if requested) */
  highlights?: Record<string, string[]>;
  /** Result type/category */
  type: string;
}

/**
 * Search response
 */
export interface SearchResponse<T = unknown> {
  /** Search results */
  results: SearchResult<T>[];
  /** Total number of matching results */
  total: number;
  /** Search query information */
  query: {
    original: string;
    normalized: string;
    tokens: string[];
  };
  /** Facets/aggregations for filtering */
  facets?: Record<string, Array<{
    value: string;
    count: number;
  }>>;
  /** Search duration in milliseconds */
  duration: number;
}

// ==================== WEBSOCKET EVENT TYPES ====================

/**
 * WebSocket message envelope
 */
export interface WebSocketMessage<T = unknown> {
  /** Message type/event name */
  type: string;
  /** Message payload */
  data: T;
  /** Message timestamp */
  timestamp: string;
  /** Message ID for deduplication */
  messageId?: string;
  /** Correlation ID for request/response */
  correlationId?: string;
}

/**
 * WebSocket connection status
 */
export interface WebSocketStatus {
  /** Connection state */
  state: 'connecting' | 'connected' | 'disconnected' | 'reconnecting';
  /** Last connection timestamp */
  lastConnectedAt?: string;
  /** Connection attempts count */
  connectionAttempts: number;
  /** Whether connection is healthy */
  isHealthy: boolean;
  /** Latency in milliseconds */
  latency?: number;
}

/**
 * Real-time event types
 */
export type RealTimeEvent = 
  | { type: 'notification.created'; data: Notification }
  | { type: 'user.status.changed'; data: { userId: string; status: 'online' | 'offline' | 'away' } }
  | { type: 'message.received'; data: { roomId: string; message: unknown } }
  | { type: 'data.updated'; data: { entity: string; id: string; changes: Record<string, unknown> } }
  | { type: 'error.occurred'; data: { code: string; message: string } };

// ==================== EXPORT UTILITIES ====================

/**
 * Type guard for API response
 */
export function isApiResponse<T>(obj: unknown): obj is ApiResponse<T> {
  return (
    typeof obj === 'object' &&
    obj !== null &&
    'success' in obj &&
    'timestamp' in obj &&
    'version' in obj
  );
}

/**
 * Type guard for paginated response
 */
export function isPaginatedResponse<T>(obj: unknown): obj is PaginatedResponse<T> {
  return (
    isApiResponse(obj) &&
    'items' in obj.data &&
    'page' in obj.data &&
    'totalItems' in obj.data
  );
}

/**
 * Creates a successful API response
 */
export function createSuccessResponse<T>(
  data: T,
  message?: string
): ApiResponse<T> {
  return {
    success: true,
    data,
    message,
    timestamp: new Date().toISOString(),
    version: '1.0',
  };
}

/**
 * Creates an error API response
 */
export function createErrorResponse(
  errorCode: string,
  message: string,
  validationErrors?: Record<string, string[]>
): ApiResponse {
  return {
    success: false,
    errorCode,
    message,
    validationErrors,
    timestamp: new Date().toISOString(),
    version: '1.0',
  };
}

/**
 * Creates paginated response
 */
export function createPaginatedResponse<T>(
  items: T[],
  page: number,
  pageSize: number,
  totalItems: number
): ApiResponse<PaginatedResponse<T>> {
  const totalPages = Math.ceil(totalItems / pageSize);
  
  return createSuccessResponse({
    items,
    page,
    pageSize,
    totalItems,
    totalPages,
    hasNextPage: page < totalPages,
    hasPreviousPage: page > 1,
  });
}

// ==================== CONSTANTS ====================

/**
 * Common API error codes
 */
export const ApiErrorCodes = {
  // Authentication errors
  UNAUTHORIZED: 'UNAUTHORIZED',
  INVALID_CREDENTIALS: 'INVALID_CREDENTIALS',
  TOKEN_EXPIRED: 'TOKEN_EXPIRED',
  TOKEN_INVALID: 'TOKEN_INVALID',
  ACCESS_DENIED: 'ACCESS_DENIED',
  
  // Validation errors
  VALIDATION_ERROR: 'VALIDATION_ERROR',
  INVALID_INPUT: 'INVALID_INPUT',
  MISSING_REQUIRED_FIELD: 'MISSING_REQUIRED_FIELD',
  
  // Resource errors
  NOT_FOUND: 'NOT_FOUND',
  ALREADY_EXISTS: 'ALREADY_EXISTS',
  CONFLICT: 'CONFLICT',
  RATE_LIMITED: 'RATE_LIMITED',
  
  // System errors
  INTERNAL_ERROR: 'INTERNAL_ERROR',
  SERVICE_UNAVAILABLE: 'SERVICE_UNAVAILABLE',
  DATABASE_ERROR: 'DATABASE_ERROR',
  EXTERNAL_SERVICE_ERROR: 'EXTERNAL_SERVICE_ERROR',
  
  // Business logic errors
  INSUFFICIENT_PERMISSIONS: 'INSUFFICIENT_PERMISSIONS',
  INVALID_STATE: 'INVALID_STATE',
  BUSINESS_RULE_VIOLATION: 'BUSINESS_RULE_VIOLATION',
} as const;

/**
 * Common HTTP status codes
 */
export const HttpStatus = {
  OK: 200,
  CREATED: 201,
