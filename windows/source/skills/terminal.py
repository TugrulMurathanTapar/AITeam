"""
Terminal Execution Skill for Multi-AI Orchestrator.

Provides asynchronous shell command execution with strict permission enforcement,
sudo privilege verification, command sanitization, and timeout handling.
"""

from __future__ import annotations

import asyncio
import os
import re
import shlex
from typing import Any, Dict, List, Optional

from core.security_guard import SecurityGuard
from core.skill_manager import BaseSkill


class TerminalSkill(BaseSkill):
    """
    Skill for executing shell commands in the host environment.
    
    Enforces security policies for sudo usage, path boundaries,
    and restricts destructive unvalidated commands.
    """

    name: str = "terminal"
    description: str = "Execute shell commands in the system terminal"
    required_permissions: list[str] = ["terminal"]

    # Block destructive patterns that risk catastrophic system corruption
    _DANGEROUS_PATTERNS = [
        re.compile(r"\brm\s+-(?:r[fF]|f[rR])\s+(?:/[^a-zA-Z0-9_\.]*|\*)\b"),
        re.compile(r":\(\)\s*\{\s*:\s*\|\s*:\s*&\s*\}\s*;\s*:"),  # Fork bomb
        re.compile(r"\bdd\s+.*of=/dev/(?:sd[a-z]|nvme[0-9]n[0-9]|hd[a-z])\b"),
        re.compile(r"\bmkfs(?:\.[a-z0-9]+)?\s+/dev/"),
    ]

    def __init__(self, security_guard: Optional[SecurityGuard] = None) -> None:
        """
        Initialize TerminalSkill with a reference to SecurityGuard.

        Args:
            security_guard: Optional SecurityGuard instance. If None, uses singleton.
        """
        self._security = security_guard if security_guard is not None else SecurityGuard()

    @property
    def parameters_schema(self) -> dict[str, Any]:
        """Tool parameter schema for terminal skill."""
        return {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "Shell command to execute in the system terminal",
                },
                "cwd": {
                    "type": "string",
                    "description": "Optional working directory path for execution",
                },
                "timeout": {
                    "type": "integer",
                    "description": "Maximum execution time in seconds (default: 30)",
                    "default": 30,
                },
            },
            "required": ["command"],
        }

    def _contains_sudo(self, command: str) -> bool:
        """Check if command invokes sudo."""
        return bool(re.search(r"(?:^|[;&|]\s*|\b)sudo(?:\s+|$)", command))

    def _sanitize_command(self, command: str) -> tuple[bool, str]:
        """
        Scan command for overtly malicious patterns.

        Returns:
            tuple[bool, str]: (is_safe, error_message)
        """
        for pattern in self._DANGEROUS_PATTERNS:
            if pattern.search(command):
                return False, f"Command contains prohibited dangerous pattern matching '{pattern.pattern}'"
        return True, ""

    async def execute(self, params: dict[str, Any]) -> dict[str, Any]:
        """
        Execute command asynchronously.

        Args:
            params: Dictionary containing:
                - 'command': Shell command string (required)
                - 'cwd': Working directory (optional)
                - 'timeout': Execution timeout in seconds (optional, default 30)

        Returns:
            dict[str, Any]: {'stdout': str, 'stderr': str, 'returncode': int}
        """
        command = params.get("command")
        if not command or not isinstance(command, str) or not command.strip():
            raise ValueError("Parameter 'command' is required and must be a non-empty string.")

        command = command.strip()
        if len(command) > 4096:
            raise ValueError("Terminal command exceeds the 4096-character limit.")

        allowed, reason = self._security.check_permission("terminal")
        if not allowed:
            raise PermissionError(reason)

        cwd = params.get("cwd")
        timeout = max(1, min(int(params.get("timeout", 30)), 120))

        # Check working directory boundaries
        if cwd:
            if not self._security.is_path_allowed(cwd):
                raise PermissionError(
                    f"Permission denied: working directory '{cwd}' is outside allowed paths."
                )

        # Enforce sudo restriction
        if self._contains_sudo(command):
            allowed, reason = self._security.check_permission("sudo")
            if not allowed:
                raise PermissionError(f"Sudo command rejected: {reason}")

        # Sanitize against destructive commands
        is_safe, err_msg = self._sanitize_command(command)
        if not is_safe:
            raise PermissionError(f"Security policy violation: {err_msg}")

        # Execute subprocess asynchronously
        proc = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=cwd,
        )

        try:
            stdout_data, stderr_data = await asyncio.wait_for(
                proc.communicate(),
                timeout=float(timeout),
            )
            return {
                "stdout": stdout_data.decode("utf-8", errors="replace"),
                "stderr": stderr_data.decode("utf-8", errors="replace"),
                "returncode": proc.returncode if proc.returncode is not None else 0,
            }
        except asyncio.TimeoutError:
            try:
                proc.kill()
                await proc.wait()
            except ProcessLookupError:
                pass
            return {
                "stdout": "",
                "stderr": f"Command timed out after {timeout} seconds",
                "returncode": -1,
            }
