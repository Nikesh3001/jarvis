#!/usr/bin/env bash
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$DIR"

# Activate virtual environment if it exists
if [ -d ".venv" ]; then
    source .venv/bin/activate 2>/dev/null || source .venv/Scripts/activate 2>/dev/null || true
fi

MODE="${1:-text}"

echo "  ==========================================="
echo "  |  JARVIS - Cross-Platform AI Assistant   |"
echo "  |  Platform: $(uname -s)                    |"
echo "  |  Mode: $MODE                             |"
echo "  ==========================================="
echo ""

case "$MODE" in
    text|-t|--text)
        python jarvis.py --text
        ;;
    web|-w|--web)
        python jarvis.py --web
        ;;
    voice|-c|--continuous)
        python jarvis.py --continuous
        ;;
    cyber|--cyber|--pentest)
        python jarvis.py --cyber
        ;;
    help|-h|--help)
        python jarvis.py --help
        ;;
    *)
        python jarvis.py --text
        ;;
esac
