/**
 * WebSocket Service
 * 
 * A robust WebSocket client service with connection management,
 * automatic reconnection, event handling, and message queuing.
 * Designed for high-concurrency real-time applications.
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
 * WebSocket event types
 */
export enum WebSocketEvent {
  CONNECT = 'websocket:connect',
  DISCONNECT = 'websocket:disconnect',
  MESSAGE = 'websocket:message',
  ERROR = 'websocket:error',
  RECONNECTING = 'websocket:reconnecting',
  RECONNECTED = 'websocket:reconnected'
}

/**
 * WebSocket configuration options
 */
export interface WebSocketConfig {
  /** WebSocket server URL */
  url: string;
  /** Protocols to use (optional) */
  protocols?: string | string[];
  /** Enable automatic reconnection (default: true) */
  autoReconnect?: boolean;
  /** Maximum reconnection attempts (default: 10) */
  maxReconnectAttempts?: number;
  /** Reconnection delay in milliseconds (default: 1000) */
  reconnectDelay?: number;
  /** Exponential backoff factor (default: 1.5) */
  reconnectBackoffFactor?: number;
  /** Maximum reconnection delay in milliseconds (default: 30000) */
  maxReconnectDelay?: number;
  /** Heartbeat interval in milliseconds (default: 30000) */
  heartbeatInterval?: number;
  /** Enable message queuing when disconnected (default: true) */
  queueMessages?: boolean;
  /** Maximum queue size (default: 100) */
  maxQueueSize?: number;
  /** Connection timeout in milliseconds (default: 5000) */
  connectionTimeout?: number;
  /** Enable debug logging (default: false) */
  debug?: boolean;
}

/**
 * WebSocket message wrapper
 */
export interface WebSocketMessage<T = any> {
  /** Message type/event name */
  type: string;
  /** Message payload */
  data: T;
  /** Timestamp when message was sent/received */
  timestamp: number;
  /** Message ID for tracking */
  id?: string;
}

/**
 * WebSocket event callback
 */
export type WebSocketCallback<T = any> = (data: T) => void;

/**
 * WebSocket event listener
 */
interface WebSocketEventListener {
  event: string;
  callback: WebSocketCallback;
  once?: boolean;
}

/**
 * Reconnection attempt information
 */
interface ReconnectionAttempt {
  attempt: number;
  timestamp: number;
  delay: number;
}

// ============================================================================
// MAIN WEBSOCKET SERVICE CLASS
// ============================================================================

export class WebSocketService {
  // Configuration
  private config: Required<WebSocketConfig>;
  
  // WebSocket instance
  private socket: WebSocket | null = null;
  
  // State management
  private state: WebSocketState = WebSocketState.CLOSED;
  private reconnectAttempts = 0;
  private reconnectTimer: any = null;
  private heartbeatTimer: any = null;
  private connectionTimeoutTimer: any = null;
  
  // Message queue for when disconnected
  private messageQueue: WebSocketMessage[] = [];
  
  // Event listeners
  private listeners: Map<string, WebSocketCallback[]> = new Map();
  private eventListeners: WebSocketEventListener[] = [];
  
  // Statistics
  private stats = {
    messagesSent: 0,
    messagesReceived: 0,
    connectionAttempts: 0,
    successfulConnections: 0,
    failedConnections: 0,
    reconnections: 0,
    lastConnectedAt: 0,
    lastDisconnectedAt: 0
  };

  // ==========================================================================
  // PUBLIC API
  // ==========================================================================

  /**
   * Create a new WebSocket service instance
   */
  constructor(config: WebSocketConfig) {
    // Set default configuration
    this.config = {
      autoReconnect: true,
      maxReconnectAttempts: 10,
      reconnectDelay: 1000,
      reconnectBackoffFactor: 1.5,
      maxReconnectDelay: 30000,
      heartbeatInterval: 30000,
      queueMessages: true,
      maxQueueSize: 100,
      connectionTimeout: 5000,
      debug: false,
      ...config,
      url: config.url,
      protocols: config.protocols || []
    };

    this.log('WebSocket service initialized with config:', this.config);
  }

