/**
 * Error Handling Middleware for API
 * Standardizes error responses for frontend consumption
 */

import { Request, Response, NextFunction } from 'express';
import { ValidationError } from 'express-validator';
import { Logger } from '../utils/logger';

// ============================================================================
// ERROR TYPES
// ============================================================================

/**
 * Base application error class
 */
export class AppError extends Error {
  public readonly statusCode: number;
  public readonly isOperational: boolean;
  public readonly code?: string;
  public readonly details?: any;

  constructor(
    message: string,
    statusCode: number = 500,
    code?: string,
    details?: any,
    isOperational: boolean = true
  ) {
    super(message);
    this.statusCode = statusCode;
    this.isOperational = isOperational;
    this.code = code;
    this.details = details;
    
    // Ensure proper prototype chain for instanceof checks
    Object.setPrototypeOf(this, AppError.prototype);
    
    // Capture stack trace (excluding constructor call)
    Error.captureStackTrace(this, this.constructor);
  }
}

/**
 * 400 Bad Request Error
 */
export class BadRequestError extends AppError {
  constructor(message: string = 'Bad Request', details?: any) {
    super(message, 400, 'BAD_REQUEST', details);
  }
}

/**
 * 401 Unauthorized Error
 */
export class UnauthorizedError extends AppError {
  constructor(message: string = 'Unauthorized', details?: any) {
    super(message, 401, 'UNAUTHORIZED', details);
  }
}

/**
 * 403 Forbidden Error
 */
export class ForbiddenError extends AppError {
  constructor(message: string = 'Forbidden', details?: any) {
    super(message, 403, 'FORBIDDEN', details);
  }
}

/**
 * 404 Not Found Error
 */
export class NotFoundError extends AppError {
  constructor(message: string = 'Resource not found', details?: any) {
    super(message, 404, 'NOT_FOUND', details);
  }
}

/**
 * 409 Conflict Error
 */
export class ConflictError extends AppError {
  constructor(message: string = 'Conflict', details?: any) {
    super(message, 409, 'CONFLICT', details);
  }
}

/**
 * 422 Validation Error
 */
export class ValidationErrorResponse extends AppError {
  constructor(message: string = 'Validation failed', details?: any) {
    super(message, 422, 'VALIDATION_ERROR', details);
  }
}

/**
 * 429 Too Many Requests Error
 */
export class RateLimitError extends AppError {
  constructor(message: string = 'Too many requests', details?: any) {
    super(message, 429, 'RATE_LIMIT_EXCEEDED', details);
  }
}

/**
 * 500 Internal Server Error
 */
export class InternalServerError extends AppError {
  constructor(message: string = 'Internal server error', details?: any) {
    super(message, 500, 'INTERNAL_SERVER_ERROR', details, false);
  }
}

/**
 * 503 Service Unavailable Error
 */
export class ServiceUnavailableError extends AppError {
  constructor(message: string = 'Service temporarily unavailable', details?: any) {
    super(message, 503, 'SERVICE_UNAVAILABLE', details);
  }
}

// ============================================================================
// ERROR RESPONSE INTERFACES
// ============================================================================

export interface ErrorResponse {
  success: false;
  error: {
    message: string;
    code?: string;
    statusCode: number;
    timestamp: string;
    path?: string;
    details?: any;
    stack?: string;
  };
}

export interface ValidationErrorItem {
  field: string;
  message: string;
  value?: any;
}

export interface ValidationErrorResponse extends ErrorResponse {
  error: ErrorResponse['error'] & {
    details: ValidationErrorItem[];
  };
}

// ============================================================================
// ERROR FORMATTER
// ============================================================================

export class ErrorFormatter {
  /**
   * Format error for API response
   */
  static formatError(
    error: Error | AppError,
    req?: Request,
    includeStackTrace: boolean = false
  ): ErrorResponse {
    const isAppError = error instanceof AppError;
    const statusCode = isAppError ? (error as AppError).statusCode : 500;
    const code = isAppError ? (error as AppError).code : 'INTERNAL_ERROR';
    const details = isAppError ? (error as AppError).details : undefined;
    
    const response: ErrorResponse = {
      success: false,
      error: {
        message: error.message || 'An unexpected error occurred',
        code,
        statusCode,
        timestamp: new Date().toISOString(),
        path: req?.originalUrl,
        details,
      },
    };

    // Include stack trace in development or when explicitly requested
    if (includeStackTrace && error.stack) {
      response.error.stack = error.stack;
    }

    return response;
  }

