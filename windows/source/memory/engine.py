"""
Asynchronous memory engine for the Multi-AI Orchestrator.

Manages persistent storage, core memory, scoped sub-memories, merge workflows,
atomic writes, and context injection string formatting for AI prompts.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import json
import os
from pathlib import Path
from typing import Any
import uuid

from memory.schema import CoreMemory, MemoryEntry, MemoryStore, SubMemory


def _default_memory_path() -> Path:
    """Resolve the per-user memory store location, keeping it outside the repo."""
    env_dir = os.environ.get("AI_ORCHESTRATOR_DATA_DIR")
    if env_dir:
        return (Path(env_dir) / "memory" / "memory.json").resolve()

    if os.name == "nt":
        base_dir = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    else:
        base_dir = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
    return (base_dir / "ai-orchestrator" / "memory" / "memory.json").resolve()

try:
    import aiofiles
    import aiofiles.os
    HAS_AIOFILES = True
except ImportError:
    HAS_AIOFILES = False


class MemoryEngine:
    """
    Core engine managing multi-tiered agent memory.

    Provides atomic persistence to disk, core universal memory management,
    project-specific sub-memories, workspace merging, prompt context injection,
    and sync data export.
    """

    def __init__(self, path: str | None = None) -> None:
        """
        Initialize the MemoryEngine.

        Args:
            path: Optional explicit filesystem path to memory.json. Defaults to the
                portable per-user app-data directory when available.
        """
        if path is None:
            path = str(_default_memory_path())
        self.path: Path = Path(path).expanduser().resolve()
        self._lock: asyncio.Lock = asyncio.Lock()
        self.store: MemoryStore = MemoryStore()

    @property
    def _store(self) -> MemoryStore:
        """Alias property for backward compatibility."""
        return self.store

    @staticmethod
    def _read_sync(target_path: Path) -> str:
        """Synchronous file reader used as fallback."""
        with open(target_path, "r", encoding="utf-8") as f:
            return f.read()

    @staticmethod
    def _write_sync(target_path: Path, content: str) -> None:
        """Synchronous file writer used as fallback."""
        with open(target_path, "w", encoding="utf-8") as f:
            f.write(content)
            f.flush()
            os.fsync(f.fileno())

    async def load(self, path: str | None = None) -> MemoryStore:
        """
        Asynchronously load memory data from disk into memory store.

        If the file does not exist, an empty MemoryStore is initialized
        and saved atomically to create the file.

        Args:
            path: Optional new file path to load from. Updates engine path if provided.

        Returns:
            The loaded MemoryStore instance.
        """
        if path is not None:
            self.path = Path(path).resolve()

        async with self._lock:
            try:
                raw_text = await self._read_file(self.path)
            except FileNotFoundError:
                self.store = MemoryStore()
                await self._save_internal()
                return self.store
            except OSError:
                fallback_path = _default_memory_path()
                if self.path == fallback_path:
                    raise
                self.path = fallback_path
                try:
                    raw_text = await self._read_file(self.path)
                except FileNotFoundError:
                    self.store = MemoryStore()
                    await self._save_internal()
                    return self.store

            data = json.loads(raw_text)
            self.store = MemoryStore.model_validate(data)

        return self.store

    @staticmethod
    async def _read_file(target_path: Path) -> str:
        """Read a memory file using the available asynchronous file backend."""
        if HAS_AIOFILES:
            async with aiofiles.open(target_path, mode="r", encoding="utf-8") as f:
                return await f.read()

        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, MemoryEngine._read_sync, target_path)

    async def save(self) -> None:
        """
        Persist the current MemoryStore to disk atomically.

        Writes data to a temporary file in the same directory first,
        flushes to disk, and atomically replaces the target file.
        """
        async with self._lock:
            await self._save_internal()

    async def _save_internal(self) -> None:
        """
        Internal unlocked save implementation.
        """
        dumped_data = self.store.model_dump(mode="json")
        serialized_json = json.dumps(dumped_data, indent=2, ensure_ascii=False)

        try:
            await self._write_atomic(self.path, serialized_json)
        except OSError:
            fallback_path = _default_memory_path()
            if self.path == fallback_path:
                raise
            await self._write_atomic(fallback_path, serialized_json)
            self.path = fallback_path

    @staticmethod
    async def _write_atomic(target_path: Path, content: str) -> None:
        """Write content atomically, propagating filesystem errors to the caller."""
        target_path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = target_path.with_name(f"{target_path.name}.tmp.{uuid.uuid4().hex}")

        try:
            if HAS_AIOFILES:
                async with aiofiles.open(tmp_path, mode="w", encoding="utf-8") as f:
                    await f.write(content)
                    await f.flush()
            else:
                loop = asyncio.get_running_loop()
                await loop.run_in_executor(None, MemoryEngine._write_sync, tmp_path, content)

            os.replace(tmp_path, target_path)
        finally:
            try:
                tmp_path.unlink(missing_ok=True)
            except OSError:
                pass

    # ==========================================
    # Core Memory Operations
    # ==========================================

    def get_core_memory(self) -> CoreMemory:
        """
        Retrieve the CoreMemory instance.

        Returns:
            Current CoreMemory reference.
        """
        return self.store.core

    def update_identity(self, key: str, value: Any) -> None:
        """
        Update or add a key-value pair in the user identity profile.

        Args:
            key: Profile field name (e.g., 'name', 'role', 'expertise').
            value: Associated value.
        """
        self.store.core.user_identity[key] = value

    def update_preference(self, key: str, value: Any) -> None:
        """
        Update or add a global preference.

        Args:
            key: Preference name (e.g., 'language', 'tone', 'framework').
            value: Preference configuration value.
        """
        self.store.core.global_preferences[key] = value

    def add_core_fact(
        self,
        content: str,
        category: str = "fact",
        tags: list[str] | None = None,
    ) -> MemoryEntry:
        """
        Add a persistent universal fact to Core Memory.

        Args:
            content: The statement or factual text.
            category: Categorical label ('fact', 'preference', 'context', 'note').
            tags: Optional list of categorical tags.

        Returns:
            The created MemoryEntry instance.
        """
        now = datetime.now(timezone.utc)
        entry = MemoryEntry(
            id=str(uuid.uuid4()),
            content=content,
            category=category,
            created_at=now,
            updated_at=now,
            tags=list(tags) if tags is not None else [],
        )
        self.store.core.persistent_facts.append(entry)
        return entry

    def remove_core_fact(self, entry_id: str) -> bool:
        """
        Remove a persistent fact by ID from Core Memory.

        Args:
            entry_id: UUID of the fact to remove.

        Returns:
            True if an entry was removed, False if not found.
        """
        facts = self.store.core.persistent_facts
        for idx, entry in enumerate(facts):
            if entry.id == entry_id:
                facts.pop(idx)
                return True
        return False

    # ==========================================
    # Sub-Memory CRUD Operations
    # ==========================================

    def create_sub_memory(self, name: str, description: str = "") -> SubMemory:
        """
        Create a new scoped sub-memory workspace.

        Args:
            name: Workspace name.
            description: Workspace description or domain scope.

        Returns:
            The newly created SubMemory instance.
        """
        now = datetime.now(timezone.utc)
        sub = SubMemory(
            id=str(uuid.uuid4()),
            name=name,
            description=description,
            created_at=now,
            updated_at=now,
            entries=[],
        )
        self.store.sub_memories[sub.id] = sub
        if self.store.active_sub_memory is None:
            self.store.active_sub_memory = sub.id
        return sub

    def rename_sub_memory(self, sub_id: str, new_name: str) -> bool:
        """
        Rename an existing sub-memory workspace.

        Args:
            sub_id: UUID of the sub-memory.
            new_name: New human-readable workspace name.

        Returns:
            True if renamed successfully, False if sub_id was not found.
        """
        sub = self.store.sub_memories.get(sub_id)
        if sub is None:
            return False
        sub.name = new_name
        sub.updated_at = datetime.now(timezone.utc)
        return True

    def delete_sub_memory(self, sub_id: str) -> bool:
        """
        Delete a sub-memory workspace by ID.

        If the active sub-memory is deleted, the active reference is set to None.

        Args:
            sub_id: UUID of the sub-memory to delete.

        Returns:
            True if deleted, False if not found.
        """
        if sub_id not in self.store.sub_memories:
            return False

        del self.store.sub_memories[sub_id]
        if self.store.active_sub_memory == sub_id:
            self.store.active_sub_memory = None
        return True

    def switch_sub_memory(self, sub_id: str | None) -> bool:
        """
        Change the currently active sub-memory workspace.

        Args:
            sub_id: UUID of the sub-memory to activate, or None to deactivate.

        Returns:
            True if successfully switched, False if the requested sub_id does not exist.
        """
        if sub_id is None:
            self.store.active_sub_memory = None
            return True

        if sub_id in self.store.sub_memories:
            self.store.active_sub_memory = sub_id
            return True

        return False

    def list_sub_memories(self) -> list[SubMemory]:
        """
        List all available sub-memory workspaces.

        Returns:
            List of SubMemory instances.
        """
        return list(self.store.sub_memories.values())

    def get_active_sub_memory(self) -> SubMemory | None:
        """
        Retrieve the currently active SubMemory workspace.

        Returns:
            The active SubMemory instance, or None if no workspace is active.
        """
        active_id = self.store.active_sub_memory
        if active_id and active_id in self.store.sub_memories:
            return self.store.sub_memories[active_id]
        return None

    # ==========================================
    # Sub-Memory Entries Operations
    # ==========================================

    def add_entry(
        self,
        sub_id: str,
        content: str,
        category: str = "note",
        tags: list[str] | None = None,
    ) -> MemoryEntry:
        """
        Add a memory entry to a specific sub-memory workspace.

        Args:
            sub_id: UUID of target sub-memory.
            content: Textual content of the memory.
            category: Semantic category ('fact', 'preference', 'context', 'note').
            tags: Optional tags list.

        Returns:
            The newly created MemoryEntry.

        Raises:
            KeyError: If sub_id does not exist.
        """
        sub = self.store.sub_memories.get(sub_id)
        if sub is None:
            raise KeyError(f"SubMemory with ID '{sub_id}' does not exist.")

        now = datetime.now(timezone.utc)
        entry = MemoryEntry(
            id=str(uuid.uuid4()),
            content=content,
            category=category,
            created_at=now,
            updated_at=now,
            tags=list(tags) if tags is not None else [],
        )
        sub.entries.append(entry)
        sub.updated_at = now
        return entry

    def remove_entry(self, sub_id: str, entry_id: str) -> bool:
        """
        Remove a memory entry from a specific sub-memory workspace.

        Args:
            sub_id: UUID of the sub-memory workspace.
            entry_id: UUID of the entry to remove.

        Returns:
            True if removed, False if sub_id or entry_id not found.
        """
        sub = self.store.sub_memories.get(sub_id)
        if sub is None:
            return False

        for idx, entry in enumerate(sub.entries):
            if entry.id == entry_id:
                sub.entries.pop(idx)
                sub.updated_at = datetime.now(timezone.utc)
                return True
        return False

    # ==========================================
    # Merge Engine
    # ==========================================

    def merge_sub_memories(
        self,
        id_a: str,
        id_b: str,
        new_name: str,
        delete_originals: bool = False,
    ) -> SubMemory:
        """
        Merge two sub-memory workspaces into a new consolidated workspace.

        Entries from both workspaces are copied, deduplicated by content and category,
        and sorted chronologically.

        Args:
            id_a: UUID of first sub-memory.
            id_b: UUID of second sub-memory.
            new_name: Name for the newly created merged sub-memory.
            delete_originals: Whether to delete the original two sub-memories after merge.

        Returns:
            The new merged SubMemory instance.

        Raises:
            KeyError: If either sub-memory ID is not found.
        """
        sub_a = self.store.sub_memories.get(id_a)
        sub_b = self.store.sub_memories.get(id_b)

        if sub_a is None:
            raise KeyError(f"SubMemory with ID '{id_a}' does not exist.")
        if sub_b is None:
            raise KeyError(f"SubMemory with ID '{id_b}' does not exist.")

        # Create combined description
        desc_parts = []
        if sub_a.description:
            desc_parts.append(f"[{sub_a.name}]: {sub_a.description}")
        if sub_b.description:
            desc_parts.append(f"[{sub_b.name}]: {sub_b.description}")
        merged_description = " | ".join(desc_parts)

        now = datetime.now(timezone.utc)
        merged_sub = SubMemory(
            id=str(uuid.uuid4()),
            name=new_name,
            description=merged_description,
            created_at=now,
            updated_at=now,
            entries=[],
        )

        # Merge and deduplicate entries
        seen_entries: set[tuple[str, str]] = set()
        combined_entries: list[MemoryEntry] = []

        for entry in sub_a.entries + sub_b.entries:
            key = (entry.content.strip(), entry.category.strip().lower())
            if key not in seen_entries:
                seen_entries.add(key)
                combined_entries.append(
                    MemoryEntry(
                        id=str(uuid.uuid4()),
                        content=entry.content,
                        category=entry.category,
                        created_at=entry.created_at,
                        updated_at=entry.updated_at,
                        tags=list(set(entry.tags)),
                    )
                )

        # Sort entries chronologically by creation timestamp
        combined_entries.sort(key=lambda e: e.created_at)
        merged_sub.entries = combined_entries

        # Register merged sub-memory
        self.store.sub_memories[merged_sub.id] = merged_sub

        if delete_originals:
            was_active = self.store.active_sub_memory in (id_a, id_b)
            self.delete_sub_memory(id_a)
            self.delete_sub_memory(id_b)
            if was_active:
                self.store.active_sub_memory = merged_sub.id

        return merged_sub

    # ==========================================
    # Context Injection
    # ==========================================

    def get_context_injection(self) -> str:
        """
        Format memory data as a structured system prompt section.

        Combines Core Memory (identity, preferences, facts) and the active Sub-Memory
        (if selected) into a clean, markdown-formatted prompt injection string.

        Returns:
            A formatted markdown string ready for system prompt injection.
        """
        lines: list[str] = [
            "### PERSISTENT SYSTEM MEMORY & CONTEXT",
            "",
            "#### User Identity & Profile",
        ]

        # User Identity
        if self.store.core.user_identity:
            for k, v in self.store.core.user_identity.items():
                formatted_k = k.replace("_", " ").title()
                lines.append(f"- **{formatted_k}**: {v}")
        else:
            lines.append("- *No user profile recorded.*")

        lines.append("")
        lines.append("#### Global Preferences")

        # Global Preferences
        if self.store.core.global_preferences:
            for k, v in self.store.core.global_preferences.items():
                formatted_k = k.replace("_", " ").title()
                lines.append(f"- **{formatted_k}**: {v}")
        else:
            lines.append("- *Standard preferences apply.*")

        lines.append("")
        lines.append("#### Persistent Core Facts")

        # Core Facts
        if self.store.core.persistent_facts:
            for fact in self.store.core.persistent_facts:
                tags_str = f" [tags: {', '.join(fact.tags)}]" if fact.tags else ""
                lines.append(f"- [{fact.category.upper()}] {fact.content}{tags_str}")
        else:
            lines.append("- *No universal facts recorded.*")

        lines.append("")
        lines.append("#### Active Workspace Memory")

        # Active Sub-Memory
        active_sub = self.get_active_sub_memory()
        if active_sub is not None:
            lines.append(f"**Workspace**: {active_sub.name}")
            if active_sub.description:
                lines.append(f"**Description**: {active_sub.description}")
            lines.append("")
            lines.append("##### Workspace Entries")
            if active_sub.entries:
                for entry in active_sub.entries:
                    tags_str = f" [tags: {', '.join(entry.tags)}]" if entry.tags else ""
                    lines.append(f"- [{entry.category.upper()}] {entry.content}{tags_str}")
            else:
                lines.append("- *No entries recorded for this workspace.*")
        else:
            lines.append("- *No active sub-memory workspace selected.*")

        return "\n".join(lines)

    # ==========================================
    # Path Rebinding & Sync Token Export
    # ==========================================

    async def rebind_path(self, new_path: str) -> None:
        """
        Rebind the memory storage path to a new location.

        Writes the current memory contents to the new path and updates
        internal path tracking.

        Args:
            new_path: New relative or absolute filesystem destination.
        """
        new_target = Path(new_path).resolve()
        async with self._lock:
            self.path = new_target
            await self._save_internal()

    def export_data(self) -> dict[str, Any]:
        """
        Export the complete memory store as a plain JSON-serializable dictionary.

        Used for creating encrypted sync tokens and backups.

        Returns:
            Dictionary representation of MemoryStore.
        """
        return self.store.model_dump(mode="json")