  /**
   * Connect to the WebSocket server
   */
  public connect(): Promise<void> {
    return new Promise((resolve, reject) => {
      if (this.isConnected()) {
        this.log('Already connected');
        resolve();
        return;
      }

      if (this.isConnecting()) {
        this.log('Already connecting');
        reject(new Error('Already connecting'));
        return;
      }

      // Clear any existing reconnection timer
      this.clearReconnectionTimer();

      try {
        this.log(`Connecting to ${this.config.url}`);
        this.state = WebSocketState.CONNECTING;
        this.stats.connectionAttempts++;

        // Create WebSocket instance
        this.socket = new WebSocket(this.config.url, this.config.protocols);

        // Set up event handlers
        this.setupEventHandlers();

        // Set connection timeout
        this.connectionTimeoutTimer = setTimeout(() => {
          if (this.state === WebSocketState.CONNECTING) {
            this.log('Connection timeout');
            this.handleConnectionError(new Error('Connection timeout'));
            reject(new Error('Connection timeout'));
          }
        }, this.config.connectionTimeout);

        // Wait for connection
        const onOpen = () => {
          clearTimeout(this.connectionTimeoutTimer);
          this.handleOpen();
          resolve();
        };

        const onError = (error: Event) => {
          clearTimeout(this.connectionTimeoutTimer);
          this.handleConnectionError(error);
          reject(new Error('Connection failed'));
        };

        // Temporary listeners for promise resolution
        this.socket.addEventListener('open', onOpen, { once: true });
        this.socket.addEventListener('error', onError, { once: true });

      } catch (error) {
        this.log('Failed to create WebSocket:', error);
        this.state = WebSocketState.CLOSED;
        this.stats.failedConnections++;
        reject(error);
      }
    });
  }

  /**
   * Disconnect from the WebSocket server
   */
  public disconnect(code?: number, reason?: string): void {
    this.log('Disconnecting', { code, reason });
    
    // Clear all timers
    this.clearAllTimers();
    
    // Clear message queue
    this.messageQueue = [];
    
    // Update state
    this.state = WebSocketState.CLOSING;
    
    // Close WebSocket if it exists
    if (this.socket) {
      try {
        this.socket.close(code || 1000, reason || 'Normal closure');
      } catch (error) {
        this.log('Error during disconnect:', error);
      }
    }
    
    // Update state
    this.state = WebSocketState.CLOSED;
    this.stats.lastDisconnectedAt = Date.now();
    
    // Emit disconnect event
    this.emit(WebSocketEvent.DISCONNECT, {
      code: code || 1000,
      reason: reason || 'Normal closure',
      timestamp: Date.now()
    });
    
    this.log('Disconnected');
  }

  /**
   * Send a message through the WebSocket
   */
  public send<T = any>(type: string, data: T): boolean {
    const message: WebSocketMessage<T> = {
      type,
      data,
      timestamp: Date.now(),
      id: this.generateMessageId()
    };

    // If connected, send immediately
    if (this.isConnected() && this.socket) {
      try {
        const serialized = JSON.stringify(message);
        this.socket.send(serialized);
        this.stats.messagesSent++;
        this.log('Message sent:', message);
        return true;
      } catch (error) {
        this.log('Error sending message:', error);
        this.emit(WebSocketEvent.ERROR, {
          type: 'send_error',
          error,
          message
        });
        return false;
      }
    }
    
    // If not connected but queueing is enabled, add to queue
    if (this.config.queueMessages) {
      if (this.messageQueue.length >= this.config.maxQueueSize) {
        this.log('Message queue full, dropping oldest message');
        this.messageQueue.shift();
      }
      
      this.messageQueue.push(message);
      this.log('Message queued:', message);
      return true;
    }
    
    this.log('Cannot send message: not connected and queueing disabled');
    return false;
  }

  /**
   * Subscribe to a specific event type
   */
  public on<T = any>(event: string, callback: WebSocketCallback<T>): () => void {
    if (!this.listeners.has(event)) {
      this.listeners.set(event, []);
    }
    
    const callbacks = this.listeners.get(event)!;
    callbacks.push(callback as WebSocketCallback);
    
    this.log(`Listener added for event: ${event}`);
    
    // Return unsubscribe function
    return () => {
      const callbacks = this.listeners.get(event);
      if (callbacks) {
        const index = callbacks.indexOf(callback as WebSocketCallback);
        if (index > -1) {
          callbacks.splice(index, 1);
          this.log(`Listener removed for event: ${event}`);
        }
      }
    };
  }

