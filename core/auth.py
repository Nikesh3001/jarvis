"""Authentication and session management for web interfaces."""

import os
import json
import hmac
import hashlib
import secrets
import time
import threading
from pathlib import Path
from typing import Optional, Dict, Tuple


AUTH_DIR = Path(__file__).parent.parent / ".auth"
TOKEN_FILE = AUTH_DIR / "tokens.json"
SESSION_TIMEOUT = 3600


class SessionManager:
    """Stateless token-based authentication with rotating secrets."""

    def __init__(self):
        self._lock = threading.Lock()
        self._sessions: Dict[str, float] = {}
        AUTH_DIR.mkdir(parents=True, exist_ok=True)
        self._secret = self._load_or_create_secret()
        self._load_sessions()
        self._start_cleanup()

    def _load_or_create_secret(self) -> bytes:
        secret_file = AUTH_DIR / ".secret"
        if secret_file.exists():
            return secret_file.read_bytes()
        secret = secrets.token_bytes(64)
        secret_file.write_bytes(secret)
        secret_file.chmod(0o600)
        return secret

    def _load_sessions(self):
        if TOKEN_FILE.exists():
            try:
                data = json.loads(TOKEN_FILE.read_text(encoding="utf-8"))
                self._sessions = {k: v for k, v in data.items() if time.time() - v < SESSION_TIMEOUT}
            except Exception:
                self._sessions = {}

    def _save_sessions(self):
        try:
            TOKEN_FILE.write_text(json.dumps(self._sessions, indent=2), encoding="utf-8")
            TOKEN_FILE.chmod(0o600)
        except Exception:
            pass

    def _start_cleanup(self):
        def cleaner():
            while True:
                time.sleep(300)
                with self._lock:
                    now = time.time()
                    self._sessions = {k: v for k, v in self._sessions.items() if now - v < SESSION_TIMEOUT}
                    self._save_sessions()
        thread = threading.Thread(target=cleaner, daemon=True)
        thread.start()

    def create_token(self, user: str = "admin") -> str:
        token = secrets.token_urlsafe(48)
        h = hmac.new(self._secret, token.encode(), hashlib.sha256).hexdigest()
        session_id = f"{token}.{h}"
        with self._lock:
            self._sessions[session_id] = time.time()
            self._save_sessions()
        return session_id

    def validate_token(self, session_id: str) -> Tuple[bool, str]:
        if not session_id or "." not in session_id:
            return False, "Invalid token format"
        token, h = session_id.rsplit(".", 1)
        expected = hmac.new(self._secret, token.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(h, expected):
            return False, "Token signature invalid"
        with self._lock:
            ts = self._sessions.get(session_id)
            if ts is None:
                return False, "Token not found"
            if time.time() - ts > SESSION_TIMEOUT:
                del self._sessions[session_id]
                self._save_sessions()
                return False, "Token expired"
            self._sessions[session_id] = time.time()
        return True, "OK"

    def revoke_token(self, session_id: str) -> bool:
        with self._lock:
            if session_id in self._sessions:
                del self._sessions[session_id]
                self._save_sessions()
                return True
        return False

    @property
    def active_sessions(self) -> int:
        with self._lock:
            return len(self._sessions)


_SESSION_MANAGER: Optional[SessionManager] = None


def get_session_manager() -> SessionManager:
    global _SESSION_MANAGER
    if _SESSION_MANAGER is None:
        _SESSION_MANAGER = SessionManager()
    return _SESSION_MANAGER


def require_auth(func):
    """Decorator for FastAPI endpoints that require authentication."""
    from functools import wraps
    from fastapi import Request, HTTPException

    @wraps(func)
    async def wrapper(request: Request, *args, **kwargs):
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")
        token = auth_header[7:]
        sm = get_session_manager()
        valid, msg = sm.validate_token(token)
        if not valid:
            raise HTTPException(status_code=401, detail=msg)
        return await func(request, *args, **kwargs)
    return wrapper
