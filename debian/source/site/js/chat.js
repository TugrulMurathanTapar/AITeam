/**
 * @file chat.js
 * @description Real-time chat engine connecting directly to AI providers from the browser.
 * Supports OpenAI-compatible endpoints, Anthropic Claude, Google Gemini, and Simulated Demo providers.
 */

class ChatEngine {
  /**
   * Initialize ChatEngine with decrypted API configs and memory state.
   *
   * @param {Array<Object>} apiConfigs - Decrypted AI provider configurations.
   * @param {Object} memory - Decrypted persistent memory structure.
   */
  constructor(apiConfigs = [], memory = {}) {
    this.providers = this.normalizeProviders(apiConfigs);
    this.memory = memory;
    this.messages = [];
    this.activeModel = this.providers.length > 0 ? this.providers[0] : null;
    this.isGenerating = false;
    this.abortController = null;
    this.container = null;
  }

  /**
   * Normalize API configurations into a standard format.
   *
   * @param {Array<Object>|Object} configs - Decrypted API configurations.
   * @returns {Array<Object>} List of validated provider objects.
   */
  normalizeProviders(configs) {
    let list = [];
    if (Array.isArray(configs)) {
      list = configs;
    } else if (configs && typeof configs === 'object') {
      list = Object.values(configs);
    }

    return list.map((item, idx) => {
      const providerType = (item.provider || item.type || 'openai').toLowerCase();
      const name = item.name || item.model || `Model ${idx + 1}`;
      const model = item.model || item.model_id || 'default';
      const apiKey = item.api_key || item.apiKey || item.key || '';
      let baseUrl = item.base_url || item.baseUrl || item.endpoint || '';

      if (!baseUrl) {
        if (providerType.includes('anthropic') || providerType.includes('claude')) {
          baseUrl = 'https://api.anthropic.com/v1';
        } else if (providerType.includes('google') || providerType.includes('gemini')) {
          baseUrl = 'https://generativelanguage.googleapis.com/v1beta';
        } else if (providerType.includes('groq')) {
          baseUrl = 'https://api.groq.com/openai/v1';
        } else if (providerType.includes('openrouter')) {
          baseUrl = 'https://openrouter.ai/api/v1';
        } else {
          baseUrl = 'https://api.openai.com/v1';
        }
      }

      return {
        id: item.id || `model_${idx + 1}`,
        name: name,
        provider: providerType,
        model: model,
        apiKey: apiKey,
        baseUrl: baseUrl.replace(/\/+$/, ''),
        maxTokens: item.max_tokens || item.maxTokens || 4096,
        temperature: item.temperature !== undefined ? item.temperature : 0.7,
        isDemo: Boolean(item.isDemo || providerType === 'mock' || providerType === 'demo')
      };
    });
  }

  /**
   * Select which API model to use for subsequent interactions.
   *
   * @param {string|Object} modelOrId - Model ID or model configuration object.
   */
  setActiveModel(modelOrId) {
    if (typeof modelOrId === 'string') {
      const found = this.providers.find(p => p.id === modelOrId || p.name === modelOrId);
      if (found) this.activeModel = found;
    } else if (modelOrId && typeof modelOrId === 'object') {
      this.activeModel = modelOrId;
    }

    window.dispatchEvent(
      new CustomEvent('activeModelChanged', {
        detail: { activeModel: this.activeModel }
      })
    );
  }

  /**
   * Set target DOM container for message stream rendering.
   *
   * @param {HTMLElement|string} container - Element or selector.
   */
  setContainer(container) {
    this.container = typeof container === 'string' ? document.querySelector(container) : container;
  }

