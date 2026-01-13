/**
 * WebSocket Client & UI Manager for Real-Time Dashboard
 * High-Concurrency Architecture - CodeCraft AI Synthesis
 * 
 * Features:
 * - Exponential backoff reconnection
 * - Message queuing with priority
 * - DOM virtualization for high-frequency updates
 * - Connection health monitoring
 * - Graceful degradation
 */

// ============================================================================
// CONFIGURATION & CONSTANTS
// ============================================================================

const CONFIG = {
    WS_ENDPOINT: 'ws://' + window.location.host + '/ws',
    RECONNECT_BASE_DELAY: 1000,
    RECONNECT_MAX_DELAY: 30000,
    RECONNECT_MAX_ATTEMPTS: 10,
    HEARTBEAT_INTERVAL: 30000,
    QUEUE_FLUSH_INTERVAL: 100,
    MAX_QUEUE_SIZE: 1000,
    DOM_BATCH_SIZE: 50,
    METRICS_RETENTION: 100
};

// ============================================================================
// STATE MANAGEMENT
// ============================================================================

const AppState = {
    // Connection
    ws: null,
    connectionId: null,
    isConnected: false,
    reconnectAttempts: 0,
    reconnectTimer: null,
    heartbeatTimer: null,
    
    // Message Queue
    messageQueue: [],
    queueFlushTimer: null,
    
    // Metrics
    metrics: {
        messagesReceived: 0,
        messagesSent: 0,
        connectionUptime: 0,
        lastLatency: 0,
        errors: []
    },
    
    // UI State
    uiComponents: {},
    dataCache: new Map(),
    lastUpdateTime: 0,
    
    // Subscriptions
    subscriptions: new Set()
};

// ============================================================================
// WEBSOCKET CLIENT
// ============================================================================

class WebSocketClient {
    constructor() {
        this.initEventListeners();
        this.initUI();
        this.connect();
    }
    
    /**
     * Establish WebSocket connection with exponential backoff
     */
    connect() {
        if (AppState.ws && AppState.ws.readyState === WebSocket.CONNECTING) {
            console.warn('Connection already in progress');
            return;
        }
        
        try {
            AppState.ws = new WebSocket(CONFIG.WS_ENDPOINT);
            this.setupWebSocketHandlers();
            this.updateConnectionStatus('connecting');
        } catch (error) {
            console.error('Failed to create WebSocket:', error);
            this.scheduleReconnect();
        }
    }
    
    /**
     * Setup WebSocket event handlers
     */
    setupWebSocketHandlers() {
        const ws = AppState.ws;
        
        ws.onopen = (event) => {
            console.log('WebSocket connected successfully');
            AppState.isConnected = true;
            AppState.reconnectAttempts = 0;
            AppState.connectionId = this.generateConnectionId();
            this.updateConnectionStatus('connected');
            this.startHeartbeat();
            this.flushMessageQueue();
            
            // Send connection metadata
            this.send({
                type: 'connection_init',
                connectionId: AppState.connectionId,
                timestamp: Date.now(),
                capabilities: ['subscribe', 'unsubscribe', 'heartbeat']
            });
        };
        
        ws.onmessage = (event) => {
            try {
                const message = JSON.parse(event.data);
                this.handleIncomingMessage(message);
                AppState.metrics.messagesReceived++;
                this.updateMetricsDisplay();
            } catch (error) {
                console.error('Failed to parse message:', error, event.data);
                this.recordError('message_parse_error', error.message);
            }
        };
        
        ws.onclose = (event) => {
            console.log(`WebSocket disconnected: ${event.code} ${event.reason}`);
            AppState.isConnected = false;
            this.updateConnectionStatus('disconnected');
            this.stopHeartbeat();
            
            if (!event.wasClean) {
                this.scheduleReconnect();
            }
        };
        
        ws.onerror = (error) => {
            console.error('WebSocket error:', error);
            this.recordError('websocket_error', error.message || 'Unknown error');
            this.updateConnectionStatus('error');
        };
    }
    
