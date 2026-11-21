"""Settings screen with tabbed sections for API, Security, Deliberation, and Sync."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, List, Optional

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, ScrollableContainer
from textual.screen import Screen
from textual.widgets import (
    Button,
    DataTable,
    Footer,
    Header,
    Input,
    Label,
    Select,
    Static,
    Switch,
    TabbedContent,
    TabPane,
    TextArea,
)

from core.api_handler import AIProvider, APIClient, EffortLevel, SchemaType
from ui.i18n import I18n, t

logger = logging.getLogger(__name__)


class SettingsScreen(Screen):
    """Settings screen providing configuration tabs for all system modules."""

    BINDINGS = [
        Binding("escape", "app.open_chat", "Sohbet"),
        Binding("ctrl+c", "app.open_chat", "Sohbet"),
    ]

    DEFAULT_CSS = """
    SettingsScreen {
        background: #0a0e27;
    }
    .tab-scroll {
        height: 1fr;
        overflow-y: auto;
    }
    .setting-item {
        height: 3;
        align-vertical: middle;
        margin: 1 0;
    }
    .setting-label {
        width: 32;
        color: #f1f5f9;
    }
    #provider-form {
        background: #090c24;
        border: round #06b6d4;
        padding: 1 2;
        margin-top: 1;
        height: auto;
    }
    .feedback-msg {
        margin: 1 0;
        text-style: bold;
        height: 2;
    }
    .section-title {
        color: #06b6d4;
        text-style: bold;
        margin: 1 0;
        height: 2;
    }
    .form-label {
        color: #94a3b8;
        margin: 1 0 0 0;
        height: 1;
    }
    #sync-token-display {
        height: 6;
        background: #0a0e27;
        border: tall #7c3aed;
        color: #38bdf8;
        padding: 1;
        margin: 1 0;
    }
    .form-actions {
        margin-top: 1;
        height: 3;
    }
    .hidden {
        display: none;
    }
    Select {
        margin: 0 0 1 0;
        height: 3;
    }
    Input {
        margin: 0 0 1 0;
    }
    """

    def compose(self) -> ComposeResult:
        """Compose the tabbed settings interface."""
        i18n = I18n()

        yield Header()
        with TabbedContent():
            # ── Tab 1: API Yönetimi ──────────────────────────────────────
            with TabPane(t("api_management"), id="tab-api"):
                with ScrollableContainer(classes="tab-scroll"):
                    yield DataTable(id="api-table")
                    with Horizontal(classes="form-actions"):
                        yield Button(
                            f"➕ {t('add_provider')}",
                            id="btn-add-provider",
                            variant="primary",
                        )
                        yield Button(
                            f"🔍 {t('test_all')}",
                            id="btn-test-all",
                            variant="warning",
                        )
                    yield Static("", id="api-status-msg", classes="feedback-msg")

                    # ── Ekleme / Düzenleme Formu ──
                    with Vertical(id="provider-form", classes="hidden"):
                        yield Static(t("add_provider"), id="lbl-form-title", classes="section-title")

                        yield Static(t("provider_name"), classes="form-label")
                        yield Input(placeholder="örn: OpenAI, Groq, NVIDIA...", id="inp-name")

                        yield Static(t("base_url"), classes="form-label")
                        yield Input(placeholder="https://api.openai.com/v1", id="inp-url")

                        yield Static(t("api_key"), classes="form-label")
                        yield Input(placeholder="sk-...", id="inp-key", password=True)

                        yield Static(t("model_id"), classes="form-label")
                        yield Input(placeholder="gpt-4o, deepseek-v4.1-flash...", id="inp-model")

                        yield Static(t("schema_type"), classes="form-label")
                        yield Select(
                            [
                                ("OpenAI  (GPT, Groq, Ollama, NVIDIA)", "openai"),
                                ("Anthropic  (Claude)", "anthropic"),
                                ("Google  (Gemini)", "google"),
                                ("Custom / Özel", "custom"),
                            ],
                            value="openai",
                            id="sel-schema",
                        )

                        yield Static(t("effort_level"), classes="form-label")
                        yield Select(
                            [
                                (f"🐢 {t('effort_low')}", "low"),
                                (f"⚡ {t('effort_medium')}", "medium"),
                                (f"🔥 {t('effort_high')}", "high"),
                                (f"🧠 {t('effort_extended')}", "extended_thinking"),
                            ],
                            value="medium",
                            id="sel-effort",
                        )

                        with Horizontal(classes="setting-item"):
                            yield Label(t("enabled"), classes="setting-label")
                            yield Switch(value=True, id="sw-enabled")

                        with Horizontal(classes="form-actions"):
                            yield Button(
                                f"💾 {t('save')}",
                                id="btn-save-provider",
                                variant="success",
                            )
                            yield Button(
                                f"❌ {t('cancel')}",
                                id="btn-cancel-provider",
                            )
                            yield Button(
                                f"🗑 {t('remove_provider')}",
                                id="btn-delete-provider",
                                variant="error",
                            )

            # ── Tab 2: Güvenlik / Security ───────────────────────────────
            with TabPane(t("security_title"), id="tab-security"):
                with ScrollableContainer(classes="tab-scroll"):
                    yield Static(t("security_title"), classes="section-title")
                    yield Static(t("security_tools_note"), classes="form-label")
                    for perm_key, emoji in [
                        ("sudo_enabled", "🔐"),
                        ("fs_read", "📖"),
                        ("fs_write", "✏️"),
                        ("fs_delete", "🗑"),
                        ("screen_capture", "🖥️"),
                        ("mouse_control", "🖱️"),
                        ("keyboard_control", "⌨️"),
                        ("gui_automation", "🧩"),
                        ("terminal_enabled", "⌨️"),
                    ]:
                        with Horizontal(classes="setting-item"):
                            yield Label(f"{emoji} {t(perm_key)}", classes="setting-label")
                            yield Switch(id=f"sw-{perm_key}")

                    yield Static(t("allowed_paths"), classes="form-label")
                    yield Input(placeholder="./workspace/, ./projects/", id="inp-paths")
                    yield Button(
                        f"✅ {t('save')}",
                        id="btn-apply-security",
                        variant="primary",
                    )
                    yield Static("", id="sec-status-msg", classes="feedback-msg")

            # ── Tab 3: Müzakere / Deliberation ───────────────────────────
            with TabPane(t("deliberation_title"), id="tab-delib"):
                with ScrollableContainer(classes="tab-scroll"):
                    with Horizontal(classes="setting-item"):
                        yield Label(t("deliberation_enabled"), classes="setting-label")
                        yield Switch(id="sw-delib-enabled")
                    with Horizontal(classes="setting-item"):
                        yield Label(t("show_raw_debate"), classes="setting-label")
                        yield Switch(id="sw-show-debate")
                    yield Static(t("judge_model"), classes="form-label")
                    yield Select(
                        [("Auto / Otomatik", "none")],
                        value="none",
                        id="sel-judge",
                    )
                    # ── Token Limitleri ──
                    yield Static("⚡ Token Limitleri / Token Limits", classes="section-title")
                    yield Static("Faz-1: Her model max kaç token kullansın? (tavsiye: 1000)", classes="form-label")
                    yield Input(value="1000", placeholder="1000", id="inp-delib-max-tokens")
                    yield Static("Faz-2: Hakım sentezi için max token? (tavsiye: 2000)", classes="form-label")
                    yield Input(value="2000", placeholder="2000", id="inp-synth-max-tokens")
                    yield Button(f"💾 {t('save')}", id="btn-save-delib", variant="primary")
                    yield Static("", id="delib-status-msg", classes="feedback-msg")

            # ── Tab 4: Senkronizasyon / Sync Export ──────────────────────
            with TabPane(t("sync_title"), id="tab-sync"):
                with ScrollableContainer(classes="tab-scroll"):
                    yield Static(t("sync_description"), classes="section-title")
                    yield Static(t("sync_password"), classes="form-label")
                    yield Input(placeholder="Min 8 karakter / Min 8 chars", id="inp-sync-pass", password=True)
                    yield Button(f"🔑 {t('sync_generate')}", id="btn-generate-sync", variant="primary")
                    yield TextArea(id="sync-token-display", read_only=True)
                    yield Button(f"📋 {t('sync_copy')}", id="btn-copy-sync")
                    yield Static("", id="sync-status-msg", classes="feedback-msg")

            # ── Tab 5: Genel / General ───────────────────────────────────
            with TabPane(t("settings_title"), id="tab-general"):
                with ScrollableContainer(classes="tab-scroll"):
                    yield Static(t("language"), classes="section-title")
                    with Horizontal(classes="setting-item"):
                        yield Label(f"🌐 {t('language')}", classes="setting-label")
                        yield Button(t("language_toggle"), id="btn-lang-toggle", variant="primary")

                    yield Static(t("memory_path"), classes="section-title")
                    yield Input(placeholder="./memory/memory.json", id="inp-memory-path")
                    yield Button(f"📁 {t('rebind_path')}", id="btn-rebind-path", variant="warning")
                    yield Static("", id="gen-status-msg", classes="feedback-msg")

        yield Footer()

    # ─────────────────────────────────────────────────────────────────
    # Mount
    # ─────────────────────────────────────────────────────────────────

    async def on_mount(self) -> None:
        """Populate initial configuration values."""
        self._editing_provider_id: Optional[str] = None

        # Setup DataTable
        table = self.query_one("#api-table", DataTable)
        table.cursor_type = "row"
        table.add_columns(
            "ID",
            t("provider_name"),
            t("model_id"),
            t("schema_type"),
            t("effort_level"),
            t("enabled"),
        )
        self._refresh_api_table()

        orchestrator = getattr(self.app, "orchestrator", None)
        if orchestrator:
            # Security
            try:
                policy = orchestrator.security.policy
                self.query_one("#sw-sudo_enabled",    Switch).value = policy.sudo_enabled
                self.query_one("#sw-fs_read",         Switch).value = policy.fs_read
                self.query_one("#sw-fs_write",        Switch).value = policy.fs_write
                self.query_one("#sw-fs_delete",       Switch).value = policy.fs_delete
                self.query_one("#sw-screen_capture",  Switch).value = getattr(policy, "screen_capture", False)
                self.query_one("#sw-mouse_control",   Switch).value = getattr(policy, "mouse_control", False)
                self.query_one("#sw-keyboard_control", Switch).value = getattr(policy, "keyboard_control", False)
                self.query_one("#sw-gui_automation",  Switch).value = policy.gui_automation
                self.query_one("#sw-terminal_enabled", Switch).value = getattr(policy, "terminal_enabled", False)
                self.query_one("#inp-paths", Input).value = ", ".join(policy.allowed_paths)
            except Exception:
                pass
            # Deliberation
            try:
                self.query_one("#sw-delib-enabled", Switch).value = orchestrator.deliberation_enabled
                self.query_one("#sw-show-debate",   Switch).value = orchestrator.show_raw_debate
                self._refresh_judge_options()
            except Exception:
                pass
            # Memory path
            try:
                self.query_one("#inp-memory-path", Input).value = str(orchestrator.memory_path)
            except Exception:
                pass

        self.app.i18n.on_language_change(self._on_language_changed)

    def on_unmount(self) -> None:
        """Stop receiving language updates after this screen is removed."""
        self.app.i18n.remove_listener(self._on_language_changed)

    def _on_language_changed(self) -> None:
        """Recompose localized settings labels while preserving entered values."""
        if self.is_attached:
            self.run_worker(
                self._recompose_for_language(),
                name="settings-language-refresh",
                group="language-refresh",
                exclusive=True,
                exit_on_error=False,
            )

    async def _recompose_for_language(self) -> None:
        inputs = {widget.id: widget.value for widget in self.query(Input) if widget.id}
        selects = {widget.id: widget.value for widget in self.query(Select) if widget.id}
        switches = {widget.id: widget.value for widget in self.query(Switch) if widget.id}
        text_areas = {widget.id: widget.text for widget in self.query(TextArea) if widget.id}
        tabbed_content = self.query_one(TabbedContent)
        active_tab = tabbed_content.active
        form_was_hidden = self.query_one("#provider-form").has_class("hidden")

        await self.recompose()

        table = self.query_one("#api-table", DataTable)
        table.cursor_type = "row"
        table.add_columns(
            "ID",
            t("provider_name"),
            t("model_id"),
            t("schema_type"),
            t("effort_level"),
            t("enabled"),
        )
        self._refresh_api_table()
        self._refresh_judge_options()

        for widget_id, value in inputs.items():
            self.query_one(f"#{widget_id}", Input).value = value
        for widget_id, value in selects.items():
            self.query_one(f"#{widget_id}", Select).value = value
        for widget_id, value in switches.items():
            self.query_one(f"#{widget_id}", Switch).value = value
        for widget_id, value in text_areas.items():
            self.query_one(f"#{widget_id}", TextArea).text = value

        if active_tab:
            self.query_one(TabbedContent).active = active_tab
        if form_was_hidden:
            self.query_one("#provider-form").add_class("hidden")

    # ─────────────────────────────────────────────────────────────────
    # Helpers
    # ─────────────────────────────────────────────────────────────────

    def _refresh_api_table(self) -> None:
        """Reload DataTable from APIClient registry."""
        table = self.query_one("#api-table", DataTable)
        table.clear()
        orchestrator = getattr(self.app, "orchestrator", None)
        if not orchestrator:
            return
        lang = I18n().current_language
        yes_lbl = "✔ Evet" if lang == "tr" else "✔ Yes"
        no_lbl  = "✖ Hayır" if lang == "tr" else "✖ No"
        for p in orchestrator.api_client.list_providers():
            table.add_row(
                p.id, p.name, p.model_id,
                p.schema_type.value, p.effort_level.value,
                yes_lbl if p.enabled else no_lbl,
                key=p.id,
            )

    def _refresh_judge_options(self) -> None:
        """Populate judge Select with active providers."""
        orchestrator = getattr(self.app, "orchestrator", None)
        if not orchestrator:
            return
        opts: List[tuple[str, str]] = [("Auto / Otomatik", "none")]
        for p in orchestrator.api_client.list_providers():
            opts.append((f"{p.name}  ({p.model_id})", p.id))
        sel = self.query_one("#sel-judge", Select)
        sel.set_options(opts)
        try:
            sel.value = orchestrator.judge_model or "none"
        except Exception:
            pass

    def _show_form(self, title: str) -> None:
        """Make the provider form visible and scroll to it."""
        self.query_one("#lbl-form-title", Static).update(title)
        form = self.query_one("#provider-form")
        form.remove_class("hidden")
        try:
            form.scroll_visible()
        except Exception:
            pass

    def _hide_form(self) -> None:
        self.query_one("#provider-form").add_class("hidden")
        self._editing_provider_id = None

    # ─────────────────────────────────────────────────────────────────
    # Event: row selected → edit
    # ─────────────────────────────────────────────────────────────────

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """Open edit form when a row is clicked."""
        provider_id = str(event.row_key.value)
        orchestrator = getattr(self.app, "orchestrator", None)
        if not orchestrator:
            return
        p = orchestrator.api_client.get_provider(provider_id)
        if not p:
            return
        self._editing_provider_id = p.id
        self.query_one("#inp-name",  Input).value = p.name
        self.query_one("#inp-url",   Input).value = p.base_url
        self.query_one("#inp-key",   Input).value = p.api_key
        self.query_one("#inp-model", Input).value = p.model_id
        self.query_one("#sel-schema", Select).value = p.schema_type.value
        self.query_one("#sel-effort", Select).value = p.effort_level.value
        self.query_one("#sw-enabled", Switch).value = p.enabled
        self._show_form(f"✏ {t('edit_provider')}: {p.name}")

    # ─────────────────────────────────────────────────────────────────
    # Event: button press router
    # ─────────────────────────────────────────────────────────────────

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        btn = event.button.id
        orch = getattr(self.app, "orchestrator", None)
        lang = I18n().current_language

        # ── API Tab ──────────────────────────────────────────────────
        if btn == "btn-add-provider":
            self._editing_provider_id = None
            self.query_one("#inp-name",  Input).value = ""
            self.query_one("#inp-url",   Input).value = "https://api.openai.com/v1"
            self.query_one("#inp-key",   Input).value = ""
            self.query_one("#inp-model", Input).value = "gpt-4o"
            self.query_one("#sel-schema", Select).value = "openai"
            self.query_one("#sel-effort", Select).value = "medium"
            self.query_one("#sw-enabled", Switch).value = True
            self._show_form(f"➕ {t('add_provider')}")
            self.query_one("#inp-name", Input).focus()

        elif btn == "btn-cancel-provider":
            self._hide_form()

        elif btn == "btn-save-provider":
            try:
                await self._save_provider(lang)
            except Exception as e:
                logger.exception("Unexpected error while saving an AI provider")
                msg = f"Sağlayıcı kaydı sırasında hata: {e}" if lang == "tr" else f"Unexpected provider save error: {e}"
                self.query_one("#api-status-msg", Static).update(f"[bold red]⚠ {msg}[/]")

        elif btn == "btn-delete-provider":
            if self._editing_provider_id and orch:
                orch.api_client.remove_provider(self._editing_provider_id)
                self._hide_form()
                self._refresh_api_table()
                self._refresh_judge_options()
                msg = "Sağlayıcı silindi." if lang == "tr" else "Provider removed."
                self.query_one("#api-status-msg", Static).update(f"[bold red]🗑 {msg}[/]")

        elif btn == "btn-test-all":
            await self._test_all(lang)

        # ── Security Tab ─────────────────────────────────────────────
        elif btn == "btn-apply-security":
            await self._apply_security(lang)

        # ── Deliberation Tab ─────────────────────────────────────────
        elif btn == "btn-save-delib":
            await self._save_deliberation(lang)

        # ── Sync Tab ─────────────────────────────────────────────────
        elif btn == "btn-generate-sync":
            await self._generate_sync(lang)

        elif btn == "btn-copy-sync":
            self._copy_sync(lang)

        # ── General Tab ──────────────────────────────────────────────
        elif btn == "btn-lang-toggle":
            await self.app.action_toggle_language()
            lang2 = I18n().current_language
            lbl = "Türkçe" if lang2 == "tr" else "English"
            self.query_one("#gen-status-msg", Static).update(f"[bold green]✔ {lbl}[/]")

        elif btn == "btn-rebind-path":
            await self._rebind_path(lang)

    # ─────────────────────────────────────────────────────────────────
    # Provider save
    # ─────────────────────────────────────────────────────────────────

    async def _save_provider(self, lang: str) -> None:
        orch = getattr(self.app, "orchestrator", None)
        status = self.query_one("#api-status-msg", Static)
        if not orch:
            try:
                from core.orchestrator import Orchestrator
                orch = Orchestrator()
                await orch.load_settings()
                self.app.orchestrator = orch
            except Exception as e:
                status.update(f"[bold red]⚠ Orchestrator başlatılamadı: {e}[/]")
                return

        if not getattr(orch, "_running", False):
            try:
                await orch.initialize()
            except Exception as e:
                logger.exception("Orchestrator initialization failed while saving a provider")
                msg = f"Orchestrator başlatılamadı: {e}" if lang == "tr" else f"Could not initialize orchestrator: {e}"
                status.update(f"[bold red]⚠ {msg}[/]")
                return

        name  = self.query_one("#inp-name",  Input).value.strip()
        url   = self.query_one("#inp-url",   Input).value.strip()
        key   = self.query_one("#inp-key",   Input).value.strip()
        model = self.query_one("#inp-model", Input).value.strip()

        schema_val = self.query_one("#sel-schema", Select).value
        effort_val = self.query_one("#sel-effort", Select).value
        enabled    = self.query_one("#sw-enabled", Switch).value

        # Validation
        if not name or not url or not model:
            msg = ("Sağlayıcı Adı, Base URL ve Model ID zorunludur."
                   if lang == "tr" else
                   "Provider Name, Base URL and Model ID are required.")
            status.update(f"[bold red]⚠ {msg}[/]")
            return

        # Handle Select.BLANK
        schema_val = str(schema_val) if schema_val and str(schema_val) != "BLANK" else "openai"
        effort_val = str(effort_val) if effort_val and str(effort_val) != "BLANK" else "medium"

        prov_id = (self._editing_provider_id or
                   "_".join(part for part in (name.lower().replace(" ", "_").replace("-", "_"), model.lower().replace(" ", "_").replace("-", "_")) if part))

        try:
            provider = AIProvider(
                id=prov_id,
                name=name,
                base_url=url,
                api_key=key,
                model_id=model,
                schema_type=SchemaType(schema_val),
                effort_level=EffortLevel(effort_val),
                enabled=enabled,
            )
            APIClient._validate_provider_url(provider)
            orch.api_client.add_provider(provider)
            await orch.save_settings()
        except Exception as e:
            status.update(f"[bold red]⚠ Kayıt hatası: {e}[/]")
            return

        try:
            self._hide_form()
            self._refresh_api_table()
            self._refresh_judge_options()
        except Exception as e:
            logger.exception("Provider was saved but the settings view could not refresh")
            msg = f"Sağlayıcı kaydedildi ancak ekran güncellenemedi: {e}" if lang == "tr" else f"Provider saved, but the view could not refresh: {e}"
            status.update(f"[bold yellow]⚠ {msg}[/]")
            return

        msg = (f"'{name}' başarıyla kaydedildi ve ayarlara işlendi." if lang == "tr"
               else f"Provider '{name}' saved successfully and persisted to settings.")
        status.update(f"[bold green]✔ {msg}[/]")

    # ─────────────────────────────────────────────────────────────────
    # Other handlers
    # ─────────────────────────────────────────────────────────────────

    async def _test_all(self, lang: str) -> None:
        orch = getattr(self.app, "orchestrator", None)
        st = self.query_one("#api-status-msg", Static)
        if not orch:
            return
        msg = "Test ediliyor..." if lang == "tr" else "Testing connections..."
        st.update(f"[bold yellow]🔍 {msg}[/]")
        try:
            results = await orch.api_client.health_check_all()
            ok = sum(1 for r in results if r.status == "ok")
            fail = len(results) - ok
            if lang == "tr":
                summary = f"{len(results)} sağlayıcı: {ok} Başarılı, {fail} Hata"
            else:
                summary = f"{len(results)} providers: {ok} OK, {fail} Failed"
            st.update(f"[bold cyan]{summary}[/]")
        except Exception as e:
            st.update(f"[bold red]⚠ {e}[/]")

    async def _apply_security(self, lang: str) -> None:
        orch = getattr(self.app, "orchestrator", None)
        if not orch:
            return
        paths_raw = self.query_one("#inp-paths", Input).value
        paths = [p.strip() for p in paths_raw.split(",") if p.strip()]
        orch.security.update_policy(
            sudo_enabled=self.query_one("#sw-sudo_enabled",     Switch).value,
            fs_read     =self.query_one("#sw-fs_read",          Switch).value,
            fs_write    =self.query_one("#sw-fs_write",         Switch).value,
            fs_delete   =self.query_one("#sw-fs_delete",        Switch).value,
            screen_capture=self.query_one("#sw-screen_capture",  Switch).value,
            mouse_control=self.query_one("#sw-mouse_control",   Switch).value,
            keyboard_control=self.query_one("#sw-keyboard_control", Switch).value,
            gui_automation=self.query_one("#sw-gui_automation",  Switch).value,
            terminal_enabled=self.query_one("#sw-terminal_enabled", Switch).value,
            allowed_paths=paths or ["./workspace/"],
        )
        summary = orch.security.get_status_summary()
        status = self.query_one("#sec-status-msg", Static)
        try:
            await orch.save_settings()
        except OSError as exc:
            logger.exception("Failed to save security settings")
            msg = f"İzinler uygulandı ancak kaydedilemedi: {exc}" if lang == "tr" else f"Permissions applied but could not be saved: {exc}"
            status.update(f"[bold red]⚠ {msg}[/]")
            return
        msg = f"Güvenlik ayarları kaydedildi: {summary}" if lang == "tr" else f"Security settings saved: {summary}"
        status.update(f"[bold green]✔ {msg}[/]")

    async def _save_deliberation(self, lang: str) -> None:
        orch = getattr(self.app, "orchestrator", None)
        if not orch:
            return
        orch.deliberation_enabled = self.query_one("#sw-delib-enabled", Switch).value
        orch.show_raw_debate      = self.query_one("#sw-show-debate",   Switch).value
        judge_val = self.query_one("#sel-judge", Select).value
        orch.judge_model = None if str(judge_val) in ("none", "BLANK") else str(judge_val)
        status = self.query_one("#delib-status-msg", Static)
        try:
            await orch.save_settings()
        except OSError as exc:
            logger.exception("Failed to save deliberation settings")
            msg = f"Müzakere ayarları kaydedilemedi: {exc}" if lang == "tr" else f"Deliberation settings could not be saved: {exc}"
            status.update(f"[bold red]⚠ {msg}[/]")
            return
        msg = "Müzakere ayarları kaydedildi." if lang == "tr" else "Deliberation settings saved."
        status.update(f"[bold green]✔ {msg}[/]")

    async def _generate_sync(self, lang: str) -> None:
        orch = getattr(self.app, "orchestrator", None)
        st = self.query_one("#sync-status-msg", Static)
        if not orch:
            return
        passphrase = self.query_one("#inp-sync-pass", Input).value.strip()
        if len(passphrase) < 8:
            msg = "Parola en az 8 karakter olmalı." if lang == "tr" else "Passphrase must be ≥8 chars."
            st.update(f"[bold red]⚠ {msg}[/]")
            return
        try:
            token = orch.generate_sync_token(passphrase)
            self.query_one("#sync-token-display", TextArea).text = token
            msg = "Token oluşturuldu." if lang == "tr" else "Sync token generated."
            st.update(f"[bold green]✔ {msg}[/]")
        except Exception as e:
            st.update(f"[bold red]⚠ {e}[/]")

    def _copy_sync(self, lang: str) -> None:
        st = self.query_one("#sync-status-msg", Static)
        token = self.query_one("#sync-token-display", TextArea).text.strip()
        if not token:
            msg = "Önce token oluşturun." if lang == "tr" else "Generate a token first."
            st.update(f"[bold yellow]⚠ {msg}[/]")
            return
        try:
            self.app.copy_to_clipboard(token)
        except Exception:
            pass
        msg = "Token kopyalandı." if lang == "tr" else "Token copied."
        st.update(f"[bold green]✔ {msg}[/]")

    async def _rebind_path(self, lang: str) -> None:
        orch = getattr(self.app, "orchestrator", None)
        if not orch:
            return
        path = self.query_one("#inp-memory-path", Input).value.strip()
        if not path:
            return
        try:
            orch.memory_path = path
            await orch.memory_engine.load(path)
            msg = f"Hafıza: {path}" if lang == "tr" else f"Memory reloaded: {path}"
            self.query_one("#gen-status-msg", Static).update(f"[bold green]✔ {msg}[/]")
        except Exception as e:
            self.query_one("#gen-status-msg", Static).update(f"[bold red]⚠ {e}[/]")
