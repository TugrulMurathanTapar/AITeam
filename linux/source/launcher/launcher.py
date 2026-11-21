#!/usr/bin/env python3
"""
AI Orchestrator — Akıllı Başlatıcı
Çalıştıra basıldığında .venv otomatik oluşturulur ve aktifleştirilir.
"""
import os
import platform
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
VENV_DIR = PROJECT_ROOT / ".venv"
IS_WIN = platform.system() == "Windows"
VENV_PYTHON = VENV_DIR / ("Scripts/python.exe" if IS_WIN else "bin/python")
VENV_PIP = VENV_DIR / ("Scripts/pip.exe" if IS_WIN else "bin/pip")


def find_system_python():
    for cmd in ["python3", "python3.12", "python3.11", "python3.10", "python"]:
        try:
            r = subprocess.run(
                [cmd, "-c", "import sys; print(sys.version_info >= (3,10))"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if r.stdout.strip() == "True":
                return cmd
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass
    return None


def main() -> None:
    # Eğer zaten .venv içindeysek, direkt çalıştır.
    if sys.prefix != sys.base_prefix or str(VENV_PYTHON) == sys.executable:
        sys.path.insert(0, str(PROJECT_ROOT))
        from ui.app import run

        run()
        return

    # Değilse: .venv oluştur ve bu scripti .venv Python'u ile yeniden başlat.
    print("=" * 50)
    print("   🤖 AI Orchestrator Launcher")
    print("=" * 50)

    if not VENV_PYTHON.exists():
        sys_py = find_system_python()
        if not sys_py:
            print("❌ Python 3.10+ bulunamadı! https://python.org adresinden yükleyin.")
            input("Kapatmak için Enter'a basın...")
            sys.exit(1)
        print(f"📦 .venv oluşturuluyor ({sys_py})...")
        subprocess.run([sys_py, "-m", "venv", str(VENV_DIR)], check=True)
        print("   ✅ .venv oluşturuldu")

    req = PROJECT_ROOT / "requirements.txt"
    if req.exists():
        print("📋 Bağımlılıklar kontrol ediliyor...")
        subprocess.run(
            [str(VENV_PIP), "install", "-r", str(req), "-q", "--no-warn-script-location"],
            check=False,
        )
        print("   ✅ Hazır")

    print("🚀 Başlatılıyor...\n")
    env = os.environ.copy()
    env["PYTHONPATH"] = str(PROJECT_ROOT)
    env["VIRTUAL_ENV"] = str(VENV_DIR)
    bin_dir = VENV_DIR / ("Scripts" if IS_WIN else "bin")
    env["PATH"] = str(bin_dir) + os.pathsep + env.get("PATH", "")

    os.execve(str(VENV_PYTHON), [str(VENV_PYTHON), __file__], env)


if __name__ == "__main__":
    main()
