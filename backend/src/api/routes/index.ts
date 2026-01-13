/**
 * API Route Definitions - Central Routing Configuration
 * 
 * This module defines all API routes with proper contracts, validation,
 * and middleware integration. Routes are organized by domain/feature.
 */

import { Router, Request, Response, NextFunction } from 'express';
import { z } from 'zod';
import { validateRequest } from '../middleware/validation';
import { authenticate, authorize } from '../middleware/auth';
import { rateLimit } from '../middleware/rateLimit';
import { cacheMiddleware } from '../middleware/cache';
import { logRequest, logResponse } from '../middleware/logging';
import { errorHandler } from '../middleware/errorHandler';

// Import route handlers
import { healthRouter } from './health.routes';
import { authRouter } from './auth.routes';
import { userRouter } from './users.routes';
import { productRouter } from './products.routes';
import { orderRouter } from './orders.routes';
import { paymentRouter } from './payments.routes';
import { analyticsRouter } from './analytics.routes';
import { adminRouter } from './admin.routes';

// Import controllers
import { searchController } from '../controllers/search.controller';
import { uploadController } from '../controllers/upload.controller';
import { notificationController } from '../controllers/notification.controller';

// Import services
import { metricsService } from '../../services/metrics.service';

// Import types
import { ApiResponse, PaginatedResponse } from '../types/response.types';
import { SearchQuery, UploadRequest, NotificationRequest } from '../types/request.types';

// Initialize main router
const router = Router();

/**
 * Request validation schemas
 */
const searchSchema = z.object({
  query: z.string().min(1).max(200),
  filters: z.object({
    category: z.string().optional(),
    priceRange: z.object({
      min: z.number().min(0).optional(),
      max: z.number().positive().optional()
    }).optional(),
    inStock: z.boolean().optional()
  }).optional(),
  page: z.number().int().positive().default(1),
  limit: z.number().int().min(1).max(100).default(20),
  sortBy: z.enum(['relevance', 'price_asc', 'price_desc', 'newest']).default('relevance')
});

const uploadSchema = z.object({
  fileName: z.string().min(1).max(255),
  fileType: z.string().regex(/^[a-zA-Z0-9]+\/[a-zA-Z0-9.+-]+$/),
  fileSize: z.number().int().positive().max(50 * 1024 * 1024), // 50MB max
  metadata: z.record(z.any()).optional()
});

const notificationSchema = z.object({
  userId: z.string().uuid(),
  type: z.enum(['email', 'push', 'sms', 'in_app']),
  title: z.string().min(1).max(100),
  message: z.string().min(1).max(500),
  priority: z.enum(['low', 'medium', 'high', 'urgent']).default('medium'),
  data: z.record(z.any()).optional(),
  scheduledFor: z.string().datetime().optional()
});

const batchOperationSchema = z.object({
  operation: z.enum(['delete', 'archive', 'activate', 'deactivate']),
  ids: z.array(z.string().uuid()).min(1).max(100),
  confirm: z.boolean().default(false)
});

/**
 * Global middleware applied to all routes
 */
router.use(logRequest);
router.use(rateLimit.global);

/**
 * Health check routes (no auth required)
 */
router.use('/health', healthRouter);

/**
 * Authentication routes
 */
router.use('/auth', authRouter);

/**
 * Public search endpoint
 */
router.get(
  '/search',
  validateRequest({ query: searchSchema }),
  cacheMiddleware({ ttl: 60, key: 'search' }),
  async (req: Request, res: Response, next: NextFunction) => {
    try {
      const query = req.query as unknown as SearchQuery;
      const result = await searchController.search(query);
      
      const response: ApiResponse<PaginatedResponse<any>> = {
        success: true,
        data: result,
        timestamp: new Date().toISOString(),
        requestId: req.id
      };
      
      logResponse(req, res);
      res.status(200).json(response);
    } catch (error) {
      next(error);
    }
  }
);

/**
 * File upload endpoint
 */
