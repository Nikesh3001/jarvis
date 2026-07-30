#!/usr/bin/env bash
set -euo pipefail
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$DIR"
if [ -d ".venv" ]; then
    source .venv/bin/activate 2>/dev/null || source .venv/Scripts/activate 2>/dev/null || true
fi
echo "Starting JARVIS Cyber Web Dashboard..."
python -c "
import uvicorn
from web.cyber_server import app
uvicorn.run(app, host='0.0.0.0', port=5001)
"
