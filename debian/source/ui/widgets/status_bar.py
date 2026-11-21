"""Status bar widget displaying system health, active models, and security posture."""

from __future__ import annotations

from typing import Any, Optional

from textual.reactive import reactive
from textual.widgets import Static

from ui.i18n import t


class StatusBar(Static):
    """Status bar displaying active models, selected memory workspace, and permissions."""

    DEFAULT_CSS = """
    StatusBar {
        dock: bottom;
        height: 1;
        background: #111638;
        color: #94a3b8;
        padding: 0 2;
    }
    """

    active_models = reactive("")
    current_memory = reactive("")
    permissions = reactive("")

    def render(self) -> str:
        """Render the status bar contents."""
        lbl_models = t("active_models")
        lbl_memory = t("current_memory")
        models_str = self.active_models or t("no_models")
        memory_str = self.current_memory or t("no_memory")
        perms_str = self.permissions or "🔒 Policy Guarded"

        return f"{lbl_models}: {models_str} | {lbl_memory}: {memory_str} | {perms_str}"

    def update_from_orchestrator(self, orchestrator: Any) -> None:
        """Update reactive state fields using current orchestrator status.

        Args:
            orchestrator: The central Orchestrator instance.
        """
        if orchestrator is None:
            self.active_models = t("no_models")
            self.current_memory = t("no_memory")
            self.permissions = "🔒 Guarded"
            return

        try:
            # 1. Active models
            active_providers = orchestrator.api_client.get_active_providers()
            if active_providers:
                names = [p.name for p in active_providers]
                if len(names) <= 3:
                    self.active_models = f"{len(names)} ({', '.join(names)})"
                else:
                    self.active_models = f"{len(names)} ({', '.join(names[:2])} +{len(names)-2})"
            else:
                self.active_models = t("no_models")

            # 2. Current active memory
            mem_engine = orchestrator.get_memory()
            store = getattr(mem_engine, "store", getattr(mem_engine, "_store", None))
            if store and store.active_sub_memory and store.active_sub_memory in store.sub_memories:
                sub = store.sub_memories[store.active_sub_memory]
                self.current_memory = f"[{sub.name}] ({len(sub.entries)} entries)"
            else:
                self.current_memory = t("no_memory")

            # 3. Security guard status
            self.permissions = orchestrator.security_guard.get_status_summary()

        except Exception as exc:
            self.permissions = f"⚠ Status error: {exc}"
