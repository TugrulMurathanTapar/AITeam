"""Main screen providing interactive chat, prompt execution, and deliberation tracking."""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Optional

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Button, Footer, Header, Input, Label, Select, Static, Switch

from ui.i18n import t
from ui.widgets.chat_panel import ChatPanel
from ui.widgets.deliberation_panel import DeliberationPanel
from ui.widgets.status_bar import StatusBar

if TYPE_CHECKING:
    from core.orchestrator import OrchestratorEvent


class MainScreen(Screen):
    """Primary chat workspace with direct-model and deliberation controls."""

    BINDINGS = [
        Binding("escape", "app.pop_screen", "Back"),
    ]

    def compose(self) -> ComposeResult:
        """Compose the primary workspace layout."""
        yield Header()
        with Horizontal(id="main-layout"):
            with Vertical(id="chat-area"):
                yield ChatPanel(id="chat-scroll")
                with Horizontal(id="input-bar"):
                    yield Input(
                        placeholder=t("chat_placeholder"),
                        id="chat-input",
                    )
                    yield Button(t("send"), id="send-btn", variant="primary")
                yield Static("", id="chat-request-status", classes="hidden")

            with Vertical(id="chat-sidebar"):
                yield Static(t("chat_mode"), classes="sidebar-title")
                with Horizontal(id="deliberation-control"):
                    yield Label(t("chat_deliberation"))
                    yield Switch(id="deliberation-toggle")
                yield Static("", id="chat-mode-hint", classes="sidebar-hint")
                yield Label(t("chat_model"), id="chat-model-label")
                yield Select(
                    [],
                    prompt=t("chat_no_models"),
                    allow_blank=True,
                    id="chat-model-select",
                )
                yield DeliberationPanel(id="deliberation-panel")

        yield StatusBar(id="status-bar")
        yield Footer()

    async def on_mount(self) -> None:
        """Initialize event listeners, restore status, and sync display state."""
        self._request_active = False
        self._request_stage = "thinking"
        self._request_tool_name = ""
        self._request_started_at = 0.0
        self._request_timer = None

        # Initial welcome message in chat
        chat = self.query_one("#chat-scroll", ChatPanel)
        chat.add_message("system", self._welcome_text())

        # Register event listeners with orchestrator if available
        if hasattr(self.app, "orchestrator") and self.app.orchestrator:
            orchestrator = self.app.orchestrator
            orchestrator.add_event_listener(self._handle_orchestrator_event)
            for message in orchestrator.get_chat_history():
                if message.role in ("user", "assistant"):
                    role = "error" if message.metadata.get("error") else message.role
                    chat.add_message(role, message.content, message.model_name)

        # Register i18n change listener
        if hasattr(self.app, "i18n") and self.app.i18n:
            self.app.i18n.on_language_change(self._on_language_changed)
        self.refresh_chat_state()
        self.call_after_refresh(self.query_one("#chat-input", Input).focus)

    def on_unmount(self) -> None:
        """Cleanup listener registrations when screen unmounts."""
        if hasattr(self.app, "orchestrator") and self.app.orchestrator:
            self.app.orchestrator.remove_event_listener(self._handle_orchestrator_event)
        if hasattr(self.app, "i18n") and self.app.i18n:
            self.app.i18n.remove_listener(self._on_language_changed)

    def _handle_orchestrator_event(self, event: OrchestratorEvent) -> None:
        """Route orchestrator deliberation events into the deliberation panel."""
        if self._request_active and event.event_type == "tool_start":
            self._request_stage = "tool"
            self._request_tool_name = str(event.data.get("tool_name", ""))
            self._update_request_status()
        elif self._request_active and event.event_type == "tool_end":
            self._request_stage = "thinking"
            self._request_tool_name = ""
            self._update_request_status()
        try:
            panel = self.query_one("#deliberation-panel", DeliberationPanel)
            panel.add_event(event.event_type, event.data)
        except Exception:
            pass

    def _refresh_model_choices(self) -> None:
        """Populate the direct-chat model selector from enabled providers."""
        orchestrator = getattr(self.app, "orchestrator", None)
        if orchestrator is None:
            return

        model_select = self.query_one("#chat-model-select", Select)
        active_providers = orchestrator.api_client.get_active_providers()
        options = [
            (f"{provider.name} · {provider.model_id}", provider.id)
            for provider in active_providers
        ]
        selected_id = model_select.value
        if selected_id not in {provider.id for provider in active_providers}:
            selected_id = active_providers[0].id if active_providers else Select.NULL
        model_select.set_options(options)
        if selected_id is not Select.NULL:
            model_select.value = selected_id
        model_select.disabled = not options

    def refresh_chat_state(self) -> None:
        """Refresh model choices and response controls when returning to chat."""
        orchestrator = getattr(self.app, "orchestrator", None)
        if orchestrator is None:
            return

        self._refresh_model_choices()
        active_count = len(orchestrator.api_client.get_active_providers())
        toggle = self.query_one("#deliberation-toggle", Switch)
        toggle.disabled = active_count < 2
        toggle.value = orchestrator.deliberation_enabled and active_count > 1
        self._sync_chat_mode()
        self._update_status_bar()
        self.call_after_refresh(self.query_one("#chat-input", Input).focus)

    def _sync_chat_mode(self) -> None:
        """Show model selection for direct chat or live debate for deliberation."""
        try:
            enabled = self.query_one("#deliberation-toggle", Switch).value
            selector = self.query_one("#chat-model-select", Select)
            self.query_one("#chat-model-label", Label).display = not enabled
            selector.display = not enabled
            self.query_one("#chat-mode-hint", Static).update(
                t("chat_debate_hint") if enabled else t("chat_direct_hint")
            )
            self.query_one("#deliberation-panel", DeliberationPanel).display = enabled
        except Exception:
            pass

    def _on_language_changed(self) -> None:
        """Update interface labels and placeholders on language change."""
        try:
            chat = self.query_one("#chat-scroll", ChatPanel)
            chat.update_welcome_message(self._welcome_text())
            inp = self.query_one("#chat-input", Input)
            inp.placeholder = t("chat_placeholder")
            btn = self.query_one("#send-btn", Button)
            btn.label = t("send")
            self.query_one("#chat-model-label", Label).update(t("chat_model"))
            self.query_one(".sidebar-title", Static).update(t("chat_mode"))
            self.query_one("#deliberation-control Label", Label).update(t("chat_deliberation"))
            self.query_one("#chat-model-select", Select).prompt = t("chat_no_models")
            self._refresh_model_choices()
            self._sync_chat_mode()
            if self._request_active:
                self._update_request_status()
            self._update_status_bar()
            panel = self.query_one("#deliberation-panel", DeliberationPanel)
            panel.update_language()
        except Exception:
            pass

    def _welcome_text(self) -> str:
        """Build the localized first-run message for the main chat panel."""
        lang = getattr(self.app, "i18n", None) and self.app.i18n.current_language or "en"
        lines = [f"**{t('app_title')}** — {t('app_subtitle')}", t("empty_chat_hint"), ""]
        if lang == "tr":
            lines.extend([
                "- `Ctrl+S` tuşuna basarak **Ayarlar** ekranını açın (API Anahtarları ve Güvenlik)",
                "- `Ctrl+M` tuşuna basarak **Hafıza** tarayıcısını açın",
                "- Sağ panelden **AI müzakeresini** açın veya doğrudan yanıt için model seçin",
                "- `Ctrl+D` tuşuyla müzakere modunu açıp kapatın",
                "- `Ctrl+L` tuşuna basarak **Dil** değiştirin (TR/EN)",
            ])
        else:
            lines.extend([
                "- Press `Ctrl+S` to open **Settings** (API Keys & Security)",
                "- Press `Ctrl+M` to browse **Memory** (Core & Sub-Memories)",
                "- Use the **right sidebar** to enable deliberation or choose a direct-response model",
                "- Press `Ctrl+D` to toggle multi-AI deliberation",
                "- Press `Ctrl+L` to toggle **Language** (TR/EN)",
            ])
        return "\n\n".join(lines)

    def _update_status_bar(self) -> None:
        """Refresh the status bar state."""
        try:
            status_bar = self.query_one("#status-bar", StatusBar)
            status_bar.update_from_orchestrator(getattr(self.app, "orchestrator", None))
        except Exception:
            pass

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button press events."""
        if event.button.id == "send-btn":
            await self._send_message()

    async def on_switch_changed(self, event: Switch.Changed) -> None:
        """Persist the conversation's response mode and update the sidebar."""
        if event.switch.id != "deliberation-toggle":
            return
        await self.set_deliberation_enabled(event.value)

    async def set_deliberation_enabled(self, enabled: bool) -> None:
        """Set and persist the conversation's multi-model response mode."""
        orchestrator = getattr(self.app, "orchestrator", None)
        if orchestrator is None:
            return
        orchestrator.deliberation_enabled = enabled
        toggle = self.query_one("#deliberation-toggle", Switch)
        with toggle.prevent(Switch.Changed):
            toggle.value = enabled
        self._sync_chat_mode()
        try:
            await orchestrator.save_settings()
        except OSError as exc:
            self.app.notify(f"{t('status_error')}: {exc}", severity="error")

    async def toggle_deliberation(self) -> bool:
        """Toggle deliberation from the keyboard shortcut when multiple models exist."""
        switch = self.query_one("#deliberation-toggle", Switch)
        if switch.disabled:
            return False
        await self.set_deliberation_enabled(not switch.value)
        return switch.value

    def on_select_changed(self, event: Select.Changed) -> None:
        """Keep the selected direct-response model available for chat requests."""
        if event.select.id == "chat-model-select":
            self._sync_chat_mode()

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle enter submission in chat input."""
        if event.input.id == "chat-input":
            await self._send_message()

    async def _send_message(self) -> None:
        """Dispatch user message to orchestrator and display responses."""
        if getattr(self, "_request_active", False):
            return

        input_widget = self.query_one("#chat-input", Input)
        message = input_widget.value.strip()
        if not message:
            return
        input_widget.value = ""

        # Display user message
        self._add_message("user", message)

        orchestrator = getattr(self.app, "orchestrator", None)
        if orchestrator is None:
            self._add_message("error", "Orchestrator instance is not initialized.")
            return

        send_button = self.query_one("#send-btn", Button)
        model_select = self.query_one("#chat-model-select", Select)
        deliberation_toggle = self.query_one("#deliberation-toggle", Switch)
        status = self.query_one("#chat-request-status", Static)
        self._request_active = True
        self._request_stage = "thinking"
        self._request_tool_name = ""
        self._request_started_at = time.perf_counter()
        status.remove_class("hidden")
        input_widget.disabled = True
        send_button.disabled = True
        model_select.disabled = True
        deliberation_toggle.disabled = True
        self._update_request_status()
        self._request_timer = self.set_interval(1, self._update_request_status)
        failed = False

        try:
            selected_provider = (
                model_select.value
                if not deliberation_toggle.value
                and model_select.value is not Select.NULL
                else None
            )
            response = await orchestrator.process_message(
                message,
                provider_id=selected_provider,
            )
            failed = response.startswith("API Error (")
            self._add_message("error" if failed else "assistant", response)
        except Exception as exc:
            failed = True
            self._add_message("error", f"{t('status_error') if t('status_error') != 'status_error' else 'Error'}: {exc}")
        finally:
            elapsed = int(time.perf_counter() - self._request_started_at)
            if self._request_timer is not None:
                self._request_timer.stop()
                self._request_timer = None
            self._request_active = False
            self._request_stage = "thinking"
            self._request_tool_name = ""
            input_widget.disabled = False
            send_button.disabled = False
            self.refresh_chat_state()
            status.update(
                t("chat_request_failed" if failed else "chat_request_done").format(
                    elapsed=elapsed,
                )
            )
            self._update_status_bar()

    def _update_request_status(self) -> None:
        """Refresh the visible request stage and elapsed duration."""
        if not getattr(self, "_request_active", False):
            return
        elapsed = int(time.perf_counter() - self._request_started_at)
        hhmmss = f"{elapsed // 3600:02d}:{elapsed // 60 % 60:02d}:{elapsed % 60:02d}"
        if self._request_stage == "tool" and self._request_tool_name:
            text = t(
                "chat_tool_working",
                tool=self._request_tool_name,
                elapsed=elapsed,
                hhmmss=hhmmss,
            )
        else:
            text = t("chat_working", elapsed=elapsed, hhmmss=hhmmss)
        self.query_one("#chat-request-status", Static).update(text)

    def _add_message(self, role: str, content: str, model_name: Optional[str] = None) -> None:
        """Add a styled message bubble to the chat area."""
        chat_scroll = self.query_one("#chat-scroll", ChatPanel)
        chat_scroll.add_message(role=role, content=content, model_name=model_name)
