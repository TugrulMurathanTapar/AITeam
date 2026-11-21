"""Model selector widget for toggling active AI providers."""

from __future__ import annotations

from typing import Any, List

from textual.containers import Horizontal, Vertical
from textual.widgets import Label, Switch


class ModelSelector(Vertical):
    """Multi-select model activation panel."""

    DEFAULT_CSS = """
    ModelSelector {
        height: auto;
        padding: 1;
        border: solid #7c3aed;
        background: #111638;
    }
    .model-selector-row {
        height: 3;
        align-vertical: middle;
        margin: 1 0;
    }
    .model-selector-label {
        width: 1fr;
        color: #f1f5f9;
    }
    """

    def refresh_models(self, providers: List[Any]) -> None:
        """Rebuild provider toggle rows.

        Args:
            providers: List of AIProvider configuration instances.
        """
        self.remove_children()
        for provider in providers:
            row = Horizontal(
                Label(f"{provider.name} ({provider.model_id})", classes="model-selector-label"),
                Switch(value=provider.enabled, id=f"model-sw-{provider.id}"),
                classes="model-selector-row",
            )
            self.mount(row)