  /**
   * Build comprehensive system prompt with Core Memory and active Sub-Memory context.
   *
   * @returns {string} System prompt.
   */
  buildSystemPrompt() {
    const memoryViewer = window.app?.memoryViewer;
    const core = memoryViewer ? memoryViewer.core : (this.memory.core || {});
    const activeSub = memoryViewer ? memoryViewer.getActiveSubMemory() : null;

    let parts = [];
    parts.push('=== MULTI-AI ORCHESTRATOR SYSTEM INSTRUCTIONS ===');
    parts.push('You are an intelligent agent operating within the Cross-Platform Multi-AI Orchestrator.');
    
    // Core Identity
    if (core.identity) {
      const identityStr = typeof core.identity === 'object' ? JSON.stringify(core.identity) : String(core.identity);
      parts.push(`\n[CORE IDENTITY & DIRECTIVE]\n${identityStr}`);
    }

    // Preferences
    if (core.preferences && (!Array.isArray(core.preferences) || core.preferences.length > 0)) {
      const prefsStr = Array.isArray(core.preferences) 
        ? core.preferences.map(p => `- ${p}`).join('\n')
        : (typeof core.preferences === 'object' ? JSON.stringify(core.preferences, null, 2) : String(core.preferences));
      parts.push(`\n[USER PREFERENCES & STYLES]\n${prefsStr}`);
    }

    // Persistent Facts
    if (core.facts && (!Array.isArray(core.facts) || core.facts.length > 0)) {
      const factsStr = Array.isArray(core.facts) 
        ? core.facts.map(f => `- ${typeof f === 'object' ? JSON.stringify(f) : f}`).join('\n')
        : (typeof core.facts === 'object' ? JSON.stringify(core.facts, null, 2) : String(core.facts));
      parts.push(`\n[PERSISTENT KNOWLEDGE GRAPH]\n${factsStr}`);
    }

    // Active Sub-Memory
    if (activeSub) {
      const subContent = typeof activeSub.content === 'object' 
        ? JSON.stringify(activeSub.content, null, 2) 
        : String(activeSub.content);
      parts.push(`\n[ACTIVE SUB-MEMORY CONTEXT: ${activeSub.name}]\nDescription: ${activeSub.description}\nContent:\n${subContent}`);
    }

    parts.push('\n[OPERATIONAL GUIDANCE]\nAlways adhere to the user preferences and persistent facts. Respond accurately, cleanly, and format code snippets in markdown.');

    return parts.join('\n');
  }