  /**
   * Format validation errors from express-validator
   */
  static formatValidationErrors(
    errors: ValidationError[],
    req?: Request
  ): ValidationErrorResponse {
    const formattedErrors: ValidationErrorItem[] = errors.map(err => ({
      field: err.type === 'field' ? err.path : err.type,
      message: err.msg,
      value: err.type === 'field' ? err.value : undefined,
    }));

    return {
      success: false,
      error: {
        message: 'Validation failed',
        code: 'VALIDATION_ERROR',
        statusCode: 422,
        timestamp: new Date().toISOString(),
        path: req?.originalUrl,
        details: formattedErrors,
      },
    };
  }

  /**
   * Check if error is operational (expected/controlled)
   */
  static isOperationalError(error: Error): boolean {
    if (error instanceof AppError) {
      return error.isOperational;
    }
    return false;
  }
}

// ============================================================================
// ERROR HANDLER MIDDLEWARE
// ============================================================================

export class ErrorHandler {
  private logger: Logger;
  private isProduction: boolean;

  constructor(logger: Logger, isProduction: boolean = process.env.NODE_ENV === 'production') {
    this.logger = logger;
    this.isProduction = isProduction;
  }

  /**
   * Express error handling middleware
   */
  public handle() {
    return (error: Error, req: Request, res: Response, next: NextFunction): void => {
      // Log the error
      this.logError(error, req);

      // Handle specific error types
      if (error instanceof SyntaxError && 'body' in error) {
        this.handleJsonSyntaxError(error as any, req, res);
        return;
      }

      // Format the error response
      const response = ErrorFormatter.formatError(
        error,
        req,
        !this.isProduction // Include stack trace in non-production
      );

      // Send response
      res.status(response.error.statusCode).json(response);
    };
  }

  /**
   * Handle 404 routes
   */
  public notFound() {
    return (req: Request, res: Response, next: NextFunction): void => {
      const error = new NotFoundError(`Route not found: ${req.method} ${req.originalUrl}`);
      const response = ErrorFormatter.formatError(error, req);
      
      res.status(404).json(response);
    };
  }

  /**
   * Handle async route errors (wrap async controllers)
   */
  public catchAsync(fn: Function) {
    return (req: Request, res: Response, next: NextFunction): Promise<void> => {
      return Promise.resolve(fn(req, res, next)).catch(next);
    };
  }

  /**
   * Handle validation errors from express-validator
   */
  public handleValidationErrors() {
    return (req: Request, res: Response, next: NextFunction): void => {
      const validationErrors = (req as any).validationErrors;
      if (validationErrors && validationErrors.length > 0) {
        const response = ErrorFormatter.formatValidationErrors(validationErrors, req);
        res.status(422).json(response);
        return;
      }
      next();
    };
  }

  /**
   * Graceful shutdown handler for unhandled errors
   */
  public setupUnhandledErrorHandlers(): void {
    // Catch unhandled promise rejections
    process.on('unhandledRejection', (reason: Error | any, promise: Promise<any>) => {
      this.logger.error('Unhandled Rejection at:', promise, 'reason:', reason);
      
      // In production, we might want to restart the process
      if (!this.isProduction) {
        throw reason;
      }
    });

    // Catch uncaught exceptions
    process.on('uncaughtException', (error: Error) => {
      this.logger.error('Uncaught Exception:', error);
      
      // In production, exit and let process manager restart
      if (this.isProduction) {
        process.exit(1);
      }
    });
  }

  // ==========================================================================
  // PRIVATE METHODS
  // ==========================================================================

  private logError(error: Error, req?: Request): void {
    const logData: any = {
      message: error.message,
      name: error.name,
      stack: error.stack,
    };

    if (req) {
      logData.request = {
        method: req.method,
        url: req.originalUrl,
        ip: req.ip,
        userAgent: req.get('user-agent'),
        userId: (req as any).user?.id,
      };
    }

    if (error instanceof AppError) {
      if (error.statusCode >= 500) {
        this.logger.error('Server Error:', logData);
      } else {
        this.logger.warn('Client Error:', logData);
      }
    } else {
      this.logger.error('Unexpected Error:', logData);
    }
  }

