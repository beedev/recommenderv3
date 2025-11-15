/**
 * ESAB Recommender V2 - Internationalization (i18n)
 * Multi-language support for the configurator interface
 *
 * Supported languages: English, Spanish, French, German, Portuguese, Italian, Swedish
 * Exports: window.ESAB.Translations
 */

(function(global) {
    'use strict';

    // Translation dictionary for all supported languages
    const translations = {
        en: {
            pageTitle: '🔧 Recommender V2 - S1→S7 Configurator',
            pageSubtitle: 'State-by-State Welding Equipment Configuration System',
            connectedStatus: 'Connected to API',
            currentStateLabel: 'Current State',
            cartHeader: '🛒 Selected Products',
            cartEmpty: 'No products selected yet',
            totalComponents: 'Total Components:',
            finalizeBtn: 'Finalize Configuration',
            inputPlaceholder: 'Type your message... (e.g., "I need 500A MIG welding")',
            sendBtn: 'Send',
            welcomeMessage: 'Welcome! I\'ll help you configure your welding equipment step-by-step (S1→S7). Let\'s start with selecting a Power Source. What are your welding requirements?',
            languageChanged: 'Language changed to',
            newMessagesIn: 'New messages will be in this language.'
        },
        es: {
            pageTitle: '🔧 Recomendador V2 - Configurador S1→S7',
            pageSubtitle: 'Sistema de Configuración de Equipos de Soldadura Paso a Paso',
            connectedStatus: 'Conectado a la API',
            currentStateLabel: 'Estado Actual',
            cartHeader: '🛒 Productos Seleccionados',
            cartEmpty: 'Aún no se han seleccionado productos',
            totalComponents: 'Total de Componentes:',
            finalizeBtn: 'Finalizar Configuración',
            inputPlaceholder: 'Escriba su mensaje... (por ejemplo, "Necesito soldadura MIG de 500A")',
            sendBtn: 'Enviar',
            welcomeMessage: '¡Bienvenido! Te ayudaré a configurar tu equipo de soldadura paso a paso (S1→S7). Comencemos seleccionando una Fuente de Alimentación. ¿Cuáles son tus requisitos de soldadura?',
            languageChanged: 'Idioma cambiado a',
            newMessagesIn: 'Los nuevos mensajes estarán en este idioma.'
        },
        fr: {
            pageTitle: '🔧 Recommandeur V2 - Configurateur S1→S7',
            pageSubtitle: 'Système de Configuration d\'Équipement de Soudage Étape par Étape',
            connectedStatus: 'Connecté à l\'API',
            currentStateLabel: 'État Actuel',
            cartHeader: '🛒 Produits Sélectionnés',
            cartEmpty: 'Aucun produit sélectionné pour le moment',
            totalComponents: 'Total des Composants:',
            finalizeBtn: 'Finaliser la Configuration',
            inputPlaceholder: 'Tapez votre message... (par exemple, "J\'ai besoin de soudage MIG 500A")',
            sendBtn: 'Envoyer',
            welcomeMessage: 'Bienvenue! Je vous aiderai à configurer votre équipement de soudage étape par étape (S1→S7). Commençons par sélectionner une Source d\'Alimentation. Quelles sont vos exigences de soudage?',
            languageChanged: 'Langue changée en',
            newMessagesIn: 'Les nouveaux messages seront dans cette langue.'
        },
        de: {
            pageTitle: '🔧 Empfehler V2 - S1→S7 Konfigurator',
            pageSubtitle: 'Schritt-für-Schritt Schweißgeräte-Konfigurationssystem',
            connectedStatus: 'Mit API verbunden',
            currentStateLabel: 'Aktueller Status',
            cartHeader: '🛒 Ausgewählte Produkte',
            cartEmpty: 'Noch keine Produkte ausgewählt',
            totalComponents: 'Gesamtkomponenten:',
            finalizeBtn: 'Konfiguration Abschließen',
            inputPlaceholder: 'Geben Sie Ihre Nachricht ein... (z.B. "Ich benötige 500A MIG-Schweißen")',
            sendBtn: 'Senden',
            welcomeMessage: 'Willkommen! Ich helfe Ihnen, Ihre Schweißausrüstung Schritt für Schritt zu konfigurieren (S1→S7). Beginnen wir mit der Auswahl einer Stromquelle. Was sind Ihre Schweißanforderungen?',
            languageChanged: 'Sprache geändert auf',
            newMessagesIn: 'Neue Nachrichten werden in dieser Sprache sein.'
        },
        pt: {
            pageTitle: '🔧 Recomendador V2 - Configurador S1→S7',
            pageSubtitle: 'Sistema de Configuração de Equipamento de Soldagem Passo a Passo',
            connectedStatus: 'Conectado à API',
            currentStateLabel: 'Estado Atual',
            cartHeader: '🛒 Produtos Selecionados',
            cartEmpty: 'Nenhum produto selecionado ainda',
            totalComponents: 'Total de Componentes:',
            finalizeBtn: 'Finalizar Configuração',
            inputPlaceholder: 'Digite sua mensagem... (por exemplo, "Preciso de soldagem MIG de 500A")',
            sendBtn: 'Enviar',
            welcomeMessage: 'Bem-vindo! Vou ajudá-lo a configurar seu equipamento de soldagem passo a passo (S1→S7). Vamos começar selecionando uma Fonte de Alimentação. Quais são seus requisitos de soldagem?',
            languageChanged: 'Idioma alterado para',
            newMessagesIn: 'Novas mensagens estarão neste idioma.'
        },
        it: {
            pageTitle: '🔧 Raccomandatore V2 - Configuratore S1→S7',
            pageSubtitle: 'Sistema di Configurazione Attrezzatura di Saldatura Passo dopo Passo',
            connectedStatus: 'Connesso all\'API',
            currentStateLabel: 'Stato Attuale',
            cartHeader: '🛒 Prodotti Selezionati',
            cartEmpty: 'Nessun prodotto selezionato ancora',
            totalComponents: 'Componenti Totali:',
            finalizeBtn: 'Finalizza Configurazione',
            inputPlaceholder: 'Digita il tuo messaggio... (ad es. "Ho bisogno di saldatura MIG da 500A")',
            sendBtn: 'Invia',
            welcomeMessage: 'Benvenuto! Ti aiuterò a configurare la tua attrezzatura di saldatura passo dopo passo (S1→S7). Iniziamo selezionando una Fonte di Alimentazione. Quali sono i tuoi requisiti di saldatura?',
            languageChanged: 'Lingua cambiata in',
            newMessagesIn: 'I nuovi messaggi saranno in questa lingua.'
        },
        sv: {
            pageTitle: '🔧 Rekommenderare V2 - S1→S7 Konfigurator',
            pageSubtitle: 'Steg-för-Steg Svetsningsutrustning Konfigurationssystem',
            connectedStatus: 'Ansluten till API',
            currentStateLabel: 'Aktuellt Tillstånd',
            cartHeader: '🛒 Valda Produkter',
            cartEmpty: 'Inga produkter valda ännu',
            totalComponents: 'Totalt Komponenter:',
            finalizeBtn: 'Slutför Konfiguration',
            inputPlaceholder: 'Skriv ditt meddelande... (t.ex. "Jag behöver 500A MIG-svetsning")',
            sendBtn: 'Skicka',
            welcomeMessage: 'Välkommen! Jag hjälper dig att konfigurera din svetsutrustning steg för steg (S1→S7). Låt oss börja med att välja en strömkälla. Vilka är dina svetskrav?',
            languageChanged: 'Språk ändrat till',
            newMessagesIn: 'Nya meddelanden kommer att vara på detta språk.'
        }
    };

    // Language names for display
    const languageNames = {
        'en': 'English',
        'es': 'Español',
        'fr': 'Français',
        'de': 'Deutsch',
        'pt': 'Português',
        'it': 'Italiano',
        'sv': 'Svenska'
    };

    // Translation Manager
    const Translations = {
        /**
         * Get translations for a specific language
         * @param {string} lang - Language code (en, es, fr, de, pt, it, sv)
         * @returns {Object} Translation object
         */
        get: function(lang) {
            return translations[lang] || translations.en;
        },

        /**
         * Get all supported languages
         * @returns {Array<string>} Array of language codes
         */
        getSupportedLanguages: function() {
            return Object.keys(translations);
        },

        /**
         * Get language display name
         * @param {string} lang - Language code
         * @returns {string} Display name
         */
        getLanguageName: function(lang) {
            return languageNames[lang] || lang.toUpperCase();
        },

        /**
         * Check if language is supported
         * @param {string} lang - Language code
         * @returns {boolean}
         */
        isSupported: function(lang) {
            return lang in translations;
        },

        /**
         * Update UI language for index.html (full configurator)
         * @param {string} lang - Language code
         */
        updateUILanguage: function(lang) {
            if (!this.isSupported(lang)) {
                console.warn(`Language ${lang} not supported, falling back to English`);
                lang = 'en';
            }

            const t = translations[lang];

            // Update page title and subtitle
            const titleEl = document.querySelector('.header h1');
            const subtitleEl = document.querySelector('.header p');
            if (titleEl) titleEl.textContent = t.pageTitle;
            if (subtitleEl) subtitleEl.textContent = t.pageSubtitle;

            // Update status bar
            const statusEl = document.querySelector('.status-indicator span');
            if (statusEl) statusEl.textContent = t.connectedStatus;

            // Update cart header
            const cartHeaderEl = document.querySelector('.cart-header');
            if (cartHeaderEl) cartHeaderEl.textContent = t.cartHeader;

            // Update cart empty message if visible
            const cartEmptyDiv = document.querySelector('.cart-empty');
            if (cartEmptyDiv) {
                cartEmptyDiv.textContent = t.cartEmpty;
            }

            // Update cart summary labels
            const totalLabel = document.querySelector('.cart-summary-item span');
            if (totalLabel) {
                totalLabel.textContent = t.totalComponents;
            }

            // Update finalize button
            const finalizeBtn = document.getElementById('finalizeBtn');
            if (finalizeBtn) {
                finalizeBtn.textContent = t.finalizeBtn;
            }

            // Update input placeholder
            const inputEl = document.getElementById('userInput');
            if (inputEl) {
                inputEl.placeholder = t.inputPlaceholder;
            }

            // Update send button
            const sendBtn = document.getElementById('sendBtn');
            if (sendBtn) {
                sendBtn.textContent = t.sendBtn;
            }

            // Update welcome message (replace first message in chat)
            const firstMessage = document.querySelector('.chat-container .message.assistant .message-content p');
            if (firstMessage) {
                firstMessage.innerHTML = t.welcomeMessage;
            }

            console.log(`✅ UI language updated to: ${this.getLanguageName(lang)}`);
        },

        /**
         * Handle language change from dropdown
         * @param {string} selectElementId - ID of select element
         * @param {Function} addMessageCallback - Optional callback to add message to chat
         * @returns {string} New language code
         */
        changeLanguage: function(selectElementId = 'languageSelect', addMessageCallback = null) {
            const select = document.getElementById(selectElementId);
            if (!select) {
                console.error(`Language select element #${selectElementId} not found`);
                return 'en';
            }

            const newLang = select.value;

            // Save to session storage
            sessionStorage.setItem('preferredLanguage', newLang);

            // Update all UI text
            this.updateUILanguage(newLang);

            // Show language change notification if callback provided
            if (addMessageCallback && typeof addMessageCallback === 'function') {
                const t = translations[newLang];
                addMessageCallback(
                    `🌍 ${t.languageChanged} ${languageNames[newLang]}. ${t.newMessagesIn}`,
                    false
                );
            }

            console.log('Language changed to:', newLang);
            return newLang;
        },

        /**
         * Initialize language from session storage or default
         * @param {string} selectElementId - ID of select element
         * @param {string} defaultLang - Default language code
         * @returns {string} Initialized language code
         */
        initLanguage: function(selectElementId = 'languageSelect', defaultLang = 'en') {
            const savedLang = sessionStorage.getItem('preferredLanguage') || defaultLang;

            const select = document.getElementById(selectElementId);
            if (select) {
                select.value = savedLang;
            }

            this.updateUILanguage(savedLang);

            console.log('Initialized language:', savedLang);
            return savedLang;
        }
    };

    // Export to global ESAB namespace
    if (!global.ESAB) {
        global.ESAB = {};
    }
    global.ESAB.Translations = Translations;

    // Log initialization
    console.log('✅ ESAB Translations loaded');
    console.log('Supported languages:', Object.keys(translations).join(', '));

})(window);
