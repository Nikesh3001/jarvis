"""FRIDAY Web Dashboard Server.

Provides a browser-based UI for interacting with FRIDAY.
Run with: python jarvis.py -w
"""
import asyncio
import hashlib
import hmac
import json
import os
import sys
import time
import secrets
import datetime
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.ratelimit import check_rate

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Depends, status, Request, Response
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from core.assistant import VERSION

API_KEY = os.environ.get("FRIDAY_API_KEY", "")
if not API_KEY:
    API_KEY = secrets.token_hex(16)
    _AUTO_KEY = True
else:
    _AUTO_KEY = False

_SESSION_TOKENS = {}
_SESSION_TTL = 86400
_COOKIE_NAME = "friday_session"
_NOT_AUTH_REASON = "Authentication required."


def _generate_session():
    token = secrets.token_urlsafe(32)
    _SESSION_TOKENS[token] = time.time()
    _cleanup_expired_sessions()
    return token


def _validate_session(token):
    if not token or token not in _SESSION_TOKENS:
        return False
    ts = _SESSION_TOKENS.get(token)
    if not ts:
        return False
    if time.time() - ts > _SESSION_TTL:
        del _SESSION_TOKENS[token]
        return False
    return True


def _cleanup_expired_sessions():
    now = time.time()
    expired = [k for k, v in list(_SESSION_TOKENS.items()) if now - v > _SESSION_TTL]
    for k in expired:
        _SESSION_TOKENS.pop(k, None)


def _verify_api_key(key):
    if not API_KEY:
        return False
    if not key:
        return False
    return hmac.compare_digest(key, API_KEY)


def _get_auth_key(request):
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        return auth_header[7:]
    cookie = request.cookies.get(_COOKIE_NAME, "")
    if cookie and _validate_session(cookie):
        return API_KEY
    return ""


async def _verify_request(request):
    if not API_KEY:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=_NOT_AUTH_REASON)
    key = _get_auth_key(request)
    if not _verify_api_key(key):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=_NOT_AUTH_REASON)


def _set_session_cookie(response):
    session = _generate_session()
    response.set_cookie(
        key=_COOKIE_NAME,
        value=session,
        httponly=True,
        samesite="strict",
        max_age=86400,
        secure=True,
    )


_CORS_ORIGINS_STR = os.environ.get("FRIDAY_CORS_ORIGINS",
                                     "http://127.0.0.1:8080,http://localhost:8080")


def _parse_cors_origins(raw):
    origins = [o.strip() for o in raw.split(",") if o.strip()]
    return [o for o in origins if o.startswith("http://") or o.startswith("https://")]


app = FastAPI(title="FRIDAY Dashboard", docs_url=None, redoc_url=None)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_parse_cors_origins(_CORS_ORIGINS_STR),
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["content-type", "authorization"],
)

@app.middleware("http")
async def security_headers(request, call_next):
    response = await call_next(request)
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "script-src 'self'; "
        "style-src 'self' 'unsafe-inline'; "
        "connect-src 'self' ws://127.0.0.1:* ws://localhost:*; "
        "img-src 'self' data:; "
        "font-src 'self'"
    )
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    return response


_assistant = None
_assistant_lock = asyncio.Lock()


async def get_assistant():
    global _assistant
    if _assistant is not None:
        return _assistant
    async with _assistant_lock:
        if _assistant is not None:
            return _assistant
        from core.assistant import Assistant
        _assistant = Assistant(text_mode=True)
        return _assistant


def is_valid_origin(origin):
    if not origin:
        return False
    from urllib.parse import urlparse
    parsed = urlparse(origin)
    normalized = f"{parsed.scheme}://{parsed.netloc}"
    allowed = _parse_cors_origins(_CORS_ORIGINS_STR)
    return normalized in allowed


@app.get("/", response_class=HTMLResponse)
async def index():
    html_path = Path(__file__).parent / "static" / "index.html"
    html = html_path.read_text(encoding="utf-8")
    response = HTMLResponse(html)
    _set_session_cookie(response)
    return response


@app.get("/favicon.ico")
async def favicon():
    return HTMLResponse("")


@app.get("/api/status")
async def api_status(request: Request):
    try:
        await _verify_request(request)
    except HTTPException:
        raise
    try:
        asst = await get_assistant()
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
        asst = await get_assistant()
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
        asst = await get_assistant()
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
async def api_chat(body: dict, request: Request):
    message = body.get("message", "").strip()
    key = _get_auth_key(request)
    if not _verify_api_key(key):
        return {"ok": False, "error": _NOT_AUTH_REASON}
    if not message:
        return {"ok": False, "error": "Empty message"}
    if len(message) > _MAX_MESSAGE_LENGTH:
        return {"ok": False, "error": f"Message too long (max {_MAX_MESSAGE_LENGTH} chars)"}
    if not check_rate("web_api_chat", rate=0.5, burst=3):
        return {"ok": False, "error": "Rate limit exceeded. Please wait before sending more messages."}
    try:
        asst = await get_assistant()
        with asst._conversation_lock:
            asst.conversation.append({"role": "user", "content": message})
            result_text = asst.brain.chat_with_tools(asst.conversation)
            asst._trim_conversation()
            asst._save_conversation()
            asst._post_process(message)
        return {"ok": True, "response": result_text}
    except Exception:
        return {"ok": False, "error": "Chat request failed"}


