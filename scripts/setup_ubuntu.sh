#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
echo "[*] Setting up FRIDAY on Ubuntu"
echo "[*] Project dir: $PROJECT_DIR"

echo "[*] Installing system dependencies..."
sudo apt update -qq
sudo apt install -y -qq python3 python3-pip python3-venv portaudio19-dev \
  espeak-ng espeak ffmpeg libespeak1 speech-dispatcher xprintidle \
  xdotool wmctrl playerctl libnotify-bin xdg-utils

echo "[*] Checking Chrome/Chromium..."
if ! command -v google-chrome &>/dev/null && ! command -v chromium-browser &>/dev/null; then
  echo "[*] Installing Chromium..."
  sudo apt install -y -qq chromium-browser
fi

echo "[*] Creating Python virtual environment..."
cd "$PROJECT_DIR"
python3 -m venv venv
source venv/bin/activate

echo "[*] Installing Python packages..."
pip install --quiet -r requirements.txt

echo "[*] Checking Ollama..."
if ! command -v ollama &>/dev/null; then
  echo "[*] Installing Ollama..."
  curl -fsSL https://ollama.com/install.sh | sh
fi

echo "[*] Ensuring at least one model is pulled..."
if ! ollama list 2>/dev/null | grep -q .; then
  echo "[*] Pulling llama3.1:8b (this may take a while)..."
  ollama pull llama3.1:8b
fi

echo ""
echo "[OK] Setup complete!"
echo "     Run: cd $PROJECT_DIR && source venv/bin/activate && python jarvis.py -t"
echo ""
echo "     Or set provider to 'ollama' in config.json to run fully offline."