    /**
     * Handle incoming WebSocket messages
     */
    handleIncomingMessage(message) {
        const { type, data, timestamp, requestId } = message;
        
        // Update latency
        if (timestamp) {
            AppState.metrics.lastLatency = Date.now() - timestamp;
        }
        
        // Route message by type
        switch (type) {
            case 'heartbeat_ack':
                this.handleHeartbeatAck(data);
                break;
                
            case 'subscription_update':
                this.handleSubscriptionUpdate(data);
                break;
                
            case 'connection_ack':
                this.handleConnectionAck(data);
                break;
                
            case 'error':
                this.handleServerError(data);
                break;
                
            case 'metrics':
                this.handleMetricsUpdate(data);
                break;
                
            default:
                console.warn('Unknown message type:', type);
                this.send({
                    type: 'error',
                    error: 'unknown_message_type',
                    receivedType: type
                });
        }
        
        // Fire custom event for external handlers
        this.dispatchMessageEvent(type, message);
    }
    
    /**
     * Send message with queuing fallback
     */
    send(message, priority = false) {
        if (!message.type) {
            console.error('Message must have a type');
            return;
        }
        
        // Add metadata
        const enrichedMessage = {
            ...message,
            timestamp: Date.now(),
            messageId: this.generateMessageId()
        };
        
        // Immediate send if connected
        if (AppState.isConnected && AppState.ws?.readyState === WebSocket.OPEN) {
            try {
                AppState.ws.send(JSON.stringify(enrichedMessage));
                AppState.metrics.messagesSent++;
                return true;
            } catch (error) {
                console.error('Failed to send message:', error);
                this.recordError('send_error', error.message);
            }
        }
        
        // Queue for later delivery
        return this.queueMessage(enrichedMessage, priority);
    }
    
    /**
     * Queue message for later delivery
     */
    queueMessage(message, priority = false) {
        if (AppState.messageQueue.length >= CONFIG.MAX_QUEUE_SIZE) {
            console.warn('Message queue full, dropping oldest message');
            AppState.messageQueue.shift();
        }
        
        if (priority) {
            AppState.messageQueue.unshift(message);
        } else {
            AppState.messageQueue.push(message);
        }
        
        // Ensure flush timer is running
        if (!AppState.queueFlushTimer) {
            AppState.queueFlushTimer = setInterval(
                () => this.flushMessageQueue(),
                CONFIG.QUEUE_FLUSH_INTERVAL
            );
        }
        
        return false;
    }
    
    /**
     * Flush queued messages
     */
    flushMessageQueue() {
        if (!AppState.isConnected || AppState.messageQueue.length === 0) {
            return;
        }
        
        const batchSize = Math.min(CONFIG.DOM_BATCH_SIZE, AppState.messageQueue.length);
        const batch = AppState.messageQueue.splice(0, batchSize);
        
        batch.forEach(message => {
            try {
                AppState.ws.send(JSON.stringify(message));
                AppState.metrics.messagesSent++;
            } catch (error) {
                console.error('Failed to send queued message:', error);
                this.recordError('queue_flush_error', error.message);
                // Re-queue failed message
                this.queueMessage(message, true);
            }
        });
        
        // Clear timer if queue is empty
        if (AppState.messageQueue.length === 0 && AppState.queueFlushTimer) {
            clearInterval(AppState.queueFlushTimer);
            AppState.queueFlushTimer = null;
        }
    }
    
    /**
     * Schedule reconnection with exponential backoff
     */
    scheduleReconnect() {
        if (AppState.reconnectAttempts >= CONFIG.RECONNECT_MAX_ATTEMPTS) {
            console.error('Max reconnection attempts reached');
            this.updateConnectionStatus('failed');
            return;
        }
        
        if (AppState.reconnectTimer) {
            clearTimeout(AppState.reconnectTimer);
        }
        
        const delay = Math.min(
            CONFIG.RECONNECT_BASE_DELAY * Math.pow(2, AppState.reconnectAttempts),
            CONFIG.RECONNECT_MAX_DELAY
        );
        
        console.log(`Scheduling reconnection in ${delay}ms (attempt ${AppState.reconnectAttempts + 1})`);
        
        AppState.reconnectTimer = setTimeout(() => {
            AppState.reconnectAttempts++;
            this.connect();
        }, delay);
        
        this.updateReconnectionDisplay(delay);
    }
    
    /**
     * Heartbeat mechanism
     */
    startHeartbeat() {
        if (AppState.heartbeatTimer) {
            clearInterval(AppState.heartbeatTimer);
        }
        
        AppState.heartbeatTimer = setInterval(() => {
            if (AppState.isConnected) {
                this.send({
                    type: 'heartbeat',
                    timestamp: Date.now()
                });
            }
        }, CONFIG.HEARTBEAT_INTERVAL);
    }
    
