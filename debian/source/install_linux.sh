#!/usr/bin/env bash
set -e

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$SCRIPT_DIR"

echo "=================================================="
echo "  AI Orchestrator — Linux (Debian/Ubuntu/Kali) Kurulumu"
echo "=================================================="

# 1. Sistem bağımlılıklarını kontrol et
if ! command -v python3 &> /dev/null; then
    echo "Python 3 bulunamadı. Lütfen yükleyin: sudo apt install python3 python3-pip"
    exit 1
fi

INSTALL_DIR="/opt/ai-orchestrator"
BIN_LINK="/usr/local/bin/ai-orchestrator"

echo "[1/4] Kurulum dizini hazırlanıyor ($INSTALL_DIR)..."
sudo mkdir -p "$INSTALL_DIR"
# Do not copy developer secrets, virtual environments, logs, or repository metadata.
tar -C "$PROJECT_ROOT" \
    --exclude='./.git' \
    --exclude='./.venv' \
    --exclude='./venv' \
    --exclude='./.env' \
    --exclude='./.env.*' \
    --exclude='./config/settings.json' \
    --exclude='./config/*.local.json' \
    --exclude='./config/credentials.enc' \
    --exclude='./logs/*.log' \
    --exclude='./memory/memory.json' \
    --exclude='./__pycache__' \
    --exclude='*.pyc' \
    -cf - . | sudo tar -C "$INSTALL_DIR" -xf -

echo "[2/4] Sanal ortam (venv) kuruluyor..."
sudo python3 -m venv "$INSTALL_DIR/venv"
sudo "$INSTALL_DIR/venv/bin/pip" install --upgrade pip
sudo "$INSTALL_DIR/venv/bin/pip" install -r "$INSTALL_DIR/requirements.txt"

echo "[3/4] Komut satırı kısayolu oluşturuluyor ($BIN_LINK)..."
sudo tee "$BIN_LINK" > /dev/null << 'EOF'
#!/usr/bin/env bash
cd /opt/ai-orchestrator
exec /opt/ai-orchestrator/venv/bin/python3 /opt/ai-orchestrator/baslat.py "$@"
EOF
sudo chmod +x "$BIN_LINK"

echo "[4/4] Desktop entegrasyonu tamamlanıyor..."
if [ -d "$HOME/.local/share/applications" ]; then
    cp "$INSTALL_DIR/ai-orchestrator.desktop" "$HOME/.local/share/applications/"
    update-desktop-database "$HOME/.local/share/applications" 2>/dev/null || true
fi

echo "=================================================="
echo "✔ Kurulum Başarıyla Tamamlandı!"
echo "Çalıştırmak için terminale şunu yazabilirsiniz: ai-orchestrator"
echo "=================================================="