  /**
   * Send a user message and orchestrate the AI response.
   *
   * @param {string} userText - User prompt.
   * @returns {Promise<string>} AI response text.
   */
  async sendMessage(userText) {
    if (!userText || !userText.trim()) return '';
    if (!this.activeModel) {
      const errorMsg = window.app?.i18n?.t('error_no_model') || 'No active model selected.';
      this.renderNotification(errorMsg, 'error');
      return '';
    }
    if (this.isGenerating) {
      return '';
    }

    const trimmedText = userText.trim();
    this.isGenerating = true;
    this.abortController = new AbortController();

    // 1. Render and record user message
    const userMessageObj = {
      id: `msg_${Date.now()}`,
      role: 'user',
      content: trimmedText,
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    };
    this.messages.push(userMessageObj);
    this.renderMessage('user', trimmedText, null, userMessageObj.timestamp, userMessageObj.id);

    // 2. Show typing indicator
    this.showTypingIndicator();

    // 3. Prepare AI message bubble placeholder
    const aiMessageId = `msg_${Date.now() + 1}`;
    const aiTimestamp = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    let aiBubbleEl = null;
    let fullResponseText = '';

    try {
      const systemPrompt = this.buildSystemPrompt();

      // Dispatch to specific provider handler
      if (this.activeModel.isDemo || this.activeModel.provider === 'mock' || !this.activeModel.apiKey) {
        fullResponseText = await this.handleDemoStream(trimmedText, systemPrompt, (chunk) => {
          if (!aiBubbleEl) {
            this.hideTypingIndicator();
            aiBubbleEl = this.renderMessage(
              'assistant',
              '',
              this.activeModel.name,
              aiTimestamp,
              aiMessageId
            );
          }
          this.updateMessageContent(aiBubbleEl, chunk);
        });
      } else if (this.activeModel.provider.includes('anthropic') || this.activeModel.provider.includes('claude')) {
        fullResponseText = await this.callAnthropicStream(trimmedText, systemPrompt, (chunk) => {
          if (!aiBubbleEl) {
            this.hideTypingIndicator();
            aiBubbleEl = this.renderMessage(
              'assistant',
              '',
              this.activeModel.name,
              aiTimestamp,
              aiMessageId
            );
          }
          this.updateMessageContent(aiBubbleEl, chunk);
        });
      } else if (this.activeModel.provider.includes('google') || this.activeModel.provider.includes('gemini')) {
        fullResponseText = await this.callGeminiStream(trimmedText, systemPrompt, (chunk) => {
          if (!aiBubbleEl) {
            this.hideTypingIndicator();
            aiBubbleEl = this.renderMessage(
              'assistant',
              '',
              this.activeModel.name,
              aiTimestamp,
              aiMessageId
            );
          }
          this.updateMessageContent(aiBubbleEl, chunk);
        });
      } else {
        // Default OpenAI-compatible stream (OpenAI, Groq, OpenRouter, Mistral, Ollama, etc.)
        fullResponseText = await this.callOpenAIStream(trimmedText, systemPrompt, (chunk) => {
          if (!aiBubbleEl) {
            this.hideTypingIndicator();
            aiBubbleEl = this.renderMessage(
              'assistant',
              '',
              this.activeModel.name,
              aiTimestamp,
              aiMessageId
            );
          }
          this.updateMessageContent(aiBubbleEl, chunk);
        });
      }

      // Record AI response in history
      this.messages.push({
        id: aiMessageId,
        role: 'assistant',
        content: fullResponseText,
        model: this.activeModel.name,
        timestamp: aiTimestamp
      });

    } catch (err) {
      this.hideTypingIndicator();
      if (err.name === 'AbortError') {
        if (aiBubbleEl) {
          this.updateMessageContent(aiBubbleEl, fullResponseText + ' *(Generation stopped by user)*');
        }
      } else {
        console.error('ChatEngine Error:', err);
        const errHeader = window.app?.i18n?.t('error_api') || 'API request failed';
        this.renderNotification(`${errHeader}: ${err.message}`, 'error');
        if (!aiBubbleEl) {
          this.renderMessage(
            'assistant',
            `⚠️ **${errHeader}**\n\n\`${err.message}\`\n\n*Check network connectivity, API key validity, or CORS headers on the provider.*`,
            this.activeModel ? this.activeModel.name : 'System',
            aiTimestamp,
            aiMessageId
          );
        }
      }
    } finally {
      this.hideTypingIndicator();
      this.isGenerating = false;
      this.abortController = null;
      window.dispatchEvent(new CustomEvent('generationStateChanged', { detail: { isGenerating: false } }));
    }

    return fullResponseText;
  }

  /**
   * Abort the active generation stream.
   */
  stopGeneration() {
    if (this.abortController) {
      this.abortController.abort();
    }
  }

