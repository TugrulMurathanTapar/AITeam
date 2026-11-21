"""Configuration loaders and portable runtime paths for Multi-AI Orchestrator."""

import json
import os
from pathlib import Path
from typing import Any, Dict

CONFIG_DIR = Path(__file__).resolve().parent
API_SCHEMAS_PATH = CONFIG_DIR / "api_schemas.json"


def resolve_user_data_dir() -> Path:
    """Return the persistent user-data directory for installed/local runs.

    This keeps API keys, memory, logs, and runtime settings outside the GitHub
    repository while still allowing a portable single-click install on both
    Windows and Linux.
    """
    env_path = os.environ.get("AI_ORCHESTRATOR_DATA_DIR")
    if env_path:
        return Path(env_path).expanduser().resolve()

    if os.name == "nt":
        base_dir = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    else:
        base_dir = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))

    return (base_dir / "ai-orchestrator").resolve()


def ensure_runtime_dirs() -> Path:
    """Create the per-user runtime folders used by the application."""
    data_dir = resolve_user_data_dir()
    for folder in ("config", "memory", "logs", "workspace"):
        path = data_dir / folder
        path.mkdir(parents=True, exist_ok=True, mode=0o700)
        if os.name != "nt":
            path.chmod(0o700)
    if os.name != "nt":
        data_dir.chmod(0o700)
    return data_dir


def resolve_settings_path() -> Path:
    """Return the writable settings path in the private per-user data directory."""
    data_dir = ensure_runtime_dirs()
    return data_dir / "config" / "settings.json"


SETTINGS_PATH = resolve_settings_path()


def load_settings() -> Dict[str, Any]:
    """Load private user settings, migrating a legacy repository settings file if present."""
    settings_path = resolve_settings_path()
    if not settings_path.exists():
        legacy_path = CONFIG_DIR / "settings.json"
        example_path = CONFIG_DIR / "settings.json.example"
        source_path = legacy_path if legacy_path.is_file() else example_path
        if source_path.is_file():
            settings = json.loads(source_path.read_text(encoding="utf-8"))
        else:
            settings = {
                "language": "en",
                "theme": "dark",
                "memory_path": "./memory/memory.json",
                "providers": [],
            }
        settings_path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        settings_path.write_text(json.dumps(settings, ensure_ascii=False, indent=2), encoding="utf-8")
        if os.name != "nt":
            settings_path.chmod(0o600)
        if source_path == legacy_path:
            # The migrated copy is now private; remove the old source-tree copy
            # so credentials are no longer left beside the application source.
            legacy_path.unlink()

    elif os.name != "nt":
        settings_path.chmod(0o600)

    with open(settings_path, "r", encoding="utf-8") as f:
        settings = json.load(f)

    # Sanitize memory_path if it points to an inaccessible or foreign user directory.
    mem_path_str = settings.get("memory_path", "")
    if mem_path_str:
        try:
            p = Path(mem_path_str).expanduser()
            if not p.is_absolute():
                p = (resolve_user_data_dir() / p).resolve()
            p.parent.mkdir(parents=True, exist_ok=True)
        except (OSError, RuntimeError, TypeError, ValueError):
            fallback_path = resolve_user_data_dir() / "memory" / "memory.json"
            fallback_path.parent.mkdir(parents=True, exist_ok=True)
            settings["memory_path"] = str(fallback_path)
            settings_path.write_text(json.dumps(settings, ensure_ascii=False, indent=2), encoding="utf-8")

    return settings


def load_api_schemas() -> Dict[str, Any]:
    """Load API schema templates from api_schemas.json."""
    with open(API_SCHEMAS_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


__all__ = [
    "CONFIG_DIR",
    "API_SCHEMAS_PATH",
    "resolve_user_data_dir",
    "ensure_runtime_dirs",
    "resolve_settings_path",
    "SETTINGS_PATH",
    "load_settings",
    "load_api_schemas",
]