  private handleJsonSyntaxError(
    error: any,
    req: Request,
    res: Response
  ): void {
    const badRequestError = new BadRequestError('Invalid JSON payload');
    const response = ErrorFormatter.formatError(badRequestError, req);
    
    res.status(400).json(response);
  }
}

// ============================================================================
// DEFAULT EXPORT AND HELPER FUNCTIONS
// ============================================================================

/**
 * Create and configure error handler middleware
 */
export function createErrorHandler(
  logger: Logger = new Logger('ErrorHandler'),
  isProduction: boolean = process.env.NODE_ENV === 'production'
): ErrorHandler {
  return new ErrorHandler(logger, isProduction);
}

/**
 * Default error handler instance
 */
export const defaultErrorHandler = createErrorHandler();

/**
 * Helper to throw validation errors
 */
export function throwValidationError(message: string, details?: any): never {
  throw new ValidationErrorResponse(message, details);
}

/**
 * Helper to throw not found errors
 */
export function throwNotFoundError(message: string, details?: any): never {
  throw new NotFoundError(message, details);
}

/**
 * Helper to throw unauthorized errors
 */
export function throwUnauthorizedError(message: string, details?: any): never {
  throw new UnauthorizedError(message, details);
}

/**
 * Helper to throw forbidden errors
 */
export function throwForbiddenError(message: string, details?: any): never {
  throw new ForbiddenError(message, details);
}

/**
 * Helper to throw conflict errors
 */
export function throwConflictError(message: string, details?: any): never {
  throw new ConflictError(message, details);
}

/**
 * Helper to throw bad request errors
 */
export function throwBadRequestError(message: string, details?: any): never {
  throw new BadRequestError(message, details);
}

// ============================================================================
// TYPE GUARDS
// ============================================================================

/**
 * Type guard to check if error is an AppError
 */
export function isAppError(error: any): error is AppError {
  return error instanceof AppError;
}

/**
 * Type guard to check if error is a validation error
 */
export function isValidationError(error: any): error is ValidationErrorResponse {
  return error instanceof ValidationErrorResponse;
}

/**
 * Type guard to check if error response is a validation error response
 */
export function isValidationErrorResponse(
  response: ErrorResponse
): response is ValidationErrorResponse {
  return response.error.code === 'VALIDATION_ERROR' && Array.isArray(response.error.details);
}

// ============================================================================
// ERROR CODES CONSTANTS
// ============================================================================

export const ERROR_CODES = {
  // Client Errors (4xx)
  BAD_REQUEST: 'BAD_REQUEST',
  UNAUTHORIZED: 'UNAUTHORIZED',
  FORBIDDEN: 'FORBIDDEN',
  NOT_FOUND: 'NOT_FOUND',
  CONFLICT: 'CONFLICT',
  VALIDATION_ERROR: 'VALIDATION_ERROR',
  RATE_LIMIT_EXCEEDED: 'RATE_LIMIT_EXCEEDED',
  
  // Server Errors (5xx)
  INTERNAL_SERVER_ERROR: 'INTERNAL_SERVER_ERROR',
  SERVICE_UNAVAILABLE: 'SERVICE_UNAVAILABLE',
  DATABASE_ERROR: 'DATABASE_ERROR',
  EXTERNAL_SERVICE_ERROR: 'EXTERNAL_SERVICE_ERROR',
  
  // Business Logic Errors
  INSUFFICIENT_PERMISSIONS: 'INSUFFICIENT_PERMISSIONS',
  RESOURCE_LIMIT_EXCEEDED: 'RESOURCE_LIMIT_EXCEEDED',
  INVALID_OPERATION: 'INVALID_OPERATION',
} as const;

export type ErrorCode = typeof ERROR_CODES[keyof typeof ERROR_CODES];

// ============================================================================
// DEFAULT EXPORT
// ============================================================================

export default defaultErrorHandler;
