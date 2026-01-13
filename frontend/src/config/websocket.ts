/**
 * WebSocket Configuration Module
 * 
 * Provides WebSocket connection management with dynamic URL resolution,
 * automatic reconnection, and environment-aware configuration.
 * 
 * Features:
 * - Dynamic URL resolution for development/production environments
 * - Exponential backoff reconnection strategy
 * - Connection state management
 * - Event-driven architecture
 * - Type-safe WebSocket event handling
 */

// ============================================================================
// TYPES AND INTERFACES
// ============================================================================

/**
 * WebSocket connection states
 */
export enum WebSocketState {
  CONNECTING = 0,
  OPEN = 1,
  CLOSING = 2,
  CLOSED = 3
}

/**
 * WebSocket configuration options
 */
export interface WebSocketConfig {
  /** Maximum number of reconnection attempts (0 = infinite) */
  maxReconnectAttempts: number;
  /** Base delay for reconnection in milliseconds */
  reconnectDelay: number;
  /** Maximum reconnection delay in milliseconds */
  maxReconnectDelay: number;
  /** Timeout for connection establishment in milliseconds */
  connectionTimeout: number;
  /** Enable/disable automatic reconnection */
  autoReconnect: boolean;
  /** Enable/disable debug logging */
  debug: boolean;
}

/**
 * WebSocket event types
 */
export enum WebSocketEvent {
  CONNECT = 'websocket:connect',
  CONNECTING = 'websocket:connecting',
  CONNECTED = 'websocket:connected',
  DISCONNECT = 'websocket:disconnect',
  DISCONNECTED = 'websocket:disconnected',
  MESSAGE = 'websocket:message',
  ERROR = 'websocket:error',
  RECONNECTING = 'websocket:reconnecting',
  RECONNECT_ATTEMPT = 'websocket:reconnect_attempt',
  RECONNECT_FAILED = 'websocket:reconnect_failed'
}

/**
 * WebSocket message structure
 */
export interface WebSocketMessage<T = any> {
  /** Message type identifier */
  type: string;
  /** Message payload */
  data: T;
  /** Message timestamp */
  timestamp: number;
  /** Optional message ID for tracking */
  id?: string;
}

/**
 * WebSocket event callback type
 */
export type WebSocketEventHandler = (event: any) => void;

/**
 * WebSocket connection statistics
 */
export interface ConnectionStats {
  /** Total connection attempts */
  totalAttempts: number;
  /** Successful connections */
  successfulConnections: number;
  /** Failed connections */
  failedConnections: number;
  /** Total messages sent */
  messagesSent: number;
  /** Total messages received */
  messagesReceived: number;
  /** Last connection timestamp */
  lastConnectedAt: number | null;
  /** Last disconnection timestamp */
  lastDisconnectedAt: number | null;
  /** Current reconnection attempt count */
  currentReconnectAttempt: number;
}

// ============================================================================
// ENVIRONMENT CONFIGURATION
// ============================================================================

/**
 * Environment detection utilities
 */
class Environment {
  /**
   * Check if running in development environment
   */
  static isDevelopment(): boolean {
    return process.env.NODE_ENV === 'development' || 
           import.meta.env?.MODE === 'development' ||
           window.location.hostname === 'localhost' ||
           window.location.hostname === '127.0.0.1' ||
           window.location.hostname.includes('.local');
  }

  /**
   * Check if running in production environment
   */
  static isProduction(): boolean {
    return process.env.NODE_ENV === 'production' || 
           import.meta.env?.MODE === 'production' ||
           !this.isDevelopment();
  }

  /**
   * Get the current hostname
   */
  static getHostname(): string {
    return window.location.hostname;
  }

  /**
   * Get the current protocol (http/https)
   */
  static getProtocol(): string {
    return window.location.protocol;
  }

  /**
   * Get the current port
   */
  static getPort(): string {
    return window.location.port;
  }
}

/**
 * WebSocket URL resolver
 */
export class WebSocketURLResolver {
  /**
   * Default WebSocket endpoints for different environments
   */
  private static readonly DEFAULT_ENDPOINTS = {
    development: 'ws://localhost:3000/ws',
    production: 'wss://api.example.com/ws',
    staging: 'wss://staging-api.example.com/ws'
  };

