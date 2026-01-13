/**
 * Connection Validation Script
 * 
 * Purpose: Comprehensive validation of backend-frontend integration
 * Tests API endpoints, WebSocket connections, and data consistency
 * 
 * Usage: node scripts/validate-connections.js [options]
 * 
 * Options:
 *   --api-url <url>      Base API URL (default: http://localhost:3000)
 *   --ws-url <url>       WebSocket URL (default: ws://localhost:3000)
 *   --timeout <ms>       Request timeout in ms (default: 10000)
 *   --verbose            Enable verbose logging
 *   --silent             Suppress all output except results
 *   --json               Output results as JSON only
 *   --test <test>        Run specific test (api, websocket, auth, all)
 */

import fetch from 'node-fetch';
import WebSocket from 'ws';
import { setTimeout as sleep } from 'timers/promises';

class ConnectionValidator {
  constructor(options = {}) {
    this.config = {
      apiUrl: options.apiUrl || 'http://localhost:3000',
      wsUrl: options.wsUrl || 'ws://localhost:3000',
      timeout: options.timeout || 10000,
      verbose: options.verbose || false,
      silent: options.silent || false,
      jsonOutput: options.json || false,
      specificTest: options.test || 'all'
    };

    this.results = {
      timestamp: new Date().toISOString(),
      config: { ...this.config },
      tests: {
        api: { passed: 0, failed: 0, total: 0, details: [] },
        websocket: { passed: 0, failed: 0, total: 0, details: [] },
        auth: { passed: 0, failed: 0, total: 0, details: [] },
        data: { passed: 0, failed: 0, total: 0, details: [] }
      },
      summary: { overall: 'pending', totalPassed: 0, totalFailed: 0, totalTests: 0 }
    };

    this.colors = {
      reset: '\x1b[0m',
      bright: '\x1b[1m',
      green: '\x1b[32m',
      red: '\x1b[31m',
      yellow: '\x1b[33m',
      blue: '\x1b[34m',
      magenta: '\x1b[35m',
      cyan: '\x1b[36m'
    };
  }

  log(message, type = 'info') {
    if (this.config.silent) return;
    
    const prefixes = {
      info: `${this.colors.cyan}[INFO]${this.colors.reset}`,
      success: `${this.colors.green}[✓]${this.colors.reset}`,
      error: `${this.colors.red}[✗]${this.colors.reset}`,
      warning: `${this.colors.yellow}[!]${this.colors.reset}`,
      debug: `${this.colors.magenta}[DEBUG]${this.colors.reset}`
    };

    if (type === 'debug' && !this.config.verbose) return;
    
    console.log(`${prefixes[type]} ${message}`);
  }

  async testWithTimeout(promise, timeoutMs, testName) {
    const timeoutPromise = new Promise((_, reject) => {
      setTimeout(() => reject(new Error(`Timeout after ${timeoutMs}ms`)), timeoutMs);
    });

    try {
      const result = await Promise.race([promise, timeoutPromise]);
      return { success: true, data: result };
    } catch (error) {
      return { success: false, error: error.message };
    }
  }

