/**
 * Type-safe API client with comprehensive error handling
 * Centralized HTTP client configuration for frontend-backend communication
 */

// ============================================================================
// TYPES & INTERFACES
// ============================================================================

/**
 * Standard API response envelope
 */
export interface ApiResponse<T = any> {
  data: T;
  meta?: {
    timestamp: string;
    requestId: string;
    pagination?: {
      page: number;
      limit: number;
      total: number;
      pages: number;
    };
  };
}

/**
 * Standard API error response
 */
export interface ApiError {
  error: {
    code: string;
    message: string;
    details?: Record<string, any>;
    validationErrors?: Array<{
      field: string;
      message: string;
      code: string;
    }>;
  };
  meta?: {
    timestamp: string;
    requestId: string;
  };
}

/**
 * HTTP methods supported by the client
 */
export type HttpMethod = 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE' | 'HEAD' | 'OPTIONS';

/**
 * Request configuration options
 */
export interface RequestConfig {
  method?: HttpMethod;
  headers?: Record<string, string>;
  params?: Record<string, any>;
  data?: any;
  timeout?: number;
  retries?: number;
  retryDelay?: number;
  signal?: AbortSignal;
  validateStatus?: (status: number) => boolean;
  withCredentials?: boolean;
}

/**
 * Client configuration
 */
export interface ApiClientConfig {
  baseURL: string;
  timeout?: number;
  maxRetries?: number;
  retryDelay?: number;
  defaultHeaders?: Record<string, string>;
  withCredentials?: boolean;
  requestInterceptor?: (config: RequestConfig) => RequestConfig | Promise<RequestConfig>;
  responseInterceptor?: (response: Response) => Response | Promise<Response>;
  errorInterceptor?: (error: ApiError | Error) => void | Promise<void>;
}

/**
 * Paginated response type
 */
export interface PaginatedResponse<T> extends ApiResponse<T[]> {
  meta: {
    timestamp: string;
    requestId: string;
    pagination: {
      page: number;
      limit: number;
      total: number;
      pages: number;
    };
  };
}

// ============================================================================
// ERROR CLASSES
// ============================================================================

/**
 * Base API error class
 */
export class ApiClientError extends Error {
  constructor(
    message: string,
    public code: string = 'API_CLIENT_ERROR',
    public details?: Record<string, any>,
    public status?: number
  ) {
    super(message);
    this.name = 'ApiClientError';
    
    // Maintain proper stack trace
    if (Error.captureStackTrace) {
      Error.captureStackTrace(this, ApiClientError);
    }
  }
}

/**
 * Network connectivity error
 */
export class NetworkError extends ApiClientError {
  constructor(message: string = 'Network connection failed') {
    super(message, 'NETWORK_ERROR');
    this.name = 'NetworkError';
  }
}

/**
 * Timeout error
 */
export class TimeoutError extends ApiClientError {
  constructor(message: string = 'Request timeout exceeded') {
    super(message, 'TIMEOUT_ERROR');
    this.name = 'TimeoutError';
  }
}

/**
 * HTTP status error (4xx, 5xx)
 */
export class HttpError extends ApiClientError {
  constructor(
    message: string,
    public status: number,
    code: string = 'HTTP_ERROR',
    details?: Record<string, any>
  ) {
    super(message, code, details, status);
    this.name = 'HttpError';
  }
}

/**
 * Validation error (422)
 */
export class ValidationError extends HttpError {
  constructor(
    message: string = 'Validation failed',
    public validationErrors?: Array<{
      field: string;
      message: string;
      code: string;
    }>
  ) {
    super(message, 422, 'VALIDATION_ERROR', { validationErrors });
    this.name = 'ValidationError';
  }
}

/**
 * Authentication error (401)
 */
export class AuthenticationError extends HttpError {
  constructor(message: string = 'Authentication required') {
    super(message, 401, 'AUTHENTICATION_ERROR');
    this.name = 'AuthenticationError';
  }
}

/**
 * Authorization error (403)
 */
export class AuthorizationError extends HttpError {
  constructor(message: string = 'Insufficient permissions') {
    super(message, 403, 'AUTHORIZATION_ERROR');
    this.name = 'AuthorizationError';
  }
}

/**
 * Not found error (404)
 */