    stopHeartbeat() {
        if (AppState.heartbeatTimer) {
            clearInterval(AppState.heartbeatTimer);
            AppState.heartbeatTimer = null;
        }
    }
    
    /**
     * Handle heartbeat acknowledgment
     */
    handleHeartbeatAck(data) {
        // Update last successful heartbeat
        AppState.lastHeartbeat = Date.now();
        this.updateConnectionHealth();
    }
    
    // ============================================================================
    // MESSAGE HANDLERS
    // ============================================================================
    
    handleConnectionAck(data) {
        console.log('Connection acknowledged by server:', data);
        if (data.sessionId) {
            AppState.sessionId = data.sessionId;
        }
    }
    
    handleSubscriptionUpdate(data) {
        const { subscriptionId, payload, timestamp } = data;
        
        // Cache the data
        AppState.dataCache.set(subscriptionId, {
            data: payload,
            timestamp: timestamp || Date.now(),
            received: Date.now()
        });
        
        // Update UI components subscribed to this data
        this.updateSubscribedComponents(subscriptionId, payload);
    }
    
    handleServerError(data) {
        console.error('Server error:', data);
        this.recordError('server_error', data.message || 'Unknown server error');
        
        // Show user-friendly error
        this.showNotification({
            type: 'error',
            title: 'Server Error',
            message: data.message || 'An error occurred on the server',
            duration: 5000
        });
    }
    
    handleMetricsUpdate(data) {
        // Merge server metrics with client metrics
        AppState.serverMetrics = data;
        this.updateMetricsDisplay();
    }
    
    // ============================================================================
    // UI MANAGEMENT
    // ============================================================================
    
    /**
     * Initialize UI components and event listeners
     */
    initUI() {
        // Cache DOM elements
        AppState.uiComponents = {
            connectionStatus: document.getElementById('connection-status'),
            connectionDetails: document.getElementById('connection-details'),
            metricsDisplay: document.getElementById('metrics-display'),
            messageLog: document.getElementById('message-log'),
            subscriptionList: document.getElementById('subscription-list'),
            errorDisplay: document.getElementById('error-display'),
            reconnectBtn: document.getElementById('reconnect-btn'),
            clearLogBtn: document.getElementById('clear-log-btn'),
            subscribeBtn: document.getElementById('subscribe-btn'),
            unsubscribeBtn: document.getElementById('unsubscribe-btn'),
            subscriptionInput: document.getElementById('subscription-input')
        };
        
        // Setup event listeners
        this.setupUIEventListeners();
        
        // Initialize displays
        this.updateConnectionStatus('initializing');
        this.updateMetricsDisplay();
    }
    
    /**
     * Setup UI event listeners
     */
    setupUIEventListeners() {
        const ui = AppState.uiComponents;
        
        if (ui.reconnectBtn) {
            ui.reconnectBtn.addEventListener('click', () => {
                this.manualReconnect();
            });
        }
        
        if (ui.clearLogBtn) {
            ui.clearLogBtn.addEventListener('click', () => {
                this.clearMessageLog();
            });
        }
        
        if (ui.subscribeBtn && ui.subscriptionInput) {
            ui.subscribeBtn.addEventListener('click', () => {
                const topic = ui.subscriptionInput.value.trim();
                if (topic) {
                    this.subscribe(topic);
                    ui.subscriptionInput.value = '';
                }
            });
            
            // Allow Enter key
            ui.subscriptionInput.addEventListener('keypress', (e) => {
                if (e.key === 'Enter') {
                    ui.subscribeBtn.click();
                }
            });
        }
        
        if (ui.unsubscribeBtn) {
            ui.unsubscribeBtn.addEventListener('click', () => {
                const topic = ui.subscriptionInput?.value.trim();
                if (topic) {
                    this.unsubscribe(topic);
                }
            });
        }
    }
    
