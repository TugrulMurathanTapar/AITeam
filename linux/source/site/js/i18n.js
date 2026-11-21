/**
 * @file i18n.js
 * @description Internationalization (i18n) module supporting English and Turkish languages.
 */

const STRINGS = {
  en: {
    app_title: 'AI Orchestrator',
    app_tagline: 'Cross-Platform Multi-AI Orchestrator',
    language_toggle: 'TR',
    connected: 'Connected',
    offline: 'Offline',
    status_ready: 'Ready',
    status_active: 'Active',
    status_error: 'Error',
    status_streaming: 'Streaming...',

    // Token View
    token_title: 'Connect to Orchestrator',
    token_subtitle: 'Decrypt your secure multi-agent configuration and persistent memory token.',
    token_label: 'Encrypted Sync Token',
    token_placeholder: 'Paste your encrypted sync token here...',
    password_label: 'Decryption Passphrase',
    password_placeholder: 'Enter decryption passphrase...',
    decrypt_button: 'Decrypt & Connect',
    load_demo_button: 'Launch Demo Workspace',
    demo_badge: 'Instant Preview',
    token_helper: 'All cryptography runs locally in your browser via Web Crypto API (AES-256-GCM). No private keys or tokens leave your device.',
    error_decrypt: 'Decryption failed. Check your token and passphrase.',
    error_empty_fields: 'Please enter both the sync token and your passphrase.',
    error_passphrase_min_length: 'Enter an encryption passphrase of at least 8 characters.',
    decrypting: 'Decrypting credentials...',

    // Chat Workspace
    sidebar_title: 'Orchestration Hub',
    sub_memory_label: 'Active Sub-Memory',
    select_sub_memory: 'Select sub-memory context...',
    no_sub_memory: 'None (Core Memory Only)',
    active_models: 'Active AI Models',
    no_models: 'No AI models configured',
    memory_browser: 'Memory Browser',
    settings: 'Settings',
    logout: 'Disconnect',
    chat_welcome_title: 'Multi-AI Orchestrator Ready',
    chat_welcome_desc: 'Your persistent memory and AI provider configurations are loaded and active. Choose a model below or begin sending queries.',
    chat_placeholder: 'Type your message... (Press Enter to send, Shift+Enter for newline)',
    send_button: 'Send',
    stop_button: 'Stop',
    model_chips_label: 'Quick Switch:',
    copy_tooltip: 'Copy to clipboard',
    copied: 'Copied!',
    clear_chat: 'Clear Chat',
    streaming: 'Generating response...',
    error_api: 'API request failed',
    error_no_model: 'Please select an active model before sending a message.',

    // Memory Browser
    memory_title: 'Persistent Memory Graph',
    memory_subtitle: 'Inspect your decrypted Core Memory and contextual Sub-Memories.',
    core_memory: 'Core Memory',
    identity: 'Identity & Persona',
    preferences: 'User Preferences',
    facts: 'Persistent Facts',
    sub_memories: 'Sub-Memories',
    empty_memory: 'No memory data available in this configuration.',
    close: 'Close',
    export_memory: 'Copy JSON',
    active_badge: 'Active Context',
    set_active: 'Select Context',
    memory_active_pill: 'Context Active',

    // Settings Modal
    settings_title: 'Settings & Tools',
    session_info: 'Session Information',
    token_generator_title: 'Sync Token Generator',
    token_generator_desc: 'Create a new encrypted token from your own memory and API keys.',
    gen_memory_label: 'Memory JSON',
    gen_configs_label: 'API Configs JSON',
    gen_pass_label: 'Passphrase for New Token',
    generate_token: 'Encrypt & Generate Token',
    token_generated_success: 'New sync token generated and copied to clipboard!',
    clear_session: 'Clear Session Data'
  },
  tr: {
    app_title: 'AI Orkestratör',
    app_tagline: 'Çapraz Platform Çoklu-AI Orkestratörü',
    language_toggle: 'EN',
    connected: 'Bağlandı',
    offline: 'Çevrimdışı',
    status_ready: 'Hazır',
    status_active: 'Aktif',
    status_error: 'Hata',
    status_streaming: 'Akış yapılıyor...',

    // Token View
    token_title: 'Orkestratöre Bağlan',
    token_subtitle: 'Güvenli çoklu-ajan yapılandırmanızı ve kalıcı hafıza tokeninizi çözün.',
    token_label: 'Şifrelenmiş Senkronizasyon Tokeni',
    token_placeholder: 'Şifrelenmiş senkronizasyon tokeninizi buraya yapıştırın...',
    password_label: 'Şifre Çözme Parolası',
    password_placeholder: 'Şifre çözme parolasını girin...',
    decrypt_button: 'Şifreyi Çöz ve Bağlan',
    load_demo_button: 'Demo Çalışma Alanını Başlat',
    demo_badge: 'Hızlı Önizleme',
    token_helper: 'Tüm kriptografi Web Crypto API (AES-256-GCM) ile doğrudan tarayıcınızda çalışır. Özel anahtarlarınız veya tokenleriniz hiçbir sunucuya gönderilmez.',
    error_decrypt: 'Şifre çözme başarısız. Token ve parolanızı kontrol edin.',
    error_empty_fields: 'Lütfen hem senkronizasyon tokenini hem de parolanızı girin.',
    error_passphrase_min_length: 'En az 8 karakterli bir şifreleme parolası girin.',
    decrypting: 'Kimlik bilgileri çözülüyor...',

    // Chat Workspace
    sidebar_title: 'Orkestrasyon Merkezi',
    sub_memory_label: 'Aktif Ara Hafıza',
    select_sub_memory: 'Ara hafıza bağlamı seçin...',
    no_sub_memory: 'Yok (Yalnızca Temel Hafıza)',
    active_models: 'Aktif AI Modelleri',
    no_models: 'Yapılandırılmış AI modeli yok',
    memory_browser: 'Hafıza Tarayıcısı',
    settings: 'Ayarlar',
    logout: 'Bağlantıyı Kes',
    chat_welcome_title: 'Çoklu-AI Orkestratörü Hazır',
    chat_welcome_desc: 'Kalıcı hafızanız ve AI sağlayıcı yapılandırmalarınız yüklendi ve aktif. Aşağıdan bir model seçin veya mesaj göndermeye başlayın.',
    chat_placeholder: 'Mesajınızı yazın... (Göndermek için Enter, yeni satır için Shift+Enter)',
    send_button: 'Gönder',
    stop_button: 'Durdur',
    model_chips_label: 'Hızlı Geçiş:',
    copy_tooltip: 'Panoya kopyala',
    copied: 'Kopyalandı!',
    clear_chat: 'Sohbeti Temizle',
    streaming: 'Yanıt üretiliyor...',
    error_api: 'API isteği başarısız oldu',
    error_no_model: 'Mesaj göndermeden önce lütfen aktif bir model seçin.',

    // Memory Browser
    memory_title: 'Kalıcı Hafıza Grafiği',
    memory_subtitle: 'Çözülmüş Temel Hafızanızı ve bağlamsal Ara Hafızalarınızı inceleyin.',
    core_memory: 'Temel Hafıza',
    identity: 'Kimlik & Kişilik',
    preferences: 'Kullanıcı Tercihleri',
    facts: 'Kalıcı Bilgiler',
    sub_memories: 'Ara Hafızalar',
    empty_memory: 'Bu yapılandırmada hafıza verisi bulunamadı.',
    close: 'Kapat',
    export_memory: 'JSON Kopyala',
    active_badge: 'Aktif Bağlam',
    set_active: 'Bağlam Olarak Seç',
    memory_active_pill: 'Bağlam Aktif',

    // Settings Modal
    settings_title: 'Ayarlar & Araçlar',
    session_info: 'Oturum Bilgisi',
    token_generator_title: 'Senkronizasyon Tokeni Oluşturucu',
    token_generator_desc: 'Kendi hafıza ve API anahtarlarınızdan yeni bir şifreli token oluşturun.',
    gen_memory_label: 'Hafıza JSON',
    gen_configs_label: 'API Yapılandırmaları JSON',
    gen_pass_label: 'Yeni Token Parolası',
    generate_token: 'Şifrele ve Token Oluştur',
    token_generated_success: 'Yeni senkronizasyon tokeni oluşturuldu ve panoya kopyalandı!',
    clear_session: 'Kayıtlı Oturumu Temizle'
  }
};