  async validateApiEndpoints() {
    this.log('Validating API endpoints...', 'info');
    
    const endpoints = [
      { path: '/api/health', method: 'GET', expectedStatus: 200, description: 'Health check' },
      { path: '/api/config', method: 'GET', expectedStatus: 200, description: 'Configuration endpoint' },
      { path: '/api/users', method: 'GET', expectedStatus: 200, description: 'Users endpoint' },
      { path: '/api/sessions', method: 'GET', expectedStatus: 200, description: 'Sessions endpoint' },
      { path: '/api/connections', method: 'GET', expectedStatus: 200, description: 'Connections endpoint' },
      { path: '/api/metrics', method: 'GET', expectedStatus: 200, description: 'Metrics endpoint' },
      { path: '/api/nonexistent', method: 'GET', expectedStatus: 404, description: '404 handling' }
    ];

    for (const endpoint of endpoints) {
      const testResult = {
        endpoint: endpoint.path,
        method: endpoint.method,
        description: endpoint.description,
        status: 'pending',
        responseTime: null,
        error: null
      };

      try {
        const startTime = Date.now();
        const response = await this.testWithTimeout(
          fetch(`${this.config.apiUrl}${endpoint.path}`, { method: endpoint.method }),
          this.config.timeout,
          `${endpoint.method} ${endpoint.path}`
        );

        if (response.success) {
          const responseTime = Date.now() - startTime;
          testResult.responseTime = responseTime;
          
          if (response.data.status === endpoint.expectedStatus) {
            testResult.status = 'passed';
            this.results.tests.api.passed++;
            this.log(`${endpoint.method} ${endpoint.path} - ${response.data.status} (${responseTime}ms)`, 'success');
          } else {
            testResult.status = 'failed';
            testResult.error = `Expected ${endpoint.expectedStatus}, got ${response.data.status}`;
            this.results.tests.api.failed++;
            this.log(`${endpoint.method} ${endpoint.path} - Expected ${endpoint.expectedStatus}, got ${response.data.status}`, 'error');
          }
        } else {
          testResult.status = 'failed';
          testResult.error = response.error;
          this.results.tests.api.failed++;
          this.log(`${endpoint.method} ${endpoint.path} - ${response.error}`, 'error');
        }
      } catch (error) {
        testResult.status = 'failed';
        testResult.error = error.message;
        this.results.tests.api.failed++;
        this.log(`${endpoint.method} ${endpoint.path} - ${error.message}`, 'error');
      }

      testResult.timestamp = new Date().toISOString();
      this.results.tests.api.details.push(testResult);
      this.results.tests.api.total++;
    }
  }

  async validateWebSocketConnection() {
    this.log('Validating WebSocket connection...', 'info');
    
    const testResult = {
      url: this.config.wsUrl,
      description: 'WebSocket connection and messaging',
      status: 'pending',
      connectionTime: null,
      messageLatency: null,
      error: null,
      events: []
    };

    return new Promise((resolve) => {
      const startTime = Date.now();
      let connected = false;
      let messageReceived = false;
      let pingSent = false;

      const ws = new WebSocket(this.config.wsUrl);
      const timeoutId = setTimeout(() => {
        if (!connected) {
          testResult.status = 'failed';
          testResult.error = 'Connection timeout';
          this.results.tests.websocket.failed++;
          this.log(`WebSocket connection timeout to ${this.config.wsUrl}`, 'error');
          ws.terminate();
          resolve();
        }
      }, this.config.timeout);

      ws.on('open', () => {
        clearTimeout(timeoutId);
        connected = true;
        const connectionTime = Date.now() - startTime;
        testResult.connectionTime = connectionTime;
        testResult.events.push({ type: 'connected', timestamp: new Date().toISOString(), latency: connectionTime });
        
        this.log(`WebSocket connected to ${this.config.wsUrl} (${connectionTime}ms)`, 'success');

        // Send test ping
        pingSent = true;
        const pingTime = Date.now();
        ws.send(JSON.stringify({ type: 'ping', timestamp: pingTime }));
        testResult.events.push({ type: 'ping_sent', timestamp: new Date().toISOString() });

        // Set message receive timeout
        setTimeout(() => {
          if (!messageReceived) {
            testResult.status = 'failed';
            testResult.error = 'No response to ping';
            this.results.tests.websocket.failed++;
            this.log('No response to WebSocket ping', 'error');
            ws.close();
            resolve();
          }
        }, 5000);
      });

      ws.on('message', (data) => {
        try {
          const message = JSON.parse(data.toString());
          testResult.events.push({ type: 'message_received', timestamp: new Date().toISOString(), data: message });

          if (message.type === 'pong' && pingSent) {
            messageReceived = true;
            const latency = Date.now() - message.timestamp;
            testResult.messageLatency = latency;
            
            testResult.status = 'passed';
            this.results.tests.websocket.passed++;
            this.log(`WebSocket ping-pong latency: ${latency}ms`, 'success');
            
            // Test subscription
            ws.send(JSON.stringify({ type: 'subscribe', channel: 'test' }));
            setTimeout(() => {
              ws.close();
              resolve();
            }, 1000);
          }
        } catch (error) {
          testResult.events.push({ type: 'parse_error', timestamp: new Date().toISOString(), error: error.message });
        }
      });

      ws.on('error', (error) => {
        clearTimeout(timeoutId);
        testResult.status = 'failed';
        testResult.error = error.message;
        this.results.tests.websocket.failed++;
        this.log(`WebSocket error: ${error.message}`, 'error');
        resolve();
      });

      ws.on('close', () => {
        testResult.events.push({ type: 'closed', timestamp: new Date().toISOString() });
        if (!testResult.status || testResult.status === 'pending') {
          testResult.status = connected ? 'passed' : 'failed';
          if (testResult.status === 'passed') {
            this.results.tests.websocket.passed++;
          } else {
            this.results.tests.websocket.failed++;
          }
        }
        this.results.tests.websocket.total++;
        resolve();
      });
    });
  }

