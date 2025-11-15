/**
 * ESAB Recommender V2 - Common JavaScript Utilities
 * Shared functionality across all HTML interfaces
 *
 * Exports: window.ESAB object with modules:
 * - Config: Configuration access
 * - UserManager: User ID management
 * - SessionManager: Session lifecycle
 * - APIHelpers: API request utilities
 * - UIHelpers: UI utilities (markdown, loading, etc.)
 * - CartManager: Shopping cart functionality
 */

(function(global) {
    'use strict';

    // ===== CONFIGURATION ACCESS =====
    const Config = {
        get API_BASE() {
            return global.APP_CONFIG ? global.APP_CONFIG.API_BASE : 'http://localhost:8000';
        },
        get apiEndpoint() {
            return global.APP_CONFIG ? global.APP_CONFIG.apiEndpoint : (path) => `${this.API_BASE}/api/v1/configurator${path}`;
        },
        get FRONTEND_BASE() {
            return global.APP_CONFIG ? global.APP_CONFIG.FRONTEND_BASE : global.location.origin;
        },
        get ENVIRONMENT() {
            return global.APP_CONFIG ? global.APP_CONFIG.ENVIRONMENT : 'development';
        },
        get DEBUG() {
            return global.APP_CONFIG ? global.APP_CONFIG.DEBUG : true;
        }
    };

    // ===== USER MANAGEMENT =====
    const UserManager = {
        /**
         * Get or create user ID from localStorage
         * @returns {string} User ID
         */
        getUserId: function() {
            let userId = localStorage.getItem('esab_user_id');
            if (!userId) {
                userId = prompt('Enter your user ID (or leave empty for auto-generated):') ||
                         `user-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
                localStorage.setItem('esab_user_id', userId);
                console.log('Created new user ID:', userId);
            } else {
                console.log('Retrieved user ID from localStorage:', userId);
            }
            return userId;
        },

        /**
         * Update user badge display in UI
         * @param {string} userId - User ID to display
         * @param {string} elementId - DOM element ID (default: 'userBadge')
         */
        updateUserDisplay: function(userId, elementId = 'userBadge') {
            const userBadge = document.getElementById(elementId);
            if (userBadge && userId) {
                const displayId = userId.length > 20
                    ? userId.substring(0, 17) + '...'
                    : userId;
                userBadge.textContent = displayId;
                userBadge.title = userId; // Full ID in tooltip
            }
        },

        /**
         * Clear user ID and reload page
         */
        switchUser: function() {
            if (confirm('Are you sure you want to switch users? This will clear your current user ID.')) {
                localStorage.removeItem('esab_user_id');
                location.reload();
            }
        },

        /**
         * Get current user ID (if exists) without prompting
         * @returns {string|null}
         */
        getCurrentUserId: function() {
            return localStorage.getItem('esab_user_id');
        },

        /**
         * Set user ID explicitly
         * @param {string} userId
         */
        setUserId: function(userId) {
            localStorage.setItem('esab_user_id', userId);
            console.log('Set user ID:', userId);
        }
    };

    // ===== SESSION MANAGEMENT =====
    const SessionManager = {
        /**
         * Start a new session (clears session ID but keeps user ID)
         * @param {Object} callbacks - Optional callbacks
         * @param {Function} callbacks.onReset - Called when session resets
         * @param {Function} callbacks.onMessage - Called to add message to UI
         */
        startNewSession: function(callbacks = {}) {
            const msg = 'Start a new configuration session? Your current session will remain available in Redis.';
            if (confirm(msg)) {
                if (callbacks.onReset) {
                    callbacks.onReset();
                }
                if (callbacks.onMessage) {
                    callbacks.onMessage('🆕 Started new session', false);
                }
                return true;
            }
            return false;
        },

        /**
         * Initialize or resume session for a user
         * @param {string} userId - User ID
         * @param {Function} apiEndpoint - API endpoint function
         * @param {Object} callbacks - Callbacks for success/error
         * @param {Function} callbacks.onSuccess - Called with session data
         * @param {Function} callbacks.onError - Called with error
         * @param {string} callbacks.language - Language code (default: 'en')
         * @returns {Promise<Object>} Session data
         */
        initSession: async function(userId, apiEndpoint, callbacks = {}) {
            console.log('Initializing session for user:', userId);

            try {
                const response = await fetch(apiEndpoint('/message'), {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        user_id: userId,
                        message: 'resume',
                        language: callbacks.language || 'en'
                    })
                });

                if (!response.ok) {
                    throw new Error(`HTTP ${response.status}: ${response.statusText}`);
                }

                const data = await response.json();
                console.log('Session initialized:', data.session_id);
                console.log('Session data:', data);

                if (callbacks.onSuccess) {
                    callbacks.onSuccess(data);
                }

                return data;
            } catch (error) {
                console.error('Failed to initialize session:', error);
                if (callbacks.onError) {
                    callbacks.onError(error);
                }
                throw error;
            }
        }
    };

    // ===== API HELPERS =====
    const APIHelpers = {
        /**
         * Make an API request with standardized error handling
         * @param {string} endpoint - Full endpoint URL
         * @param {string} method - HTTP method
         * @param {Object} body - Request body
         * @returns {Promise<Object>} Response data
         */
        makeRequest: async function(endpoint, method, body) {
            try {
                const response = await fetch(endpoint, {
                    method: method,
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(body)
                });

                if (!response.ok) {
                    const errorText = await response.text();
                    throw new Error(`HTTP ${response.status}: ${errorText}`);
                }

                return await response.json();
            } catch (error) {
                console.error('API request failed:', error);
                throw error;
            }
        },

        /**
         * Send message to configurator
         * @param {string} sessionId - Session ID (null for new session)
         * @param {string} userId - User ID
         * @param {string} message - User message
         * @param {string} language - Language code
         * @param {Function} apiEndpoint - API endpoint function
         * @returns {Promise<Object>} Response data
         */
        sendMessage: async function(sessionId, userId, message, language, apiEndpoint) {
            return await this.makeRequest(apiEndpoint('/message'), 'POST', {
                session_id: sessionId,
                user_id: userId,
                message: message,
                language: language
            });
        },

        /**
         * Select a product
         * @param {string} sessionId - Session ID
         * @param {string} userId - User ID
         * @param {string} productGin - Product GIN
         * @param {Object} productData - Product data object
         * @param {Function} apiEndpoint - API endpoint function
         * @returns {Promise<Object>} Response data
         */
        selectProduct: async function(sessionId, userId, productGin, productData, apiEndpoint) {
            return await this.makeRequest(apiEndpoint('/select'), 'POST', {
                session_id: sessionId,
                user_id: userId,
                product_gin: productGin,
                product_data: productData
            });
        }
    };

    // ===== UI HELPERS =====
    const UIHelpers = {
        /**
         * Format text with markdown-like syntax to HTML
         * @param {string} text - Input text
         * @returns {string} HTML formatted text
         */
        formatMarkdown: function(text) {
            let formatted = text;

            // Code blocks (```language\ncode\n```)
            formatted = formatted.replace(/```(\w+)?\n([\s\S]*?)```/g, (match, lang, code) => {
                return `<pre style="background: #f4f4f4; padding: 12px; border-radius: 6px; overflow-x: auto; margin: 10px 0;"><code>${this.escapeHtml(code.trim())}</code></pre>`;
            });

            // Inline code (`code`)
            formatted = formatted.replace(/`([^`]+)`/g, '<code style="background: #f4f4f4; padding: 2px 6px; border-radius: 3px; font-family: monospace;">$1</code>');

            // Bullet lists (lines starting with • or -)
            formatted = formatted.replace(/^[•\-]\s+(.+)$/gm, '<li>$1</li>');
            formatted = formatted.replace(/(<li>.*<\/li>\n?)+/g, '<ul style="margin: 10px 0; padding-left: 20px;">$&</ul>');

            // Bold (**text**)
            formatted = formatted.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');

            // Italic (*text*)
            formatted = formatted.replace(/\*(.+?)\*/g, '<em>$1</em>');

            // Line breaks
            formatted = formatted.replace(/\n/g, '<br>');

            return formatted;
        },

        /**
         * Escape HTML special characters
         * @param {string} text
         * @returns {string}
         */
        escapeHtml: function(text) {
            const div = document.createElement('div');
            div.textContent = text;
            return div.innerHTML;
        },

        /**
         * Create loading spinner HTML
         * @returns {string}
         */
        createLoadingSpinner: function() {
            return '<div class="loading"></div>';
        },

        /**
         * Set button to loading state
         * @param {string|HTMLElement} button - Button element or ID
         * @param {boolean} isLoading - Loading state
         * @param {string} originalText - Text to restore when not loading
         */
        setButtonLoading: function(button, isLoading, originalText = 'Send') {
            const btn = typeof button === 'string' ? document.getElementById(button) : button;
            if (!btn) return;

            btn.disabled = isLoading;
            if (isLoading) {
                btn.innerHTML = this.createLoadingSpinner();
            } else {
                btn.textContent = originalText;
            }
        },

        /**
         * Scroll element to bottom
         * @param {string|HTMLElement} element - Element or ID
         */
        scrollToBottom: function(element) {
            const el = typeof element === 'string' ? document.getElementById(element) : element;
            if (el) {
                el.scrollTop = el.scrollHeight;
            }
        },

        /**
         * Add message to chat container (generic version)
         * @param {HTMLElement} container - Chat container element
         * @param {string} text - Message text
         * @param {boolean} isUser - Is user message
         * @param {Array} products - Optional products array
         * @returns {HTMLElement} Created message element
         */
        addMessageToChat: function(container, text, isUser, products = null) {
            const messageDiv = document.createElement('div');
            messageDiv.className = `message ${isUser ? 'user' : 'assistant'}`;

            let content = `
                <div class="message-avatar">${isUser ? '👤' : '🤖'}</div>
                <div class="message-content">
                    <p>${this.formatMarkdown(text)}</p>
            `;

            if (products && products.length > 0) {
                content += `
                    <div class="products-grid">
                        ${products.map(p => `
                            <div class="product-card" data-gin="${p.gin}">
                                <h4>${this.escapeHtml(p.name)}</h4>
                                <p><strong>GIN:</strong> ${this.escapeHtml(p.gin)}</p>
                                <p><strong>Category:</strong> ${this.escapeHtml(p.category)}</p>
                            </div>
                        `).join('')}
                    </div>
                `;
            }

            content += '</div>';
            messageDiv.innerHTML = content;
            container.appendChild(messageDiv);
            this.scrollToBottom(container);

            return messageDiv;
        }
    };

    // ===== CART MANAGER =====
    const CartManager = {
        /**
         * Update cart display with response JSON
         * @param {Object} responseJson - Response JSON from API
         * @param {string} cartContentId - Cart content element ID
         * @param {string} summaryId - Summary element ID
         * @param {string} totalComponentsId - Total components element ID
         * @param {string} finalizeBtnId - Finalize button ID
         */
        updateCart: function(responseJson, cartContentId = 'cartContent', summaryId = 'cartSummary', totalComponentsId = 'totalComponents', finalizeBtnId = 'finalizeBtn') {
            const cartContent = document.getElementById(cartContentId);
            const cartSummary = document.getElementById(summaryId);
            const totalComponents = document.getElementById(totalComponentsId);
            const finalizeBtn = document.getElementById(finalizeBtnId);

            if (!cartContent) return;

            const cartHTML = this.generateCartHTML(responseJson);
            const count = this.getComponentCount(responseJson);

            if (count === 0) {
                cartContent.innerHTML = '<div class="cart-empty">No products selected yet</div>';
                if (cartSummary) cartSummary.style.display = 'none';
            } else {
                cartContent.innerHTML = cartHTML;
                if (cartSummary) cartSummary.style.display = 'block';
                if (totalComponents) totalComponents.textContent = count;

                // Enable finalize button if we have at least PowerSource
                if (finalizeBtn) {
                    finalizeBtn.disabled = !responseJson.PowerSource;
                }
            }
        },

        /**
         * Generate cart HTML from response JSON
         * @param {Object} responseJson
         * @returns {string} HTML string
         */
        generateCartHTML: function(responseJson) {
            let html = '';
            const componentOrder = ['PowerSource', 'Feeder', 'Cooler', 'Interconnector', 'Torch', 'Accessories'];

            for (const key of componentOrder) {
                const item = responseJson[key];

                if (key === 'Accessories' && Array.isArray(item) && item.length > 0) {
                    html += `<div class="cart-item">
                        <h4>🔧 Accessories (${item.length})</h4>
                        ${item.map(acc => `
                            <p><strong>${UIHelpers.escapeHtml(acc.name)}</strong></p>
                            <p style="font-size: 12px;">GIN: ${UIHelpers.escapeHtml(acc.gin)}</p>
                        `).join('')}
                    </div>`;
                } else if (item && typeof item === 'object' && item.name) {
                    const icon = this.getComponentIcon(key);
                    html += `<div class="cart-item">
                        <h4>${icon} ${key}</h4>
                        <p><strong>${UIHelpers.escapeHtml(item.name)}</strong></p>
                        <p>GIN: ${UIHelpers.escapeHtml(item.gin)}</p>
                    </div>`;
                }
            }

            return html || '<div class="cart-empty">No products selected yet</div>';
        },

        /**
         * Get component count from response JSON
         * @param {Object} responseJson
         * @returns {number}
         */
        getComponentCount: function(responseJson) {
            let count = 0;
            const components = ['PowerSource', 'Feeder', 'Cooler', 'Interconnector', 'Torch'];

            for (const key of components) {
                if (responseJson[key] && responseJson[key].name) {
                    count++;
                }
            }

            if (Array.isArray(responseJson.Accessories)) {
                count += responseJson.Accessories.length;
            }

            return count;
        },

        /**
         * Get icon for component type
         * @param {string} componentKey
         * @returns {string}
         */
        getComponentIcon: function(componentKey) {
            const icons = {
                'PowerSource': '⚡',
                'Feeder': '🔄',
                'Cooler': '❄️',
                'Interconnector': '🔌',
                'Torch': '🔥',
                'Accessories': '🔧'
            };
            return icons[componentKey] || '📦';
        }
    };

    // ===== EXPORT TO GLOBAL =====
    global.ESAB = global.ESAB || {};
    Object.assign(global.ESAB, {
        Config,
        UserManager,
        SessionManager,
        APIHelpers,
        UIHelpers,
        CartManager,

        // Version info
        version: '2.0.0',

        // Utility to check if loaded
        isLoaded: function() {
            return true;
        }
    });

    // Log initialization
    if (Config.DEBUG) {
        console.log('✅ ESAB Common Utilities loaded (v2.0.0)');
        console.log('Available modules:', Object.keys(global.ESAB).filter(k => typeof global.ESAB[k] === 'object'));
    }

})(window);