@app.post("/api/command")
async def api_command(body: dict, request: Request):
    command = body.get("command", "").strip()
    key = _get_auth_key(request)
    if not _verify_api_key(key):
        return {"ok": False, "error": _NOT_AUTH_REASON}
    if not command:
        return {"ok": False, "error": "Empty command"}
    if len(command) > _MAX_MESSAGE_LENGTH:
        return {"ok": False, "error": f"Command too long (max {_MAX_MESSAGE_LENGTH} chars)"}
    if not check_rate("web_api_command", rate=0.5, burst=3):
        return {"ok": False, "error": "Rate limit exceeded. Please wait before sending more commands."}
    try:
        asst = await get_assistant()
        handled = asst._handle_command(command)
        if handled:
            return {"ok": True, "handled": True, "response": "(command executed)"}
        return {"ok": True, "handled": False}
    except Exception:
        return {"ok": False, "error": "Command execution failed"}


@app.post("/api/model")
async def api_model(body: dict, request: Request):
    model = body.get("model", "").strip()
    key = _get_auth_key(request)
    if not _verify_api_key(key):
        return {"ok": False, "error": _NOT_AUTH_REASON}
    if not model:
        return {"ok": False, "error": "No model specified"}
    if not check_rate("web_api_model", rate=1, burst=3):
        return {"ok": False, "error": "Rate limit exceeded"}
    try:
        asst = await get_assistant()
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
        asst = await get_assistant()
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
    ws_api_key = ""
    cookie_header = websocket.headers.get("cookie", "")
    if not ws_api_key and cookie_header:
        for part in cookie_header.split(";"):
            part = part.strip()
            if part.startswith(f"{_COOKIE_NAME}="):
                token = part[len(_COOKIE_NAME) + 1:]
                if _validate_session(token):
                    ws_api_key = API_KEY
                break
    try:
        while True:
            data = await websocket.receive_text()
            payload = json.loads(data)
            if not ws_api_key:
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

            asst = await get_assistant()
            with asst._conversation_lock:
                asst.conversation.append({"role": "user", "content": message})

            cmd_lower = message.strip().lower()
            if any(w in cmd_lower for w in ["list models", "available models", "switch model", "change model"]):
                models = asst.brain.list_models()
                if isinstance(models, list) and models:
                    reply = "Available models: " + ", ".join(models[:10])
                else:
                    reply = "No models available."
                await websocket.send_json({"type": "done", "content": reply})
                continue

            if any(w in cmd_lower for w in ["reduce ram", "free memory", "ram usage", "optimize ram", "clear memory", "too slow", "reduce memory"]):
                import gc, psutil
                freed = gc.collect()
                asst._trim_conversation(max_messages=5)
                freed2 = gc.collect()
                pct = psutil.virtual_memory().percent
                reply = f"Freed {freed + freed2} garbage objects. Conversation trimmed. Current RAM: {pct}%."
                await websocket.send_json({"type": "done", "content": reply})
                continue

            collected = []
            token_queue = asyncio.Queue()
            loop = asyncio.get_running_loop()

            def on_token(token):
                collected.append(token)
                try:
                    loop.call_soon_threadsafe(token_queue.put_nowait, token)
                except Exception:
                    pass

            cancelled = False

            def _run_chat():
                try:
                    asst.brain.chat_with_tools(asst.conversation, on_speak=on_token)
                except Exception as exc:
                    if not cancelled:
                        collected.clear()
                        collected.append(f"Error: {exc}")
                finally:
                    try:
                        loop.call_soon_threadsafe(token_queue.put_nowait, None)
                    except RuntimeError:
                        pass

            chat_task = loop.run_in_executor(None, _run_chat)

            while True:
                try:
                    token = await asyncio.wait_for(token_queue.get(), timeout=120)
                except asyncio.TimeoutError:
                    cancelled = True
                    await websocket.send_json({"type": "error", "content": "Response timed out."})
                    break
                if token is None:
                    break
                await websocket.send_json({"type": "token", "content": token})

            full_response = "".join(collected) if collected else "(no response)"
            await websocket.send_json({"type": "done", "content": full_response})
            with asst._conversation_lock:
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
    if _AUTO_KEY:
        print(f"\n  FRIDAY Dashboard starting on http://localhost:{port}")
        print("  API Key auto-generated (see .env file)\n")
    else:
        print(f"\n  FRIDAY Dashboard starting on http://localhost:{port}\n")
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="info")


if __name__ == "__main__":
    main()