  /**
   * OpenAI-compatible streaming API caller.
   *
   * @param {string} userText - User prompt.
   * @param {string} systemPrompt - Injected system context.
   * @param {Function} onChunk - Callback for incremental text.
   * @returns {Promise<string>} Accumulated response text.
   */
  async callOpenAIStream(userText, systemPrompt, onChunk) {
    const url = `${this.activeModel.baseUrl}/chat/completions`;
    const headers = {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${this.activeModel.apiKey}`
    };

    // Build message array with recent history (last 10 turns)
    const historyPayload = this.messages
      .filter(m => m.role === 'user' || m.role === 'assistant')
      .slice(-10)
      .map(m => ({ role: m.role, content: m.content }));

    const body = {
      model: this.activeModel.model,
      messages: [
        { role: 'system', content: systemPrompt },
        ...historyPayload
      ],
      stream: true,
      temperature: this.activeModel.temperature,
      max_tokens: this.activeModel.maxTokens
    };

    const response = await fetch(url, {
      method: 'POST',
      headers: headers,
      body: JSON.stringify(body),
      signal: this.abortController.signal
    });

    if (!response.ok) {
      const errorText = await response.text();
      let parsedMsg = response.statusText;
      try {
        const json = JSON.parse(errorText);
        parsedMsg = json.error?.message || json.message || errorText;
      } catch (e) {
        parsedMsg = errorText || response.statusText;
      }
      throw new Error(`[${response.status}] ${parsedMsg}`);
    }

    return await this.streamResponse(response, onChunk, (data) => {
      return data.choices?.[0]?.delta?.content || '';
    });
  }

  /**
   * Anthropic Claude streaming API caller.
   *
   * @param {string} userText - User prompt.
   * @param {string} systemPrompt - Injected system context.
   * @param {Function} onChunk - Callback for incremental text.
   * @returns {Promise<string>} Accumulated response text.
   */
  async callAnthropicStream(userText, systemPrompt, onChunk) {
    const url = `${this.activeModel.baseUrl}/messages`;
    const headers = {
      'Content-Type': 'application/json',
      'x-api-key': this.activeModel.apiKey,
      'anthropic-version': '2023-06-01',
      'anthropic-dangerous-direct-browser-access': 'true'
    };

    const historyPayload = this.messages
      .filter(m => m.role === 'user' || m.role === 'assistant')
      .slice(-10)
      .map(m => ({ role: m.role, content: m.content }));

    const body = {
      model: this.activeModel.model,
      system: systemPrompt,
      messages: historyPayload,
      max_tokens: this.activeModel.maxTokens,
      stream: true,
      temperature: this.activeModel.temperature
    };

    const response = await fetch(url, {
      method: 'POST',
      headers: headers,
      body: JSON.stringify(body),
      signal: this.abortController.signal
    });

    if (!response.ok) {
      const errorText = await response.text();
      let parsedMsg = response.statusText;
      try {
        const json = JSON.parse(errorText);
        parsedMsg = json.error?.message || errorText;
      } catch (e) {
        parsedMsg = errorText;
      }
      throw new Error(`[${response.status}] ${parsedMsg}`);
    }

    return await this.streamResponse(response, onChunk, (data) => {
      if (data.type === 'content_block_delta' && data.delta?.type === 'text_delta') {
        return data.delta.text || '';
      }
      return '';
    });
  }

  /**
   * Google Gemini streaming API caller.
   *
   * @param {string} userText - User prompt.
   * @param {string} systemPrompt - Injected system context.
   * @param {Function} onChunk - Callback for incremental text.
   * @returns {Promise<string>} Accumulated response text.
   */
  async callGeminiStream(userText, systemPrompt, onChunk) {
    const url = `${this.activeModel.baseUrl}/models/${this.activeModel.model}:streamGenerateContent?alt=sse&key=${this.activeModel.apiKey}`;
    
    // Convert history to Gemini format
    const contents = [];
    contents.push({
      role: 'user',
      parts: [{ text: `[System Context]\n${systemPrompt}` }]
    });
    contents.push({
      role: 'model',
      parts: [{ text: 'Understood. I have absorbed the persistent memory, directives, and active sub-context.' }]
    });

    this.messages
      .filter(m => m.role === 'user' || m.role === 'assistant')
      .slice(-10)
      .forEach(m => {
        contents.push({
          role: m.role === 'assistant' ? 'model' : 'user',
          parts: [{ text: m.content }]
        });
      });

    const body = { contents: contents };

    const response = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
      signal: this.abortController.signal
    });

    if (!response.ok) {
      const errorText = await response.text();
      throw new Error(`[${response.status}] ${errorText}`);
    }

    return await this.streamResponse(response, onChunk, (data) => {
      const candidate = data.candidates?.[0];
      return candidate?.content?.parts?.[0]?.text || '';
    });
  }

  /**
   * Parse SSE stream from fetch response, extract tokens and invoke callback.
   *
   * @param {Response} response - Fetch response.
   * @param {Function} onChunk - Callback for each new chunk.
   * @param {Function} tokenExtractor - Function to extract text token from JSON payload.
   * @returns {Promise<string>} Full assembled text.
   */
  async streamResponse(response, onChunk, tokenExtractor) {
    const reader = response.body.getReader();
    const decoder = new TextDecoder('utf-8');
    let accumulatedText = '';
    let buffer = '';

    try {
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        // Keep the last partial line in buffer
        buffer = lines.pop() || '';

        for (const line of lines) {
          const trimmed = line.trim();
          if (!trimmed || trimmed.startsWith(':')) continue;

          if (trimmed.startsWith('data:')) {
            const dataStr = trimmed.slice(5).trim();
            if (dataStr === '[DONE]') {
              break;
            }

            try {
              const parsed = JSON.parse(dataStr);
              const token = tokenExtractor(parsed);
              if (token) {
                accumulatedText += token;
                onChunk(accumulatedText);
              }
            } catch (err) {
              // Ignore non-json keep-alive or trailing characters
            }
          }
        }
      }
    } finally {
      reader.releaseLock();
    }

    return accumulatedText;
  }

  /**
   * Simulated streaming provider for preview and offline testing.
   *
   * @param {string} userText - User prompt.
   * @param {string} systemPrompt - Injected system context.
   * @param {Function} onChunk - Callback for streaming chunks.
   * @returns {Promise<string>} Simulated response.
   */
  async handleDemoStream(userText, systemPrompt, onChunk) {
    const memoryViewer = window.app?.memoryViewer;
    const activeSub = memoryViewer ? memoryViewer.getActiveSubMemory() : null;
    const isTurkish = window.app?.i18n?.lang === 'tr';

    // Rich contextual response demonstrating orchestrator features
    const subContextNotice = activeSub 
      ? (isTurkish ? `\n> **Aktif Ara Hafıza**: \`${activeSub.name}\` (${activeSub.description})\n` : `\n> **Active Sub-Memory**: \`${activeSub.name}\` (${activeSub.description})\n`)
      : '';

    let template = '';
    if (isTurkish) {
      template = `Merhaba! Ben **Multi-AI Orchestrator** sisteminin birleşik ajanıyım.

Şifrelenmiş hafıza kasanız ve model yapılandırmalarınız başarıyla doğrulandı.

${subContextNotice}
Sorgunuz:
> *"${userText}"*

İşte orkestrasyon motorunun aktif çalışma parametreleri:

\`\`\`json
{
  "status": "synchronized",
  "active_model": "${this.activeModel ? this.activeModel.name : 'Demo Model'}",
  "sub_memory": "${activeSub ? activeSub.name : 'Core Only'}",
  "crypto_cipher": "AES-256-GCM",
  "key_derivation": "PBKDF2-SHA256 (100,000 iterations)",
  "latency_ms": 24
}
\`\`\`

İstediğiniz zaman sol menüden farklı bir **Ara Hafıza** seçebilir veya **Hafıza Tarayıcısı** ile kalıcı nöral grafiği inceleyebilirsiniz. Size nasıl yardımcı olabilirim?`;
    } else {
      template = `Greetings! I am the unified agent of the **Multi-AI Orchestrator**.

Your encrypted memory vault and model configurations have been successfully decrypted and synchronized in-browser.

${subContextNotice}
Your query:
> *"${userText}"*

Here are the active orchestration engine parameters:

\`\`\`json
{
  "status": "synchronized",
  "active_model": "${this.activeModel ? this.activeModel.name : 'Demo Model'}",
  "sub_memory": "${activeSub ? activeSub.name : 'Core Only'}",
  "crypto_cipher": "AES-256-GCM",
  "key_derivation": "PBKDF2-SHA256 (100,000 iterations)",
  "latency_ms": 24
}
\`\`\`

You can switch between sub-memories in the left sidebar or launch the **Memory Browser** to explore the persistent neural memory graph anytime. How can I assist you further?`;
    }

    // Simulate realistic typing stream
    let accumulated = '';
    const words = template.split(' ');

    for (let i = 0; i < words.length; i++) {
      if (this.abortController?.signal?.aborted) {
        throw new DOMException('Aborted', 'AbortError');
      }

      accumulated += (i === 0 ? '' : ' ') + words[i];
      onChunk(accumulated);
      // Random delay between 15ms and 45ms per word
      await new Promise(r => setTimeout(r, Math.floor(Math.random() * 30) + 15));
    }

    return accumulated;
  }