class I18n {
  /**
   * Initialize i18n module with saved or default language.
   * @param {string} [defaultLang='en'] - Fallback language ('en' | 'tr').
   */
  constructor(defaultLang = 'en') {
    const saved = typeof localStorage !== 'undefined' ? localStorage.getItem('lang') : null;
    this.lang = saved === 'tr' || saved === 'en' ? saved : defaultLang;
  }

  /**
   * Look up translated string by key.
   * @param {string} key - Translation key.
   * @returns {string} Translated string or fallback key.
   */
  t(key) {
    return STRINGS[this.lang]?.[key] || STRINGS['en']?.[key] || key;
  }

  /**
   * Set active language and refresh DOM elements.
   * @param {string} lang - 'en' or 'tr'.
   */
  setLanguage(lang) {
    if (lang !== 'en' && lang !== 'tr') return;
    this.lang = lang;
    if (typeof localStorage !== 'undefined') {
      localStorage.setItem('lang', lang);
    }
    this.updateAllElements();
    window.dispatchEvent(new CustomEvent('languageChanged', { detail: { lang: this.lang } }));
  }

  /**
   * Toggle between English and Turkish.
   */
  toggleLanguage() {
    this.setLanguage(this.lang === 'en' ? 'tr' : 'en');
  }

  /**
   * Scan DOM for [data-i18n] and [data-i18n-placeholder] attributes and update.
   */
  updateAllElements() {
    if (typeof document === 'undefined') return;

    // Update text content
    document.querySelectorAll('[data-i18n]').forEach((el) => {
      const key = el.getAttribute('data-i18n');
      if (el.tagName === 'INPUT' || el.tagName === 'TEXTAREA') {
        el.placeholder = this.t(key);
      } else {
        el.textContent = this.t(key);
      }
    });

    // Update placeholders specifically if marked
    document.querySelectorAll('[data-i18n-placeholder]').forEach((el) => {
      const key = el.getAttribute('data-i18n-placeholder');
      el.placeholder = this.t(key);
    });

    // Update title tooltips
    document.querySelectorAll('[data-i18n-title]').forEach((el) => {
      const key = el.getAttribute('data-i18n-title');
      el.title = this.t(key);
    });

    // Update html lang attribute
    document.documentElement.lang = this.lang;
  }
}

// Make globally accessible
if (typeof window !== 'undefined') {
  window.I18n = I18n;
  window.STRINGS = STRINGS;
}
if (typeof module !== 'undefined' && module.exports) {
  module.exports = { I18n, STRINGS };
}