  /**
   * Resolve WebSocket URL based on environment
   */
  static resolveURL(customEndpoint?: string): string {
    // Use custom endpoint if provided
    if (customEndpoint) {
      return this.normalizeURL(customEndpoint);
    }

    // Check for environment-specific endpoint in configuration
    const configEndpoint = this.getConfigEndpoint();
    if (configEndpoint) {
      return this.normalizeURL(configEndpoint);
    }

    // Use default endpoints based on environment
    if (Environment.isDevelopment()) {
      return this.DEFAULT_ENDPOINTS.development;
    }

    // Check for staging environment
    if (this.isStagingEnvironment()) {
      return this.DEFAULT_ENDPOINTS.staging;
    }

    // Default to production
    return this.DEFAULT_ENDPOINTS.production;
  }

  /**
   * Get WebSocket endpoint from configuration
   */
  private static getConfigEndpoint(): string | null {
    // Check for global configuration
    if (typeof window !== 'undefined' && (window as any).APP_CONFIG?.websocketEndpoint) {
      return (window as any).APP_CONFIG.websocketEndpoint;
    }

    // Check for environment variables
    if (import.meta.env?.VITE_WEBSOCKET_ENDPOINT) {
      return import.meta.env.VITE_WEBSOCKET_ENDPOINT;
    }

    if (process.env.REACT_APP_WEBSOCKET_ENDPOINT) {
      return process.env.REACT_APP_WEBSOCKET_ENDPOINT;
    }

    return null;
  }

  /**
   * Check if running in staging environment
   */
  private static isStagingEnvironment(): boolean {
    const hostname = Environment.getHostname();
    return hostname.includes('staging') || 
           hostname.includes('test') || 
           hostname.includes('preview');
  }

  /**
   * Normalize WebSocket URL
   */
  private static normalizeURL(url: string): string {
    // Ensure URL starts with ws:// or wss://
    if (!url.startsWith('ws://') && !url.startsWith('wss://')) {
      const protocol = Environment.getProtocol() === 'https:' ? 'wss:' : 'ws:';
      url = `${protocol}//${url.replace(/^\/\//, '')}`;
    }

    // Remove trailing slashes from path
    url = url.replace(/([^:]\/)\/+/g, '$1');

    return url;
  }

  /**
   * Generate WebSocket URL with query parameters
   */
  static generateURL(baseURL: string, params: Record<string, string> = {}): string {
    const url = new URL(baseURL);
    
    // Add timestamp to prevent caching
    params._t = params._t || Date.now().toString();
    
    // Add environment identifier
    params.env = Environment.isDevelopment() ? 'dev' : 'prod';
    
    // Add client identifier
    params.client = 'web';
    
    Object.entries(params).forEach(([key, value]) => {
      url.searchParams.append(key, value);
    });
    
    return url.toString();
  }
}

// ============================================================================
// WEB SOCKET MANAGER
// ============================================================================

/**
 * Main WebSocket manager class
 */
export class WebSocketManager {
  private socket: WebSocket | null = null;
  private config: WebSocketConfig;
  private eventHandlers: Map<WebSocketEvent, Set<WebSocketEventHandler>> = new Map();
  private reconnectTimer: number | null = null;
  private connectionTimeoutTimer: number | null = null;
  private reconnectAttempts = 0;
  private isManualDisconnect = false;
  private stats: ConnectionStats;
  private messageQueue: Array<WebSocketMessage> = [];
  private isConnected = false;
  private connectionId: string | null = null;

  /**
   * Default configuration
   */
  private static readonly DEFAULT_CONFIG: WebSocketConfig = {
    maxReconnectAttempts: 10,
    reconnectDelay: 1000,
    maxReconnectDelay: 30000,
    connectionTimeout: 10000,
    autoReconnect: true,
    debug: Environment.isDevelopment()
  };

  /**
   * Constructor
   */
  constructor(
    private endpoint?: string,
    config: Partial<WebSocketConfig> = {}
  ) {
    this.config = { ...WebSocketManager.DEFAULT_CONFIG, ...config };
    this.stats = this.initializeStats();
    
    // Initialize event handler maps
    Object.values(WebSocketEvent).forEach(event => {
      this.eventHandlers.set(event, new Set());
    });
    
    // Set up global error handler
    this.setupGlobalErrorHandler();
  }

  /**
   * Initialize connection statistics
   */
  private initializeStats(): ConnectionStats {
    return {
      totalAttempts: 0,
      successfulConnections: 0,
      failedConnections: 0,
      messagesSent: 0,
      messagesReceived: 0,
      lastConnectedAt: null,
      lastDisconnectedAt: null,
      currentReconnectAttempt: 0
    };
  }