router.post(
  '/upload',
  authenticate,
  rateLimit.upload,
  validateRequest({ body: uploadSchema }),
  async (req: Request, res: Response, next: NextFunction) => {
    try {
      const uploadRequest: UploadRequest = req.body;
      const result = await uploadController.handleUpload(uploadRequest, req.user!);
      
      const response: ApiResponse<any> = {
        success: true,
        data: result,
        timestamp: new Date().toISOString(),
        requestId: req.id
      };
      
      logResponse(req, res);
      res.status(201).json(response);
    } catch (error) {
      next(error);
    }
  }
);

/**
 * Protected API routes (require authentication)
 */
router.use(authenticate);

/**
 * User management routes
 */
router.use('/users', userRouter);

/**
 * Product catalog routes
 */
router.use('/products', productRouter);

/**
 * Order management routes
 */
router.use('/orders', orderRouter);

/**
 * Payment processing routes
 */
router.use('/payments', paymentRouter);

/**
 * Analytics and reporting routes
 */
router.use('/analytics', analyticsRouter);

/**
 * Notification endpoint
 */
router.post(
  '/notifications',
  rateLimit.notifications,
  validateRequest({ body: notificationSchema }),
  async (req: Request, res: Response, next: NextFunction) => {
    try {
      const notificationRequest: NotificationRequest = req.body;
      const result = await notificationController.sendNotification(notificationRequest);
      
      const response: ApiResponse<any> = {
        success: true,
        data: result,
        timestamp: new Date().toISOString(),
        requestId: req.id
      };
      
      logResponse(req, res);
      res.status(202).json(response);
    } catch (error) {
      next(error);
    }
  }
);

/**
 * Batch operations endpoint
 */
router.post(
  '/batch',
  authorize(['admin', 'manager']),
  validateRequest({ body: batchOperationSchema }),
  async (req: Request, res: Response, next: NextFunction) => {
    try {
      const { operation, ids, confirm } = req.body;
      
      if (!confirm) {
        const response: ApiResponse<{ count: number }> = {
          success: true,
          data: { count: ids.length },
          message: 'Add confirm: true to execute this batch operation',
          timestamp: new Date().toISOString(),
          requestId: req.id
        };
        
        logResponse(req, res);
        return res.status(200).json(response);
      }
      
      // Execute batch operation based on type
      let result;
      switch (operation) {
        case 'delete':
          result = await userRouter.batchDelete(ids);
          break;
        case 'archive':
          result = await productRouter.batchArchive(ids);
          break;
        case 'activate':
          result = await userRouter.batchActivate(ids);
          break;
        case 'deactivate':
          result = await userRouter.batchDeactivate(ids);
          break;
        default:
          throw new Error(`Unsupported operation: ${operation}`);
      }
      
      const response: ApiResponse<any> = {
        success: true,
        data: result,
        message: `Batch ${operation} completed successfully`,
        timestamp: new Date().toISOString(),
        requestId: req.id
      };
      
      logResponse(req, res);
      res.status(200).json(response);
    } catch (error) {
      next(error);
    }
  }
);

/**
 * Admin routes (require admin privileges)
 */
router.use('/admin', authorize(['admin']), adminRouter);

/**
 * Metrics endpoint for monitoring
 */
router.get(
  '/metrics',
  authorize(['admin', 'monitor']),
  cacheMiddleware({ ttl: 30, key: 'metrics' }),
  async (req: Request, res: Response, next: NextFunction) => {
    try {
      const metrics = await metricsService.getSystemMetrics();
      
      const response: ApiResponse<any> = {
        success: true,
        data: metrics,
        timestamp: new Date().toISOString(),
        requestId: req.id
      };
      
      logResponse(req, res);
      res.status(200).json(response);
    } catch (error) {
      next(error);
    }
  }
);

/**
 * API documentation endpoint
 */
