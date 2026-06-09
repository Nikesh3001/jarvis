"""FRIDAY Web Dashboard Server.

Provides a browser-based UI for interacting with FRIDAY.
Run with: python -m web.server --web
"""
import asyncio
import json
import os
import sys
import datetime
import threading
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

app = FastAPI(title="FRIDAY Dashboard", docs_url=None, redoc_url=None)

# CORS origins: configurable via FRIDAY_CORS_ORIGINS env var (comma-separated)
_cors_origins = os.environ.get("FRIDAY_CORS_ORIGINS", "http://127.0.0.1:8080,http://localhost:8080").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in _cors_origins if o.strip()],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global assistant instance (lazy, thread-safe)
_assistant = None
_assistant_lock = threading.Lock()


def get_assistant():
    global _assistant
    if _assistant is not None:
        return _assistant
    with _assistant_lock:
        if _assistant is not None:
            return _assistant
        from core.assistant import Assistant
        _assistant = Assistant(text_mode=True)
        return _assistant


# ── REST Endpoints ──────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def index():
    html_path = Path(__file__).parent / "static" / "index.html"
    return HTMLResponse(html_path.read_text(encoding="utf-8"))


@app.get("/api/status")
async def api_status():
    try:
        asst = get_assistant()
        import psutil
        mem = psutil.virtual_memory()
        cpu = psutil.cpu_percent(interval=0)
        disk_path = os.path.expanduser("~") if sys.platform.startswith("win") else "/"
        disk = psutil.disk_usage(disk_path)
        uptime = datetime.datetime.now() - asst.session_start
        hc = asst.brain.health_check()
        return {
            "ok": True,
            "version": asst.VERSION,
            "model": asst.brain.current_model,
            "provider": hc.get("provider", "?"),
            "tools_registered": hc.get("tools_registered", 0),
            "total_calls": hc.get("total_calls", 0),
            "total_errors": hc.get("total_errors", 0),
            "total_time": hc.get("total_time_seconds", 0),
            "stark_mode": asst.stark_mode,
            "safe_mode": asst.safe_mode,
            "uptime_minutes": int(uptime.total_seconds() / 60),
            "commands_run": asst.commands_run,
            "cpu_percent": cpu,
            "ram_percent": mem.percent,
            "ram_used_gb": round(mem.used / (1024**3), 1),
            "ram_total_gb": round(mem.total / (1024**3), 1),
            "disk_percent": disk.percent,
            "disk_used_gb": round(disk.used / (1024**3), 1),
            "disk_total_gb": round(disk.total / (1024**3), 1),
        }
    except Exception as e:
        return {"ok": False, "error": str(e)}


@app.get("/api/conversations")
async def api_conversations():
    try:
        asst = get_assistant()
        convos = asst._list_conversations()
        return {"ok": True, "conversations": convos}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@app.get("/api/tools")
async def api_tools():
    try:
        asst = get_assistant()
        tools = [
            {
                "name": td["function"]["name"],
                "description": td["function"].get("description", ""),
            }
            for td in asst.brain.tool_definitions
        ]
        return {"ok": True, "tools": tools, "count": len(tools)}
    except Exception as e:
        return {"ok": False, "error": str(e)}


_MAX_MESSAGE_LENGTH = 10000

@app.post("/api/chat")
async def api_chat(body: dict):
    """Non-streaming chat endpoint."""
    message = body.get("message", "").strip()
    if not message:
        return {"ok": False, "error": "Empty message"}
    if len(message) > _MAX_MESSAGE_LENGTH:
        return {"ok": False, "error": f"Message too long (max {_MAX_MESSAGE_LENGTH} chars)"}
    try:
        asst = get_assistant()
        asst.conversation.append({"role": "user", "content": message})
        result_text = asst.brain.chat_with_tools(asst.conversation)
        asst._trim_conversation()
        asst._save_conversation()
        asst._post_process(message)
        return {"ok": True, "response": result_text}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@app.post("/api/command")
async def api_command(body: dict):
    """Process a direct command (suit status, help, etc)."""
    command = body.get("command", "").strip()
    if not command:
        return {"ok": False, "error": "Empty command"}
    if len(command) > _MAX_MESSAGE_LENGTH:
        return {"ok": False, "error": f"Command too long (max {_MAX_MESSAGE_LENGTH} chars)"}
    try:
        asst = get_assistant()
        handled = asst._handle_command(command)
        if handled:
            return {"ok": True, "handled": True, "response": "(command executed)"}
        return {"ok": True, "handled": False}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@app.post("/api/model")
async def api_model(body: dict):
    """Switch the AI model."""
    model = body.get("model", "").strip()
    if not model:
        return {"ok": False, "error": "No model specified"}
    try:
        asst = get_assistant()
        asst.brain.current_model = model
        return {"ok": True, "model": model}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@app.get("/api/models")
async def api_models():
    try:
        asst = get_assistant()
        models = asst.brain.list_models()
        return {"ok": True, "models": models, "current": asst.brain.current_model}
    except Exception as e:
        return {"ok": False, "error": str(e)}


# ── WebSocket for streaming chat ────────────────────────────────────────────

@app.websocket("/ws/chat")
async def ws_chat(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            data = await websocket.receive_text()
            payload = json.loads(data)
            message = payload.get("message", "").strip()
            if not message:
                await websocket.send_json({"type": "error", "content": "Empty message"})
                continue
            if len(message) > _MAX_MESSAGE_LENGTH:
                await websocket.send_json({"type": "error", "content": f"Message too long (max {_MAX_MESSAGE_LENGTH} chars)"})
                continue

            asst = get_assistant()
            asst.conversation.append({"role": "user", "content": message})

            # Stream tokens via simple_chat for responsive UI
            collected = []
            token_queue = asyncio.Queue()

            # Capture loop before entering thread context
            loop = asyncio.get_running_loop()

            def on_token(token):
                collected.append(token)
                try:
                    loop.call_soon_threadsafe(token_queue.put_nowait, token)
                except Exception:
                    pass

            # Producer: run AI in thread, put final response into queue
            def _run_chat():
                asst.brain.chat_with_tools(asst.conversation, on_speak=on_token)
                loop.call_soon_threadsafe(token_queue.put_nowait, None)

            await loop.run_in_executor(None, _run_chat)

            # Consumer: read tokens from queue and send to WebSocket
            while True:
                token = await token_queue.get()
                if token is None:
                    break
                await websocket.send_json({"type": "token", "content": token})

            full_response = "".join(collected) if collected else "(no response)"
            await websocket.send_json({"type": "done", "content": full_response})
            asst._trim_conversation()
            asst._save_conversation()
            asst._post_process(message)

    except WebSocketDisconnect:
        pass
    except Exception as e:
        try:
            await websocket.send_json({"type": "error", "content": str(e)})
        except Exception:
            pass


# ── Serve static files ──────────────────────────────────────────────────────

static_dir = Path(__file__).parent / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


def main():
    import uvicorn
    port = int(os.environ.get("FRIDAY_PORT", 8080))
    print(f"\n  FRIDAY Dashboard starting on http://localhost:{port}\n")
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="info")


if __name__ == "__main__":
    main()