  /**
   * Render a message bubble into the chat DOM container.
   *
   * @param {'user'|'assistant'|'system'} role - Role of the message.
   * @param {string} content - Markdown or plain text message content.
   * @param {string} [modelName] - Name of generating model for assistant messages.
   * @param {string} [timestamp] - Formatted timestamp.
   * @param {string} [messageId] - Unique message ID.
   * @returns {HTMLElement} Created message element.
   */
  renderMessage(role, content, modelName, timestamp, messageId) {
    if (!this.container) {
      this.container = document.getElementById('chat-messages-container');
    }
    if (!this.container) return null;

    const timeStr = timestamp || new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    const msgId = messageId || `msg_${Date.now()}`;

    const wrapper = document.createElement('div');
    wrapper.className = `chat-message-wrapper message-${role}`;
    wrapper.id = msgId;

    if (role === 'user') {
      wrapper.innerHTML = `
        <div class="message-bubble user-bubble">
          <div class="message-content">${this.escapeHtml(content).replace(/\n/g, '<br>')}</div>
          <div class="message-meta">
            <span class="message-time">${timeStr}</span>
          </div>
        </div>
      `;
    } else {
      const badge = modelName || (this.activeModel ? this.activeModel.name : 'AI Agent');
      wrapper.innerHTML = `
        <div class="message-avatar">
          <div class="ai-avatar-glow"></div>
          <span class="ai-avatar-icon">✦</span>
        </div>
        <div class="message-bubble ai-bubble">
          <div class="ai-message-header">
            <span class="model-badge"><span class="badge-dot"></span>${this.escapeHtml(badge)}</span>
            <div class="message-actions">
              <button class="btn-copy-msg" title="Copy message" onclick="window.app.chatEngine.copyMessageText('${msgId}')">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect>
                  <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path>
                </svg>
              </button>
              <span class="message-time">${timeStr}</span>
            </div>
          </div>
          <div class="message-content">${this.formatMarkdown(content)}</div>
        </div>
      `;
    }

    this.container.appendChild(wrapper);
    this.scrollToBottom();
    return wrapper;
  }

