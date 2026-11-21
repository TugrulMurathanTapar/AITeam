"""Sync export widget for generating zero-knowledge encrypted tokens."""

from __future__ import annotations

from typing import Any

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Button, Input, Static, TextArea

from ui.i18n import t


class SyncExport(Vertical):
    """Encrypted sync token generator and display widget."""

    DEFAULT_CSS = """
    SyncExport {
        height: auto;
        padding: 1;
        background: #111638;
        border: round #7c3aed;
    }
    #sync-title {
        text-style: bold;
        color: #06b6d4;
        margin-bottom: 1;
    }
    #sync-desc {
        color: #94a3b8;
        margin-bottom: 1;
    }
    #sync-passphrase {
        margin: 1 0;
    }
    #sync-output {
        height: 6;
        margin: 1 0;
        background: #0a0e27;
        border: tall #7c3aed;
    }
    #sync-status-msg {
        color: #10b981;
        margin-top: 1;
    }
    """

    def compose(self) -> ComposeResult:
        """Compose the sync export interface components."""
        yield Static(t("sync_title"), id="sync-title")
        yield Static(t("sync_description"), id="sync-desc")
        yield Input(
            placeholder=t("sync_password"),
            id="sync-passphrase",
            password=True,
        )
        with Horizontal():
            yield Button(t("sync_generate"), id="btn-gen-sync", variant="primary")
            yield Button(t("sync_copy"), id="btn-copy-sync", variant="default")
        yield TextArea(id="sync-output", read_only=True)
        yield Static("", id="sync-status-msg")

    async def generate_token(self, orchestrator: Any) -> None:
        """Generate AES-256-GCM token from orchestrator state and display it."""
        inp = self.query_one("#sync-passphrase", Input)
        passphrase = inp.value.strip()
        status_lbl = self.query_one("#sync-status-msg", Static)

        if not passphrase:
            status_lbl.update(f"[bold red]⚠ {t('sync_passphrase_hint')}[/]")
            return

        if len(passphrase) < 8:
            status_lbl.update(f"[bold red]⚠ {t('sync_passphrase_min_len')}[/]")
            return

        try:
            token = orchestrator.generate_sync_token(passphrase)
            out = self.query_one("#sync-output", TextArea)
            out.text = token
            status_lbl.update(f"[bold green]✔ {t('sync_token_generated')}[/]")
        except Exception as exc:
            status_lbl.update(f"[bold red]⚠ {t('sync_error')}: {exc}[/]")

    def copy_token(self) -> None:
        """Copy the generated sync token to the clipboard or notification."""
        out = self.query_one("#sync-output", TextArea)
        token = out.text.strip()
        status_lbl = self.query_one("#sync-status-msg", Static)

        if not token:
            status_lbl.update("[bold yellow]⚠ No token generated yet.[/]")
            return

        try:
            if hasattr(self.app, "copy_to_clipboard"):
                self.app.copy_to_clipboard(token)
            status_lbl.update(f"[bold green]✔ {t('sync_token_copied')}[/]")
        except Exception:
            status_lbl.update("[bold green]✔ Token ready in text area for manual copying.[/]")