    /**
     * Update connection status display
     */
    updateConnectionStatus(status) {
        const ui = AppState.uiComponents;
        if (!ui.connectionStatus) return;
        
        const statusMap = {
            initializing: { text: 'Initializing...', className: 'status-initializing' },
            connecting: { text: 'Connecting...', className: 'status-connecting' },
            connected: { text: 'Connected', className: 'status-connected' },
            disconnected: { text: 'Disconnected', className: 'status-disconnected' },
            error: { text: 'Error', className: 'status-error' },
            failed: { text: 'Connection Failed', className: 'status-failed' }
        };
        
        const statusInfo = statusMap[status] || { text: 'Unknown', className: 'status-unknown' };
        
        ui.connectionStatus.textContent = statusInfo.text;
        ui.connectionStatus.className = `connection-status ${statusInfo.className}`;
        
        // Update details
        if (ui.connectionDetails) {
            const details = [];
            
            if (AppState.connectionId) {
                details.push(`ID: ${AppState.connectionId.substring(0, 8)}...`);
            }
            
            if (AppState.isConnected) {
                details.push(`Latency: ${AppState.metrics.lastLatency}ms`);
            }
            
            if (AppState.reconnectAttempts > 0) {
                details.push(`Reconnect attempts: ${AppState.reconnectAttempts}`);
            }
            
            ui.connectionDetails.textContent = details.join(' • ');
        }
    }
    
    /**
     * Update reconnection countdown display
     */
    updateReconnectionDisplay(delay) {
        const ui = AppState.uiComponents;
        if (!ui.connectionDetails) return;
        
        const seconds = Math.ceil(delay / 1000);
        ui.connectionDetails.textContent = `Reconnecting in ${seconds}s...`;
    }
    
    /**
     * Update metrics display
     */
    updateMetricsDisplay() {
        const ui = AppState.uiComponents;
        if (!ui.metricsDisplay) return;
        
        const metrics = AppState.metrics;
        const html = `
            <div class="metric">
                <span class="metric-label">Messages Received:</span>
                <span class="metric-value">${metrics.messagesReceived.toLocaleString()}</span>
            </div>
            <div class="metric">
                <span class="metric-label">Messages Sent:</span>
                <span class="metric-value">${metrics.messagesSent.toLocaleString()}</span>
            </div>
            <div class="metric">
                <span class="metric-label">Latency:</span>
                <span class="metric-value">${metrics.lastLatency}ms</span>
            </div>
            <div class="metric">
                <span class="metric-label">Queue Size:</span>
                <span class="metric-value">${AppState.messageQueue.length}</span>
            </div>
            <div class="metric">
                <span class="metric-label">Subscriptions:</span>
                <span class="metric-value">${AppState.subscriptions.size}</span>
            </div>
        `;
        
        ui.metricsDisplay.innerHTML = html;
    }
    
    /**
     * Log message to UI
     */
    logMessage(message, type = 'info') {
        const ui = AppState.uiComponents;
        if (!ui.messageLog) return;
        
        const timestamp = new Date().toISOString().substring(11, 23);
        const messageText = typeof message === 'object' ? JSON.stringify(message) : message;
        
        const logEntry = document.createElement('div');
        logEntry.className = `log-entry log-${type}`;
        logEntry.innerHTML = `
            <span class="log-timestamp">${timestamp}</span>
            <span class="log-type">[${type.toUpperCase()}]</span>
            <span class="log-message">${this.escapeHtml(messageText)}</span>
        `;
        
        // Virtualization: Keep only last N entries
        const maxEntries = 100;
        if (ui.messageLog.children.length >= maxEntries) {
            ui.messageLog.removeChild(ui.messageLog.firstChild);
        }
        
        ui.messageLog.appendChild(logEntry);
        ui.messageLog.scrollTop = ui.messageLog.scrollHeight;
    }
    
    /**
     * Clear message log
     */
    clearMessageLog() {
        const ui = AppState.uiComponents;
        if (ui.messageLog) {
            ui.messageLog.innerHTML = '';
        }
    }
    
    /**
     * Show notification to user
     */
    showNotification(options) {
        // Create notification element
        const notification = document.createElement('div');
        notification.className = `notification notification-${options.type || 'info'}`;
        notification.innerHTML = `
            <div class="notification-header">
                <strong>${options.title || 'Notification'}</strong>
                <button class="notification-close">&times;</button>
            </div>
            <div class="notification-body">${options.message || ''}</div>
        `;
        
        // Add to document
        document.body.appendChild(notification);
        
        // Auto-remove after duration
        const duration = options.duration || 3000;
        setTimeout(() => {
            if (notification.parentNode) {
                notification.style.opacity = '0';
                setTimeout(() => {
                    if (notification.parentNode) {
                        notification.parentNode.removeChild(notification);
                    }
                }, 300);
            }
        }, duration);
        
        // Close button
        const closeBtn = notification.querySelector('.notification-close');
        closeBtn.addEventListener('click', () => {
            if (notification.parentNode) {
                notification.parentNode.removeChild(notification);
            }
        });
    }
    
    /**
     * Update subscription list display