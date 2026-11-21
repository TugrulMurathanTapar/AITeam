#!/usr/bin/env bash
# AI Orchestrator — Debian launcher with automatic system/Python dependencies.
set -Eeuo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd -- "$SCRIPT_DIR/.." && pwd)"
VENV_DIR="$PROJECT_ROOT/.venv"

if [[ ! -r /etc/os-release ]]; then
    echo "[ERROR] Cannot identify the Linux distribution (/etc/os-release missing)." >&2
    exit 1
fi
# shellcheck disable=SC1091
source /etc/os-release
if [[ "${ID:-}" != debian && " ${ID_LIKE:-} " != *" debian "* ]]; then
    echo "[ERROR] Automatic system-package installation currently supports Debian and Debian-based distributions only." >&2
    exit 1
fi

APT_PACKAGES=(python3 python3-venv python3-pip python3-tk python3-dev build-essential scrot python3-xlib)
need_apt=false
for package in "${APT_PACKAGES[@]}"; do
    if ! dpkg-query -W -f='${db:Status-Status}' "$package" 2>/dev/null | grep -qx installed; then
        need_apt=true
        break
    fi
done

if [[ "$need_apt" == true ]]; then
    if (( EUID == 0 )); then
        APT=(apt-get)
    elif command -v sudo >/dev/null 2>&1; then
        APT=(sudo apt-get)
        echo "[INFO] System packages require administrator access; sudo may prompt for your password."
    else
        echo "[ERROR] Missing Debian packages. Run this launcher as root or install sudo and retry." >&2
        exit 1
    fi
    "${APT[@]}" update
    "${APT[@]}" install -y "${APT_PACKAGES[@]}"
fi

find_python() {
    local candidate version
    for candidate in python3 python3.13 python3.12 python3.11 python3.10; do
        if command -v "$candidate" >/dev/null 2>&1; then
            version="$("$candidate" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")' 2>/dev/null || true)"
            if [[ "$version" =~ ^([0-9]+)\.([0-9]+)$ ]] && (( BASH_REMATCH[1] > 3 || (BASH_REMATCH[1] == 3 && BASH_REMATCH[2] >= 10) )); then
                printf '%s\n' "$(command -v "$candidate")"
                return 0
            fi
        fi
    done
    return 1
}

PYTHON="$(find_python || true)"
if [[ -z "$PYTHON" ]]; then
    echo "[ERROR] Python 3.10+ is required, but Debian's installed Python is older or unavailable." >&2
    echo "[INFO] Use a supported Debian release (Debian 12 or newer), then run this launcher again." >&2
    exit 1
fi

echo "[INFO] Python: $("$PYTHON" --version)"
if [[ ! -x "$VENV_DIR/bin/python" ]]; then
    echo '[INFO] Creating the project virtual environment...'
    if ! "$PYTHON" -m venv "$VENV_DIR"; then
        python_version="$("$PYTHON" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"
        venv_package="python${python_version}-venv"
        if (( EUID == 0 )); then
            APT=(apt-get)
        elif command -v sudo >/dev/null 2>&1; then
            APT=(sudo apt-get)
        else
            echo "[ERROR] Could not create venv; install $venv_package with administrator access." >&2
            exit 1
        fi
        "${APT[@]}" install -y "$venv_package"
        "$PYTHON" -m venv "$VENV_DIR"
    fi
fi

REQ_FILE="$PROJECT_ROOT/requirements.txt"
if [[ -f "$REQ_FILE" ]]; then
    echo '[INFO] Installing/updating Python requirements...'
    "$VENV_DIR/bin/python" -m pip install --upgrade pip
    "$VENV_DIR/bin/python" -m pip install -r "$REQ_FILE"
fi

export PYTHONPATH="$PROJECT_ROOT"
cd "$PROJECT_ROOT"
echo '[INFO] Starting AI Orchestrator...'
exec "$VENV_DIR/bin/python" -c 'from ui.app import run; run()'
