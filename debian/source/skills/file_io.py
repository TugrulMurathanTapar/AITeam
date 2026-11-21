"""
File I/O Skill for Multi-AI Orchestrator.

Provides asynchronous filesystem operations including read, write, modify,
delete, and directory listing with strict security policy enforcement.
"""

from __future__ import annotations

import asyncio
import os
import shutil
from pathlib import Path
from typing import Any, Dict, List, Optional

from core.security_guard import SecurityGuard
from core.skill_manager import BaseSkill

try:
    import aiofiles  # type: ignore
    import aiofiles.os  # type: ignore

    HAS_AIOFILES = True
except ImportError:
    HAS_AIOFILES = False


class FileIOSkill(BaseSkill):
    """
    Skill for performing secured filesystem operations.
    
    Verifies path permissions, enforces read/write/delete policies,
    and performs non-blocking I/O using aiofiles with sync fallback.
    """

    name: str = "file_io"
    description: str = "Read, write, modify, and delete files"
    required_permissions: list[str] = []  # Each action checks its own permission in execute().

    def __init__(self, security_guard: Optional[SecurityGuard] = None) -> None:
        """
        Initialize FileIOSkill with reference to SecurityGuard.

        Args:
            security_guard: Optional SecurityGuard instance. If None, uses singleton.
        """
        self._security = security_guard if security_guard is not None else SecurityGuard()

    @property
    def parameters_schema(self) -> dict[str, Any]:
        """Tool parameter schema for file_io operations."""
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["read", "write", "modify", "delete", "list_dir"],
                    "description": "File system action to perform",
                },
                "path": {
                    "type": "string",
                    "description": "Target file or directory path",
                },
                "content": {
                    "type": "string",
                    "description": "Text content to write or append",
                },
                "mode": {
                    "type": "string",
                    "enum": ["overwrite", "append", "replace"],
                    "description": "Mode for modify operations: 'overwrite', 'append', or 'replace'",
                    "default": "overwrite",
                },
                "find": {
                    "type": "string",
                    "description": "Target substring to replace when action is 'modify' and mode is 'replace'",
                },
                "replace": {
                    "type": "string",
                    "description": "Replacement string when action is 'modify' and mode is 'replace'",
                },
            },
            "required": ["action", "path"],
        }

    async def _read_file_async(self, file_path: Path) -> str:
        """Read file asynchronously via aiofiles or asyncio.to_thread."""
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        if not file_path.is_file():
            raise IsADirectoryError(f"Target path is a directory, not a file: {file_path}")

        if HAS_AIOFILES:
            async with aiofiles.open(file_path, mode="r", encoding="utf-8", errors="replace") as f:
                return await f.read()

        def _sync_read() -> str:
            with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                return f.read()

        return await asyncio.to_thread(_sync_read)

    async def _write_file_async(self, file_path: Path, content: str, mode: str = "w") -> int:
        """Write content to file asynchronously, creating parent directories if needed."""
        file_path.parent.mkdir(parents=True, exist_ok=True)

        if HAS_AIOFILES:
            async with aiofiles.open(file_path, mode=mode, encoding="utf-8") as f:
                return await f.write(content)

        def _sync_write() -> int:
            with open(file_path, mode=mode, encoding="utf-8") as f:
                return f.write(content)

        return await asyncio.to_thread(_sync_write)

    async def _delete_path_async(self, target_path: Path) -> bool:
        """Delete file or directory asynchronously."""
        def _sync_delete() -> bool:
            if not target_path.exists():
                raise FileNotFoundError(f"Target does not exist: {target_path}")
            if target_path.is_dir():
                shutil.rmtree(target_path)
            else:
                target_path.unlink()
            return True

        return await asyncio.to_thread(_sync_delete)

    async def _list_dir_async(self, dir_path: Path) -> list[dict[str, Any]]:
        """List directory contents asynchronously."""
        def _sync_list() -> list[dict[str, Any]]:
            if not dir_path.exists():
                raise FileNotFoundError(f"Directory not found: {dir_path}")
            if not dir_path.is_dir():
                raise NotADirectoryError(f"Path is not a directory: {dir_path}")

            entries: list[dict[str, Any]] = []
            for item in dir_path.iterdir():
                try:
                    stat_info = item.stat()
                    entries.append({
                        "name": item.name,
                        "path": str(item),
                        "is_dir": item.is_dir(),
                        "is_file": item.is_file(),
                        "size": stat_info.st_size if item.is_file() else None,
                        "modified_timestamp": stat_info.st_mtime,
                    })
                except (PermissionError, FileNotFoundError):
                    continue

            return sorted(entries, key=lambda x: (not x["is_dir"], x["name"].lower()))

        return await asyncio.to_thread(_sync_list)

    async def execute(self, params: dict[str, Any]) -> dict[str, Any]:
        """
        Execute file operations with security validations.

        Args:
            params: Dictionary containing action, path, and optional content/mode.

        Returns:
            dict[str, Any]: Structured operation result.
        """
        action = params.get("action")
        raw_path = params.get("path")

        if not action or not isinstance(action, str):
            raise ValueError("Parameter 'action' is required.")
        if not raw_path or not isinstance(raw_path, str):
            raise ValueError("Parameter 'path' is required.")

        action = action.strip().lower()
        target_path = Path(raw_path)

        # 1. Path boundary validation
        if not self._security.is_path_allowed(target_path):
            raise PermissionError(
                f"Permission denied: path '{raw_path}' is outside allowed paths: "
                f"{self._security.policy.allowed_paths}"
            )

        # 2. Action permission validation & execution
        if action == "read":
            allowed, reason = self._security.check_permission("fs_read", target_path=target_path)
            if not allowed:
                raise PermissionError(reason)

            content = await self._read_file_async(target_path)
            return {
                "action": "read",
                "path": str(target_path),
                "content": content,
                "size_bytes": len(content.encode("utf-8")),
            }

        elif action == "write":
            allowed, reason = self._security.check_permission("fs_write", target_path=target_path)
            if not allowed:
                raise PermissionError(reason)

            content = params.get("content", "")
            if content is None:
                content = ""

            bytes_written = await self._write_file_async(target_path, content, mode="w")
            return {
                "action": "write",
                "path": str(target_path),
                "bytes_written": bytes_written,
            }

        elif action == "modify":
            allowed, reason = self._security.check_permission("fs_write", target_path=target_path)
            if not allowed:
                raise PermissionError(reason)

            mode = params.get("mode", "overwrite")
            content = params.get("content", "")

            if mode == "append":
                bytes_written = await self._write_file_async(
                    target_path, content or "", mode="a"
                )
            elif mode == "replace":
                read_allowed, read_reason = self._security.check_permission("fs_read", target_path=target_path)
                if not read_allowed:
                    raise PermissionError(read_reason)

                existing = await self._read_file_async(target_path)
                find_str = params.get("find", "")
                replace_str = params.get("replace", "")

                if not find_str:
                    raise ValueError("Parameter 'find' is required when mode is 'replace'.")
                if find_str not in existing:
                    raise ValueError(f"Target string '{find_str}' not found in '{target_path}'.")

                updated = existing.replace(find_str, replace_str)
                bytes_written = await self._write_file_async(target_path, updated, mode="w")
            else:  # overwrite
                bytes_written = await self._write_file_async(
                    target_path, content or "", mode="w"
                )

            return {
                "action": "modify",
                "path": str(target_path),
                "bytes_written": bytes_written,
                "mode": mode,
            }

        elif action == "delete":
            allowed, reason = self._security.check_permission("fs_delete", target_path=target_path)
            if not allowed:
                raise PermissionError(reason)

            deleted = await self._delete_path_async(target_path)
            return {
                "action": "delete",
                "path": str(target_path),
                "deleted": deleted,
            }

        elif action == "list_dir":
            allowed, reason = self._security.check_permission("fs_read", target_path=target_path)
            if not allowed:
                raise PermissionError(reason)

            entries = await self._list_dir_async(target_path)
            return {
                "action": "list_dir",
                "path": str(target_path),
                "entries": entries,
                "count": len(entries),
            }

        else:
            raise ValueError(
                f"Unknown file action '{action}'. "
                "Supported actions: 'read', 'write', 'modify', 'delete', 'list_dir'."
            )
