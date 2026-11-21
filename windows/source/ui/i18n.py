"""Internationalization (i18n) module for Multi-AI Orchestrator.

Provides bilingual string registry (English / Turkish) with ~200 strings,
dynamic language switching, parameterized string interpolation, singleton
registry pattern, and subscriber notification support for UI reactive updates.
"""

from __future__ import annotations

import inspect
from typing import Any, Callable, Dict, List, Optional


class I18n:
    """Singleton internationalization manager with event notification.

    Maintains comprehensive language dictionaries, handles missing key fallbacks,
    supports keyword substitution, and notifies registered listeners
    when language preference changes.
    """

    _instance: Optional[I18n] = None
    _listeners: List[Callable[..., Any]] = []
    _current_lang: str = "en"

    STRINGS: Dict[str, Dict[str, str]] = {
        "en": {
            # --- Application Metadata ---
            "app_title": "AI Orchestrator",
            "app_subtitle": "Multi-AI Coordination Platform",
            "app_description": "Cross-Platform Multi-AI Orchestrator with Portable Memory & Encrypted Sync",
            "version": "Version",
            "about": "About",
            "quit": "Quit",
            "quit_confirm": "Are you sure you want to exit the application?",

            # --- Navigation & Tabs ---
            "nav_chat": "Chat & Deliberation",
            "nav_settings": "Settings",
            "nav_memory": "Memory Browser",
            "nav_security": "Security Policy",
            "nav_sync": "Cloud & Sync",
            "nav_skills": "Skills & Tools",
            "nav_logs": "System Logs",
            "nav_models": "Model Catalog",

            # --- Main Chat & Interaction Screen ---
            "chat_placeholder": "Type your message...",
            "send": "Send",
            "chat_mode": "Response mode",
            "chat_deliberation": "Multi-AI deliberation",
            "chat_model": "Direct response model",
            "chat_no_models": "No active models",
            "chat_debate_hint": "Enabled models will deliberate together.",
            "chat_direct_hint": "Choose one active model for this conversation.",
            "chat_working": "Çalışıyor… {hhmmss}",
            "chat_working_elapsed": "Bu işlem {elapsed} saniye süredir çalışıyor",
            "chat_tool_working": "Running {tool}… {hhmmss}",
            "chat_request_done": "Reply received in {elapsed}s.",
            "chat_request_failed": "Request failed after {elapsed}s.",
            "deliberation_panel": "AI Deliberation",
            "hide_deliberation": "Hide Deliberation",
            "show_deliberation": "Show Deliberation",
            "copy_message": "Copy Message",
            "regenerate": "Regenerate",
            "clear_chat": "Clear Chat",
            "export_chat": "Export Chat",
            "message_sent": "Message sent",
            "token_count": "{count} tokens",
            "cost_estimate": "Estimated cost: ${cost}",
            "role_user": "User",
            "role_assistant": "Assistant",
            "role_system": "System",
            "role_judge": "Judge",
            "pinned_message": "Pinned",
            "unpin_message": "Unpin",
            "retry": "Retry",
            "stop_generation": "Stop Generation",
            "user_input_hint": "Press Enter to send, Shift+Enter for new line",
            "empty_chat_hint": "Start a conversation or trigger a multi-AI deliberation session.",

            # --- Status Bar ---
            "active_models": "Active Models",
            "current_memory": "Memory",
            "permissions": "Permissions",
            "no_models": "No models active",
            "no_memory": "No sub-memory selected",
            "status_idle": "Idle",
            "status_busy": "Processing...",
            "status_ready": "Ready",
            "network_status": "Network",
            "latency_ms": "{ms} ms",

            # --- Settings & Provider Management ---
            "settings_title": "Settings",
            "api_management": "API Management",
            "add_provider": "Add Provider",
            "edit_provider": "Edit Provider",
            "remove_provider": "Remove Provider",
            "test_connection": "Test Connection",
            "test_all": "Test All Connections",
            "provider_name": "Provider Name",
            "base_url": "Base URL",
            "api_key": "API Key",
            "api_key_placeholder": "Enter secret API key or leave blank for local models",
            "model_id": "Model ID",
            "schema_type": "Schema Type",
            "enabled": "Enabled",
            "disabled": "Disabled",
            "effort_level": "Effort Level",
            "effort_low": "Low",
            "effort_medium": "Medium",
            "effort_high": "High",
            "effort_extended": "Extended Thinking",
            "temperature": "Temperature",
            "max_tokens": "Max Tokens",
            "system_prompt": "System Prompt",
            "context_window": "Context Window",
            "timeout_seconds": "Timeout (seconds)",
            "streaming_enabled": "Stream Responses",
            "cost_tracking": "Track Costs",
            "delete_provider_confirm": "Delete provider '{name}'? This cannot be undone.",
            "provider_openai": "OpenAI",
            "provider_anthropic": "Anthropic Claude",
            "provider_google": "Google Gemini",
            "provider_groq": "Groq LPU",
            "provider_ollama": "Ollama Local",
            "provider_custom": "Custom OpenAI-Compatible",
            "provider_type_hint": "Select API provider schema format",

            # --- Security & Permissions ---
            "security_title": "Security Policy",
            "security_tools_note": "These switches grant the app's registered tools permission; they do not enable screen, mouse, or keyboard control unless a matching tool is available.",
            "security_level": "Security Enforcement Level",
            "security_strict": "Strict (Isolated)",
            "security_moderate": "Moderate (Prompt on dangerous actions)",
            "security_permissive": "Permissive (Automated execution)",
            "sudo_enabled": "Elevated Privileges (Sudo)",
            "fs_read": "File System Read",
            "fs_write": "File System Write",
            "fs_delete": "File System Delete",
            "allowed_paths": "Allowed Paths",
            "gui_automation": "GUI Automation",
            "terminal_enabled": "Allow AI to run terminal commands",
            "network_access": "Network Outbound Access",
            "shell_execution": "Shell Command Execution",
            "read_only_mode": "Read-Only Mode",
            "audit_log": "Security Audit Log",
            "danger_zone": "Danger Zone",
            "sandbox_status": "Sandbox Status",
            "sandbox_active": "Sandbox Active",
            "sandbox_disabled": "Sandbox Disabled",
            "elevated_warning": "Warning: Elevated privileges can modify system critical files.",
            "alert_command_blocked": "Blocked potentially unsafe command: {cmd}",
            "alert_fs_blocked": "File access denied for path: {path}",
            "alert_sudo_attempt": "Unauthorized sudo execution attempt intercepted",
            "audit_timestamp": "Timestamp",
            "audit_action": "Action",
            "audit_resource": "Resource",
            "audit_result": "Result",
            "audit_cleared": "Security audit log cleared.",
            "clear_audit_log": "Clear Audit Log",

            # --- Memory Browser & Management ---
            "memory_title": "Memory Browser",
            "core_memory": "Core Memory",
            "sub_memories": "Sub-Memories",
            "identity": "Identity",
            "preferences": "Preferences",
            "persistent_facts": "Persistent Facts",
            "create_sub": "Create Sub-Memory",
            "rename_sub": "Rename",
            "delete_sub": "Delete",
            "merge_sub": "Merge Sub-Memories",
            "switch_sub": "Switch To",
            "sub_name": "Sub-Memory Name",
            "sub_description": "Description",
            "merge_source_a": "First Sub-Memory",
            "merge_source_b": "Second Sub-Memory",
            "merge_result_name": "Merged Name",
            "memory_path": "Memory File Path",
            "rebind_path": "Change Path",
            "import_memory": "Import Memory File",
            "export_memory": "Export Memory File",
            "memory_stats": "Memory Statistics",
            "memory_size": "Storage Size",
            "memory_entries_count": "{count} facts registered",
            "last_modified": "Last Modified",
            "search_memory": "Search Facts & Context",
            "search_placeholder": "Filter stored memories...",
            "filter_all": "All Categories",
            "filter_identity": "Identity",
            "filter_facts": "Facts",
            "clear_memory_confirm": "Clear all entries in this sub-memory?",
            "sub_memory_created": "Sub-memory '{name}' created successfully.",
            "sub_memory_deleted": "Sub-memory '{name}' deleted.",
            "sub_memory_switched": "Switched active sub-memory to '{name}'.",
            "sub_memory_count": "{count} sub-memories",
            "active_sub_memory": "Active Sub-Memory",
            "no_sub_memories": "No sub-memories defined",
            "pin_fact": "Pin Fact",
            "unpin_fact": "Unpin Fact",
            "edit_fact": "Edit Fact",
            "delete_fact": "Delete Fact",
            "fact_key": "Fact Key / Topic",
            "fact_value": "Fact Content",
            "category": "Category",
            "category_work": "Work & Projects",
            "category_code": "Code & Architecture",
            "category_personal": "Preferences & Notes",
            "category_general": "General Knowledge",

            # --- Sync & Cloud Token ---
            "sync_title": "Export Sync Token",
            "sync_description": "Generate an encrypted token containing your memory and API credentials. Paste this into the web client to access from any device.",
            "sync_password": "Encryption Passphrase",
            "sync_generate": "Generate Token",
            "sync_copy": "Copy to Clipboard",
            "sync_qr": "Show QR Code",
            "sync_status": "Sync Status",
            "sync_active": "Synchronized",
            "sync_idle": "Awaiting Export",
            "sync_error": "Encryption / Sync Error",
            "sync_token_generated": "Sync token generated successfully.",
            "sync_token_copied": "Sync token copied to system clipboard.",
            "sync_passphrase_hint": "Choose a strong passphrase (minimum 8 characters).",
            "sync_passphrase_min_len": "Passphrase must be at least 8 characters long.",
            "sync_invalid_passphrase": "Invalid passphrase or corrupted token payload.",
            "sync_qr_hint": "Scan with mobile device or web client camera.",
            "sync_web_url": "Web Client URL",
            "sync_import_title": "Import Sync Token",
            "sync_import_paste": "Paste encrypted sync token string here",
            "sync_import_btn": "Decrypt & Import",
            "sync_import_success": "Configuration and memory imported successfully.",
            "qr_code_display": "Encrypted Sync QR Code",
            "qr_save_image": "Save QR Code Image",
            "qr_instructions": "Point camera to transfer state securely.",

            # --- Multi-AI Deliberation & Debate ---
            "deliberation_title": "Deliberation Settings",
            "deliberation_enabled": "Enable Multi-AI Deliberation",
            "show_raw_debate": "Show Raw Debate",
            "judge_model": "Judge Model",
            "deliberation_round": "Round {round} / {total}",
            "deliberation_consensus": "Consensus Reached",
            "deliberation_disagreement": "Persistent Disagreement",
            "deliberation_summary": "Deliberation Synthesis",
            "deliberation_turn": "{model}'s turn to speak",
            "judge_verdict": "Judge Verdict",
            "divergence_score": "Divergence Score: {score}",
            "deliberation_history": "Deliberation History",
            "rounds_count": "Max Deliberation Rounds",
            "judge_prompt": "Judge Synthesis Prompt",
            "deliberation_status": "Deliberation Status",
            "deliberation_in_progress": "Deliberation in progress...",
            "deliberation_completed": "Deliberation concluded successfully.",
            "deliberation_failed": "Deliberation failed to complete.",
            "debate_mode_sequential": "Sequential Round-Robin",
            "debate_mode_parallel": "Parallel Synthesis",
            "debate_mode_panel": "Expert Panel",
            "agreement_level": "Agreement Level",
            "agreement_high": "High Consensus",
            "agreement_medium": "Moderate Consensus",
            "agreement_low": "Significant Divergence",
            "export_debate_report": "Export Debate Report",

            # --- Skills & Tools System ---
            "skills_title": "Skills & Automation Tools",
            "available_skills": "Available Skills",
            "skill_enabled": "Enabled",
            "skill_disabled": "Disabled",
            "skill_params": "Parameters",
            "skill_executing": "Executing tool '{name}'...",
            "skill_success": "Tool '{name}' completed successfully.",
            "skill_failed": "Tool '{name}' execution failed.",
            "web_search_skill": "Web Search & Extraction",
            "code_exec_skill": "Python Sandbox Execution",
            "file_ops_skill": "File System Operations",
            "crypto_skill": "Cryptographic Utilities",
            "bash_skill": "Terminal Command Execution",

            # --- Language Selection ---
            "language": "Language",
            "language_toggle": "Türkçe",
            "lang_en": "English",
            "lang_tr": "Türkçe",

            # --- Status Messages & Feedback ---
            "connecting": "Connecting...",
            "connected": "Connected",
            "disconnected": "Disconnected",
            "error": "Error",
            "success": "Success",
            "health_ok": "Connection OK",
            "health_fail": "Connection Failed",
            "saved": "Saved",
            "deleted": "Deleted",
            "merged": "Merged",
            "permission_denied": "Permission Denied",
            "path_not_allowed": "Path not in allowed scope",
            "loading": "Loading...",
            "validating": "Validating...",
            "copied": "Copied!",

            # --- Deliberation Real-Time Notifications ---
            "thinking": "Thinking...",
            "debating": "AI models are deliberating...",
            "consensus_reached": "Consensus reached",
            "model_response": "{model} responded",
            "judge_synthesizing": "Judge model synthesizing...",
            "deliberation_started_with": "Deliberation started with: {models}",
            "deliberation_consensus_in": "Consensus reached in {ms}ms",
            "no_response": "No response",
            "event_details": "Event ({event_type}): {data}",

            # --- Error Codes & Diagnostics ---
            "error_network": "Network connection error: {details}",
            "error_timeout": "Request timed out after {seconds}s",
            "error_rate_limit": "Rate limit exceeded. Retry in {seconds}s",
            "error_auth": "Authentication failure: Invalid API key",
            "error_not_found": "Requested resource not found",
            "error_invalid_input": "Invalid input provided: {details}",
            "error_unexpected": "An unexpected error occurred: {details}",
            "restart_required": "Application restart required for changes to take effect",
            "unsaved_changes": "You have unsaved changes. Discard?",
            "file_not_found": "File not found: {path}",
            "corrupted_data": "Data corruption detected in {target}",
            "unknown": "Unknown",

            # --- Confirmations & Dialog Actions ---
            "confirm_delete": "Are you sure you want to delete?",
            "confirm_merge": "Merge these sub-memories?",
            "confirm_reset": "Reset to defaults?",
            "confirm_action": "Please confirm this operation.",
            "yes": "Yes",
            "no": "No",
            "cancel": "Cancel",
            "ok": "OK",
            "close": "Close",
            "save": "Save",
            "back": "Back",
            "apply": "Apply",
            "refresh": "Refresh",
            "edit": "Edit",
            "remove": "Remove",
            "search": "Search",
            "filter": "Filter",
            "details": "Details",
            "options": "Options",
            "help": "Help",
            "select": "Select",
            "none": "None",
            "expand": "Expand",
            "collapse": "Collapse",

            # --- Markdown & Editor ---
            "copy_code": "Copy Code",
            "code_copied": "Code snippet copied to clipboard.",
            "syntax_highlighting": "Syntax Highlighting",
            "word_wrap": "Word Wrap",
            "line_numbers": "Line Numbers",

            # --- Keyboard Shortcuts ---
            "shortcut_help": "F1: Help",
            "shortcut_toggle_lang": "Ctrl+L: Toggle Language",
            "shortcut_toggle_delib": "Ctrl+D: Deliberation Panel",
            "shortcut_new_chat": "Ctrl+N: New Session",
            "shortcut_settings": "Ctrl+S: Settings",
            "shortcut_quit": "Ctrl+Q: Quit",

            # --- Date & Time References ---
            "just_now": "Just now",
            "seconds_ago": "{seconds} seconds ago",
            "minutes_ago": "{minutes} minutes ago",
            "hours_ago": "{hours} hours ago",
            "today": "Today",
            "yesterday": "Yesterday",
        },
        "tr": {
            # --- Uygulama Üst Bilgileri ---
            "app_title": "AI Orkestratör",
            "app_subtitle": "Çoklu AI Koordinasyon Platformu",
            "app_description": "Taşınabilir Hafıza ve Şifreli Eşitleme Özellikli Çapraz Platform Çoklu AI Orkestratörü",
            "version": "Sürüm",
            "about": "Hakkında",
            "quit": "Çıkış",
            "quit_confirm": "Uygulamadan çıkmak istediğinizden emin misiniz?",

            # --- Navigasyon ve Sekmeler ---
            "nav_chat": "Sohbet ve Müzakere",
            "nav_settings": "Ayarlar",
            "nav_memory": "Hafıza Tarayıcısı",
            "nav_security": "Güvenlik Politikası",
            "nav_sync": "Bulut ve Eşitleme",
            "nav_skills": "Yetenekler ve Araçlar",
            "nav_logs": "Sistem Günlükleri",
            "nav_models": "Model Kataloğu",

            # --- Ana Sohbet ve Etkileşim Ekranı ---
            "chat_placeholder": "Mesajınızı yazın...",
            "send": "Gönder",
            "chat_mode": "Yanıt modu",
            "chat_deliberation": "Çoklu AI müzakeresi",
            "chat_model": "Doğrudan yanıt modeli",
            "chat_no_models": "Aktif model yok",
            "chat_debate_hint": "Etkin modeller birlikte müzakere eder.",
            "chat_direct_hint": "Bu sohbet için etkin bir model seçin.",
            "chat_working": "Çalışıyor… {hhmmss}",
            "chat_working_elapsed": "Bu işlem {elapsed} saniye süredir çalışıyor",
            "chat_tool_working": "{tool} çalışıyor… {hhmmss}",
            "chat_request_done": "Yanıt {elapsed} sn içinde geldi.",
            "chat_request_failed": "İstek {elapsed} sn sonra başarısız oldu.",
            "deliberation_panel": "AI Müzakeresi",
            "hide_deliberation": "Müzakereyi Gizle",
            "show_deliberation": "Müzakereyi Göster",
            "copy_message": "Mesajı Kopyala",
            "regenerate": "Yeniden Üret",
            "clear_chat": "Sohbeti Temizle",
            "export_chat": "Sohbeti Dışa Aktar",
            "message_sent": "Mesaj gönderildi",
            "token_count": "{count} belirteç",
            "cost_estimate": "Tahmini maliyet: ${cost}",
            "role_user": "Kullanıcı",
            "role_assistant": "Asistan",
            "role_system": "Sistem",
            "role_judge": "Hakem",
            "pinned_message": "Sabitlendi",
            "unpin_message": "Sabitlemeyi Kaldır",
            "retry": "Tekrar Dene",
            "stop_generation": "Üretimi Durdur",
            "user_input_hint": "Göndermek için Enter, yeni satır için Shift+Enter tuşlayın",
            "empty_chat_hint": "Bir konuşma başlatın veya çoklu AI müzakere oturumu tetikleyin.",

            # --- Durum Çubuğu ---
            "active_models": "Aktif Modeller",
            "current_memory": "Hafıza",
            "permissions": "İzinler",
            "no_models": "Aktif model yok",
            "no_memory": "Alt hafıza seçilmedi",
            "status_idle": "Boşta",
            "status_busy": "İşleniyor...",
            "status_ready": "Hazır",
            "network_status": "Ağ",
            "latency_ms": "{ms} ms",

            # --- Ayarlar ve Sağlayıcı Yönetimi ---
            "settings_title": "Ayarlar",
            "api_management": "API Yönetimi",
            "add_provider": "Sağlayıcı Ekle",
            "edit_provider": "Sağlayıcıyı Düzenle",
            "remove_provider": "Sağlayıcıyı Kaldır",
            "test_connection": "Bağlantıyı Test Et",
            "test_all": "Tüm Bağlantıları Test Et",
            "provider_name": "Sağlayıcı Adı",
            "base_url": "Temel URL",
            "api_key": "API Anahtarı",
            "api_key_placeholder": "Gizli API anahtarını girin veya yerel modeller için boş bırakın",
            "model_id": "Model ID",
            "schema_type": "Şema Türü",
            "enabled": "Etkin",
            "disabled": "Devre Dışı",
            "effort_level": "Çaba Düzeyi",
            "effort_low": "Düşük",
            "effort_medium": "Orta",
            "effort_high": "Yüksek",
            "effort_extended": "Genişletilmiş Düşünme",
            "temperature": "Sıcaklık (Temperature)",
            "max_tokens": "Maksimum Belirteç",
            "system_prompt": "Sistem Yönergesi",
            "context_window": "Bağlam Penceresi",
            "timeout_seconds": "Zaman Aşımı (saniye)",
            "streaming_enabled": "Akışlı Yanıtlar (Streaming)",
            "cost_tracking": "Maliyet Takibi",
            "delete_provider_confirm": "'{name}' sağlayıcısı silinsin mi? Bu işlem geri alınamaz.",
            "provider_openai": "OpenAI",
            "provider_anthropic": "Anthropic Claude",
            "provider_google": "Google Gemini",
            "provider_groq": "Groq LPU",
            "provider_ollama": "Ollama Yerel",
            "provider_custom": "Özel OpenAI-Uyumlu",
            "provider_type_hint": "API sağlayıcı şema biçimini seçin",

            # --- Güvenlik Politikası ---
            "security_title": "Güvenlik Politikası",
            "security_tools_note": "Bu anahtarlar kayıtlı uygulama araçlarına izin verir; eşleşen bir araç yoksa ekran, fare veya klavye kontrolünü etkinleştirmez.",
            "security_level": "Güvenlik Uygulama Düzeyi",
            "security_strict": "Katı (Yalıtılmış)",
            "security_moderate": "Orta (Tehlikeli eylemlerde sor)",
            "security_permissive": "Esnek (Otomatik çalıştırma)",
            "sudo_enabled": "Yükseltilmiş Yetkiler (Sudo)",
            "fs_read": "Dosya Sistemi Okuma",
            "fs_write": "Dosya Sistemi Yazma",
            "fs_delete": "Dosya Sistemi Silme",
            "allowed_paths": "İzin Verilen Yollar",
            "gui_automation": "GUI Otomasyonu",
            "terminal_enabled": "AI'ın terminal komutları çalıştırmasına izin ver",
            "network_access": "Dış Ağ Erişimi",
            "shell_execution": "Kabuk Komut Çalıştırma",
            "read_only_mode": "Salt Okunur Mod",
            "audit_log": "Güvenlik Denetim Günlüğü",
            "danger_zone": "Tehlike Bölgesi",
            "sandbox_status": "Kum Havuzu (Sandbox) Durumu",
            "sandbox_active": "Sandbox Aktif",
            "sandbox_disabled": "Sandbox Devre Dışı",
            "elevated_warning": "Uyarı: Yükseltilmiş yetkiler kritik sistem dosyalarını değiştirebilir.",
            "alert_command_blocked": "Güvenli olmayan komut engellendi: {cmd}",
            "alert_fs_blocked": "Dizin için dosya erişimi reddedildi: {path}",
            "alert_sudo_attempt": "Yetkisiz sudo çalıştırma girişimi engellendi",
            "audit_timestamp": "Zaman Damgası",
            "audit_action": "Eylem",
            "audit_resource": "Kaynak",
            "audit_result": "Sonuç",
            "audit_cleared": "Güvenlik denetim günlüğü temizlendi.",
            "clear_audit_log": "Denetim Günlüğünü Temizle",

            # --- Hafıza Tarayıcısı ve Yönetimi ---
            "memory_title": "Hafıza Tarayıcısı",
            "core_memory": "Temel Hafıza",
            "sub_memories": "Ara Hafızalar",
            "identity": "Kimlik",
            "preferences": "Tercihler",
            "persistent_facts": "Kalıcı Bilgiler",
            "create_sub": "Ara Hafıza Oluştur",
            "rename_sub": "Yeniden Adlandır",
            "delete_sub": "Sil",
            "merge_sub": "Ara Hafızaları Birleştir",
            "switch_sub": "Geçiş Yap",
            "sub_name": "Ara Hafıza Adı",
            "sub_description": "Açıklama",
            "merge_source_a": "Birinci Ara Hafıza",
            "merge_source_b": "İkinci Ara Hafıza",
            "merge_result_name": "Birleştirilmiş Ad",
            "memory_path": "Hafıza Dosya Yolu",
            "rebind_path": "Yolu Değiştir",
            "import_memory": "Hafıza Dosyası İçe Aktar",
            "export_memory": "Hafıza Dosyası Dışa Aktar",
            "memory_stats": "Hafıza İstatistikleri",
            "memory_size": "Depolama Boyutu",
            "memory_entries_count": "{count} bilgi kayıtlı",
            "last_modified": "Son Düzenleme",
            "search_memory": "Kayıtları ve Bağlamı Ara",
            "search_placeholder": "Kayıtlı hafızaları filtreleyin...",
            "filter_all": "Tüm Kategoriler",
            "filter_identity": "Kimlik",
            "filter_facts": "Bilgiler",
            "clear_memory_confirm": "Bu ara hafızadaki tüm kayıtlar silinsin mi?",
            "sub_memory_created": "'{name}' ara hafızası başarıyla oluşturuldu.",
            "sub_memory_deleted": "'{name}' ara hafızası silindi.",
            "sub_memory_switched": "Aktif ara hafıza '{name}' olarak değiştirildi.",
            "sub_memory_count": "{count} ara hafıza",
            "active_sub_memory": "Aktif Ara Hafıza",
            "no_sub_memories": "Tanımlı ara hafıza bulunmuyor",
            "pin_fact": "Bilgiyi Sabitle",
            "unpin_fact": "Sabitlemeyi Kaldır",
            "edit_fact": "Bilgiyi Düzenle",
            "delete_fact": "Bilgiyi Sil",
            "fact_key": "Bilgi Başlığı / Konu",
            "fact_value": "Bilgi İçeriği",
            "category": "Kategori",
            "category_work": "İş ve Projeler",
            "category_code": "Kod ve Mimari",
            "category_personal": "Tercihler ve Notlar",
            "category_general": "Genel Bilgi",

            # --- Senkronizasyon ve Bulut Tokenı ---
            "sync_title": "Senkronizasyon Tokenı Dışa Aktar",
            "sync_description": "Hafızanızı ve API kimlik bilgilerinizi içeren şifreli bir token oluşturun. Herhangi bir cihazdan erişmek için web istemcisine yapıştırın.",
            "sync_password": "Şifreleme Parolası",
            "sync_generate": "Token Oluştur",
            "sync_copy": "Panoya Kopyala",
            "sync_qr": "QR Kodu Göster",
            "sync_status": "Eşitleme Durumu",
            "sync_active": "Eşitlendi",
            "sync_idle": "Dışa Aktarma Bekleniyor",
            "sync_error": "Şifreleme / Eşitleme Hatası",
            "sync_token_generated": "Senkronizasyon tokenı başarıyla üretildi.",
            "sync_token_copied": "Senkronizasyon tokenı sistem panosuna kopyalandı.",
            "sync_passphrase_hint": "Güçlü bir parola seçin (en az 8 karakter).",
            "sync_passphrase_min_len": "Parola en az 8 karakter uzunluğunda olmalıdır.",
            "sync_invalid_passphrase": "Geçersiz parola veya bozuk token verisi.",
            "sync_qr_hint": "Mobil cihazınız veya web istemcisi kamerasıyla tarayın.",
            "sync_web_url": "Web İstemcisi URL'si",
            "sync_import_title": "Senkronizasyon Tokenı İçe Aktar",
            "sync_import_paste": "Şifrelenmiş token dizesini buraya yapıştırın",
            "sync_import_btn": "Şifreyi Çöz ve İçe Aktar",
            "sync_import_success": "Yapılandırma ve hafıza başarıyla içe aktarıldı.",
            "qr_code_display": "Şifrelenmiş Eşitleme QR Kodu",
            "qr_save_image": "QR Kod Resmini Kaydet",
            "qr_instructions": "Durumu güvenli aktarmak için kamerayı doğrultun.",

            # --- Çoklu AI Müzakeresi ve Tartışma ---
            "deliberation_title": "Müzakere Ayarları",
            "deliberation_enabled": "Çoklu AI Müzakeresini Etkinleştir",
            "show_raw_debate": "Ham Tartışmayı Göster",
            "judge_model": "Hakem Model",
            "deliberation_round": "Tur {round} / {total}",
            "deliberation_consensus": "Uzlaşma Sağlandı",
            "deliberation_disagreement": "Süreğen Fikir Ayrılığı",
            "deliberation_summary": "Müzakere Sentezi",
            "deliberation_turn": "Söz sırası: {model}",
            "judge_verdict": "Hakem Kararı",
            "divergence_score": "Fikir Ayrılığı Skoru: {score}",
            "deliberation_history": "Müzakere Geçmişi",
            "rounds_count": "Maksimum Müzakere Turu",
            "judge_prompt": "Hakem Sentez Yönergesi",
            "deliberation_status": "Müzakere Durumu",
            "deliberation_in_progress": "Müzakere sürüyor...",
            "deliberation_completed": "Müzakere başarıyla sonuçlandı.",
            "deliberation_failed": "Müzakere tamamlanamadı.",
            "debate_mode_sequential": "Sıralı Tur Düzeni (Round-Robin)",
            "debate_mode_parallel": "Paralel Sentez",
            "debate_mode_panel": "Uzman Paneli",
            "agreement_level": "Uzlaşma Seviyesi",
            "agreement_high": "Yüksek Uzlaşma",
            "agreement_medium": "Orta Seviye Uzlaşma",
            "agreement_low": "Belirgin Fikir Ayrılığı",
            "export_debate_report": "Müzakere Raporunu Dışa Aktar",

            # --- Yetenekler ve Araçlar Sistemi ---
            "skills_title": "Yetenekler ve Otomasyon Araçları",
            "available_skills": "Kullanılabilir Yetenekler",
            "skill_enabled": "Etkin",
            "skill_disabled": "Devre Dışı",
            "skill_params": "Parametreler",
            "skill_executing": "'{name}' aracı yürütülüyor...",
            "skill_success": "'{name}' aracı başarıyla tamamlandı.",
            "skill_failed": "'{name}' aracı yürütmesi başarısız oldu.",
            "web_search_skill": "Web Araması ve Bilgi Çıkarımı",
            "code_exec_skill": "Python Kum Havuzu Çalıştırma",
            "file_ops_skill": "Dosya Sistemi İşlemleri",
            "crypto_skill": "Kriptografik Araçlar",
            "bash_skill": "Terminal Komutu Çalıştırma",

            # --- Dil Seçimi ---
            "language": "Dil",
            "language_toggle": "English",
            "lang_en": "English",
            "lang_tr": "Türkçe",

            # --- Durum Mesajları ve Geri Bildirim ---
            "connecting": "Bağlanıyor...",
            "connected": "Bağlandı",
            "disconnected": "Bağlantı Kesildi",
            "error": "Hata",
            "success": "Başarılı",
            "health_ok": "Bağlantı Başarılı",
            "health_fail": "Bağlantı Başarısız",
            "saved": "Kaydedildi",
            "deleted": "Silindi",
            "merged": "Birleştirildi",
            "permission_denied": "İzin Reddedildi",
            "path_not_allowed": "Yol izin verilen kapsamda değil",
            "loading": "Yükleniyor...",
            "validating": "Doğrulanıyor...",
            "copied": "Kopyalandı!",

            # --- Müzakere Gerçek Zamanlı Bildirimleri ---
            "thinking": "Düşünüyor...",
            "debating": "AI modelleri müzakere ediyor...",
            "consensus_reached": "Uzlaşma sağlandı",
            "model_response": "{model} yanıt verdi",
            "judge_synthesizing": "Hakem model sentezliyor...",
            "deliberation_started_with": "Müzakere şu modellerle başladı: {models}",
            "deliberation_consensus_in": "{ms} ms içinde uzlaşma sağlandı",
            "no_response": "Yanıt yok",
            "event_details": "Olay ({event_type}): {data}",

            # --- Hata Kodları ve Tanılama ---
            "error_network": "Ağ bağlantı hatası: {details}",
            "error_timeout": "İstek {seconds} saniye sonra zaman aşımına uğradı",
            "error_rate_limit": "Hız limiti aşıldı. {seconds} saniye sonra tekrar deneyin",
            "error_auth": "Kimlik doğrulama hatası: Geçersiz API anahtarı",
            "error_not_found": "İstenen kaynak bulunamadı",
            "error_invalid_input": "Geçersiz giriş sağlandı: {details}",
            "error_unexpected": "Beklenmeyen bir hata oluştu: {details}",
            "restart_required": "Değişikliklerin etkili olması için uygulamanın yeniden başlatılması gerekir",
            "unsaved_changes": "Kaydedilmemiş değişiklikleriniz var. Göz ardı edilsin mi?",
            "file_not_found": "Dosya bulunamadı: {path}",
            "corrupted_data": "{target} üzerinde veri bozulması tespit edildi",
            "unknown": "Bilinmeyen",

            # --- Onaylar ve İletişim Eylemleri ---
            "confirm_delete": "Silmek istediğinizden emin misiniz?",
            "confirm_merge": "Bu ara hafızalar birleştirilsin mi?",
            "confirm_reset": "Varsayılanlara sıfırlansın mı?",
            "confirm_action": "Lütfen bu işlemi onaylayın.",
            "yes": "Evet",
            "no": "Hayır",
            "cancel": "İptal",
            "ok": "Tamam",
            "close": "Kapat",
            "save": "Kaydet",
            "back": "Geri",
            "apply": "Uygula",
            "refresh": "Yenile",
            "edit": "Düzenle",
            "remove": "Kaldır",
            "search": "Ara",
            "filter": "Filtrele",
            "details": "Ayrıntılar",
            "options": "Seçenekler",
            "help": "Yardım",
            "select": "Seç",
            "none": "Hiçbiri",
            "expand": "Genişlet",
            "collapse": "Daralt",

            # --- Markdown ve Kod Görüntüleyici ---
            "copy_code": "Kodu Kopyala",
            "code_copied": "Kod parçası panoya kopyalandı.",
            "syntax_highlighting": "Sözdizimi Vurgulama",
            "word_wrap": "Metin Kaydırma",
            "line_numbers": "Satır Numaraları",

            # --- Klavye Kısayolları ---
            "shortcut_help": "F1: Yardım",
            "shortcut_toggle_lang": "Ctrl+L: Dili Değiştir",
            "shortcut_toggle_delib": "Ctrl+D: Müzakere Paneli",
            "shortcut_new_chat": "Ctrl+N: Yeni Oturum",
            "shortcut_settings": "Ctrl+S: Ayarlar",
            "shortcut_quit": "Ctrl+Q: Çıkış",

            # --- Tarih ve Zaman İfadeleri ---
            "just_now": "Az önce",
            "seconds_ago": "{seconds} saniye önce",
            "minutes_ago": "{minutes} dakika önce",
            "hours_ago": "{hours} saat önce",
            "today": "Bugün",
            "yesterday": "Dün",
        },
    }

    def __new__(cls) -> I18n:
        """Create or return the singleton instance."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._current_lang = "en"
            cls._instance._listeners = []
        return cls._instance

    @property
    def current_language(self) -> str:
        """Get the current active language code ('en' or 'tr')."""
        return self._current_lang

    def set_language(self, lang: str) -> None:
        """Set the active language and notify all registered listeners.

        Args:
            lang: Language code ('en' or 'tr'). If invalid, defaults to 'en'.
        """
        if lang not in self.STRINGS:
            lang = "en"

        if self._current_lang != lang:
            self._current_lang = lang
            self.notify_listeners()

    def toggle_language(self) -> None:
        """Toggle between English ('en') and Turkish ('tr')."""
        new_lang = "tr" if self._current_lang == "en" else "en"
        self.set_language(new_lang)

    def t(self, key: str, **kwargs: Any) -> str:
        """Lookup localized string by key with fallback and keyword formatting.

        Searches first in the active language dictionary, then falls back to English.
        If key is absent in both, returns key. Keyword arguments are safely interpolated.

        Args:
            key: Translation key name.
            **kwargs: Dynamic arguments to interpolate into {placeholder} fields.

        Returns:
            Localized and formatted string.
        """
        # Lookup in current language, fallback to English, fallback to key itself
        lang_dict = self.STRINGS.get(self._current_lang, {})
        text = lang_dict.get(key)

        if text is None:
            en_dict = self.STRINGS.get("en", {})
            text = en_dict.get(key, key)

        if kwargs:
            try:
                return text.format(**kwargs)
            except (KeyError, IndexError, ValueError):
                # Return unformatted or partially formatted string if interpolation fails
                return text

        return text

    def on_language_change(self, callback: Callable[..., Any]) -> None:
        """Register a callback function to be invoked when language changes.

        Args:
            callback: Callable that accepts either 0 arguments or (new_lang: str).
        """
        if callback not in self._listeners:
            self._listeners.append(callback)

    def remove_listener(self, callback: Callable[..., Any]) -> None:
        """Unregister a previously registered language change callback."""
        if callback in self._listeners:
            self._listeners.remove(callback)

    def notify_listeners(self) -> None:
        """Invoke all registered callbacks on language change safely."""
        for callback in list(self._listeners):
            try:
                sig = inspect.signature(callback)
                if len(sig.parameters) > 0:
                    callback(self._current_lang)
                else:
                    callback()
            except Exception:
                # Listener errors should not break application state
                pass


# Global singleton instance and convenience accessor
_i18n_instance = I18n()


def t(key: str, **kwargs: Any) -> str:
    """Convenience functional wrapper for localized string translation."""
    return _i18n_instance.t(key, **kwargs)