  /**
   * Subscribe to a specific event type once
   */
  public once<T = any>(event: string, callback: WebSocketCallback<T>): () => void {
    const onceCallback: WebSocketCallback<T> = (data: T) => {
      callback(data);
      unsubscribe();
    };
    
    const unsubscribe = this.on(event, onceCallback);
    return unsubscribe;
  }

  /**
   * Subscribe to raw WebSocket events
   */
  public onEvent<T = any>(event: WebSocketEvent, callback: WebSocketCallback<T>): () => void {
    const listener: WebSocketEventListener = {
      event,
      callback: callback as WebSocketCallback,
      once: false
    };
    
    this.eventListeners.push(listener);
    
    this.log(`Event listener added for: ${event}`);
    
    return () => {
      const index = this.eventListeners.indexOf(listener);
      if (index > -1) {
        this.eventListeners.splice(index, 1);
        this.log(`Event listener removed for: ${event}`);
      }
    };
  }

  /**
   * Unsubscribe from all events
   */
  public offAll(): void {
    this.listeners.clear();
    this.eventListeners = [];
    this.log('All listeners removed');
  }

  /**
   * Check if WebSocket is connected
   */
  public isConnected(): boolean {
    return this.state === WebSocketState.OPEN && 
           this.socket !== null && 
           this.socket.readyState === WebSocket.OPEN;
  }

  /**
   * Check if WebSocket is connecting
   */
  public isConnecting(): boolean {
    return this.state === WebSocketState.CONNECTING;
  }

  /**
   * Check if WebSocket is closed
   */
  public isClosed(): boolean {
    return this.state === WebSocketState.CLOSED;
  }

  /**
   * Get current connection state
   */
  public getState(): WebSocketState {
    return this.state;
  }

  /**
   * Get connection statistics
   */
  public getStats(): typeof this.stats {
    return { ...this.stats };
  }

  /**
   * Get queued messages count
   */
  public getQueueSize(): number {
    return this.messageQueue.length;
  }

  /**
   * Flush the message queue (send all queued messages)
   */
  public flushQueue(): number {
    if (!this.isConnected()) {
      this.log('Cannot flush queue: not connected');
      return 0;
    }
    
    const queueSize = this.messageQueue.length;
    this.log(`Flushing ${queueSize} queued messages`);
    
    // Send all queued messages
    while (this.messageQueue.length > 0) {
      const message = this.messageQueue.shift();
      if (message) {
        this.send(message.type, message.data);
      }
    }
    
    return queueSize;
  }

  /**
   * Clear the message queue
   */
  public clearQueue(): void {
    const queueSize = this.messageQueue.length;
    this.messageQueue = [];
    this.log(`Cleared ${queueSize} queued messages`);
  }

  /**
   * Reconnect manually
   */
  public reconnect(): Promise<void> {
    this.log('Manual reconnection requested');
    this.clearReconnectionTimer();
    return this.connect();
  }

  // ==========================================================================
  // PRIVATE METHODS
  // ==========================================================================

  /**
   * Set up WebSocket event handlers
   */
  private setupEventHandlers(): void {
    if (!this.socket) return;

    // Open event
    this.socket.addEventListener('open', (event) => {
      this.handleOpen();
    });

    // Message event
    this.socket.addEventListener('message', (event) => {
      this.handleMessage(event);
    });

    // Error event
    this.socket.addEventListener('error', (event) => {
      this.handleError(event);
    });

    // Close event
    this.socket.addEventListener('close', (event) => {
      this.handleClose(event);
    });
  }

  /**
   * Handle WebSocket open event
   */
  private handleOpen(): void {
    this.log('WebSocket connection established');
    
    // Update state
    this.state = WebSocketState.OPEN;
    this.reconnectAttempts = 0;
    this.stats.successfulConnections++;
    this.stats.lastConnectedAt = Date.now();
    
    // Clear connection timeout
    clearTimeout(this.connectionTimeoutTimer);
    
    // Start heartbeat
    this.startHeartbeat();
    
    // Emit connect event
    this.emit(WebSocketEvent.CONNECT, {
      timestamp: Date.now(),
      url: this.config.url
    });
    
    // Flush queued messages
    if (this.config.queueMessages && this.messageQueue.length > 0) {
      this.flushQueue();
    }
  }