export class NotFoundError extends HttpError {
  constructor(message: string = 'Resource not found') {
    super(message, 404, 'NOT_FOUND_ERROR');
    this.name = 'NotFoundError';
  }
}

/**
 * Rate limit error (429)
 */
export class RateLimitError extends HttpError {
  constructor(
    message: string = 'Rate limit exceeded',
    public retryAfter?: number
  ) {
    super(message, 429, 'RATE_LIMIT_ERROR', { retryAfter });
    this.name = 'RateLimitError';
  }
}

/**
 * Server error (5xx)
 */
export class ServerError extends HttpError {
  constructor(message: string = 'Internal server error') {
    super(message, 500, 'SERVER_ERROR');
    this.name = 'ServerError';
  }
}

// ============================================================================
// UTILITY FUNCTIONS
// ============================================================================

/**
 * Sleep utility for retry delays
 */
const sleep = (ms: number): Promise<void> => {
  return new Promise(resolve => setTimeout(resolve, ms));
};

/**
 * Build URL with query parameters
 */
const buildUrl = (baseUrl: string, path: string, params?: Record<string, any>): string => {
  const url = new URL(path, baseUrl);
  
  if (params) {
    Object.entries(params).forEach(([key, value]) => {
      if (value !== undefined && value !== null) {
        if (Array.isArray(value)) {
          value.forEach(item => {
            url.searchParams.append(`${key}[]`, String(item));
          });
        } else {
          url.searchParams.append(key, String(value));
        }
      }
    });
  }
  
  return url.toString();
};

/**
 * Default status validator
 */
const defaultValidateStatus = (status: number): boolean => {
  return status >= 200 && status < 300;
};

/**
 * Parse JSON response with error handling
 */
const parseJson = async (response: Response): Promise<any> => {
  const text = await response.text();
  
  if (!text) {
    return null;
  }
  
  try {
    return JSON.parse(text);
  } catch (error) {
    throw new ApiClientError(
      `Failed to parse JSON response: ${error instanceof Error ? error.message : 'Unknown error'}`,
      'JSON_PARSE_ERROR'
    );
  }
};

/**
 * Create HTTP error from response
 */
const createHttpError = async (response: Response): Promise<HttpError> => {
  let errorData: ApiError | null = null;
  
  try {
    errorData = await parseJson(response);
  } catch {
    // Ignore JSON parse errors for error responses
  }
  
  const errorMessage = errorData?.error?.message || response.statusText || `HTTP ${response.status}`;
  const errorCode = errorData?.error?.code || `HTTP_${response.status}`;
  const details = errorData?.error?.details;
  const validationErrors = errorData?.error?.validationErrors;
  
  switch (response.status) {
    case 400:
      return new HttpError(errorMessage, 400, errorCode, details);
    case 401:
      return new AuthenticationError(errorMessage);
    case 403:
      return new AuthorizationError(errorMessage);
    case 404:
      return new NotFoundError(errorMessage);
    case 422:
      return new ValidationError(errorMessage, validationErrors);
    case 429:
      const retryAfter = response.headers.get('Retry-After');
      return new RateLimitError(errorMessage, retryAfter ? parseInt(retryAfter) : undefined);
    case 500:
    case 502:
    case 503:
    case 504:
      return new ServerError(errorMessage);
    default:
      return new HttpError(errorMessage, response.status, errorCode, details);
  }
};

// ============================================================================
// API CLIENT CLASS
// ============================================================================

export class ApiClient {
  private config: ApiClientConfig;
  private abortControllers: Map<string, AbortController> = new Map();
  
  constructor(config: ApiClientConfig) {
    this.config = {
      timeout: 30000,
      maxRetries: 3,
      retryDelay: 1000,
      withCredentials: false,
      ...config,
      defaultHeaders: {
        'Content-Type': 'application/json',
        'Accept': 'application/json',
        ...config.defaultHeaders,
      },
    };
  }
  
  /**
   * Update client configuration
   */
  public updateConfig(config: Partial<ApiClientConfig>): void {
    this.config = {
      ...this.config,
      ...config,
      defaultHeaders: {
        ...this.config.defaultHeaders,
        ...config.defaultHeaders,
      },
    };
  }
  
  /**
   * Get current configuration
   */
  public getConfig(): ApiClientConfig {
    return { ...this.config };
  }
  
