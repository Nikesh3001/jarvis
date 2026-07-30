import os
import sys
import time
import json
from pathlib import Path

_AUTH_STORE = Path(__file__).parent.parent / ".authorized_ops"
_SESSION_TIMEOUT = 300


def _load_auths():
    try:
        if _AUTH_STORE.exists():
            data = json.loads(_AUTH_STORE.read_text())
            now = time.time()
            valid = {}
            for k, v in data.items():
                if now - v.get("time", 0) < v.get("ttl", _SESSION_TIMEOUT):
                    valid[k] = v
            return valid
    except Exception:
        pass
    return {}


def _save_auths(auths):
    try:
        _AUTH_STORE.write_text(json.dumps(auths), encoding="utf-8")
    except Exception:
        pass


_verified_ops = _load_auths()


def require_auth(operation, details=""):
    global _verified_ops
    now = time.time()

    cached = _verified_ops.get(operation)
    if cached and now - cached.get("time", 0) < cached.get("ttl", _SESSION_TIMEOUT):
        return True

    if not sys.stdin.isatty():
        return False
    print(f"\n  [SECURITY] Authorization required: {operation}")
    if details:
        print(f"  [SECURITY] Details: {details}")
    print(f"  [SECURITY] Type 'YES' to authorize, anything else to deny: ", end="")
    try:
        response = sys.stdin.readline().strip()
    except Exception:
        response = ""
    print()
    if response.upper() == "YES":
        _verified_ops[operation] = {"time": now, "ttl": _SESSION_TIMEOUT}
        _save_auths(_verified_ops)
        return True
    return False


def require_auth_noninteractive(operation, details=""):
    return False


def clear_auths():
    global _verified_ops
    _verified_ops = {}
    _save_auths({})


def set_auth_timeout(seconds):
    global _SESSION_TIMEOUT
    _SESSION_TIMEOUT = max(30, seconds)