  /**
   * Set up global error handler for unhandled WebSocket errors
   */
  private setupGlobalErrorHandler(): void {
    if (typeof window !== 'undefined') {
      window.addEventListener('error', (event) => {
        if (event.error?.message?.includes('WebSocket')) {
          this.log('Global WebSocket error:', event.error);
          this.emit(WebSocketEvent.ERROR, event.error);
        }
      });
    }
  }

  /**
   * Connect to WebSocket server
   */
  public connect(params: Record<string, string> = {}): void {
    if (this.isConnected && this.socket?.readyState === WebSocketState.OPEN) {
      this.log('WebSocket already connected');
      return;
    }

    this.isManualDisconnect = false;
    this.connectionId = this.generateConnectionId();
    
    this.emit(WebSocketEvent.CONNECT, { connectionId: this.connectionId });
    this.emit(WebSocketEvent.CONNECTING, { 
      endpoint: this.endpoint,
      params,
      timestamp: Date.now()
    });

    this.stats.totalAttempts++;
    this.stats.currentReconnectAttempt = this.reconnectAttempts;

    try {
      const url = WebSocketURLResolver.generateURL(
        WebSocketURLResolver.resolveURL(this.endpoint),
        params
      );

      this.log(`Connecting to WebSocket: ${url}`);
      this.socket = new WebSocket(url);

      this.setupSocketEventHandlers();
      this.startConnectionTimeout();
    } catch (error) {
      this.handleConnectionError(error as Error);
    }
  }

