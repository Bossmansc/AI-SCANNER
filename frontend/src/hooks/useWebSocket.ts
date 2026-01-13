import { useCallback, useEffect, useRef, useState } from 'react';
import { v4 as uuidv4 } from 'uuid';

export type WebSocketMessage = {
  type: string;
  payload: any;
  timestamp: number;
  id?: string;
};

export type WebSocketStatus = 'connecting' | 'open' | 'closing' | 'closed' | 'error';

export type WebSocketOptions = {
  url: string | (() => string);
  protocols?: string | string[];
  autoConnect?: boolean;
  reconnectAttempts?: number;
  reconnectInterval?: number;
  heartbeatInterval?: number;
  heartbeatMessage?: WebSocketMessage | (() => WebSocketMessage);
  onOpen?: (event: Event) => void;
  onClose?: (event: CloseEvent) => void;
  onError?: (event: Event) => void;
  onMessage?: (message: WebSocketMessage) => void;
  debug?: boolean;
  maxMessageQueueSize?: number;
};

export type WebSocketSendOptions = {
  retryOnFailure?: boolean;
  maxRetries?: number;
  retryDelay?: number;
  timeout?: number;
};

export type WebSocketHookReturn = {
  status: WebSocketStatus;
  isConnected: boolean;
  send: (message: WebSocketMessage, options?: WebSocketSendOptions) => Promise<boolean>;
  sendRaw: (data: string | ArrayBuffer | Blob) => boolean;
  lastMessage: WebSocketMessage | null;
  messageHistory: WebSocketMessage[];
  clearMessageHistory: () => void;
  connect: () => void;
  disconnect: (code?: number, reason?: string) => void;
  error: Error | null;
  messageQueueSize: number;
  flushMessageQueue: () => void;
  getWebSocketInstance: () => WebSocket | null;
};

const DEFAULT_OPTIONS: Required<Omit<WebSocketOptions, 'url' | 'protocols' | 'onOpen' | 'onClose' | 'onError' | 'onMessage'>> = {
  autoConnect: true,
  reconnectAttempts: 5,
  reconnectInterval: 3000,
  heartbeatInterval: 30000,
  heartbeatMessage: () => ({
    type: 'heartbeat',
    payload: { timestamp: Date.now() },
    timestamp: Date.now(),
  }),
  debug: false,
  maxMessageQueueSize: 100,
};

const DEFAULT_SEND_OPTIONS: Required<WebSocketSendOptions> = {
  retryOnFailure: true,
  maxRetries: 3,
  retryDelay: 1000,
  timeout: 5000,
};

