/**
 * @file memory.js
 * @description Persistent Memory Viewer for Core Memory and contextual Sub-Memories.
 * Handles rendering the interactive memory tree, sub-memory switching, and context injection.
 */

class MemoryViewer {
  /**
   * Initialize MemoryViewer with decrypted memory payload.
   * @param {Object} memoryData - Decrypted memory structure.
   */
  constructor(memoryData = {}) {
    this.raw = memoryData || {};
    this.core = this.normalizeCore(this.raw);
    this.subMemories = this.normalizeSubMemories(this.raw);
    this.activeSubMemoryId = null;
  }

  /**
   * Normalize core memory attributes (identity, preferences, facts).
   *
   * @param {Object} raw - Raw memory payload.
   * @returns {{identity: any, preferences: any, facts: Array}}
   */
  normalizeCore(raw) {
    const src = raw.core || raw;
    return {
      identity: src.identity || 'Autonomous Multi-AI Orchestrator with cross-agent coordination and unified persistent memory.',
      preferences: src.preferences || ['Production-ready code', 'Async-first architecture', 'Bilingual Turkish & English support', 'Strict type safety'],
      facts: Array.isArray(src.facts) ? src.facts : (src.facts ? [src.facts] : ['Encrypted AES-256-GCM browser storage', 'Zero backend dependency', 'Real-time multi-provider model routing'])
    };
  }

  /**
   * Normalize sub-memories into a standardized list of objects.
   *
   * @param {Object} raw - Raw memory payload.
   * @returns {Array<{id: string, name: string, description: string, content: any}>}
   */
  normalizeSubMemories(raw) {
    const list = raw.sub_memories || raw.subMemories || raw.submemories || [];
    if (Array.isArray(list)) {
      return list.map((item, index) => ({
        id: item.id || `sub_${index + 1}`,
        name: item.name || item.title || `Sub-Memory ${index + 1}`,
        description: item.description || 'Contextual project knowledge base',
        content: item.content || item.data || item
      }));
    } else if (typeof list === 'object' && list !== null) {
      return Object.entries(list).map(([key, val], index) => ({
        id: key,
        name: (val && (val.name || val.title)) || key,
        description: (val && val.description) || 'Contextual domain memory',
        content: val && val.content ? val.content : val
      }));
    }
    return [];
  }

  /**
   * Get list of sub-memories for dropdowns and selectors.
   *
   * @returns {Array<{id: string, name: string, description: string}>}
   */
  getSubMemoryList() {
    return this.subMemories.map(item => ({
      id: item.id,
      name: item.name,
      description: item.description
    }));
  }

  /**
   * Switch the active sub-memory for chat context.
   *
   * @param {string|null} subMemoryId - ID of sub-memory to activate, or null for core only.
   */
  switchSubMemory(subMemoryId) {
    this.activeSubMemoryId = subMemoryId || null;
    window.dispatchEvent(
      new CustomEvent('subMemoryChanged', {
        detail: {
          activeSubMemoryId: this.activeSubMemoryId,
          activeSubMemory: this.getActiveSubMemory()
        }
      })
    );
  }

  /**
   * Retrieve active sub-memory object.
   *
   * @returns {Object|null}
   */
  getActiveSubMemory() {
    if (!this.activeSubMemoryId) return null;
    return this.subMemories.find(item => item.id === this.activeSubMemoryId) || null;
  }

  /**
   * Render the interactive memory tree into a DOM container.
   *
   * @param {string} [containerId='memory-tree-container'] - Container element ID.
   */
  render(containerId = 'memory-tree-container') {
    const container = document.getElementById(containerId);
    if (!container) return;

    const i18n = window.app?.i18n || { t: (k) => k };

    let html = `
      <div class="memory-tree">
        <!-- Core Memory Branch -->
        <div class="memory-section core-memory-branch">
          <div class="memory-section-header" onclick="this.parentElement.classList.toggle('collapsed')">
            <div class="section-title-wrap">
              <span class="tree-toggle-icon">▼</span>
              <span class="section-icon">🧠</span>
              <h3 class="section-title">${this.escapeHtml(i18n.t('core_memory'))}</h3>
            </div>
            <span class="section-badge core-badge">L1 Core</span>
          </div>
          
          <div class="memory-section-content">
            <!-- Identity Node -->
            <div class="memory-node">
              <div class="node-header">
                <span class="node-icon">👤</span>
                <span class="node-title">${this.escapeHtml(i18n.t('identity'))}</span>
              </div>
              <div class="node-body">
                <div class="identity-card">
                  ${this.formatContent(this.core.identity)}
                </div>
              </div>
            </div>

            <!-- Preferences Node -->
            <div class="memory-node">
              <div class="node-header">
                <span class="node-icon">⚙️</span>
                <span class="node-title">${this.escapeHtml(i18n.t('preferences'))}</span>
              </div>
              <div class="node-body">
                <div class="preferences-grid">
                  ${this.renderPreferences(this.core.preferences)}
                </div>
              </div>
            </div>

            <!-- Facts Node -->
            <div class="memory-node">
              <div class="node-header">
                <span class="node-icon">📌</span>
                <span class="node-title">${this.escapeHtml(i18n.t('facts'))}</span>
              </div>
              <div class="node-body">
                <ul class="facts-list">
                  ${this.renderFacts(this.core.facts)}
                </ul>
              </div>
            </div>
          </div>
        </div>

        <!-- Sub-Memories Branch -->
        <div class="memory-section sub-memories-branch">
          <div class="memory-section-header" onclick="this.parentElement.classList.toggle('collapsed')">
            <div class="section-title-wrap">
              <span class="tree-toggle-icon">▼</span>
              <span class="section-icon">📂</span>
              <h3 class="section-title">${this.escapeHtml(i18n.t('sub_memories'))}</h3>
            </div>
            <span class="section-badge sub-badge">${this.subMemories.length} scopes</span>
          </div>

          <div class="memory-section-content">
            ${this.renderSubMemoriesList(i18n)}
          </div>
        </div>
      </div>
    `;

    container.innerHTML = html;
    container.querySelectorAll('[data-action="switch-sub-memory"]').forEach(button => {
      button.addEventListener('click', event => {
        event.stopPropagation();
        const subMemoryId = button.dataset.subMemoryId;
        if (subMemoryId && window.app?.memoryViewer) {
          window.app.memoryViewer.switchSubMemory(subMemoryId);
          window.app.memoryViewer.render();
        }
      });
    });
  }