  /**
   * Update the text content of an ongoing streamed message bubble.
   *
   * @param {HTMLElement} wrapper - Message bubble wrapper.
   * @param {string} fullText - Full accumulated text.
   */
  updateMessageContent(wrapper, fullText) {
    if (!wrapper) return;
    const contentEl = wrapper.querySelector('.message-content');
    if (contentEl) {
      contentEl.innerHTML = this.formatMarkdown(fullText);
      this.scrollToBottom();
    }
  }

  /**
   * Display the animated typing indicator.
   */
  showTypingIndicator() {
    this.hideTypingIndicator();
    if (!this.container) {
      this.container = document.getElementById('chat-messages-container');
    }
    if (!this.container) return;

    const indicator = document.createElement('div');
    indicator.id = 'typing-indicator-wrapper';
    indicator.className = 'chat-message-wrapper message-assistant typing-indicator-item';
    indicator.innerHTML = `
      <div class="message-avatar">
        <span class="ai-avatar-icon">✦</span>
      </div>
      <div class="message-bubble ai-bubble typing-bubble">
        <div class="typing-dots">
          <span class="dot"></span>
          <span class="dot"></span>
          <span class="dot"></span>
        </div>
      </div>
    `;
    this.container.appendChild(indicator);
    this.scrollToBottom();
  }

  /**
   * Hide the typing indicator.
   */
  hideTypingIndicator() {
    const existing = document.getElementById('typing-indicator-wrapper');
    if (existing) {
      existing.remove();
    }
  }

  /**
   * Scroll chat message viewport to bottom smoothly.
   */
  scrollToBottom() {
    if (!this.container) return;
    this.container.scrollTop = this.container.scrollHeight;
  }

