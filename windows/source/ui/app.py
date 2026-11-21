"""Root Textual Application for Multi-AI Orchestrator.

The main TUI entry point that wires together the Orchestrator, screens,
and global keybindings. Handles async initialization, language toggling,
and graceful shutdown.
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys
from pathlib import Path
from typing import Any

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.widgets import Header, Footer, Static, LoadingIndicator
from textual.containers import Container, Vertical
from textual.screen import Screen

from ui.i18n import I18n, t
from ui.screens.main_screen import MainScreen
from ui.screens.settings_screen import SettingsScreen
from ui.screens.memory_screen import MemoryScreen

logger = logging.getLogger("orchestrator.ui")


# ──────────────────────────────────────────────────────────────────
# Splash / Loading Screen
# ──────────────────────────────────────────────────────────────────

class SplashScreen(Screen):
    """Initial splash screen shown while the orchestrator initializes."""

    DEFAULT_CSS = """
    SplashScreen {
        background: #0a0e27;
        align: center middle;
    }
    #splash-box {
        width: 60;
        height: 16;
        border: round #7c3aed;
        background: #111638;
        padding: 2 4;
        content-align: center middle;
    }
    #splash-title {
        text-align: center;
        color: #7c3aed;
        text-style: bold;
        margin-bottom: 1;
    }
    #splash-subtitle {
        text-align: center;
        color: #94a3b8;
        margin-bottom: 1;
    }
    #splash-status {
        text-align: center;
        color: #06b6d4;
        margin-top: 1;
    }
    LoadingIndicator {
        height: 3;
        color: #7c3aed;
    }
    """

    def compose(self) -> ComposeResult:
        with Vertical(id="splash-box"):
            yield Static(
                "🤖  AI Orchestrator  🤖",
                id="splash-title",
            )
            yield Static(
                "Multi-AI Coordination Platform\nÇoklu AI Koordinasyon Platformu",
                id="splash-subtitle",
            )
            yield LoadingIndicator()
            yield Static("Başlatılıyor... / Initializing...", id="splash-status")


# ──────────────────────────────────────────────────────────────────
# Main Application
# ──────────────────────────────────────────────────────────────────

class OrchestratorApp(App):
    """Multi-AI Orchestrator TUI Application.

    Root Textual app that manages screen navigation, orchestrator lifecycle,
    global keybindings, and bilingual language support.
    """

    TITLE = "AI Orchestrator"
    SUB_TITLE = "Multi-AI Coordination Platform"

    # Load theme CSS from the styles.tcss file alongside this module
    CSS_PATH = "styles.tcss"

    # Bindings — descriptions update dynamically via _refresh_bindings
    BINDINGS = [
        Binding("ctrl+c", "open_chat", "Sohbet / Chat", show=True, priority=True),
        Binding("ctrl+s", "open_settings", "Ayarlar / Settings", show=True, priority=True),
        Binding("ctrl+m", "open_memory", "Hafıza / Memory", show=True, priority=True),
        Binding("ctrl+l", "toggle_language", "TR ↔ EN", show=True, priority=True),
        Binding("ctrl+d", "toggle_deliberation", "Müzakere / Delib.", show=True, priority=True),
        Binding("ctrl+q", "quit_app", "Çıkış / Quit", show=True, priority=True),
    ]

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.orchestrator = None
        self.i18n = I18n()
        self._initialized = False
        # Register language change listener to refresh bindings
        self.i18n.on_language_change(self._on_language_changed)

    def compose(self) -> ComposeResult:
        """Compose the root layout. Screens handle their own composition."""
        yield Header(show_clock=True)
        yield Footer()

    async def on_mount(self) -> None:
        """Initialize the orchestrator on app mount and transition to the main screen."""

        # Show splash screen first
        splash = SplashScreen()
        await self.push_screen(splash)

        # Initialize orchestrator in the background
        try:
            await self._initialize_orchestrator(splash)
        except Exception as exc:
            logger.error("Failed to initialize orchestrator: %s", exc, exc_info=True)
            self.notify(
                f"⚠ {t('error')}: {exc}",
                severity="warning",
                timeout=5,
            )

        # Pop splash and push main screen
        self.pop_screen()
        await self.push_screen(MainScreen())
        self._initialized = True

    async def _initialize_orchestrator(self, splash: SplashScreen) -> None:
        """Boot the orchestrator subsystem."""
        project_root = str(Path(__file__).resolve().parent.parent)
        if project_root not in sys.path:
            sys.path.insert(0, project_root)

        splash_status = splash.query_one("#splash-status", Static)

        splash_status.update(t("connecting") if t("connecting") != "connecting" else "Yükleniyor...")
        await asyncio.sleep(0.1)

        from core.orchestrator import Orchestrator

        self.orchestrator = Orchestrator()

        splash_status.update("API istemcileri başlatılıyor... / Initializing API clients...")
        await asyncio.sleep(0.1)

        await self.orchestrator.initialize()

        splash_status.update("Hazır! ✓ / Ready! ✓")
        await asyncio.sleep(0.3)

    # ──────────────────────────────────────────────────────────────
    # Language-aware title refresh
    # ──────────────────────────────────────────────────────────────

    def _on_language_changed(self) -> None:
        """Callback invoked when the I18n language toggles — updates title bar."""
        lang = self.i18n.current_language
        if lang == "tr":
            self.title = "AI Orkestratör"
            self.sub_title = "Çoklu AI Koordinasyon Platformu"
        else:
            self.title = "AI Orchestrator"
            self.sub_title = "Multi-AI Coordination Platform"

        # Refresh root app bindings
        lang = self.i18n.current_language
        if lang == "tr":
            self.bindings = [
                Binding("ctrl+c", "open_chat", "Sohbet", show=True, priority=True),
                Binding("ctrl+s", "open_settings", "Ayarlar", show=True, priority=True),
                Binding("ctrl+m", "open_memory", "Hafıza", show=True, priority=True),
                Binding("ctrl+l", "toggle_language", "Türkçe ↔ English", show=True, priority=True),
                Binding("ctrl+d", "toggle_deliberation", "Müzakere", show=True, priority=True),
                Binding("ctrl+q", "quit_app", "Çıkış", show=True, priority=True),
            ]
        else:
            self.bindings = [
                Binding("ctrl+c", "open_chat", "Chat", show=True, priority=True),
                Binding("ctrl+s", "open_settings", "Settings", show=True, priority=True),
                Binding("ctrl+m", "open_memory", "Memory", show=True, priority=True),
                Binding("ctrl+l", "toggle_language", "EN ↔ Türkçe", show=True, priority=True),
                Binding("ctrl+d", "toggle_deliberation", "Deliberation", show=True, priority=True),
                Binding("ctrl+q", "quit_app", "Quit", show=True, priority=True),
            ]
        try:
            self.refresh_bindings()
        except Exception:
            pass

    # ──────────────────────────────────────────────────────────────
    # Actions (bound to global keys)
    async def action_open_chat(self) -> None:
        """Return to the main chat workspace from any sub-screen."""
        if not self._initialized:
            return
        while len(self.screen_stack) > 1 and not isinstance(self.screen, MainScreen):
            self.pop_screen()
        if isinstance(self.screen, MainScreen):
            self.screen.refresh_chat_state()


    # ──────────────────────────────────────────────────────────────

    async def action_open_settings(self) -> None:
        """Push the settings screen."""
        if not self._initialized:
            return
        await self.push_screen(SettingsScreen())

    async def action_open_memory(self) -> None:
        """Push the memory browser screen."""
        if not self._initialized:
            return
        await self.push_screen(MemoryScreen())

    async def action_toggle_language(self) -> None:
        """Toggle between Turkish and English UI."""
        self.i18n.toggle_language()
        lang = self.i18n.current_language
        lang_label = "Türkçe'ye geçildi" if lang == "tr" else "Switched to English"
        self.notify(f"🌐 {lang_label}", timeout=2)

    async def action_toggle_deliberation(self) -> None:
        """Toggle multi-model deliberation from the main chat screen."""
        if not self._initialized:
            return
        current = self.screen
        if isinstance(current, MainScreen):
            enabled = await current.toggle_deliberation()
            if self.i18n.current_language == "tr":
                state = "AÇIK" if enabled else "KAPALI"
                self.notify(f"🔄 Müzakere modu: {state}", timeout=2)
            else:
                state = "ON" if enabled else "OFF"
                self.notify(f"🔄 Deliberation mode: {state}", timeout=2)

    async def action_quit_app(self) -> None:
        """Graceful shutdown and quit."""
        if self.orchestrator:
            try:
                await self.orchestrator.shutdown()
            except Exception as exc:
                logger.error("Error during shutdown: %s", exc)
        self.exit()

    # ──────────────────────────────────────────────────────────────
    # Orchestrator access helpers
    # ──────────────────────────────────────────────────────────────

    def get_orchestrator(self):
        """Get the orchestrator instance, if initialized."""
        return self.orchestrator

    def is_initialized(self) -> bool:
        """Check if the application is fully initialized."""
        return self._initialized and self.orchestrator is not None


# ──────────────────────────────────────────────────────────────────
# Entry point
# ──────────────────────────────────────────────────────────────────

def run():
    """Launch the AI Orchestrator TUI application."""
    project_root = Path(__file__).resolve().parent.parent
    os.chdir(project_root)
    log_dir = project_root / "logs"
    log_dir.mkdir(exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        handlers=[
            logging.FileHandler(log_dir / "orchestrator.log", encoding="utf-8"),
        ],
    )
    # httpx logs complete request URLs at INFO; some providers put API keys in query strings.
    logging.getLogger("httpx").setLevel(logging.WARNING)

    app = OrchestratorApp()
    app.run()


if __name__ == "__main__":
    run()