  async validateAuthentication() {
    this.log('Validating authentication flow...', 'info');
    
    const authTests = [
      {
        name: 'Login with valid credentials',
        method: 'POST',
        path: '/api/auth/login',
        body: { username: 'testuser', password: 'testpass' },
        validate: (response) => response.token && response.user
      },
      {
        name: 'Login with invalid credentials',
        method: 'POST',
        path: '/api/auth/login',
        body: { username: 'invalid', password: 'wrong' },
        expectedStatus: 401
      },
      {
        name: 'Protected endpoint without token',
        method: 'GET',
        path: '/api/auth/profile',
        expectedStatus: 401
      }
    ];

    let authToken = null;

    for (const test of authTests) {
      const testResult = {
        name: test.name,
        endpoint: test.path,
        method: test.method,
        status: 'pending',
        responseTime: null,
        error: null
      };

      try {
        const headers = { 'Content-Type': 'application/json' };
        if (authToken && test.path !== '/api/auth/login') {
          headers['Authorization'] = `Bearer ${authToken}`;
        }

        const startTime = Date.now();
        const response = await this.testWithTimeout(
          fetch(`${this.config.apiUrl}${test.path}`, {
            method: test.method,
            headers,
            body: test.body ? JSON.stringify(test.body) : undefined
          }),
          this.config.timeout,
          test.name
        );

        if (response.success) {
          const responseTime = Date.now() - startTime;
          testResult.responseTime = responseTime;

          if (test.expectedStatus && response.data.status !== test.expectedStatus) {
            testResult.status = 'failed';
            testResult.error = `Expected status ${test.expectedStatus}, got ${response.data.status}`;
            this.results.tests.auth.failed++;
            this.log(`${test.name} - Status mismatch: ${response.data.status}`, 'error');
          } else if (test.validate) {
            try {
              const data = await response.data.json();
              if (test.validate(data)) {
                testResult.status = 'passed';
                this.results.tests.auth.passed++;
                this.log(`${test.name} - Success (${responseTime}ms)`, 'success');
                
                // Store token for subsequent tests
                if (data.token) {
                  authToken = data.token;
                }
              } else {
                testResult.status = 'failed';
                testResult.error = 'Validation failed';
                this.results.tests.auth.failed++;
                this.log(`${test.name} - Validation failed`, 'error');
              }
            } catch (parseError) {
              testResult.status = 'failed';
              testResult.error = `JSON parse error: ${parseError.message}`;
              this.results.tests.auth.failed++;
              this.log(`${test.name} - JSON parse error`, 'error');
            }
          } else {
            testResult.status = 'passed';
            this.results.tests.auth.passed++;
            this.log(`${test.name} - Success (${responseTime}ms)`, 'success');
          }
        } else {
          testResult.status = 'failed';
          testResult.error = response.error;
          this.results.tests.auth.failed++;
          this.log(`${test.name} - ${response.error}`, 'error');
        }
      } catch (error) {
        testResult.status = 'failed';
        testResult.error = error.message;
        this.results.tests.auth.failed++;
        this.log(`${test.name} - ${error.message}`, 'error');
      }

      testResult.timestamp = new Date().toISOString();
      this.results.tests.auth.details.push(testResult);
      this.results.tests.auth.total++;
    }
  }

