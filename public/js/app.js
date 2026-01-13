/**
 * CodeCraft AI - Client-Side Logic Module
 * File: public/js/app.js
 * Purpose: Handles data fetching, state management, and DOM manipulation for the frontend.
 */

'use strict';

class Application {
    constructor() {
        // Configuration
        this.config = {
            apiBaseUrl: '/api/v1',
            endpoints: {
                data: '/data',
                status: '/status'
            },
            refreshInterval: 30000, // 30 seconds
            maxRetries: 3
        };

        // State
        this.state = {
            isLoading: false,
            data: [],
            lastUpdated: null,
            error: null,
            retryCount: 0
        };

        // DOM Elements Cache
        this.elements = {
            container: null,
            statusIndicator: null,
            refreshButton: null,
            lastUpdatedLabel: null,
            errorMessage: null,
            loadingOverlay: null
        };

        // Bind methods to preserve context
        this.init = this.init.bind(this);
        this.fetchData = this.fetchData.bind(this);
        this.handleRefreshClick = this.handleRefreshClick.bind(this);
    }

    /**
     * Initialize the application.
     * Sets up DOM references and event listeners.
     */
    init() {
        console.log('[App] Initializing...');

        // Cache DOM elements
        this.elements.container = document.getElementById('data-container');
        this.elements.statusIndicator = document.getElementById('system-status');
        this.elements.refreshButton = document.getElementById('btn-refresh');
        this.elements.lastUpdatedLabel = document.getElementById('last-updated');
        this.elements.errorMessage = document.getElementById('error-message');
        this.elements.loadingOverlay = document.getElementById('loading-overlay');

        // Validate essential DOM elements exist
        if (!this.elements.container) {
            console.error('[App] Critical Error: #data-container not found in DOM.');
            return;
        }

        // Attach Event Listeners
        if (this.elements.refreshButton) {
            this.elements.refreshButton.addEventListener('click', this.handleRefreshClick);
        }

        // Start initial data fetch
        this.fetchData();

        // Set up auto-refresh
        setInterval(() => {
            if (!this.state.isLoading && !this.state.error) {
                console.log('[App] Auto-refreshing data...');
                this.fetchData(true); // true = silent refresh
            }
        }, this.config.refreshInterval);
    }

    /**
     * Handles the manual refresh button click.
     * @param {Event} e 
     */
    handleRefreshClick(e) {
        if (e) e.preventDefault();
        if (this.state.isLoading) return;
        
        console.log('[App] Manual refresh triggered.');
        this.fetchData(false);
    }

    /**
     * Fetches data from the backend API.
     * @param {boolean} silent - If true, suppresses full loading overlay.
     */
    async fetchData(silent = false) {
        this.setLoading(true, silent);
        this.clearError();

        try {
            const url = `${this.config.apiBaseUrl}${this.config.endpoints.data}`;
            const response = await fetch(url, {
                method: 'GET',
                headers: {
                    'Content-Type': 'application/json',
                    'Accept': 'application/json'
                }
            });

            if (!response.ok) {
                throw new Error(`HTTP Error: ${response.status} ${response.statusText}`);
            }

            const result = await response.json();

            // Simulate network delay for UX demonstration (optional, remove in prod)
            // await new Promise(r => setTimeout(r, 500));

            this.state.data = result.data || [];
            this.state.lastUpdated = new Date();
            this.state.retryCount = 0; // Reset retries on success

            this.render();
            this.updateStatus('online');

        } catch (error) {
            console.error('[App] Fetch failed:', error);
            this.state.error = error.message;
            this.updateStatus('offline');
            
            // Retry logic
            if (this.state.retryCount < this.config.maxRetries) {
                this.state.retryCount++;
                const delay = this.state.retryCount * 1000; // Exponential backoff-ish
                console.log(`[App] Retrying in ${delay}ms (Attempt ${this.state.retryCount})...`);
                setTimeout(() => this.fetchData(silent), delay);
            } else {
                this.renderError();
            }
        } finally {
            this.setLoading(false, silent);
        }
    }

    /**
     * Updates the application state regarding loading.
     * @param {boolean} isLoading 
     * @param {boolean} silent 
     */
    setLoading(isLoading, silent) {
        this.state.isLoading = isLoading;

        if (this.elements.refreshButton) {
            this.elements.refreshButton.disabled = isLoading;
            this.elements.refreshButton.textContent = isLoading ? 'Loading...' : 'Refresh Data';
        }

        if (!silent && this.elements.loadingOverlay) {
            if (isLoading) {
                this.elements.loadingOverlay.classList.remove('hidden');
                this.elements.loadingOverlay.classList.add('flex');
            } else {
                this.elements.loadingOverlay.classList.add('hidden');
                this.elements.loadingOverlay.classList.remove('flex');
            }
        }
    }

    /**
     * Clears any existing error messages from the UI.
     */
    clearError() {
        this.state.error = null;
        if (this.elements.errorMessage) {
            this.elements.errorMessage.classList.add('hidden');
            this.elements.errorMessage.textContent = '';
        }
        if (this.elements.container) {
            this.elements.container.classList.remove('opacity-50');
        }
    }