  /**
   * Handle WebSocket message event
   */
  private handleMessage(event: MessageEvent): void {
    try {
      const message: WebSocketMessage = JSON.parse(event.data);
      this.stats.messagesReceived++;
      
      this.log('Message received:', message);
      
      // Emit raw message event
      this.emit(WebSocketEvent.MESSAGE, message);
      
      // Emit typed event if message has a type
      if (message.type) {
        this.emit(message.type, message.data);
      }
      
    } catch (error) {
      this.log('Error parsing message:', error, 'Raw data:', event.data);
      
      // Emit error for unparseable messages
      this.emit(WebSocketEvent.ERROR, {
        type: 'parse_error',
        error,
        rawData: event.data
      });
    }
  }

  /**
   * Handle WebSocket error event
   */
  private handleError(event: Event): void {
    this.log('WebSocket error:', event);
    this.stats.failedConnections++;
    
    // Emit error event
    this.emit(WebSocketEvent.ERROR, {
      type: 'websocket_error',
      event,
      timestamp: Date.now()
    });
  }

  /**
   * Handle WebSocket close event
   */
  private handleClose(event: CloseEvent): void {
    this.log('WebSocket connection closed:', {
      code: event.code,
      reason: event.reason,
      wasClean: event.wasClean
    });
    
    // Update state
    this.state = WebSocketState.CLOSED;
    this.stats.lastDisconnectedAt = Date.now();
    
    // Stop heartbeat
    this.stopHeartbeat();
    
    // Clean up socket
    this.socket = null;
    
    // Emit disconnect event
    this.emit(WebSocketEvent.DISCONNECT, {
      code: event.code,
      reason: event.reason,
      wasClean: event.wasClean,
      timestamp: Date.now()
    });
    
    // Attempt reconnection if configured
    if (this.config.autoReconnect && event.code !== 1000) {
      this.scheduleReconnection();
    }
  }

  /**
   * Handle connection error (during initial connection)
   */
  private handleConnectionError(error: Event | Error): void {
    this.log('Connection error:', error);
    this.stats.failedConnections++;
    
    // Update state
    this.state = WebSocketState.CLOSED;
    
    // Clean up socket
    if (this.socket) {
      try {
        this.socket.close();
      } catch (e) {
        // Ignore close errors
      }
      this.socket = null;
    }
    
    // Emit error event
    this.emit(WebSocketEvent.ERROR, {
      type: 'connection_error',
      error,
      timestamp: Date.now()
    });
    
    // Attempt reconnection if configured
    if (this.config.autoReconnect) {
      this.scheduleReconnection();
    }
  }

  /**
   * Schedule reconnection attempt
   */
  private scheduleReconnection(): void {
    // Check if we've exceeded max reconnection attempts
    if (this.reconnectAttempts >= this.config.maxReconnectAttempts) {
      this.log(`Max reconnection attempts (${this.config.maxReconnectAttempts}) exceeded`);
      return;
    }
    
    // Calculate delay with exponential backoff
    const baseDelay = this.config.reconnectDelay;
    const backoffFactor = this.config.reconnectBackoffFactor;
    const maxDelay = this.config.maxReconnectDelay;
    
    let delay = baseDelay * Math.pow(backoffFactor, this.reconnectAttempts);
    delay = Math.min(delay, maxDelay);
    
    this.reconnectAttempts++;
    this.stats.reconnections++;
    
    const attemptInfo: ReconnectionAttempt = {
      attempt: this.reconnectAttempts,
      timestamp: Date.now(),
      delay
    };
    
    this.log(`Scheduling reconnection attempt ${this.reconnectAttempts} in ${delay}ms`, attemptInfo);
    
    // Emit reconnecting event
    this.emit(WebSocketEvent.RECONNECTING, attemptInfo);
    
    // Schedule reconnection
    this.reconnectTimer = setTimeout(() => {
      this.log(`Attempting reconnection ${this.reconnectAttempts}`);
      this.connect()
        .then(() => {
          this.log(`Reconnection ${this.reconnectAttempt