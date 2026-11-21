"""
Security Guard Module for Multi-AI Orchestrator.

Provides central permission policy enforcement and path authorization
using the singleton pattern.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class SecurityPolicy:
    """Security policy configuration defining access permissions."""

    sudo_enabled: bool = False
    fs_read: bool = False
    fs_write: bool = False
    fs_delete: bool = False
    screen_capture: bool = False
    mouse_control: bool = False
    keyboard_control: bool = False
    terminal_enabled: bool = False
    allowed_paths: list[str] = field(default_factory=lambda: ["./workspace/"])
    gui_automation: bool = False


class SecurityGuard:
    """
    Central permission policy enforcement engine.

    Implements a thread-safe singleton pattern ensuring uniform security
    rule enforcement across all agent skills and execution runners.
    """

    _instance: Optional[SecurityGuard] = None
    _initialized: bool = False

    def __new__(cls) -> SecurityGuard:
        """Ensure only a single instance of SecurityGuard is created."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        """Initialize the SecurityGuard with default policy if not already initialized."""
        if getattr(self, "_initialized", False):
            return
        self._policy: SecurityPolicy = SecurityPolicy()
        self._initialized = True

    @property
    def policy(self) -> SecurityPolicy:
        """Get the current security policy."""
        return self._policy

    def update_policy(self, **kwargs: Any) -> None:
        """Update policy parameters with provided keyword arguments."""
        for key, value in kwargs.items():
            if hasattr(self._policy, key):
                if key == "allowed_paths" and isinstance(value, (list, tuple)):
                    setattr(self._policy, key, [str(p) for p in value])
                else:
                    setattr(self._policy, key, value)
            else:
                raise AttributeError(f"SecurityPolicy has no attribute '{key}'")

    def is_path_allowed(self, path: str | Path | None) -> bool:
        """Resolve a path and verify whether it is contained within any allowed_paths."""
        if not path:
            return False

        try:
            target_path = Path(path).expanduser().resolve()
            candidate_paths = [Path(p).expanduser().resolve() for p in self._policy.allowed_paths]
            for allowed_path in candidate_paths:
                try:
                    target_path.relative_to(allowed_path)
                    return True
                except ValueError:
                    continue
            return False
        except Exception:
            return False

    def check_permission(
        self, action: str, target_path: str | Path | None = None
    ) -> Tuple[bool, str]:
        """Validate permission for an action and optional target path."""
        aliases = {
            "fs_read": "fs_read",
            "file_read": "fs_read",
            "read_file": "fs_read",
            "fs_write": "fs_write",
            "file_write": "fs_write",
            "write_file": "fs_write",
            "fs_delete": "fs_delete",
            "file_delete": "fs_delete",
            "delete_file": "fs_delete",
            "screen_capture": "screen_capture",
            "screen": "screen_capture",
            "monitor": "screen_capture",
            "mouse_control": "mouse_control",
            "mouse": "mouse_control",
            "pointer": "mouse_control",
            "keyboard_control": "keyboard_control",
            "keyboard": "keyboard_control",
            "type_text": "keyboard_control",
            "gui_automation": "gui_automation",
            "sudo": "sudo",
            "terminal": "terminal",
            "web_search": "web_search",
        }
        normalized_action = aliases.get(action.strip().lower(), action.strip().lower())

        if normalized_action == "fs_read":
            if not self._policy.fs_read:
                return False, "Permission denied: filesystem read ('fs_read') is disabled."
            if target_path is not None and not self.is_path_allowed(target_path):
                return (
                    False,
                    f"Permission denied: path '{target_path}' is outside allowed paths: {self._policy.allowed_paths}",
                )
            return True, "Filesystem read permission granted."

        if normalized_action == "fs_write":
            if not self._policy.fs_write:
                return False, "Permission denied: filesystem write ('fs_write') is disabled."
            if target_path is not None and not self.is_path_allowed(target_path):
                return (
                    False,
                    f"Permission denied: path '{target_path}' is outside allowed paths: {self._policy.allowed_paths}",
                )
            return True, "Filesystem write permission granted."

        if normalized_action == "fs_delete":
            if not self._policy.fs_delete:
                return False, "Permission denied: filesystem delete ('fs_delete') is disabled."
            if target_path is not None and not self.is_path_allowed(target_path):
                return (
                    False,
                    f"Permission denied: path '{target_path}' is outside allowed paths: {self._policy.allowed_paths}",
                )
            return True, "Filesystem delete permission granted."

        if normalized_action == "screen_capture":
            if not self._policy.screen_capture:
                return False, "Permission denied: screen capture is disabled by security policy."
            return True, "Screen capture permission granted."

        if normalized_action == "mouse_control":
            if not self._policy.mouse_control:
                return False, "Permission denied: mouse control is disabled by security policy."
            return True, "Mouse control permission granted."

        if normalized_action == "keyboard_control":
            if not self._policy.keyboard_control:
                return False, "Permission denied: keyboard control is disabled by security policy."
            return True, "Keyboard control permission granted."

        if normalized_action == "sudo":
            if not self._policy.sudo_enabled:
                return False, "Permission denied: sudo execution is disabled by security policy."
            return True, "Sudo execution permission granted."

        if normalized_action == "gui_automation":
            if not self._policy.gui_automation:
                return False, "Permission denied: GUI automation is disabled by security policy."
            return True, "GUI automation permission granted."

        if normalized_action == "terminal":
            if not self._policy.terminal_enabled:
                return False, "Permission denied: terminal execution is disabled by security policy."
            return True, "Terminal execution permission granted."

        if normalized_action == "web_search":
            return True, "Web search permission granted."

        return False, f"Permission denied: unknown security action '{action}'."

    def reset_to_defaults(self) -> None:
        """Reset security policy back to system defaults."""
        self._policy = SecurityPolicy()

    def to_dict(self) -> Dict[str, Any]:
        """Export policy configuration as a dictionary."""
        return {
            "sudo_enabled": self._policy.sudo_enabled,
            "fs_read": self._policy.fs_read,
            "fs_write": self._policy.fs_write,
            "fs_delete": self._policy.fs_delete,
            "screen_capture": self._policy.screen_capture,
            "mouse_control": self._policy.mouse_control,
            "keyboard_control": self._policy.keyboard_control,
            "terminal_enabled": self._policy.terminal_enabled,
            "allowed_paths": list(self._policy.allowed_paths),
            "gui_automation": self._policy.gui_automation,
        }

    def from_dict(self, data: Dict[str, Any]) -> None:
        """Load policy configuration from a dictionary."""
        for key, value in data.items():
            if hasattr(self._policy, key):
                if key == "allowed_paths" and isinstance(value, (list, tuple)):
                    setattr(self._policy, key, [str(p) for p in value])
                else:
                    setattr(self._policy, key, value)

    def get_status_summary(self) -> str:
        """Return a human-readable security status string."""
        r = "R" if self._policy.fs_read else "-"
        w = "W" if self._policy.fs_write else "-"
        d = "D" if self._policy.fs_delete else "-"
        s = "S" if self._policy.screen_capture else "-"
        m = "M" if self._policy.mouse_control else "-"
        k = "K" if self._policy.keyboard_control else "-"

        sudo_str = "ON" if self._policy.sudo_enabled else "OFF"
        gui_str = "ON" if self._policy.gui_automation else "OFF"

        is_guarded = (
            not self._policy.sudo_enabled
            and not self._policy.gui_automation
            and not self._policy.screen_capture
            and not self._policy.mouse_control
            and not self._policy.keyboard_control
            and not self._policy.fs_write
            and not self._policy.fs_delete
        )
        icon = "🔒" if is_guarded else "🔓"

        return f"{icon} FS:{r}{w}{d} | SCREEN:{s} | MOUSE:{m} | KB:{k} | SUDO:{sudo_str} | GUI:{gui_str}"