  async validateDataConsistency() {
    this.log('Validating data consistency between endpoints...', 'info');
    
    const consistencyTests = [
      {
        name: 'User count consistency',
        endpoints: ['/api/users', '/api/metrics/users'],
        validate: async (responses) => {
          const users = await responses[0].json();
          const metrics = await responses[1].json();
          return users.length === metrics.total;
        }
      },
      {
        name: 'Session data structure',
        endpoint: '/api/sessions',
        validate: async (response) => {
          const sessions = await response.json();
          return Array.isArray(sessions) && 
                 sessions.every(s => s.id && s.userId && s.createdAt);
        }
      }
    ];

    for (const test of consistencyTests) {
      const testResult = {
        name: test.name,
        status: 'pending',
        error: null,
        validationResult: null
      };

      try {
        if (test.endpoints) {
          // Multiple endpoint comparison
          const responses = await Promise.all(
            test.endpoints.map(endpoint =>
              this.testWithTimeout(
                fetch(`${this.config.apiUrl}${endpoint}`),
                this.config.timeout,
                `${test.name} - ${endpoint}`
              )
            )
          );

          const allSuccessful = responses.every(r => r.success);
          if (allSuccessful) {
            const isValid = await test.validate(responses.map(r => r.data));
            testResult.validationResult = isValid;
            
            if (isValid) {
              testResult.status = 'passed';
              this.results.tests.data.passed++;
              this.log(`${test.name} - Data consistent`, 'success');
            } else {
              testResult.status = 'failed';
              testResult.error = 'Data inconsistency detected';
              this.results.tests.data.failed++;
              this.log(`${test.name} - Data inconsistency`, 'error');
            }
          } else {
            testResult.status = 'failed';
            testResult.error = responses.find(r => !r.success).error;
            this.results.tests.data.failed++;
            this.log(`${test.name} - ${testResult.error}`, 'error');
          }
        } else {
          // Single endpoint validation
          const response = await this.testWithTimeout(
            fetch(`${this.config.apiUrl}${test.endpoint}`),
            this.config.timeout,
            `${test.name} - ${test.endpoint}`
          );

          if (response.success) {
            const isValid = await test.validate(response.data);
            testResult.validationResult = isValid;
            
            if (isValid) {
              testResult.status = 'passed';
              this.results.tests.data.passed++;
              this.log(`${test.name} - Valid data structure`, 'success');
            } else {
              testResult.status = 'failed';
              testResult.error = 'Invalid data structure';
              this.results.tests.data.failed++;
              this.log(`${test.name} - Invalid structure`, 'error');
            }
          } else {
            testResult.status = 'failed';
            testResult.error = response.error;
            this.results.tests.data.failed++;
            this.log(`${test.name} - ${response.error}`, 'error');
          }
        }
      } catch (error) {
        testResult.status = 'failed';
        testResult.error = error.message;
        this.results.tests.data.failed++;
        this.log(`${test.name} - ${error.message}`, 'error');
      }

      testResult.timestamp = new Date().toISOString();
      this.results.tests.data.details.push(testResult);
      this.results.tests.data.total++;
    }
  }

  calculateSummary() {
    const tests = this.results.tests;
    let totalPassed = 0;
    let totalFailed = 0;
    let totalTests = 0;

    for (const category in tests) {
      totalPassed += tests[category].passed;
      totalFailed += tests[category].failed;
      totalTests += tests[category].total;
    }

    this.results.summary = {
      overall: totalFailed === 0 ? 'passed' : 'failed',
      totalPassed,
      totalFailed,
      totalTests,
      passRate: totalTests > 0 ? ((totalPassed / totalTests) * 100).toFixed(2) + '%' : '0%'
    };
  }

  printResults() {
    if (