  /**
   * Set default header
   */
  public setHeader(key: string, value: string): void {
    this.config.defaultHeaders = {
      ...this.config.defaultHeaders,
      [key]: value,
    };
  }
  
  /**
   * Remove default header
   */
  public removeHeader(key: string): void {
    if (this.config.defaultHeaders) {
      delete this.config.defaultHeaders[key];
    }
  }
  
  /**
   * Abort a specific request by request ID
   */
  public abortRequest(requestId: string): void {
    const controller = this.abortControllers.get(requestId);
    if (controller) {
      controller.abort();
      this.abortControllers.delete(requestId);
    }
  }
  
  /**
   * Abort all pending requests
   */
  public abortAllRequests(): void {
    this.abortControllers.forEach(controller => controller.abort());
    this.abortControllers.clear();
  }
  
  /**
   * Execute HTTP request with retry logic
   */
  public async request<T = any>(
    path: string,
    config: RequestConfig = {}
  ): Promise<ApiResponse<T>> {
    const requestId = this.generateRequestId();
    const controller = new AbortController();
    this.abortControllers.set(requestId, controller);
    
    const requestConfig: RequestConfig = {
      method: 'GET',
      headers: {},
      timeout: this.config.timeout,
      retries: this.config.maxRetries,
      retryDelay: this.config.retryDelay,
      validateStatus: defaultValidateStatus,
      withCredentials: this.config.withCredentials,
      signal: controller.signal,
      ...config,
      headers: {
        ...this.config.defaultHeaders,
        ...config.headers,
      },
    };
    
    // Apply request interceptor
    let finalConfig = requestConfig;
    if (this.config.requestInterceptor) {
      finalConfig = await Promise.resolve(this.config.requestInterceptor(requestConfig));
    }
    
    let lastError: Error | null = null;
    
    for (let attempt = 0; attempt <= (finalConfig.retries || 0); attempt++) {
      try {
        const response = await this.executeRequest(path, finalConfig);
        
        // Apply response interceptor
        let finalResponse = response;
        if (this.config.responseInterceptor) {
          finalResponse = await Promise.resolve(this.config.responseInterceptor(response));
        }
        
        // Validate status
        const isValidStatus = finalConfig.validateStatus
          ? finalConfig.validateStatus(finalResponse.status)
          : defaultValidateStatus(finalResponse.status);
        
        if (!isValidStatus) {
          throw await createHttpError(finalResponse);
        }
        
        // Parse response
        const responseData = await parseJson(finalResponse);
        
        // Clean up abort controller
        this.abortControllers.delete(requestId);
        
        return responseData;
      } catch (error) {
        lastError = error as Error;
        
        // Don't retry on certain errors
        if (
          error instanceof AuthenticationError ||
          error instanceof AuthorizationError ||
          error instanceof ValidationError ||
          error instanceof NotFoundError ||
          (error instanceof HttpError && error.status >= 400 && error.status < 500) ||
          error instanceof ApiClientError && error.code === 'ABORT_ERROR'
        ) {
          break;
        }
        
        // Check if we should retry
        if (attempt < (finalConfig.retries || 0)) {
          const delay = finalConfig.retryDelay || 1000;
          await sleep(delay * Math.pow(2, attempt)); // Exponential backoff
          continue;
        }
        
        break;
      }
    }
    
    // Clean up abort controller on final error
    this.abortControllers.delete(requestId);
    
    // Apply error interceptor
    if (this.config.errorInterceptor && lastError) {
      await Promise.resolve(this.config.errorInterceptor(lastError));
    }
    
    // Re-throw the last error
    throw lastError;
  }
  
