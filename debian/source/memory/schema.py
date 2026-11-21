"""
Pydantic v2 schemas defining the memory store data structures.

This module provides data models for atomic memory entries, global core memory,
scoped sub-memory workspaces, and the top-level memory store container.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field


class MemoryEntry(BaseModel):
    """
    Represents an atomic piece of knowledge, preference, context, or note.

    Attributes:
        id: Unique UUID string identifying this memory entry.
        content: The actual text content of the memory.
        category: Semantic classification ('fact', 'preference', 'context', 'note', etc.).
        created_at: UTC timestamp when the entry was created.
        updated_at: UTC timestamp when the entry was last modified.
        tags: List of descriptive string tags for categorization and search.
    """

    model_config = ConfigDict(
        extra="ignore",
        validate_assignment=True,
        populate_by_name=True,
    )

    id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="Unique identifier for the memory entry (UUID4).",
    )
    content: str = Field(
        ...,
        description="The textual content of the memory entry.",
    )
    category: str = Field(
        default="note",
        description="Category classification: 'fact', 'preference', 'context', or 'note'.",
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Timestamp when the entry was created in UTC.",
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Timestamp when the entry was last updated in UTC.",
    )
    tags: list[str] = Field(
        default_factory=list,
        description="Optional list of tags for indexing and filtering.",
    )


class CoreMemory(BaseModel):
    """
    Universal memory structure shared across all contexts and conversations.

    Attributes:
        user_identity: Key-value profile data (e.g., name, role, background, goals).
        global_preferences: Global behavioral preferences (e.g., language, tone, code style).
        persistent_facts: Universal facts that apply across all projects and interactions.
    """

    model_config = ConfigDict(
        extra="ignore",
        validate_assignment=True,
        populate_by_name=True,
    )

    user_identity: dict[str, Any] = Field(
        default_factory=dict,
        description="User identity dictionary containing biographical and role details.",
    )
    global_preferences: dict[str, Any] = Field(
        default_factory=lambda: {
            "language": "en",
            "tone": "professional",
        },
        description="Global preferences dictionary (e.g. language, tone, style).",
    )
    persistent_facts: list[MemoryEntry] = Field(
        default_factory=list,
        description="List of persistent universal facts.",
    )


class SubMemory(BaseModel):
    """
    Project-specific or domain-scoped memory workspace.

    Attributes:
        id: Unique UUID string identifying this sub-memory workspace.
        name: Name of the project or contextual workspace (e.g., 'Drone Flight Controller').
        description: Informative summary of the project or domain.
        created_at: UTC timestamp when the sub-memory was created.
        updated_at: UTC timestamp when the sub-memory was last modified.
        entries: Ordered list of memory entries associated with this domain.
    """

    model_config = ConfigDict(
        extra="ignore",
        validate_assignment=True,
        populate_by_name=True,
    )

    id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="Unique identifier for the sub-memory workspace (UUID4).",
    )
    name: str = Field(
        ...,
        description="Human-readable name of the sub-memory workspace.",
    )
    description: str = Field(
        default="",
        description="Detailed description of the sub-memory workspace.",
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Timestamp when the sub-memory was created in UTC.",
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Timestamp when the sub-memory was last updated in UTC.",
    )
    entries: list[MemoryEntry] = Field(
        default_factory=list,
        description="Domain-specific memory entries belonging to this workspace.",
    )


class MemoryStore(BaseModel):
    """
    Top-level memory storage container serialized to disk.

    Attributes:
        version: Version of the memory schema format.
        core: The central CoreMemory instance.
        sub_memories: Map of sub-memory workspace ID to SubMemory instance.
        active_sub_memory: ID of the currently selected/active sub-memory, if any.
    """

    model_config = ConfigDict(
        extra="ignore",
        validate_assignment=True,
        populate_by_name=True,
    )

    version: str = Field(
        default="1.0.0",
        description="Schema specification version.",
    )
    core: CoreMemory = Field(
        default_factory=CoreMemory,
        description="Universal core memory configuration.",
    )
    sub_memories: dict[str, SubMemory] = Field(
        default_factory=dict,
        description="Keyed map of sub-memory workspaces by ID.",
    )
    active_sub_memory: str | None = Field(
        default=None,
        description="UUID of the currently active sub-memory workspace, or None.",
    )
