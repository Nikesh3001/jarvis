"""FRIDAY Web Dashboard Server.

Provides a browser-based UI for interacting with FRIDAY.
Run with: python -m web.server --web
"""
import asyncio
import hashlib
import hmac
import json
import os
import sys
import datetime
import threading
from pathlib import Path

from core.ratelimit import check_rate

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Depends, status, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.assistant import VERSION

API_KEY = os.environ.get("FRIDAY_API_KEY", "")
_CORS_ORIGINS_STR = os.environ.get("FRIDAY_CORS_ORIGINS",
                                     "http://127.0.0.1:8080,http://localhost:8080")


def _parse_cors_origins(raw):
    origins = [o.strip() for o in raw.split(",") if o.strip()]
    return [o for o in origins if o.startswith("http://") or o.startswith("https://")]


def _verify_api_key(key):
    if not API_KEY:
        return True
    if not key:
        return False
    return hmac.compare_digest(key, API_KEY)


_NOT_AUTH_REASON = "Authentication required. Set FRIDAY_API_KEY env var or disable with empty key."


async def _verify_request(request):
    if not API_KEY:
        return
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header[7:]
    else:
        token = request.query_params.get("api_key", "")
    if not _verify_api_key(token):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=_NOT_AUTH_REASON)


app = FastAPI(title="FRIDAY Dashboard", docs_url=None, redoc_url=None)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_parse_cors_origins(_CORS_ORIGINS_STR),
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


def is_valid_origin(origin):
    if not origin:
        return False
    allowed = _parse_cors_origins(_CORS_ORIGINS_STR)
    return origin in allowed or origin.rstrip("/") in allowed


@app.get("/", response_class=HTMLResponse)
async def index():
    html_path = Path(__file__).parent / "static" / "index.html"
    return HTMLResponse(html_path.read_text(encoding="utf-8"))


@app.get("/api/status")
async def api_status(request: Request):
    try:
        await _verify_request(request)
    except HTTPException:
        raise
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
            "version": VERSION,
            "model": asst.brain.current_model,
            "provider": hc.get("provider", "?"),
            "stark_mode": asst.stark_mode,
            "safe_mode": asst.safe_mode,
            "rate_limited": getattr(asst.brain, 'rate_limited', False),
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
    except HTTPException:
        raise
    except Exception:
        return {"ok": False, "error": "Status check failed"}


@app.get("/api/conversations")
async def api_conversations(request: Request):
    try:
        await _verify_request(request)
    except HTTPException:
        raise
    try:
        if not check_rate("web_api_conversations", rate=2, burst=5):
            return {"ok": False, "error": "Rate limit exceeded"}
        asst = get_assistant()
        convos = asst._list_conversations()
        return {"ok": True, "conversations": convos}
    except HTTPException:
        raise
    except Exception:
        return {"ok": False, "error": "Failed to list conversations"}


@app.get("/api/tools")
async def api_tools(request: Request):
    try:
        await _verify_request(request)
    except HTTPException:
        raise
    try:
        if not check_rate("web_api_tools", rate=5, burst=10):
            return {"ok": False, "error": "Rate limit exceeded"}
        asst = get_assistant()
        tools = [
            {
                "name": td["function"]["name"],
                "description": td["function"].get("description", ""),
            }
            for td in asst.brain.tool_definitions
        ]
        return {"ok": True, "tools": tools, "count": len(tools)}
    except HTTPException:
        raise
    except Exception:
        return {"ok": False, "error": "Failed to list tools"}


_MAX_MESSAGE_LENGTH = 10000


@app.post("/api/chat")
async def api_chat(body: dict):
    message = body.get("message", "").strip()
    auth_key = body.get("api_key", "")
    if not _verify_api_key(auth_key):
        return {"ok": False, "error": _NOT_AUTH_REASON}
    if not message:
        return {"ok": False, "error": "Empty message"}
    if len(message) > _MAX_MESSAGE_LENGTH:
        return {"ok": False, "error": f"Message too long (max {_MAX_MESSAGE_LENGTH} chars)"}
    if not check_rate("web_api_chat", rate=0.5, burst=3):
        return {"ok": False, "error": "Rate limit exceeded. Please wait before sending more messages."}
    try:
        asst = get_assistant()
        asst.conversation.append({"role": "user", "content": message})
        result_text = asst.brain.chat_with_tools(asst.conversation)
        asst._trim_conversation()
        asst._save_conversation()
        asst._post_process(message)
        return {"ok": True, "response": result_text}
    except Exception:
        return {"ok": False, "error": "Chat request failed"}