  /**
   * Execute a single HTTP request
   */
  private async executeRequest(path: string, config: RequestConfig): Promise<Response> {
    const url = buildUrl(this.config.baseURL, path, config.params);
    
    const requestInit: RequestInit = {
      method: config.method,
      headers: config.headers,
      credentials: config.withCredentials ? 'include' : 'same-origin',
      signal: config.signal,
    };
    
    if (config.data !== undefined) {
      if (config.headers?.['Content-Type']?.includes('application/json')) {
        requestInit.body = JSON.stringify(config.data);
      } else if (config.data instanceof FormData) {
        requestInit.body = config.data;
        // Remove Content-Type header for FormData to let browser set it
        if (requestInit.headers) {
          delete (requestInit.headers as Record<string, string>)['Content-Type'];
        }
      } else {
        requestInit.body = config.data;
      }
    }
    
    // Create timeout promise
    const timeoutPromise = new Promise<never>((_, reject) => {
      setTimeout(() => {
        reject(new TimeoutError(`Request timeout after ${config.timeout}ms`));
      }, config.timeout);
    });
    
    // Create fetch promise
    const fetchPromise = fetch(url, requestInit).catch(error => {
      if (error.name === 'AbortError') {
        throw new ApiClientError('Request aborted', 'ABORT_ERROR');
      }
      if (error instanceof TimeoutError) {
        throw error;
      }
      throw new NetworkError(`Network error: ${error.message}`);
    });
    
    // Race between fetch and timeout
    return Promise.race([fetchPromise, timeoutPromise]);
  }
  
  /**
   * Generate unique request ID
   */
  private generateRequestId(): string {
    return `req_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
  }
  
  // ==========================================================================
  // CONVENIENCE METHODS
  // ==========================================================================
  
  public async get<T = any>(
    path: string,
    params?: Record<string, any>,
    config?: Omit<RequestConfig, 'method' | 'params'>
  ): Promise<ApiResponse<T>> {
    return this.request<T>(path, {
      ...config,
      method: 'GET',
      params,
    });
  }
  
  public async post<T = any>(
    path: string,
    data?: any,
    config?: Omit<RequestConfig, 'method' | 'data'>
  ): Promise<ApiResponse<T>> {
    return this.request<T>(path, {
      ...config,
      method: 'POST',
      data,
    });
  }
  
  public async put<T = any>(
    path: string,
    data?: any,
    config?: Omit<RequestConfig, 'method' | 'data'>
  ): Promise<ApiResponse<T>> {
    return this.request<T>(path, {
      ...config,
      method: 'PUT',
      data,
    });
  }
  
  public async patch<T = any>(
    path: string,
    data?: any,
    config?: Omit<RequestConfig, 'method' | 'data'>
  ): Promise<ApiResponse<T>> {
    return this.request<T>(path, {
      ...config,
      method: 'PATCH',
      data,
    });
  }
  
  public async delete<T = any>(
    path: string,
    config?: Omit<RequestConfig, 'method'>
  ): Promise<ApiResponse<T>> {
    return this.request<T>(path, {
      ...config,
      method: 'DELETE',
    });
  }
  
  public async head(
    path: string,
    config?: Omit<RequestConfig, 'method'>
  ): Promise<Response> {
    const response = await this.executeRequest(path, {
      ...config,
      method: 'HEAD',
    });
    return response;
  }
  
  public async options(
    path: string,
    config?: Omit<RequestConfig, 'method'>
  ): Promise<Response> {
    const response = await this.executeRequest(path, {
      ...config,
      method: 'OPTIONS',
    });
    return response;
  }
  
  // ==========================================================================
  // PAGINATION SUPPORT
  // ==========================================================================
  
  /**
   * Get paginated data
   */
  public async getPaginated<T = any>(
    path: string,
    page: number = 1,
    limit: number = 20,
    params?: Record<string, any>,
    config?: Omit<RequestConfig, 'method' | 'params'>
  ): Promise<PaginatedResponse<T>> {
    const paginationParams = {
      page,
      limit,
      ...params,
    };
    
    return this.request<T[]>(path, {
      ...config,
      method: 'GET',
      params: paginationParams,
    }) as Promise<PaginatedResponse<T>>;
  }
  
  /**
   * Fetch all pages of paginated data
   */
  public async getAllPages<T = any>(
    path: string,
    limit: number = 100,
    params?: Record<string, any>,
    config?: Omit<RequestConfig, 'method' | 'params'>
  ): Promise<T[]> {
    let currentPage = 1;
    let allItems: T[] = [];
    let totalPages = 1;
    
    do {
      const response = await this.getPaginated<T>(path, currentPage, limit, params, config);
      
      allItems = [...allItems, ...response.data];
      totalPages = response.meta?.pagination?.pages || 1;
      currentPage++;
      
    } while (currentPage <= totalPages);
    
    return allItems;
  }
}

// ============================================================================
// DEFAULT CLIENT INSTANCE
// =========================================================================