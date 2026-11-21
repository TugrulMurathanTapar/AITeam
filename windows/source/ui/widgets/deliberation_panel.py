"""Deliberation panel widget displaying live AI debate events and consensus."""

from __future__ import annotations

from typing import Any, Dict

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import RichLog, Static

from ui.i18n import t


class DeliberationPanel(Vertical):
    """Collapsible panel showing raw AI-to-AI deliberation and judge synthesis."""

    DEFAULT_CSS = """
    DeliberationPanel {
        width: 1fr;
        height: 100%;
        border: round #06b6d4;
        background: #0f1235;
        padding: 1;
    }
    #delib-header {
        text-style: bold;
        color: #06b6d4;
        margin-bottom: 1;
    }
    #delib-log {
        height: 1fr;
        background: #090c24;
        border: solid #1e293b;
    }
    """

    def compose(self) -> ComposeResult:
        """Compose deliberation header and rich log widget."""
        title = t("deliberation_panel")
        yield Static(f"🔄 {title}", id="delib-title")
        yield RichLog(id="deliberation-log", wrap=True, highlight=True, max_lines=500)

    def add_event(self, event_type: str, data: Dict[str, Any]) -> None:
        """Process and append an orchestrator event to the live log."""
        if not hasattr(self, "_events"):
            self._events: list[tuple[str, Dict[str, Any]]] = []
        self._events.append((event_type, dict(data)))
        del self._events[:-500]
        self._render_event(event_type, data)

    def _render_event(self, event_type: str, data: Dict[str, Any]) -> None:
        """Render one event using the currently selected language."""
        try:
            log = self.query_one("#deliberation-log", RichLog)
        except Exception:
            try:
                log = self.query_one(RichLog)
            except Exception:
                return

        if event_type == "deliberation_start":
            models = data.get("models", [])
            model_list = ", ".join(models) if models else t("unknown")
            log.write(f"[bold yellow]⚡ {t('deliberation_started_with', models=model_list)}[/]")
        elif event_type == "deliberation_response":
            model = data.get("model", "Model")
            content = data.get("content") or data.get("error") or t("no_response")
            log.write(f"[bold cyan]📝 {model}:[/] {content}")
        elif event_type == "deliberation_synthesis":
            judge = data.get("judge", "Judge")
            log.write(f"[bold green]🧑‍⚖️ {judge}: {t('judge_synthesizing')}[/]")
        elif event_type == "deliberation_end":
            time_ms = data.get("total_time_ms", 0)
            formatted_ms = f"{time_ms:.0f}"
            log.write(f"[bold green]✅ {t('deliberation_consensus_in', ms=formatted_ms)}[/]")
        else:
            log.write(f"[dim]ℹ {t('event_details', event_type=event_type, data=data)}[/]")

    def clear_log(self) -> None:
        """Clear all logged events."""
        try:
            self.query_one("#delib-log", RichLog).clear()
        except Exception:
            pass

    def update_language(self) -> None:
        """Update the title and re-render retained events in the new language."""
        try:
            header = self.query_one("#delib-title", Static)
            title = t("deliberation_panel")
            header.update(f"🔄 {title}")
            log = self.query_one("#deliberation-log", RichLog)
            log.clear()
            for event_type, data in getattr(self, "_events", []):
                self._render_event(event_type, data)
        except Exception:
            pass