  /**
   * Generate unique connection ID
   */
  private generateConnectionId(): string {
    return `ws_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
  }

  /**
   * Set up WebSocket event handlers
   */
  private setupSocketEventHandlers(): void {
    if (!this.socket) return;

    this.socket.onopen = (event) => this.handleOpen(event);
    this.socket.onmessage = (event) => this.handleMessage(event);
    this.socket.onerror = (event) => this.handleError(event);
    this.socket.onclose = (event) => this.handleClose(event);
  }

  /**
   * Handle WebSocket open event
   */
  private handleOpen(event: Event): void {
    this.log('WebSocket connection established');
    
    this.isConnected = true;
    this.reconnectAttempts = 0;
    this.clearConnectionTimeout();
    
    this.stats.successfulConnections++;
    this.stats.lastConnectedAt = Date.now();
    
    this.emit(WebSocketEvent.CONNECTED, {
      event,
      connectionId: this.connectionId,
      timestamp: Date.now(),
      stats: { ...this.stats }
    });

    // Process any queued messages
    this.processMessageQueue();
  }

  /**
   * Handle WebSocket message event
   */
  private handleMessage(event: MessageEvent): void {
    try {
      let data: WebSocketMessage;
      
      if (typeof event.data === 'string') {
        data = JSON.parse(event.data);
      } else if (event.data instanceof Blob) {
        // Handle binary data if needed
        const reader = new FileReader();
        reader.onload = () => {
          if (typeof reader.result === 'string') {
            this.processMessage(JSON.parse(reader.result));
          }
        };
        reader.readAsText(event.data);
        return;
      } else {
        data = event.data;
      }

      this.processMessage(data);
    } catch (error) {
      this.log('Error parsing WebSocket message:', error);
      this.emit(WebSocketEvent.ERROR, {
        error,
        rawData: event.data,
        timestamp: Date.now()
      });
    }
  }

  /**
   * Process incoming message
   */
  private processMessage(message: WebSocketMessage): void {
    this.stats.messagesReceived++;
    
    this.emit(WebSocketEvent.MESSAGE, {
      message,
      timestamp: Date.now(),
      connectionId: this.connectionId
    });

    // Emit type-specific events
    if (message.type) {
      this.emit(`message:${message.type}` as WebSocketEvent, message);
    }
  }

  /**
   * Handle WebSocket error event
   */
  private handleError(event: Event): void {
    this.log('WebSocket error:', event);
    
    this.emit(WebSocketEvent.ERROR, {
      event,
      connectionId: this.connectionId,
      timestamp: Date.now(),
      reconnectAttempt: this.reconnectAttempts
    });
  }

  /**
   * Handle WebSocket close event
   */
  private handleClose(event: CloseEvent): void {
    this.log(`WebSocket connection closed. Code: ${event.code}, Reason: ${event.reason}`);
    
    this.isConnected = false;
    this.clearConnectionTimeout();
    this.stats.lastDisconnectedAt = Date.now();
    
    this.emit(WebSocketEvent.DISCONNECTED, {
      event,
      connectionId: this.connectionId,
      timestamp: Date.now(),
      wasClean: event.wasClean,
      code: event.code,
      reason: event.reason
    });

    // Handle reconnection if not manually disconnected
    if (!this.isManualDisconnect && this.config.autoReconnect) {
      this.scheduleReconnection();
    }
  }

  /**
   * Handle connection error
   */
  private handleConnectionError(error: Error): void {
    this.log('Connection error:', error);
    
    this.stats.failedConnections++;
    
    this.emit(WebSocketEvent.ERROR, {
      error,
      connectionId: this.connectionId,
      timestamp: Date.now(),
      isConnectionError: true
    });

    if (this.config.autoReconnect && !this.isManualDisconnect) {
      this.scheduleReconnection();
    }
  }

  /**
   * Start connection timeout
   */
  private startConnectionTimeout(): void {
    this.clearConnectionTimeout();
    
    this.connectionTimeoutTimer = window.setTimeout(() => {
      if (this.socket?.readyState !== WebSocketState.OPEN) {
        this.log('Connection timeout');
        this.socket?.close();
        this.handleConnectionError(new Error('Connection timeout'));
      }
    }, this.config.connectionTimeout);
  }

  /**
   * Clear connection timeout
   */
  private clearConnectionTimeout(): void {
    if (this.connectionTimeoutTimer) {
      clearTimeout(this.connectionTimeoutTimer);
      this.connectionTimeoutTimer = null;
    }
  }

  /**
   * Schedule reconnection with exponential backoff
   */
  private scheduleReconnection(): void {
    if (this.isManualDisconnect) return;
    
    const maxAttempts = this.config.maxReconnectAttempts;
    if (maxAttempts > 0 && this.reconnectAttempts >= maxAttempts) {
      this.log(`Max reconnection attempts (${maxAttempts}) reached`);
      this.emit(WebSocketEvent.RECONNECT_FAILED, {
        attempts: this.reconnectAttempts,
        maxAttempts,
        timestamp: Date.now()
      });
      return;
    }

    this.reconnectAttempts++;
    this.stats.currentReconnectAttempt = this.reconnectAttempts;
    
    const delay = this.calculateReconnectDelay();
    
    this.log(`Scheduling reconnection attempt ${this.reconnectAttempts} in ${delay}ms`);
    
    this.emit(WebSocketEvent.RECONNECTING, {
      attempt: this.reconnectAttempts,
      delay,
      maxAttempts,
      timestamp: Date.now()
    });

    this.emit(WebSocketEvent.RECONNECT_ATTEMPT, {
      attempt: this.reconnectAttempts,
      nextAttemptIn: delay,
      timestamp: Date.now()
    });

    this.reconnectTimer = window.setTimeout(() => {
      this.reconnectTimer = null;
      this.connect();
    }, delay);
  }

  /**
   * Calculate reconnection delay with exponential backoff
   */
  private calculateReconnectDelay(): number {
    const baseDelay = this.config.reconnectDelay;
    const maxDelay = this.config.maxReconnectDelay;
    const delay = Math.min(baseDelay * Math.pow(1.5, this.reconnectAttempts - 1), maxDelay);
    
    // Add jitter to prevent thundering herd
    const jitter = delay * 0.1 * (Math.random() * 2 - 1);
    return Math.max(100, delay + jitter);
  }

  /**
   * Send message through WebSocket
   */
  public send<T = any>(type: string, data: T, id?: string): boolean {
    const message: WebSocketMessage<T> = {
      type,
      data,
      timestamp: Date.now(),
      id: id || this.generateMessageId()
    };

    // Queue message if not connected
    if (!this.isConnected || this.socket?.readyState !== WebSocketState.OPEN) {
      this.log('WebSocket not connected, queuing message:', message);
      this.messageQueue.push(message);
      return false;
    }

    try {
      const jsonString = JSON.stringify(message);
      this.socket.send(jsonString);
      this.stats.messagesSent++;
      return true;
    } catch (error) {
      this.log('Error sending message:', error);
      this.emit(WebSocketEvent.ERROR, {
        error,
        message,
        timestamp: