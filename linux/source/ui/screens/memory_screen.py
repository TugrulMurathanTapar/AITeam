"""Memory screen providing hierarchical browsing, sub-memory management, and merging."""

from __future__ import annotations

from typing import Any, List, Optional

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import (
    Button,
    Footer,
    Header,
    Input,
    Label,
    Select,
    Static,
    Tree,
)

from ui.i18n import t


class MemoryScreen(Screen):
    """Memory browser with tree view, CRUD operations, and workspace merging."""

    BINDINGS = [
        Binding("escape", "app.open_chat", "Sohbet"),
        Binding("ctrl+c", "app.open_chat", "Sohbet"),
    ]

    DEFAULT_CSS = """
    MemoryScreen {
        background: #0a0e27;
    }
    #memory-layout {
        height: 1fr;
    }
    #memory-tree-panel {
        width: 2fr;
        height: 100%;
        padding: 1;
    }
    #memory-tree {
        height: 100%;
        background: #111638;
        border: round #7c3aed;
        scrollbar-color: #7c3aed;
    }
    #memory-actions {
        width: 1fr;
        height: 100%;
        padding: 1 2;
        background: #0f1235;
        border: round #06b6d4;
        overflow-y: auto;
    }
    .action-header {
        text-style: bold;
        color: #06b6d4;
        margin: 1 0;
    }
    .status-feedback {
        margin-top: 1;
        text-style: bold;
    }
    """

    def compose(self) -> ComposeResult:
        """Compose the memory tree navigation and management controls."""
        yield Header()
        with Horizontal(id="memory-layout"):
            # Left: Memory tree
            with Vertical(id="memory-tree-panel"):
                yield Tree("Memory Store", id="memory-tree")

            # Right: Actions panel
            with Vertical(id="memory-actions"):
                yield Static(t("sub_memories"), classes="action-header")
                yield Input(placeholder=t("sub_name"), id="inp-sub-name")
                yield Input(placeholder=t("sub_description"), id="inp-sub-desc")
                with Horizontal():
                    yield Button(t("create_sub"), id="btn-create-sub", variant="success")
                    yield Button(t("rename_sub"), id="btn-rename-sub", variant="default")
                with Horizontal():
                    yield Button(t("switch_sub"), id="btn-switch-sub", variant="primary")
                    yield Button(t("delete_sub"), id="btn-delete-sub", variant="error")

                yield Static(t("merge_sub"), classes="action-header")
                yield Label(t("merge_source_a"))
                yield Select([("None", "none")], value="none", id="sel-merge-a")
                yield Label(t("merge_source_b"))
                yield Select([("None", "none")], value="none", id="sel-merge-b")
                yield Input(placeholder=t("merge_result_name"), id="inp-merge-name")
                yield Button(t("merge_sub"), id="btn-merge-sub", variant="warning")

                yield Static("", id="mem-status-msg", classes="status-feedback")

        yield Footer()

    async def on_mount(self) -> None:
        """Initialize memory tree and selection options upon mounting."""
        self._selected_sub_id: Optional[str] = None
        self._refresh_tree()
        self._refresh_selects()
        self.app.i18n.on_language_change(self._on_language_changed)

    def on_unmount(self) -> None:
        """Stop receiving language updates after this screen is removed."""
        self.app.i18n.remove_listener(self._on_language_changed)

    def _on_language_changed(self) -> None:
        """Recompose localized memory controls while preserving entered values."""
        if self.is_attached:
            self.run_worker(
                self._recompose_for_language(),
                name="memory-language-refresh",
                group="language-refresh",
                exclusive=True,
                exit_on_error=False,
            )

    async def _recompose_for_language(self) -> None:
        inputs = {widget.id: widget.value for widget in self.query(Input) if widget.id}
        selects = {widget.id: widget.value for widget in self.query(Select) if widget.id}

        await self.recompose()
        self._refresh_tree()
        self._refresh_selects()

        for widget_id, value in inputs.items():
            self.query_one(f"#{widget_id}", Input).value = value
        for widget_id, value in selects.items():
            self.query_one(f"#{widget_id}", Select).value = value

    def _refresh_tree(self) -> None:
        """Rebuild the memory tree from current memory store state."""
        tree = self.query_one("#memory-tree", Tree)
        tree.clear()

        orchestrator = getattr(self.app, "orchestrator", None)
        if not orchestrator:
            return

        memory = orchestrator.get_memory()
        store = getattr(memory, "_store", getattr(memory, "store", None))
        if not store:
            return

        # Core Memory branch
        core_node = tree.root.add(f"🧠 {t('core_memory')}")
        identity_node = core_node.add(f"👤 {t('identity')}")
        for key, val in store.core.user_identity.items():
            identity_node.add_leaf(f"{key}: {val}")
        if not store.core.user_identity:
            identity_node.add_leaf("(empty profile)")

        prefs_node = core_node.add(f"⚙️ {t('preferences')}")
        for key, val in store.core.global_preferences.items():
            prefs_node.add_leaf(f"{key}: {val}")
        if not store.core.global_preferences:
            prefs_node.add_leaf("(standard preferences)")

        facts_node = core_node.add(f"📌 {t('persistent_facts')}")
        for fact in store.core.persistent_facts:
            facts_node.add_leaf(f"[{fact.category}] {fact.content}")
        if not store.core.persistent_facts:
            facts_node.add_leaf("(no facts stored)")

        # Sub-memories branch
        sub_node = tree.root.add(f"📁 {t('sub_memories')}")
        for sub_id, sub in store.sub_memories.items():
            active = " ★" if sub_id == store.active_sub_memory else ""
            sub_branch = sub_node.add(f"{sub.name}{active}")
            sub_branch.data = sub_id
            for entry in sub.entries:
                sub_branch.add_leaf(f"[{entry.category}] {entry.content}")
            if not sub.entries:
                sub_branch.add_leaf("(no entries)")

        if not store.sub_memories:
            sub_node.add_leaf(f"({t('no_sub_memories')})")

        tree.root.expand_all()

    def _refresh_selects(self) -> None:
        """Update source selection dropdowns for merging sub-memories."""
        orchestrator = getattr(self.app, "orchestrator", None)
        if not orchestrator:
            return

        memory = orchestrator.get_memory()
        store = getattr(memory, "_store", getattr(memory, "store", None))
        if not store:
            return

        options = [("None", "none")]
        for sub_id, sub in store.sub_memories.items():
            options.append((sub.name, sub_id))

        sel_a = self.query_one("#sel-merge-a", Select)
        sel_b = self.query_one("#sel-merge-b", Select)
        sel_a.set_options(options)
        sel_b.set_options(options)
        sel_a.value = "none"
        sel_b.value = "none"

    def on_tree_node_selected(self, event: Tree.NodeSelected) -> None:
        """Select a sub-memory from the tree and populate the edit fields."""
        node = event.node
        sub_id = getattr(node, "data", None)
        if sub_id:
            self._selected_sub_id = sub_id
            orchestrator = getattr(self.app, "orchestrator", None)
            if orchestrator:
                store = orchestrator.get_memory().store
                sub = store.sub_memories.get(sub_id)
                if sub:
                    self.query_one("#inp-sub-name", Input).value = sub.name
                    self.query_one("#inp-sub-desc", Input).value = sub.description
                    status = self.query_one("#mem-status-msg", Static)
                    active_tag = " (Active)" if sub_id == store.active_sub_memory else ""
                    status.update(f"[cyan]Selected: {sub.name}{active_tag}[/]")

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button actions for sub-memory creation, deletion, and merging."""
        btn_id = event.button.id
        orchestrator = getattr(self.app, "orchestrator", None)
        if not orchestrator:
            return

        memory = orchestrator.get_memory()
        status = self.query_one("#mem-status-msg", Static)

        if btn_id == "btn-create-sub":
            name = self.query_one("#inp-sub-name", Input).value.strip()
            desc = self.query_one("#inp-sub-desc", Input).value.strip()
            if not name:
                status.update(f"[bold red]⚠ {t('sub_name')} is required.[/]")
                return

            sub = memory.create_sub_memory(name=name, description=desc)
            await memory.save()
            self._selected_sub_id = sub.id
            self._refresh_tree()
            self._refresh_selects()
            status.update(f"[bold green]✔ {t('sub_memory_created', name=name)}[/]")

        elif btn_id == "btn-rename-sub":
            if not self._selected_sub_id:
                status.update("[bold red]⚠ Please select a sub-memory from the tree first.[/]")
                return
            new_name = self.query_one("#inp-sub-name", Input).value.strip()
            if not new_name:
                return

            if memory.rename_sub_memory(self._selected_sub_id, new_name):
                await memory.save()
                self._refresh_tree()
                self._refresh_selects()
                status.update(f"[bold green]✔ Sub-memory renamed to '{new_name}'.[/]")
            else:
                status.update("[bold red]⚠ Failed to rename sub-memory.[/]")

        elif btn_id == "btn-delete-sub":
            if not self._selected_sub_id:
                status.update("[bold red]⚠ Please select a sub-memory from the tree first.[/]")
                return

            old_name = self.query_one("#inp-sub-name", Input).value.strip() or "Workspace"
            if memory.delete_sub_memory(self._selected_sub_id):
                await memory.save()
                self._selected_sub_id = None
                self.query_one("#inp-sub-name", Input).value = ""
                self.query_one("#inp-sub-desc", Input).value = ""
                self._refresh_tree()
                self._refresh_selects()
                status.update(f"[bold red]✔ {t('sub_memory_deleted', name=old_name)}[/]")
            else:
                status.update("[bold red]⚠ Failed to delete sub-memory.[/]")

        elif btn_id == "btn-switch-sub":
            if not self._selected_sub_id:
                status.update("[bold red]⚠ Please select a sub-memory from the tree first.[/]")
                return

            if memory.switch_sub_memory(self._selected_sub_id):
                await memory.save()
                self._refresh_tree()
                sub = memory.store.sub_memories.get(self._selected_sub_id)
                name = sub.name if sub else ""
                status.update(f"[bold green]✔ {t('sub_memory_switched', name=name)}[/]")
            else:
                status.update("[bold red]⚠ Failed to switch active sub-memory.[/]")

        elif btn_id == "btn-merge-sub":
            id_a = str(self.query_one("#sel-merge-a", Select).value)
            id_b = str(self.query_one("#sel-merge-b", Select).value)
            new_name = self.query_one("#inp-merge-name", Input).value.strip()

            if id_a == "none" or id_b == "none" or id_a == id_b:
                status.update("[bold red]⚠ Select two different sub-memories to merge.[/]")
                return

            if not new_name:
                status.update("[bold red]⚠ Merged name is required.[/]")
                return

            try:
                merged = memory.merge_sub_memories(id_a=id_a, id_b=id_b, new_name=new_name)
                await memory.save()
                self._selected_sub_id = merged.id
                self._refresh_tree()
                self._refresh_selects()
                status.update(f"[bold green]✔ Sub-memories merged into '{new_name}'.[/]")
            except Exception as exc:
                status.update(f"[bold red]⚠ Merge error: {exc}[/]")