  /**
   * Render user preferences as chips or formatted key-value pairs.
   *
   * @param {any} prefs - Preferences data.
   * @returns {string} HTML string.
   */
  renderPreferences(prefs) {
    if (Array.isArray(prefs)) {
      return prefs
        .map(
          item => `<span class="pref-pill"><span class="pref-dot"></span>${this.escapeHtml(String(item))}</span>`
        )
        .join('');
    } else if (typeof prefs === 'object' && prefs !== null) {
      return Object.entries(prefs)
        .map(
          ([k, v]) => `
          <div class="pref-kv-item">
            <span class="pref-key">${this.escapeHtml(k)}:</span>
            <span class="pref-val">${this.escapeHtml(typeof v === 'object' ? JSON.stringify(v) : String(v))}</span>
          </div>`
        )
        .join('');
    }
    return `<div class="pref-text">${this.escapeHtml(String(prefs))}</div>`;
  }

  /**
   * Render persistent facts as a clean bulleted list.
   *
   * @param {Array|any} facts - Facts data.
   * @returns {string} HTML string.
   */
  renderFacts(facts) {
    if (!Array.isArray(facts)) {
      facts = [facts];
    }
    return facts
      .map(
        fact => `
        <li class="fact-item">
          <span class="fact-icon">✦</span>
          <span class="fact-text">${this.escapeHtml(typeof fact === 'object' ? JSON.stringify(fact) : String(fact))}</span>
        </li>`
      )
      .join('');
  }

  /**
   * Render the list of sub-memories with collapsible details and context selection.
   *
   * @param {Object} i18n - Translation provider.
   * @returns {string} HTML string.
   */
  renderSubMemoriesList(i18n) {
    if (this.subMemories.length === 0) {
      return `<div class="empty-state-notice">${this.escapeHtml(i18n.t('empty_memory'))}</div>`;
    }

    return this.subMemories
      .map(sub => {
        const isActive = this.activeSubMemoryId === sub.id;
        const activeClass = isActive ? 'sub-card-active' : '';
        const badgeText = isActive ? i18n.t('active_badge') : i18n.t('set_active');

        return `
        <div class="sub-memory-card ${activeClass}" data-sub-memory-id="${this.escapeHtml(String(sub.id))}">
          <div class="sub-card-header" onclick="this.parentElement.classList.toggle('open')">
            <div class="sub-card-title-group">
              <span class="sub-folder-icon">📁</span>
              <div>
                <h4 class="sub-card-name">${this.escapeHtml(sub.name)}</h4>
                <p class="sub-card-desc">${this.escapeHtml(sub.description)}</p>
              </div>
            </div>
            <div class="sub-card-actions" onclick="event.stopPropagation()">
              <button
                class="btn-context-toggle ${isActive ? 'btn-active-context' : ''}" 
                type="button"
                data-action="switch-sub-memory"
                data-sub-memory-id="${this.escapeHtml(String(sub.id))}"
                title="${this.escapeHtml(badgeText)}"
              >
                ${isActive ? '✓ ' : ''}${this.escapeHtml(badgeText)}
              </button>
            </div>
          </div>
          <div class="sub-card-body">
            <div class="sub-card-content-view">
              ${this.formatContent(sub.content)}
            </div>
          </div>
        </div>
      `;
      })
      .join('');
  }

  /**
   * Format arbitrary content (string or JSON) for safe and clean rendering.
   *
   * @param {any} content - Content to format.
   * @returns {string} HTML string.
   */
  formatContent(content) {
    if (typeof content === 'string') {
      return `<p class="formatted-text">${this.escapeHtml(content).replace(/\n/g, '<br>')}</p>`;
    }
    const jsonStr = JSON.stringify(content, null, 2);
    return `<pre class="json-code-block"><code>${this.escapeHtml(jsonStr)}</code></pre>`;
  }

  /**
   * Escape HTML special characters to prevent XSS.
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

// Global registration
if (typeof window !== 'undefined') {
  window.MemoryViewer = MemoryViewer;
}
if (typeof module !== 'undefined' && module.exports) {
  module.exports = { MemoryViewer };
}
