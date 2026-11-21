/**
 * @file app.js
 * @description Main application controller for the Multi-AI Orchestrator web client.
 * Manages views, session lifecycle, encryption/decryption workflows, and UI event binding.
 */

class App {
  /**
   * Instantiate application controller and initialize core properties.
   */
  constructor() {
    this.currentView = 'token-entry';
    this.memory = null;
    this.apiConfigs = [];
    this.chatEngine = null;
    this.memoryViewer = null;
    this.i18n = new I18n();
    this.sessionStorageKey = 'ai_orchestrator_session';
  }

  /**
   * Initialize application, wire up DOM event listeners, and check for existing session.
   */
  async init() {
    // Apply initial localized strings to UI
    this.i18n.updateAllElements();
    this.updateLanguageButtonText();

    // Bind all user interactions
    this.bindEvents();

    // Check if session is stored in sessionStorage
    const restored = this.restoreSession();
    if (!restored) {
      this.showView('token-entry');
    }
  }

  /**
   * Wire up event listeners for inputs, buttons, and modals.
   */
  bindEvents() {
    // Language toggle
    const langBtn = document.getElementById('btn-lang-toggle');
    if (langBtn) {
      langBtn.addEventListener('click', () => this.toggleLanguage());
    }

    // Decrypt button
    const decryptBtn = document.getElementById('btn-decrypt');
    if (decryptBtn) {
      decryptBtn.addEventListener('click', () => this.handleDecrypt());
    }

    // Enter key triggers decryption on password input
    const passInput = document.getElementById('input-passphrase');
    if (passInput) {
      passInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') {
          e.preventDefault();
          this.handleDecrypt();
        }
      });
    }

    // Launch Demo button
    const demoBtn = document.getElementById('btn-load-demo');
    if (demoBtn) {
      demoBtn.addEventListener('click', () => this.handleLoadDemo());
    }

    // Mobile sidebar toggle button
    const sidebarToggle = document.getElementById('btn-sidebar-toggle');
    const sidebarClose = document.getElementById('btn-sidebar-close');
    const sidebarBackdrop = document.getElementById('sidebar-backdrop');
    const sidebar = document.getElementById('sidebar-panel');

    const toggleSidebar = (open) => {
      if (!sidebar) return;
      if (open) {
        sidebar.classList.add('mobile-open');
        sidebarBackdrop?.classList.add('visible');
      } else {
        sidebar.classList.remove('mobile-open');
        sidebarBackdrop?.classList.remove('visible');
      }
    };

    sidebarToggle?.addEventListener('click', () => toggleSidebar(true));
    sidebarClose?.addEventListener('click', () => toggleSidebar(false));
    sidebarBackdrop?.addEventListener('click', () => toggleSidebar(false));

    // Memory Browser modal trigger and close
    const btnOpenMemory = document.getElementById('btn-open-memory');
    const btnCloseMemory = document.getElementById('btn-close-memory');
    const btnModalClose = document.getElementById('modal-memory-close-x');
    const memoryModal = document.getElementById('modal-memory');

    btnOpenMemory?.addEventListener('click', () => this.openMemoryModal());
    btnCloseMemory?.addEventListener('click', () => this.closeMemoryModal());
    btnModalClose?.addEventListener('click', () => this.closeMemoryModal());

    // Settings modal trigger and close
    const btnOpenSettings = document.getElementById('btn-open-settings');
    const btnCloseSettings = document.getElementById('btn-close-settings');
    const btnModalSettingsClose = document.getElementById('modal-settings-close-x');
    const settingsModal = document.getElementById('modal-settings');

    btnOpenSettings?.addEventListener('click', () => this.openSettingsModal());
    btnCloseSettings?.addEventListener('click', () => this.closeSettingsModal());
    btnModalSettingsClose?.addEventListener('click', () => this.closeSettingsModal());

    // Disconnect / Logout button
    const logoutBtn = document.getElementById('btn-logout');
    logoutBtn?.addEventListener('click', () => this.handleLogout());

    // Chat Message Form & Input
    const chatForm = document.getElementById('chat-input-form');
    const chatInput = document.getElementById('chat-input');
    const sendBtn = document.getElementById('btn-send-message');

    chatForm?.addEventListener('submit', (e) => {
      e.preventDefault();
      this.handleSendMessage();
    });

    chatInput?.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        this.handleSendMessage();
      }
    });

    // Sub-memory selector in sidebar
    const subMemorySelect = document.getElementById('select-sub-memory');
    subMemorySelect?.addEventListener('change', (e) => {
      const val = e.target.value;
      this.memoryViewer?.switchSubMemory(val || null);
    });

    // Listen to custom subMemoryChanged event
    window.addEventListener('subMemoryChanged', (e) => {
      this.onSubMemoryChanged(e.detail.activeSubMemory);
    });

    // Listen to activeModelChanged event
    window.addEventListener('activeModelChanged', (e) => {
      this.onActiveModelChanged(e.detail.activeModel);
    });

    // Clear chat button
    const clearChatBtn = document.getElementById('btn-clear-chat');
    clearChatBtn?.addEventListener('click', () => this.handleClearChat());

    // Token Generator button inside settings
    const btnGenerateToken = document.getElementById('btn-generate-token');
    btnGenerateToken?.addEventListener('click', () => this.handleGenerateCustomToken());

    // Clear stored session button
    const btnClearSession = document.getElementById('btn-clear-session');
    btnClearSession?.addEventListener('click', () => this.handleLogout());

    // Copy memory JSON button in Memory Modal
    const btnExportMemory = document.getElementById('btn-export-memory-json');
    btnExportMemory?.addEventListener('click', () => {
      if (this.memory) {
        navigator.clipboard.writeText(JSON.stringify(this.memory, null, 2)).then(() => {
          btnExportMemory.textContent = this.i18n.t('copied');
          setTimeout(() => {
            btnExportMemory.textContent = this.i18n.t('export_memory');
          }, 2000);
        });
      }
    });
  }

  /**
   * Switch between views with smooth transitions.
   *
   * @param {'token-entry'|'chat'} viewName - Target view.
   */
  showView(viewName) {
    this.currentView = viewName;
    const tokenView = document.getElementById('view-token');
    const chatView = document.getElementById('view-chat');

    if (viewName === 'token-entry') {
      chatView?.classList.remove('active');
      tokenView?.classList.add('active');
    } else if (viewName === 'chat') {
      tokenView?.classList.remove('active');
      chatView?.classList.add('active');
      // Focus chat input on workspace load
      setTimeout(() => {
        document.getElementById('chat-input')?.focus();
      }, 300);
    }
  }

  /**
   * Decrypt sync token and initialize workspace.
   */
  async handleDecrypt() {
    const tokenInput = document.getElementById('input-sync-token');
    const passInput = document.getElementById('input-passphrase');
    const errorEl = document.getElementById('token-error-message');
    const cardEl = document.getElementById('token-card');
    const btnDecrypt = document.getElementById('btn-decrypt');

    const token = tokenInput?.value?.trim();
    const passphrase = passInput?.value;

    // Reset error display
    if (errorEl) {
      errorEl.textContent = '';
      errorEl.classList.remove('visible');
    }
    cardEl?.classList.remove('shake-card');

    if (!token || !passphrase) {
      this.showDecryptError(this.i18n.t('error_empty_fields'));
      return;
    }

    // Set loading state on button
    const originalBtnHtml = btnDecrypt.innerHTML;
    btnDecrypt.disabled = true;
    btnDecrypt.innerHTML = `
      <span class="btn-spinner"></span>
      <span>${this.i18n.t('decrypting')}</span>
    `;

    try {
      // Decrypt using Web Crypto API
      const decrypted = await CryptoEngine.decrypt(token, passphrase);

      if (!decrypted || typeof decrypted !== 'object') {
        throw new Error('Invalid decrypted payload structure.');
      }

      this.memory = decrypted.memory || {};
      this.apiConfigs = decrypted.api_configs || decrypted.apiConfigs || [];

      // Launch Workspace
      this.initializeWorkspace();
      this.showView('chat');

    } catch (err) {
      console.error('Decryption failed:', err);
      this.showDecryptError(`${this.i18n.t('error_decrypt')} (${err.message})`);
    } finally {
      btnDecrypt.disabled = false;
      btnDecrypt.innerHTML = originalBtnHtml;
    }
  }

  /**
   * Display decryption error message and animate card shake.
   *
   * @param {string} message - Error description.
   */
  showDecryptError(message) {
    const errorEl = document.getElementById('token-error-message');
    const cardEl = document.getElementById('token-card');

    if (errorEl) {
      errorEl.textContent = message;
      errorEl.classList.add('visible');
    }

    if (cardEl) {
      cardEl.classList.remove('shake-card');
      // Trigger reflow to restart animation
      void cardEl.offsetWidth;
      cardEl.classList.add('shake-card');
    }
  }

  /**
   * Load rich demo workspace instantly for preview and offline testing.
   */
  async handleLoadDemo() {
    const demoPayload = {
      memory: {
        core: {
          identity: 'Unified Autonomous AI Orchestrator with cross-agent coordination and persistent neural memory context.',
          preferences: [
            'Clean modular architecture',
            'Type safety and JSDoc documentation',
            'Bilingual Turkish & English responsiveness',
            'Glassmorphic dark design language'
          ],
          facts: [
            'Web Crypto API AES-256-GCM browser encryption with PBKDF2 (100k rounds)',
            'Direct provider browser streaming without proxy backend servers',
            'Persistent Core and contextual Sub-Memory injection'
          ]
        },
        sub_memories: [
          {
            id: 'proj_nebula',
            name: 'Project Nebula',
            description: 'Distributed microservice cluster with gRPC telemetry and edge cache',
            content: {
              architecture: 'Event-driven pub/sub on Kafka with Go workers',
              primary_database: 'PostgreSQL 16 with pgvector extension',
              active_nodes: 12,
              deployment_target: 'Kubernetes on bare-metal Frankfurt cluster'
            }
          },
          {
            id: 'sec_audit',
            name: 'Security & Cryptography',
            description: 'Zero-trust architecture and client-side encryption specifications',
            content: {
              encryption: 'AES-256-GCM with 96-bit random nonce per packet',
              kdf: 'PBKDF2-HMAC-SHA256 with 128-bit cryptographically secure salt',
              zero_knowledge: true
            }
          }
        ]
      },
      api_configs: [
        {
          id: 'demo-gpt4o',
          name: 'GPT-4o (Simulated Demo)',
          provider: 'demo',
          model: 'gpt-4o',
          apiKey: '',
          isDemo: true
        },
        {
          id: 'demo-claude',
          name: 'Claude 3.5 Sonnet (Simulated Demo)',
          provider: 'demo',
          model: 'claude-3-5-sonnet-20241022',
          apiKey: '',
          isDemo: true
        },
        {
          id: 'demo-gemini',
          name: 'Gemini 1.5 Pro (Simulated Demo)',
          provider: 'demo',
          model: 'gemini-1.5-pro',
          apiKey: '',
          isDemo: true
        }
      ]
    };

    // Encrypt demo payload into real AES-256-GCM token using "demo123" passphrase
    const demoPassphrase = 'demo123';
    const encryptedToken = await CryptoEngine.encrypt(demoPayload, demoPassphrase);

    // Populate inputs for visual demonstration
    const tokenInput = document.getElementById('input-sync-token');
    const passInput = document.getElementById('input-passphrase');
    if (tokenInput) tokenInput.value = encryptedToken;
    if (passInput) passInput.value = demoPassphrase;

    // Decrypt and proceed
    await this.handleDecrypt();
  }

  /**
   * Restore decrypted workspace session from sessionStorage if present.
   *
   * @returns {boolean} True if session was successfully restored.
   */
  restoreSession() {
    try {
      // Remove sessions written by older versions: they contained plaintext
      // passphrases and decrypted API credentials in browser storage.
      sessionStorage.removeItem(this.sessionStorageKey);
    } catch (e) {
      console.warn('Could not clear the legacy browser session:', e);
    }
    return false;
  }

  /**
   * Initialize memory viewer, chat engine, models list, and context selectors.
   */
  initializeWorkspace() {
    // 1. Initialize Memory Viewer
    this.memoryViewer = new MemoryViewer(this.memory);
    this.memoryViewer.render('memory-tree-container');

    // 2. Initialize Chat Engine
    this.chatEngine = new ChatEngine(this.apiConfigs, this.memory);
    this.chatEngine.setContainer('chat-messages-container');

    // 3. Populate Sub-memory dropdown in sidebar
    this.populateSubMemorySelector();

    // 4. Populate Active Models in sidebar and Chip row above input
    this.populateModelsList();
    this.populateModelChips();

    // 5. Update status badges
    this.updateStatusHeader();
  }

  /**
   * Populate sub-memory dropdown options in the sidebar.
   */
  populateSubMemorySelector() {
    const select = document.getElementById('select-sub-memory');
    if (!select) return;

    select.innerHTML = '';

    // Default: None / Core only
    const defaultOption = document.createElement('option');
    defaultOption.value = '';
    defaultOption.textContent = this.i18n.t('no_sub_memory');
    select.appendChild(defaultOption);

    const subList = this.memoryViewer.getSubMemoryList();
    subList.forEach(sub => {
      const opt = document.createElement('option');
      opt.value = sub.id;
      opt.textContent = sub.name;
      if (this.memoryViewer.activeSubMemoryId === sub.id) {
        opt.selected = true;
      }
      select.appendChild(opt);
    });
  }

  /**
   * Populate active models in the sidebar with live pulsing status indicators.
   */
  populateModelsList() {
    const container = document.getElementById('sidebar-models-list');
    if (!container) return;

    container.innerHTML = '';
    const models = this.chatEngine.providers;

    if (models.length === 0) {
      container.innerHTML = `<li class="no-models-msg">${this.escapeHtml(this.i18n.t('no_models'))}</li>`;
      return;
    }

    models.forEach(model => {
      const li = document.createElement('li');
      li.className = `model-list-item ${this.chatEngine.activeModel?.id === model.id ? 'active-model-item' : ''}`;
      li.setAttribute('data-model-id', model.id);
      li.onclick = () => {
        this.chatEngine.setActiveModel(model);
      };

      li.innerHTML = `
        <div class="model-item-info">
          <div class="model-pulse-indicator">
            <span class="pulsing-dot"></span>
          </div>
          <div class="model-meta">
            <span class="model-name">${this.escapeHtml(model.name)}</span>
            <span class="model-type-badge">${this.escapeHtml(model.provider.toUpperCase())}</span>
          </div>
        </div>
        <span class="model-active-check">${this.chatEngine.activeModel?.id === model.id ? '●' : ''}</span>
      `;

      container.appendChild(li);
    });
  }

  /**
   * Populate quick-switch model chips above the bottom chat input bar.
   */
  populateModelChips() {
    const container = document.getElementById('chat-model-chips');
    if (!container) return;

    container.innerHTML = '';
    const models = this.chatEngine.providers;

    models.forEach(model => {
      const chip = document.createElement('button');
      chip.type = 'button';
      chip.className = `model-chip ${this.chatEngine.activeModel?.id === model.id ? 'chip-active' : ''}`;
      chip.setAttribute('data-model-id', model.id);
      chip.onclick = () => {
        this.chatEngine.setActiveModel(model);
      };

      chip.innerHTML = `
        <span class="chip-dot"></span>
        <span class="chip-label">${this.escapeHtml(model.name)}</span>
      `;

      container.appendChild(chip);
    });
  }

  /**
   * Update active model indicators when selection changes.
   *
   * @param {Object} activeModel - Currently selected model.
   */
  onActiveModelChanged(activeModel) {
    if (!activeModel) return;

    // Update sidebar items
    document.querySelectorAll('.model-list-item').forEach(item => {
      const id = item.getAttribute('data-model-id');
      const isCurrent = id === activeModel.id;
      item.classList.toggle('active-model-item', isCurrent);
      const checkEl = item.querySelector('.model-active-check');
      if (checkEl) checkEl.textContent = isCurrent ? '●' : '';
    });

    // Update chips
    document.querySelectorAll('.model-chip').forEach(chip => {
      const id = chip.getAttribute('data-model-id');
      chip.classList.toggle('chip-active', id === activeModel.id);
    });

    // Update header badge
    const headerModelName = document.getElementById('header-active-model-name');
    if (headerModelName) {
      headerModelName.textContent = activeModel.name;
    }
  }

  /**
   * Update UI when active sub-memory changes.
   *
   * @param {Object|null} activeSub - Active sub-memory or null.
   */
  onSubMemoryChanged(activeSub) {
    // Update select element in sidebar
    const select = document.getElementById('select-sub-memory');
    if (select) {
      select.value = activeSub ? activeSub.id : '';
    }

    // Update context pill in chat header
    const pill = document.getElementById('header-submemory-pill');
    if (pill) {
      if (activeSub) {
        pill.textContent = `📂 ${activeSub.name}`;
        pill.classList.remove('hidden');
      } else {
        pill.classList.add('hidden');
      }
    }
  }

  /**
   * Update chat workspace header status badges.
   */
  updateStatusHeader() {
    const headerModelName = document.getElementById('header-active-model-name');
    if (headerModelName && this.chatEngine?.activeModel) {
      headerModelName.textContent = this.chatEngine.activeModel.name;
    }

    const pill = document.getElementById('header-submemory-pill');
    const activeSub = this.memoryViewer?.getActiveSubMemory();
    if (pill) {
      if (activeSub) {
        pill.textContent = `📂 ${activeSub.name}`;
        pill.classList.remove('hidden');
      } else {
        pill.classList.add('hidden');
      }
    }
  }

  /**
   * Send current message in chat input.
   */
  async handleSendMessage() {
    const input = document.getElementById('chat-input');
    const sendBtn = document.getElementById('btn-send-message');
    if (!input || !this.chatEngine) return;

    if (this.chatEngine.isGenerating) {
      this.chatEngine.stopGeneration();
      return;
    }

    const text = input.value.trim();
    if (!text) return;

    input.value = '';
    input.style.height = 'auto';

    // Switch send button to stop icon/text
    if (sendBtn) {
      sendBtn.classList.add('btn-stopping');
      sendBtn.innerHTML = `
        <span class="btn-stop-icon">■</span>
        <span class="btn-text">${this.i18n.t('stop_button')}</span>
      `;
    }

    try {
      await this.chatEngine.sendMessage(text);
    } finally {
      if (sendBtn) {
        sendBtn.classList.remove('btn-stopping');
        sendBtn.innerHTML = `
          <span class="btn-send-icon">▲</span>
          <span class="btn-text">${this.i18n.t('send_button')}</span>
        `;
      }
    }
  }

  /**
   * Clear all messages in current chat stream.
   */
  handleClearChat() {
    if (!this.chatEngine) return;
    this.chatEngine.messages = [];
    const container = document.getElementById('chat-messages-container');
    if (container) {
      container.innerHTML = `
        <div class="chat-welcome-card" id="chat-welcome">
          <div class="welcome-glow-orb"></div>
          <div class="welcome-icon">✦</div>
          <h2 class="welcome-title" data-i18n="chat_welcome_title">${this.escapeHtml(this.i18n.t('chat_welcome_title'))}</h2>
          <p class="welcome-desc" data-i18n="chat_welcome_desc">${this.escapeHtml(this.i18n.t('chat_welcome_desc'))}</p>
        </div>
      `;
    }
  }

  /**
   * Open Memory Browser modal.
   */
  openMemoryModal() {
    const modal = document.getElementById('modal-memory');
    if (modal && this.memoryViewer) {
      this.memoryViewer.render('memory-tree-container');
      modal.classList.add('modal-open');
    }
  }

  /**
   * Close Memory Browser modal.
   */
  closeMemoryModal() {
    const modal = document.getElementById('modal-memory');
    modal?.classList.remove('modal-open');
  }

  /**
   * Open Settings modal.
   */
  openSettingsModal() {
    const modal = document.getElementById('modal-settings');
    modal?.classList.add('modal-open');
  }

  /**
   * Close Settings modal.
   */
  closeSettingsModal() {
    const modal = document.getElementById('modal-settings');
    modal?.classList.remove('modal-open');
  }

  /**
   * Generate custom encrypted token from Settings modal inputs.
   */
  async handleGenerateCustomToken() {
    const memArea = document.getElementById('gen-input-memory');
    const cfgArea = document.getElementById('gen-input-configs');
    const passInput = document.getElementById('gen-input-passphrase');
    const resultArea = document.getElementById('gen-output-token');

    try {
      const memObj = memArea?.value ? JSON.parse(memArea.value) : (this.memory || {});
      const cfgObj = cfgArea?.value ? JSON.parse(cfgArea.value) : (this.apiConfigs || []);
      const pass = passInput?.value;
      if (!pass || pass.length < 8) {
        throw new Error(this.i18n.t('error_passphrase_min_length'));
      }

      const payload = {
        memory: memObj,
        api_configs: cfgObj
      };

      const encrypted = await CryptoEngine.encrypt(payload, pass);
      if (resultArea) {
        resultArea.value = encrypted;
        resultArea.classList.remove('hidden');
      }

      await navigator.clipboard.writeText(encrypted);
      alert(this.i18n.t('token_generated_success'));
    } catch (err) {
      alert(`Token generation failed: ${err.message}`);
    }
  }

  /**
   * Disconnect and clear session state.
   */
  handleLogout() {
    sessionStorage.removeItem(this.sessionStorageKey);
    this.memory = null;
    this.apiConfigs = [];
    this.chatEngine = null;
    this.memoryViewer = null;

    // Clear inputs
    const tokenInput = document.getElementById('input-sync-token');
    const passInput = document.getElementById('input-passphrase');
    if (tokenInput) tokenInput.value = '';
    if (passInput) passInput.value = '';

    // Close modals
    this.closeMemoryModal();
    this.closeSettingsModal();

    this.showView('token-entry');
  }

  /**
   * Toggle application language between TR and EN.
   */
  toggleLanguage() {
    this.i18n.toggleLanguage();
    this.updateLanguageButtonText();
    // Re-render memory tree if initialized
    if (this.memoryViewer) {
      this.memoryViewer.render('memory-tree-container');
    }
    // Re-render models
    if (this.chatEngine) {
      this.populateModelsList();
      this.populateModelChips();
      this.populateSubMemorySelector();
      this.updateStatusHeader();
    }
  }

  /**
   * Update the language toggle button label.
   */
  updateLanguageButtonText() {
    const btn = document.getElementById('btn-lang-toggle');
    if (btn) {
      btn.textContent = this.i18n.t('language_toggle');
    }
  }

  /**
   * Escape HTML entities.
   *
   * @param {string} str - Raw string.
   * @returns {string} Escaped string.
   */
  escapeHtml(str) {
    if (str === null || str === undefined) return '';
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
  }
}

// Global initialization upon DOM ready
window.addEventListener('DOMContentLoaded', () => {
  window.app = new App();
  window.app.init();
});