router.get('/docs', (req: Request, res: Response) => {
  const docs = {
    version: '1.0.0',
    endpoints: [
      { path: '/health', methods: ['GET'], description: 'Health check' },
      { path: '/auth/*', methods: ['POST'], description: 'Authentication endpoints' },
      { path: '/search', methods: ['GET'], description: 'Global search with filters' },
      { path: '/upload', methods: ['POST'], description: 'File upload (authenticated)' },
      { path: '/users/*', methods: ['GET', 'POST', 'PUT', 'DELETE'], description: 'User management' },
      { path: '/products/*', methods: ['GET', 'POST', 'PUT', 'DELETE'], description: 'Product catalog' },
      { path: '/orders/*', methods: ['GET', 'POST', 'PUT'], description: 'Order management' },
      { path: '/payments/*', methods: ['POST'], description: 'Payment processing' },
      { path: '/analytics/*', methods: ['GET'], description: 'Analytics and reports' },
      { path: '/notifications', methods: ['POST'], description: 'Send notifications' },
      { path: '/batch', methods: ['POST'], description: 'Batch operations' },
      { path: '/admin/*', methods: ['GET', 'POST', 'PUT', 'DELETE'], description: 'Admin operations' },
      { path: '/metrics', methods: ['GET'], description: 'System metrics' }
    ],
    authentication: {
      required: 'Most endpoints require Bearer token in Authorization header',
      scopes: ['user', 'admin', 'manager', 'monitor']
    },
    rateLimiting: {
      global: '100 requests per minute',
      upload: '10 requests per minute',
      notifications: '50 requests per minute'
    },
    validation: 'All endpoints use Zod validation schemas',
    responseFormat: {
      success: 'boolean',
      data: 'any',
      message: 'string (optional)',
      timestamp: 'ISO string',
      requestId: 'string'
    },
    errorFormat: {
      success: 'false',
      error: {
        code: 'string',
        message: 'string',
        details: 'any (optional)'
      },
      timestamp: 'ISO string',
      requestId: 'string'
    }
  };
  
  const response: ApiResponse<any> = {
    success: true,
    data: docs,
    timestamp: new Date().toISOString(),
    requestId: req.id
  };
  
  res.status(200).json(response);
});

/**
 * Catch-all route for undefined endpoints
 */
router.all('*', (req: Request, res: Response) => {
  const response: ApiResponse<null> = {
    success: false,
    data: null,
    error: {
      code: 'ENDPOINT_NOT_FOUND',
      message: `Cannot ${req.method} ${req.originalUrl}`,
      details: {
        method: req.method,
        path: req.originalUrl,
        availableEndpoints: '/docs'
      }
    },
    timestamp: new Date().toISOString(),
    requestId: req.id
  };
  
  logResponse(req, res);
  res.status(404).json(response);
});

/**
 * Global error handler
 */
router.use(errorHandler);

/**
 * Export the configured router
 */
export { router as apiRouter };

/**
 * Helper function to get all registered routes
 * Useful for testing and documentation generation
 */
export function getRegisteredRoutes(): Array<{
  path: string;
  method: string;
  middleware: string[];
}> {
  const routes: Array<{
    path: string;
    method: string;
    middleware: string[];
  }> = [];
  
  router.stack.forEach((layer) => {
    if (layer.route) {
      const path = layer.route.path;
      const methods = Object.keys(layer.route.methods);
      const middleware = layer.route.stack.map((stackLayer: any) => stackLayer.name).filter(Boolean);
      
      methods.forEach((method) => {
        routes.push({
          path,
          method: method.toUpperCase(),
          middleware
        });
      });
    }
  });
  
  return routes;
}

/**
 * Route statistics for monitoring
 */
export function getRouteStats() {
  const routes = getRegisteredRoutes();
  
  return {
    totalRoutes: routes.length,
    routesByMethod: routes.reduce((acc, route) => {
      acc[route.method] = (acc[route.method] || 0) + 1;
      return acc;
    }, {} as Record<string, number>),
    protectedRoutes: routes.filter(r => r.middleware.includes('authenticate')).length,
    adminRoutes: routes.filter(r => r.middleware.includes('authorize')).length,
    timestamp: new Date().toISOString()
  };
}

/**
 * Type exports for external use
 */
export type {
  SearchQuery,
  UploadRequest,
  NotificationRequest
} from '../types/request.types';

export type {
  ApiResponse,
  PaginatedResponse
} from '../types/response.types';