@app.post("/api/command")
async def api_command(body: dict):
    command = body.get("command", "").strip()
    auth_key = body.get("api_key", "")
    if not _verify_api_key(auth_key):
        return {"ok": False, "error": _NOT_AUTH_REASON}
    if not command:
        return {"ok": False, "error": "Empty command"}
    if len(command) > _MAX_MESSAGE_LENGTH:
        return {"ok": False, "error": f"Command too long (max {_MAX_MESSAGE_LENGTH} chars)"}
    if not check_rate("web_api_command", rate=0.5, burst=3):
        return {"ok": False, "error": "Rate limit exceeded. Please wait before sending more commands."}
    try:
        asst = get_assistant()
        handled = asst._handle_command(command)
        if handled:
            return {"ok": True, "handled": True, "response": "(command executed)"}
        return {"ok": True, "handled": False}
    except Exception:
        return {"ok": False, "error": "Command execution failed"}


@app.post("/api/model")
async def api_model(body: dict):
    model = body.get("model", "").strip()
    auth_key = body.get("api_key", "")
    if not _verify_api_key(auth_key):
        return {"ok": False, "error": _NOT_AUTH_REASON}
    if not model:
        return {"ok": False, "error": "No model specified"}
    if not check_rate("web_api_model", rate=1, burst=3):
        return {"ok": False, "error": "Rate limit exceeded"}
    try:
        asst = get_assistant()
        asst.brain.current_model = model
        return {"ok": True, "model": model}
    except Exception:
        return {"ok": False, "error": "Failed to switch model"}


@app.get("/api/models")
async def api_models(request: Request):
    try:
        await _verify_request(request)
    except HTTPException:
        raise
    try:
        asst = get_assistant()
        models = asst.brain.list_models()
        return {"ok": True, "models": models, "current": asst.brain.current_model}
    except HTTPException:
        raise
    except Exception:
        return {"ok": False, "error": "Failed to list models"}


@app.websocket("/ws/chat")
async def ws_chat(websocket: WebSocket):
    origin = websocket.headers.get("origin", "")
    if not is_valid_origin(origin):
        await websocket.close(code=4001, reason="Origin not allowed")
        return
    await websocket.accept()
    try:
        while True:
            data = await websocket.receive_text()
            payload = json.loads(data)
            ws_api_key = payload.get("api_key", "")
            if not _verify_api_key(ws_api_key):
                await websocket.send_json({"type": "error", "content": _NOT_AUTH_REASON})
                await websocket.close(code=4001)
                break

            message = payload.get("message", "").strip()
            if not message:
                await websocket.send_json({"type": "error", "content": "Empty message"})
                continue
            if len(message) > _MAX_MESSAGE_LENGTH:
                await websocket.send_json({"type": "error", "content": f"Message too long (max {_MAX_MESSAGE_LENGTH} chars)"})
                continue

            asst = get_assistant()
            asst.conversation.append({"role": "user", "content": message})

            collected = []
            token_queue = asyncio.Queue()
            loop = asyncio.get_running_loop()

            def on_token(token):
                collected.append(token)
                try:
                    loop.call_soon_threadsafe(token_queue.put_nowait, token)
                except Exception:
                    pass

            def _run_chat():
                try:
                    asst.brain.chat_with_tools(asst.conversation, on_speak=on_token)
                except Exception as exc:
                    collected.clear()
                    collected.append(f"Error: {exc}")
                finally:
                    loop.call_soon_threadsafe(token_queue.put_nowait, None)

            await loop.run_in_executor(None, _run_chat)

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
    except Exception:
        try:
            await websocket.send_json({"type": "error", "content": "WebSocket error occurred"})
        except Exception:
            pass


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