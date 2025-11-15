/**
 * ESAB Recommender V2 - Frontend Configuration
 * Automatic environment detection with manual override support
 *
 * ⚙️ CONFIGURATION GUIDE:
 *
 * For most deployments, this file auto-detects the environment and configures
 * URLs automatically. Manual configuration is only needed for special cases.
 *
 * See CONFIG.md for detailed deployment instructions, especially for Azure.
 */

(function (global) {
    'use strict';

    // ========================================================================
    // 🔧 MANUAL CONFIGURATION (Edit these if auto-detection fails)
    // ========================================================================

    /**
     * Manual Override Configuration
     * Set these ONLY if auto-detection doesn't work for your deployment.
     * Leave as null to use auto-detection.
     */
    const MANUAL_CONFIG = {
        // Override API base URL (e.g., "https://your-domain.com" or "http://10.0.1.5:8000")
        API_BASE: null,

        // Override frontend base URL (usually same as API_BASE for static serving)
        FRONTEND_BASE: null,

        // Override environment detection ('development', 'staging', 'production')
        ENVIRONMENT: null,

        // Enable debug logging (true/false, or null for auto)
        DEBUG: null
    };

    /**
     * Environment-specific defaults
     * Used when auto-detection succeeds but you want custom defaults per environment
     */
    const ENVIRONMENT_DEFAULTS = {
        development: {
            API_BASE: 'http://localhost:8000',
            FRONTEND_BASE: 'http://localhost:8000',
            DEBUG: true
        },
        staging: {
            // Staging defaults - customize as needed
            API_BASE: null,  // Will use current origin
            FRONTEND_BASE: null,  // Will use current origin
            DEBUG: true
        },
        production: {
            // Production defaults - customize as needed
            API_BASE: null,  // Will use current origin
            FRONTEND_BASE: null,  // Will use current origin
            DEBUG: false
        }
    };

    // ========================================================================
    // 🤖 AUTOMATIC ENVIRONMENT DETECTION
    // ========================================================================

    /**
     * Detect environment based on hostname
     * @returns {'development'|'staging'|'production'}
     */
    function detectEnvironment() {
        if (MANUAL_CONFIG.ENVIRONMENT) {
            return MANUAL_CONFIG.ENVIRONMENT;
        }

        const hostname = global.location.hostname.toLowerCase();

        // Development indicators
        if (hostname === 'localhost' ||
            hostname === '127.0.0.1' ||
            hostname.startsWith('192.168.') ||
            hostname.startsWith('10.') ||
            hostname.startsWith('172.16.') ||
            hostname.endsWith('.local')) {
            return 'development';
        }

        // Staging indicators
        if (hostname.includes('staging') ||
            hostname.includes('stage') ||
            hostname.includes('dev.') ||
            hostname.includes('test.')) {
            return 'staging';
        }

        // Default to production
        return 'production';
    }

    /**
     * Sanitize and normalize base URL
     * @param {string} value - URL to sanitize
     * @returns {string|null}
     */
    function sanitizeBase(value) {
        if (!value) {
            return null;
        }
        try {
            const url = new URL(value, global.location.origin);
            return url.toString().replace(/\/+$/, '');
        } catch (_err) {
            return value.replace(/\/+$/, '');
        }
    }

    /**
     * Get current page origin
     * @returns {string}
     */
    function getDefaultOrigin() {
        const origin = global.location.origin;
        if (origin && origin !== 'null' && !origin.startsWith('file:')) {
            return origin.replace(/\/+$/, '');
        }
        return 'http://localhost:8000';
    }

    /**
     * Ensure path has leading slash
     * @param {string} path
     * @returns {string}
     */
    function ensureLeadingSlash(path) {
        if (!path) {
            return '';
        }
        return path.startsWith('/') ? path : `/${path}`;
    }

    // ========================================================================
    // 🔍 CONFIGURATION RESOLUTION
    // ========================================================================

    // Detect environment
    const environment = detectEnvironment();
    const envDefaults = ENVIRONMENT_DEFAULTS[environment] || ENVIRONMENT_DEFAULTS.development;

    // Check for URL parameters (highest priority)
    const params = new URLSearchParams(global.location.search || '');
    const urlApiBase = params.get('apiBase');
    const urlFrontendBase = params.get('frontendBase');

    // Resolve API_BASE (priority: URL param > Manual > Environment defaults > Auto-detect)
    const apiBase = sanitizeBase(urlApiBase) ||
                    sanitizeBase(MANUAL_CONFIG.API_BASE) ||
                    sanitizeBase(envDefaults.API_BASE) ||
                    getDefaultOrigin();

    // Resolve FRONTEND_BASE
    const frontendBase = sanitizeBase(urlFrontendBase) ||
                        sanitizeBase(MANUAL_CONFIG.FRONTEND_BASE) ||
                        sanitizeBase(envDefaults.FRONTEND_BASE) ||
                        getDefaultOrigin();

    // Resolve DEBUG flag
    const debugMode = MANUAL_CONFIG.DEBUG !== null
        ? MANUAL_CONFIG.DEBUG
        : (envDefaults.DEBUG !== undefined ? envDefaults.DEBUG : environment !== 'production');

    // ========================================================================
    // 📦 EXPORTED CONFIGURATION
    // ========================================================================

    const config = {
        // Base URLs
        API_BASE: apiBase,
        FRONTEND_BASE: frontendBase,

        // Environment info
        ENVIRONMENT: environment,
        DEBUG: debugMode,

        // Helper function to build API endpoint URLs
        apiEndpoint(path = '') {
            const trimmed = ensureLeadingSlash(path);
            if (!trimmed) {
                return `${apiBase}/api/v1/configurator`;
            }
            return `${apiBase}/api/v1/configurator${trimmed}`;
        },

        // Get full configuration as object (for debugging)
        getConfig() {
            return {
                API_BASE: this.API_BASE,
                FRONTEND_BASE: this.FRONTEND_BASE,
                ENVIRONMENT: this.ENVIRONMENT,
                DEBUG: this.DEBUG,
                MANUAL_OVERRIDES: MANUAL_CONFIG,
                DETECTED_HOSTNAME: global.location.hostname,
                CURRENT_URL: global.location.href
            };
        }
    };

    // Freeze and export configuration
    Object.defineProperty(global, 'APP_CONFIG', {
        value: Object.freeze(config),
        configurable: false,
        enumerable: false,
        writable: false,
    });

    // Debug logging
    if (config.DEBUG) {
        console.log('🔧 ESAB Configuration Loaded:');
        console.log('  Environment:', config.ENVIRONMENT);
        console.log('  API Base:', config.API_BASE);
        console.log('  Frontend Base:', config.FRONTEND_BASE);
        console.log('  Debug Mode:', config.DEBUG);
        console.log('  Hostname:', global.location.hostname);
        console.log('  Full config:', config.getConfig());
    }

})(window);