    /**
     * Renders the error state to the UI.
     */
    renderError() {
        if (this.elements.errorMessage) {
            this.elements.errorMessage.textContent = `Error: ${this.state.error}. Please check your connection.`;
            this.elements.errorMessage.classList.remove('hidden');
        }
        
        // Dim the container to indicate stale data
        if (this.elements.container) {
            this.elements.container.classList.add('opacity-50');
        }
    }

    /**
     * Updates the system status indicator.
     * @param {'online'|'offline'} status 
     */
    updateStatus(status) {
        if (!this.elements.statusIndicator) return;

        const indicator = this.elements.statusIndicator;
        
        // Remove old classes
        indicator.classList.remove('bg-green-500', 'bg-red-500', 'bg-yellow-500');

        if (status === 'online') {
            indicator.classList.add('bg-green-500');
            indicator.title = "System Online";
        } else {
            indicator.classList.add('bg-red-500');
            indicator.title = "Connection Lost";
        }
    }

    /**
     * Main render function. Updates the DOM based on current state.
     */
    render() {
        // Update timestamp
        if (this.elements.lastUpdatedLabel && this.state.lastUpdated) {
            const timeString = this.state.lastUpdated.toLocaleTimeString();
            this.elements.lastUpdatedLabel.textContent = `Last updated: ${timeString}`;
        }

        // Clear container
        const container = this.elements.container;
        container.innerHTML = '';

        // Handle empty state
        if (this.state.data.length === 0) {
            this.renderEmptyState(container);
            return;
        }

        // Render items
        const fragment = document.createDocumentFragment();
        
        this.state.data.forEach(item => {
            const card = this.createItemCard(item);
            fragment.appendChild(card);
        });

        container.appendChild(fragment);
    }

    /**
     * Renders a message when no data is available.
     * @param {HTMLElement} container 
     */
    renderEmptyState(container) {
        const emptyDiv = document.createElement('div');
        emptyDiv.className = 'col-span-full text-center py-12 text-gray-500';
        
        const icon = document.createElement('div');
        icon.className = 'text-4xl mb-2';
        icon.textContent = '📭'; // Simple emoji icon
        
        const text = document.createElement('p');
        text.textContent = 'No data available at the moment.';

        emptyDiv.appendChild(icon);
        emptyDiv.appendChild(text);
        container.appendChild(emptyDiv);
    }

    /**
     * Creates a DOM element for a single data item.
     * Assumes item structure: { id, title, description, status, value }
     * @param {Object} item 
     * @returns {HTMLElement}
     */
    createItemCard(item) {
        // Create Card Container
        const card = document.createElement('div');
        card.className = 'bg-white rounded-lg shadow-md p-6 hover:shadow-lg transition-shadow duration-200 border border-gray-100';
        card.dataset.id = item.id;

        // Header: Title and Status
        const header = document.createElement('div');
        header.className = 'flex justify-between items-start mb-4';

        const title = document.createElement('h3');
        title.className = 'text-lg font-semibold text-gray-800';
        title.textContent = item.title || 'Untitled Item';

        const statusBadge = document.createElement('span');
        const statusColor = this.getStatusColor(item.status);
        statusBadge.className = `px-2 py-1 text-xs font-bold rounded-full uppercase tracking-wide ${statusColor}`;
        statusBadge.textContent = item.status || 'Unknown';

        header.appendChild(title);
        header.appendChild(statusBadge);

        // Body: Description
        const body = document.createElement('div');
        body.className = 'mb-4';
        
        const desc = document.createElement('p');
        desc.className = 'text-gray-600 text-sm line-clamp-2';
        desc.textContent = item.description || 'No description provided.';
        
        body.appendChild(desc);

        // Footer: Metrics/Values
        const footer = document.createElement('div');
        footer.className = 'flex items-center justify-between pt-4 border-t border-gray-100 mt-auto';

        const valueLabel = document.createElement('span');
        valueLabel.className = 'text-xs text-gray-400 uppercase';
        valueLabel.textContent = 'Metric Value';

        const valueData = document.createElement('span');
        valueData.className = 'text-xl font-mono font-bold text-indigo-600';
        valueData.textContent = this.formatValue(item.value);

        footer.appendChild(valueLabel);
        footer.appendChild(valueData);

        // Assemble Card
        card.appendChild(header);
        card.appendChild(body);
        card.appendChild(footer);

        return card;
    }

    /**
     * Helper to determine badge color based on status string.
     * @param {string} status 
     * @returns {string} Tailwind CSS classes
     */
    getStatusColor(status) {
        const s = (status || '').toLowerCase();
        if (s === 'active' || s === 'success' || s === 'healthy') return 'bg-green-100 text-green-800';
        if (s === 'warning' || s === 'pending') return 'bg-yellow-100 text-yellow-800';
        if (s === 'error' || s === 'failed' || s === 'critical') return 'bg-red-100 text-red-800';
        return 'bg-gray-100 text-gray-800';
    }

    /**
     * Helper to format numerical values.
     * @param {number|string} value 
     * @returns {string}
     */
    formatValue(value) {
        if (value === undefined || value === null) return '-';
        if (typeof value === 'number') {
            return value.toLocaleString(undefined, { maximumFractionDigits: 2 });
        }
        return value.toString();
    }
}

// Instantiate and start the application when the DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    window.app = new Application();
    window.app.init();
});