export const useWebSocket = (options: WebSocketOptions): WebSocketHookReturn => {
  const {
    url,
    protocols,
    autoConnect = DEFAULT_OPTIONS.autoConnect,
    reconnectAttempts = DEFAULT_OPTIONS.reconnectAttempts,
    reconnectInterval = DEFAULT_OPTIONS.reconnectInterval,
    heartbeatInterval = DEFAULT_OPTIONS.heartbeatInterval,
    heartbeatMessage = DEFAULT_OPTIONS.heartbeatMessage,
    onOpen,
    onClose,
    onError,
    onMessage,
    debug = DEFAULT_OPTIONS.debug,
    maxMessageQueueSize = DEFAULT_OPTIONS.maxMessageQueueSize,
  } = options;

  const wsRef = useRef<WebSocket | null>(null);
  const reconnectCountRef = useRef(0);
  const heartbeatTimerRef = useRef<NodeJS.Timeout | null>(null);
  const reconnectTimerRef = useRef<NodeJS.Timeout | null>(null);
  const messageQueueRef = useRef<Array<{ message: WebSocketMessage; options?: WebSocketSendOptions }>>([]);
  const isMountedRef = useRef(true);
  const pendingSendsRef = useRef<Map<string, { resolve: (value: boolean) => void; reject: (reason?: any) => void; timeoutId: NodeJS.Timeout }>>(new Map());

  const [status, setStatus] = useState<WebSocketStatus>('closed');
  const [lastMessage, setLastMessage] = useState<WebSocketMessage | null>(null);
  const [messageHistory, setMessageHistory] = useState<WebSocketMessage[]>([]);
  const [error, setError] = useState<Error | null>(null);

  const log = useCallback((level: 'log' | 'warn' | 'error', ...args: any[]) => {
    if (debug) {
      console[level]('[useWebSocket]', ...args);
    }
  }, [debug]);

  const clearTimers = useCallback(() => {
    if (heartbeatTimerRef.current) {
      clearInterval(heartbeatTimerRef.current);
      heartbeatTimerRef.current = null;
    }
    if (reconnectTimerRef.current) {
      clearTimeout(reconnectTimerRef.current);
      reconnectTimerRef.current = null;
    }
  }, []);

  const cleanupWebSocket = useCallback(() => {
    clearTimers();
    
    if (wsRef.current) {
      wsRef.current.onopen = null;
      wsRef.current.onclose = null;
      wsRef.current.onerror = null;
      wsRef.current.onmessage = null;
      
      if (wsRef.current.readyState === WebSocket.OPEN || wsRef.current.readyState === WebSocket.CONNECTING) {
        wsRef.current.close(1000, 'Component unmounting');
      }
      
      wsRef.current = null;
    }
    
    pendingSendsRef.current.forEach(({ reject, timeoutId }) => {
      clearTimeout(timeoutId);
      reject(new Error('WebSocket disconnected'));
    });
    pendingSendsRef.current.clear();
  }, [clearTimers]);

  const setupHeartbeat = useCallback(() => {
    if (heartbeatInterval <= 0 || !wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) {
      return;
    }

    clearTimers();
    
    heartbeatTimerRef.current = setInterval(() => {
      if (wsRef.current?.readyState === WebSocket.OPEN) {
        const message = typeof heartbeatMessage === 'function' ? heartbeatMessage() : heartbeatMessage;
        try {
          wsRef.current.send(JSON.stringify(message));
          log('log', 'Heartbeat sent', message);
        } catch (err) {
          log('error', 'Failed to send heartbeat', err);
        }
      }
    }, heartbeatInterval);
  }, [heartbeatInterval, heartbeatMessage, clearTimers, log]);

  const handleMessage = useCallback((event: MessageEvent) => {
    try {
      const data = JSON.parse(event.data);
      
      const message: WebSocketMessage = {
        type: data.type,
        payload: data.payload,
        timestamp: data.timestamp || Date.now(),
        id: data.id,
      };

      log('log', 'Message received', message);
      
      setLastMessage(message);
      setMessageHistory(prev => {
        const newHistory = [message, ...prev];
        return newHistory.slice(0, maxMessageQueueSize);
      });
      
      if (onMessage) {
        onMessage(message);
      }

      if (message.id && pendingSendsRef.current.has(message.id)) {
        const pending = pendingSendsRef.current.get(message.id);
        if (pending) {
          clearTimeout(pending.timeoutId);
          pending.resolve(true);
          pendingSendsRef.current.delete(message.id);
        }
      }
    } catch (err) {
      log('error', 'Failed to parse message', event.data, err);
      setError(err instanceof Error ? err : new Error('Failed to parse WebSocket message'));
    }
  }, [onMessage, maxMessageQueueSize, log]);

  const handleOpen = useCallback((event: Event) => {
    log('log', 'WebSocket connected');
    setStatus('open');
    setError(null);
    reconnectCountRef.current = 0;
    
    setupHeartbeat();
    
    if (onOpen) {
      onOpen(event);
    }

    const queue = [...messageQueueRef.current];
    messageQueueRef.current = [];
    
    queue.forEach(({ message, options: sendOptions }) => {
      send(message, sendOptions).catch(err => {
        log('error', 'Failed to send queued message', message, err);
      });
    });
  }, [onOpen, setupHeartbeat, log]);

  const handleClose = useCallback((event: CloseEvent) => {
    log('log', 'WebSocket disconnected', event.code, event.reason);
    setStatus('closed');
    clearTimers();
    
    if (onClose) {
      onClose(event);
    }

    if (event.code !== 1000 && event.code !== 1001 && isMountedRef.current) {
      if (reconnectCountRef.current < reconnectAttempts) {
        reconnectCountRef.current += 1;
        log('log', `Attempting reconnect ${reconnectCountRef.current}/${reconnectAttempts}`);
        
        reconnectTimerRef.current = setTimeout(() => {
          if (isMountedRef.current) {
            connect();
          }
        }, reconnectInterval);
      } else {
        setError(new Error(`Failed to reconnect after ${reconnectAttempts} attempts`));
      }
    }
  }, [onClose, reconnectAttempts, reconnectInterval, clearTimers, log]);

  const handleError = useCallback((event: Event) => {
    log('error', 'WebSocket error', event);
    setStatus('error');
    setError(new Error('WebSocket connection error'));
    
    if (onError) {
      onError(event);
    }
  }, [onError, log]);

  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN || wsRef.current?.readyState === WebSocket.CONNECTING) {
      log('warn', 'WebSocket already connecting or connected');
      return;
    }

    cleanupWebSocket();
    
    try {
      const actualUrl = typeof url === 'function' ? url() : url;
      log('log', 'Connecting to', actualUrl);
      
      setStatus('connecting');
      setError(null);
      
      wsRef.current = protocols ? new WebSocket(actualUrl, protocols) : new WebSocket(actualUrl);
      
      wsRef.current.onopen = handleOpen;
      wsRef.current.onclose = handleClose;
      wsRef.current.onerror = handleError;
      wsRef.current.onmessage = handleMessage;
    } catch (err) {
      log('error', 'Failed to create WebSocket', err);
      setStatus('error');
      setError(err instanceof Error ? err : new Error('Failed to create WebSocket'));
    }
  }, [url, protocols, handleOpen, handleClose, handleError, handleMessage, cleanupWebSocket, log]);

  const disconnect = useCallback((code: number = 1000, reason?: string) => {
    log('log', 'Disconnecting WebSocket', code, reason);
    setStatus('closing');
    
    if (wsRef.current) {
      wsRef.current.close(code, reason);
    }
    
    cleanupWebSocket();
    setStatus('closed');
  }, [cleanupWebSocket, log]);

  const sendRaw = useCallback((data: string | ArrayBuffer | Blob): boolean => {
    if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) {
      log('warn', 'Cannot send raw message, WebSocket not open');
      return false;
    }

    try {
      wsRef.current.send(data);
      return true;
    } catch (err) {
      log('error', 'Failed to send raw message', err);
      return false;
    }
  }, [log]);

  const send = useCallback(async (
    message: WebSocketMessage,
    options?: WebSocketSendOptions
  ): Promise<boolean> => {
    const {
      retryOnFailure = DEFAULT_SEND_OPTIONS.retryOnFailure,
      maxRetries = DEFAULT_SEND_OPTIONS.maxRetries,
      retryDelay = DEFAULT_SEND_OPTIONS.retryDelay,
      timeout = DEFAULT_SEND_OPTIONS.timeout,
    } = options || {};

    const messageWithId = {
      ...message,
      id: message.id || uuidv4(),
      timestamp: message.timestamp || Date.now(),
    };

    const sendMessage = (): Promise<boolean> => {
      return new Promise((resolve, reject) => {
        if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) {
          reject(new Error('WebSocket not connected'));
          return;
        }

        const timeoutId = setTimeout(() => {
          pendingSendsRef.current.delete(messageWithId.id!);
          reject(new Error('Send timeout'));
        }, timeout);

        pendingSendsRef.current.set(messageWithId.id!, {
          resolve,
          reject,
          timeoutId,
        });

        try {
          wsRef.current.send(JSON.stringify(messageWithId));
          log('log', 'Message sent', messageWithId);
        } catch (err) {
          clearTimeout(timeoutId);
          pendingSendsRef.current.delete(messageWithId.id!);
          reject(err);
        }
      });
    };

    let lastError: Error | null = null;
    
    for (let attempt = 0; attempt <= (retryOnFailure ? maxRetries : 0); attempt++) {
      try {
        if (attempt > 0) {
          log('log', `Retry attempt ${attempt} for message`, messageWithId);
          await new Promise(resolve => setTimeout(resolve, retryDelay));
        }

        const success = await sendMessage();
        return success;
      } catch (err) {
        lastError = err instanceof Error ? err : new Error(String(err));
        log('warn', `Send attempt ${attempt + 1} failed`, lastError);
        
        if (attempt === (retryOnFailure ? maxRetries : 0)) {
          break;
        }
      }
    }

    if (wsRef.current?.readyState !== WebSocket.OPEN) {
      log('log', 'Queueing message for later delivery', messageWithId);
      messageQueueRef.current.push({ message: messageWithId, options });
      
      if (messageQueueRef.current.length > maxMessageQueueSize) {
        log('warn', 'Message queue full, dropping oldest message');
        messageQueueRef.current.shift();
      }
      
      return false;
    }

    setError(lastError);
    return false;
  }, [maxMessageQueueSize, log]);

  const clearMessageHistory = useCallback(() => {
    setMessageHistory([]);
  }, []);

  const flushMessageQueue = useCallback(() => {
    messageQueueRef.current = [];
    log('log', 'Message queue flushed');
  }, [log]);

  const getWebSocketInstance = useCallback(() => wsRef.current, []);

  useEffect(() => {
    isMountedRef.current = true;
    
    if (autoConnect) {
      connect();
    }

    return () => {
      isMountedRef.current = false;
      cleanupWebSocket();
    };
  }, [autoConnect, connect, cleanupWebSocket]);

  return {
    status,
    isConnected: status === 'open',
    send,
    sendRaw,
    lastMessage,
    messageHistory,
    clearMessageHistory,
    connect,
    disconnect,
    error,
    messageQueueSize: messageQueueRef.current.length,
    flushMessageQueue,
    getWebSocketInstance,
  };
};

export default useWebSocket;
