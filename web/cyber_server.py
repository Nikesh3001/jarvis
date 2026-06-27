#!/usr/bin/env python3
"""
FRIDAY Cyber Console Web UI — Standalone server.
Run with: python -m web.cyber_server
Access at: http://localhost:8081
"""

import asyncio
import base64
import hmac
import io
import contextlib
import json
import os
import sys
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware

sys.path.insert(0, str(Path(__file__).parent.parent))

from tools.cyber import process_command
from tools.security import SecurityTool
from tools.internet import InternetTools

_DEFAULT_API_KEY = base64.urlsafe_b64encode(os.urandom(24)).decode("ascii")
API_KEY = os.environ.get("FRIDAY_CYBER_API_KEY", os.environ.get("FRIDAY_API_KEY", _DEFAULT_API_KEY))


def _verify_api_key(key):
    if not API_KEY:
        return True
    if not key:
        return False
    return hmac.compare_digest(key, API_KEY)


_NOT_AUTH_REASON = "Authentication required. Set FRIDAY_API_KEY env var or use the generated key shown at startup."


def _parse_cors_origins(raw):
    origins = [o.strip() for o in raw.split(",") if o.strip()]
    return [o for o in origins if o.startswith("http://") or o.startswith("https://")]


_CORS_ORIGINS = _parse_cors_origins(
    os.environ.get("FRIDAY_CYBER_CORS_ORIGINS", "http://127.0.0.1:8081,http://localhost:8081")
)


def is_valid_origin(origin):
    if not origin:
        return False
    return origin in _CORS_ORIGINS or origin.rstrip("/") in _CORS_ORIGINS


app = FastAPI(title="FRIDAY Cyber Console", docs_url=None, redoc_url=None)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_CORS_ORIGINS,
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["content-type", "authorization"],
)

@app.middleware("http")
async def security_headers(request, call_next):
    response = await call_next(request)
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline'; "
        "style-src 'self' 'unsafe-inline'; "
        "connect-src 'self' ws://127.0.0.1:* ws://localhost:*; "
        "img-src 'self' data:; "
        "font-src 'self'"
    )
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "no-referrer"
    return response

_sec = SecurityTool()
_net = InternetTools()
active_connections = []

@app.get("/", response_class=HTMLResponse)
async def index():
    html_path = Path(__file__).parent / "cyber_static" / "index.html"
    return HTMLResponse(html_path.read_text(encoding="utf-8"))

@app.get("/api/tools")
async def api_tools():
    defs = _sec.get_tool_definitions()
    net_defs = _net.get_tool_definitions()
    return {
        "ok": True,
        "tools": [
            {"name": d["function"]["name"], "description": d["function"].get("description", "")}
            for d in defs + net_defs
        ]
    }

@app.post("/api/command")
async def api_command(body: dict):
    command = body.get("command", "").strip()
    auth_key = body.get("api_key", "")
    if not _verify_api_key(auth_key):
        return {"ok": False, "error": _NOT_AUTH_REASON}
    if not command:
        return {"ok": False, "error": "Empty command"}
    try:
        output_buffer = io.StringIO()
        with contextlib.redirect_stdout(output_buffer):
            result = process_command(command)
        output = output_buffer.getvalue()
        return {"ok": True, "output": output, "continue": result}
    except Exception as e:
        return {"ok": False, "error": str(e)}

@app.websocket("/ws/cyber")
async def ws_cyber(websocket: WebSocket):
    origin = websocket.headers.get("origin", "")
    if not is_valid_origin(origin):
        await websocket.close(code=4001, reason="Origin not allowed")
        return
    await websocket.accept()
    active_connections.append(websocket)

    from tools.cyber import CYBER_BANNER_ASCII
    await websocket.send_json({"type": "banner", "content": CYBER_BANNER_ASCII})
    await websocket.send_json({"type": "prompt"})

    try:
        while True:
            data = await websocket.receive_text()
            payload = json.loads(data)
            ws_api_key = payload.get("api_key", "")
            if not _verify_api_key(ws_api_key):
                await websocket.send_json({"type": "error", "content": _NOT_AUTH_REASON})
                await websocket.close(code=4001)
                break

            command = payload.get("command", "").strip()
            if not command:
                await websocket.send_json({"type": "prompt"})
                continue

            output_buffer = io.StringIO()
            try:
                with contextlib.redirect_stdout(output_buffer):
                    should_continue = process_command(command)
                output = output_buffer.getvalue()
                if output:
                    await websocket.send_json({"type": "output", "content": output.rstrip()})
            except Exception as e:
                await websocket.send_json({"type": "error", "content": f"Error: {e}"})

            if not should_continue:
                await websocket.send_json({"type": "output", "content": "\n  [CYBER] Console session ended.\n", "class": "output-warning"})
                break

            await websocket.send_json({"type": "prompt"})

    except WebSocketDisconnect:
        pass
    except Exception as e:
        try:
            await websocket.send_json({"type": "error", "content": str(e)})
        except Exception:
            pass
    finally:
        if websocket in active_connections:
            active_connections.remove(websocket)

static_dir = Path(__file__).parent / "cyber_static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

def main():
    import uvicorn
    port = int(os.environ.get("FRIDAY_CYBER_PORT", 8081))
    print(f"\n  fsociety Cyber Console UI starting on http://localhost:{port}")
    has_custom_key = bool(os.environ.get("FRIDAY_CYBER_API_KEY") or os.environ.get("FRIDAY_API_KEY"))
    if not has_custom_key:
        print(f"  API Key (auto-generated): {API_KEY}")
        print(f"  Set FRIDAY_CYBER_API_KEY env var to use your own key.\n")
    else:
        print(f"  API Key: {API_KEY[:8]}... (from env var)\n")
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="info")

if __name__ == "__main__":
    main()