  /**
   * Copy message plain text to clipboard.
   *
   * @param {string} messageId - Message element ID.
   */
  copyMessageText(messageId) {
    const el = document.getElementById(messageId);
    if (!el) return;
    const contentEl = el.querySelector('.message-content');
    if (contentEl) {
      navigator.clipboard.writeText(contentEl.innerText).then(() => {
        const copyBtn = el.querySelector('.btn-copy-msg');
        if (copyBtn) {
          copyBtn.classList.add('copied');
          setTimeout(() => copyBtn.classList.remove('copied'), 2000);
        }
      });
    }
  }

  /**
   * Copy specific code block snippet to clipboard.
   *
   * @param {string} codeBlockId - ID of code block element.
   */
  static copyCodeSnippet(codeBlockId) {
    const codeEl = document.getElementById(codeBlockId);
    if (!codeEl) return;
    navigator.clipboard.writeText(codeEl.innerText).then(() => {
      const btn = codeEl.parentElement?.querySelector('.btn-copy-code');
      if (btn) {
        btn.textContent = 'Copied!';
        setTimeout(() => {
          btn.textContent = 'Copy';
        }, 2000);
      }
    });
  }

  /**
   * Display a floating or embedded notification in the chat workspace.
   *
   * @param {string} text - Message text.
   * @param {'info'|'success'|'error'} [type='info'] - Notification type.
   */
  renderNotification(text, type = 'info') {
    const notifContainer = document.getElementById('notification-portal');
    if (!notifContainer) return;

    const notif = document.createElement('div');
    notif.className = `app-notification notif-${type}`;
    notif.innerHTML = `
      <span class="notif-icon">${type === 'error' ? '⚠️' : type === 'success' ? '✓' : 'ℹ️'}</span>
      <span class="notif-text">${this.escapeHtml(text)}</span>
    `;

    notifContainer.appendChild(notif);
    setTimeout(() => {
      notif.classList.add('notif-fade-out');
      setTimeout(() => notif.remove(), 400);
    }, 4500);
  }

  /**
   * Format basic Markdown syntax into safe HTML.
   *
   * @param {string} text - Markdown input text.
   * @returns {string} Safe rendered HTML.
   */
  formatMarkdown(text) {
    if (!text) return '';

    // First escape raw HTML
    let escaped = this.escapeHtml(text);

    // Code blocks with syntax container and copy button
    let codeIndex = 0;
    escaped = escaped.replace(/```([a-zA-Z0-9_\-\+]*)\n([\s\S]*?)```/g, (match, lang, code) => {
      const id = `code_block_${Date.now()}_${codeIndex++}`;
      const languageBadge = lang ? `<span class="code-lang-tag">${lang}</span>` : '';
      return `
        <div class="code-block-container">
          <div class="code-block-header">
            ${languageBadge}
            <button class="btn-copy-code" onclick="ChatEngine.copyCodeSnippet('${id}')">Copy</button>
          </div>
          <pre><code id="${id}" class="language-${lang}">${code}</code></pre>
        </div>
      `;
    });

    // Inline code: `code`
    escaped = escaped.replace(/`([^`]+)`/g, '<code class="inline-code">$1</code>');

    // Bold: **text**
    escaped = escaped.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');

    // Italic: *text* or _text_
    escaped = escaped.replace(/\*([^*]+)\*/g, '<em>$1</em>');

    // Blockquotes: > quote
    escaped = escaped.replace(/^>\s?(.*)$/gm, '<blockquote class="chat-quote">$1</blockquote>');

    // Bulleted lists: - item or * item
    escaped = escaped.replace(/^\s*[-*]\s+(.*)$/gm, '<li class="chat-list-item">$1</li>');

    // Line breaks to <br> (outside of code blocks)
    escaped = escaped.replace(/\n/g, '<br>');

    // Clean up excessive breaks around block elements
    escaped = escaped.replace(/<\/div><br>/g, '</div>');
    escaped = escaped.replace(/<\/blockquote><br>/g, '</blockquote>');
    escaped = escaped.replace(/<\/li><br>/g, '</li>');

    return escaped;
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

// Global registration
if (typeof window !== 'undefined') {
  window.ChatEngine = ChatEngine;
}
if (typeof module !== 'undefined' && module.exports) {
  module.exports = { ChatEngine };
}
