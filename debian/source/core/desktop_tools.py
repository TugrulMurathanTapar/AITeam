"""Secure desktop automation helpers behind explicit opt-in permission checks.

All desktop activity is disabled by default. The user must enable the relevant
permission in settings before these helpers can be used. The tool set only
allows operations inside configured allowed paths for filesystem actions.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from core.security_guard import SecurityGuard

try:
    import pyautogui
except Exception:  # pragma: no cover - dependency may be absent in some setups
    pyautogui = None


_security = SecurityGuard()


def _require_permission(action: str, target_path: str | Path | None = None) -> None:
    """Raise PermissionError if the action is blocked by policy."""
    allowed, reason = _security.check_permission(action, target_path)
    if not allowed:
        raise PermissionError(reason)


def _resolve_allowed_path(path: str | Path) -> Path:
    """Resolve a filesystem path and ensure it stays inside configured allowed roots."""
    candidate = Path(path).expanduser()
    if not candidate.is_absolute():
        candidate = (Path.cwd() / candidate).resolve()
    else:
        candidate = candidate.resolve()

    if not _security.is_path_allowed(candidate):
        raise PermissionError(
            f"Path '{candidate}' is outside the configured allowed paths: {_security.policy.allowed_paths}"
        )
    return candidate


def capture_screen(region: tuple[int, int, int, int] | None = None) -> Any:
    """Capture a screenshot only when screen capture is enabled."""
    _require_permission("screen_capture")
    if pyautogui is None:
        raise RuntimeError("pyautogui is not installed.")
    return pyautogui.screenshot(region=region) if region else pyautogui.screenshot()


def move_mouse(x: int, y: int, duration: float = 0.0) -> None:
    """Move the mouse pointer only when mouse control is enabled."""
    _require_permission("mouse_control")
    if pyautogui is None:
        raise RuntimeError("pyautogui is not installed.")
    pyautogui.moveTo(x, y, duration=duration)


def click(x: int | None = None, y: int | None = None, button: str = "left") -> None:
    """Click the mouse only when mouse control is enabled."""
    _require_permission("mouse_control")
    if pyautogui is None:
        raise RuntimeError("pyautogui is not installed.")
    if x is None or y is None:
        pyautogui.click(button=button)
    else:
        pyautogui.click(x, y, button=button)


def type_text(text: str, interval: float = 0.0) -> None:
    """Send keystrokes only when keyboard control is enabled."""
    _require_permission("keyboard_control")
    if pyautogui is None:
        raise RuntimeError("pyautogui is not installed.")
    pyautogui.typewrite(text, interval=interval)


def list_dir(path: str | Path) -> list[str]:
    """List directory contents only when filesystem read is enabled and path is allowed."""
    _require_permission("file_read", path)
    directory = _resolve_allowed_path(path)
    return sorted(item.name for item in directory.iterdir())


def read_file(path: str | Path) -> str:
    """Read a file only when filesystem read is enabled and path is allowed."""
    _require_permission("file_read", path)
    file_path = _resolve_allowed_path(path)
    return file_path.read_text(encoding="utf-8")


def write_file(path: str | Path, content: str, append: bool = False) -> None:
    """Write a file only when filesystem write is enabled and path is allowed."""
    _require_permission("file_write", path)
    file_path = _resolve_allowed_path(path)
    file_path.parent.mkdir(parents=True, exist_ok=True)
    mode = "a" if append else "w"
    with file_path.open(mode, encoding="utf-8") as handle:
        handle.write(content)


__all__ = [
    "capture_screen",
    "move_mouse",
    "click",
    "type_text",
    "list_dir",
    "read_file",
    "write_file",
]
