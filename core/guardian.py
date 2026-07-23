"""Enterprise-grade security guardian: input validation, sandbox, audit, rate limiting, SSRF."""

import ast
import hashlib
import hmac
import ipaddress
import os
import re
import secrets
import socket
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple
from urllib.parse import urlparse


# ── Constants ────────────────────────────────────────────────────────────

SECRET_LEAK_PATTERNS = re.compile(
    r"(?i)(?:"
    r"nvapi-[a-zA-Z0-9_\-]{40,}|"
    r"sk-[a-zA-Z0-9]{32,}|"
    r"gsk_[a-zA-Z0-9]{32,}|"
    r"ghp_[a-zA-Z0-9]{36,}|"
    r"gho_[a-zA-Z0-9]{36,}|"
    r"ghu_[a-zA-Z0-9]{36,}|"
    r"AKIA[0-9A-Z]{16}|"
    r"eyJ[a-zA-Z0-9_\-]+\.[a-zA-Z0-9_\-]+\.[a-zA-Z0-9_\-]+|"
    r"api[-_]?key['\"]?\s*[:=]\s*['\"][a-zA-Z0-9_\-]{16,}|"
    r"-----BEGIN (?:RSA |EC |DSA |OPENSSH )?PRIVATE KEY-----"
    r")"
)

_SHELL_BLOCKED_TOOLS = r"\b(?:certutil|bitsadmin|wget|curl|Invoke-Expression|Start-Process|Remove-Item)\s"
_SHELL_BLOCKED_WORDS = r"(?:\b(?:certutil|bitsadmin|wget|curl|Invoke-Expression|iex|Start-Process|Remove-Item)\s)"
SHELL_INJECTION_PATTERN = re.compile(
    r"(?:[;&|`$(){}\n\r\t\x00])|"
    r"(?:\b(?:powershell|cmd|bash|sh|wscript|cscript|rundll32|regsvr32|mshta|msiexec)\s+)|"
    r"(?:\-enc(?:odedcommand)?\s+[a-z0-9+/=]{20,})|" +
    _SHELL_BLOCKED_WORDS,
    re.IGNORECASE,
)

PYTHON_SANDBOX_ESCAPE_PATTERNS = re.compile(
    r"(?:\b__\w+__\b|"
    r"\bgetattr\s*\(|"
    r"\bsetattr\s*\(|"
    r"\bdelattr\s*\(|"
    r"\bglobals\s*\(|"
    r"\blocals\s*\(|"
    r"\bvars\s*\(|"
    r"\b__import__\s*\("
    r")"
)

_PRIVATE_NETWORKS = [
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("169.254.0.0/16"),
    ipaddress.ip_network("0.0.0.0/32"),
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fc00::/7"),
    ipaddress.ip_network("fe80::/10"),
]

_CLOUD_METADATA_IPS = {"169.254.169.254", "169.254.169.253", "100.100.100.200"}

ALLOWED_ROOTS_DEFAULT = [os.path.realpath(os.path.expanduser("~"))]


# ── Audit Singleton ──────────────────────────────────────────────────────

class AuditLogger:
    """Centralized security audit logging with rotation."""
    _lock = threading.Lock()
    _instance = None
    _log_dir: Optional[Path] = None
    _log_file: Optional[Path] = None

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    inst = super().__new__(cls)
                    inst._log_dir = Path(__file__).parent.parent / "logs" / "audit"
                    inst._log_dir.mkdir(parents=True, exist_ok=True)
                    inst._log_file = inst._log_dir / "security.audit.log"
                    inst._max_bytes = 10 * 1024 * 1024
                    inst._backup_count = 5
                    cls._instance = inst
        return cls._instance

    def _rotate(self):
        path = self._log_file
        if path and path.exists() and path.stat().st_size > self._max_bytes:
            for i in range(self._backup_count - 1, 0, -1):
                backup = path.with_suffix(f".audit.{i}.log")
                prev = path.with_suffix(f".audit.{i - 1}.log" if i > 1 else ".audit.log")
                if backup.exists():
                    backup.unlink()
                if prev.exists():
                    prev.rename(backup)
            path.rename(path.with_suffix(".audit.1.log"))

    def log(self, event: str, severity: str = "info", detail: Optional[Dict] = None):
        try:
            self._rotate()
            ts = time.strftime("%Y-%m-%dT%H:%M:%S%z")
            parts = f"[{ts}] [{severity.upper():>7}] [{event}]"
            if detail:
                safe = {}
                for k, v in detail.items():
                    s = str(v)[:200]
                    s = SECRET_LEAK_PATTERNS.sub("[REDACTED]", s)
                    safe[k] = s
                parts += f" {safe}"
            with open(self._log_file, "a", encoding="utf-8") as f:
                f.write(parts + "\n")
        except (OSError, IOError) as e:
            import sys
            print(f"[AUDIT_LOG_ERROR] {e}", file=sys.stderr)


def audit(event: str, severity: str = "info", detail: Optional[Dict] = None):
    AuditLogger().log(event, severity, detail)


# ── Rate Limiter ─────────────────────────────────────────────────────────

class RateLimiter:
    _lock = threading.Lock()
    _windows: Dict[str, List[float]] = {}
    _MAX_KEYS = 10000

    @classmethod
    def _cleanup(cls):
        now = time.time()
        stale_keys = [k for k, times in cls._windows.items()
                      if not any(now - t < 60 for t in times)]
        for k in stale_keys:
            del cls._windows[k]

    @classmethod
    def check(cls, key: str, rate: float = 1.0, burst: int = 5) -> bool:
        now = time.time()
        with cls._lock:
            if len(cls._windows) > cls._MAX_KEYS:
                cls._cleanup()
            times = cls._windows.get(key, [])
            times = [t for t in times if now - t < 1.0 / rate * burst]
            if len(times) >= burst:
                return False
            times.append(now)
            cls._windows[key] = times
            return True

    @classmethod
    def remaining(cls, key: str, rate: float = 1.0, burst: int = 5) -> int:
        now = time.time()
        with cls._lock:
            times = cls._windows.get(key, [])
            times = [t for t in times if now - t < 1.0 / rate * burst]
            return max(0, burst - len(times))


# ── Input Validation ─────────────────────────────────────────────────────

class InputValidator:
    MAX_INPUT_LENGTH = 50000
    MAX_PATH_LENGTH = 512
    MAX_CODE_LENGTH = 20000

    @staticmethod
    def validate_shell_command(command: str) -> Optional[str]:
        if not command or not command.strip():
            return "Empty command"
        if len(command) > InputValidator.MAX_INPUT_LENGTH:
            return f"Command too long (max {InputValidator.MAX_INPUT_LENGTH} chars)"
        if SHELL_INJECTION_PATTERN.search(command):
            audit("shell_injection_blocked", "high", {"command": command[:100]})
            return "Command blocked: contains shell injection characters"
        _DANGEROUS = re.compile(
            r"(?:\b(?:format|diskpart|fdisk|parted|mkfs\.)\b.*?(?::|$)|"
            r"\b(?:shutdown|reboot|poweroff|halt)\b|"
            r"\bdd\s+.*?\b(?:if=|of=)|"
            r"\brm\s+.*?(?:-rf\s+/|--no-preserve-root)|"
            r"\b(?:net\s+(?:user|localgroup|group))\b|"
            r"\b(?:sc\s+delete|schtasks)\b|"
            r"\b(?:Invoke-Expression|iex|Invoke-Command)\b|"
            r"\b(?:New-Object\s+(?:System\.Net\.WebClient|Net\.WebClient))\b|"
            r"\bmshta\b|\brundll32\b|\bregsvr32\b)",
            re.IGNORECASE
        )
        if _DANGEROUS.search(command):
            audit("dangerous_command_blocked", "high", {"command": command[:100]})
            return "Command blocked: contains dangerous operations"
        return None

    @staticmethod
    def validate_path(path: str, allowed_roots: Optional[List[str]] = None) -> Optional[str]:
        if not path:
            return "Empty path"
        if len(path) > InputValidator.MAX_PATH_LENGTH:
            return "Path too long"
        if not isinstance(path, str):
            return "Invalid path type"
        null_byte = "\x00"
        if null_byte in path:
            return "Path contains null byte"
        return None

    @staticmethod
    def validate_url(url: str) -> Optional[str]:
        if not url:
            return "Empty URL"
        if len(url) > 8192:
            return "URL too long"
        if not url.startswith(("http://", "https://")):
            url = "https://" + url
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https"):
            return "Only HTTP/HTTPS URLs allowed"
        hostname = parsed.hostname
        if not hostname:
            return "Invalid URL: no hostname"
        if not re.match(r'^[a-zA-Z0-9.\-:\[\]]+$', hostname):
            return "Invalid hostname format"
        return None

    @staticmethod
    def validate_code(code: str, language: str = "python") -> Optional[str]:
        if not code or not code.strip():
            return "Empty code"
        if len(code) > InputValidator.MAX_CODE_LENGTH:
            return f"Code too long (max {InputValidator.MAX_CODE_LENGTH} chars)"
        if language == "python":
            try:
                ast.parse(code)
            except SyntaxError as e:
                return f"Syntax error: {e}"
            if PYTHON_SANDBOX_ESCAPE_PATTERNS.search(code):
                audit("python_sandbox_escape_attempt", "critical", {"code": code[:200]})
                return "Code contains forbidden patterns"
        return None


# ── Path Traversal Prevention ────────────────────────────────────────────

class PathValidator:
    @staticmethod
    def safe_resolve(path: str, allowed_roots: Optional[List[str]] = None) -> str:
        if allowed_roots is None:
            allowed_roots = ALLOWED_ROOTS_DEFAULT
        expanded = os.path.expanduser(path)
        if not os.path.isabs(expanded):
            expanded = os.path.realpath(os.path.join(os.getcwd(), expanded))
        resolved = os.path.realpath(expanded)
        for root in allowed_roots:
            resolved_root = os.path.realpath(root)
            if resolved == resolved_root or resolved.startswith(resolved_root + os.sep):
                return resolved
        audit("path_traversal_blocked", "high", {"path": path, "resolved": resolved})
        raise PermissionError(f"Access denied: path '{resolved}' is outside allowed directories")

    @staticmethod
    def verify_no_symlink_race(path: str, allowed_roots: Optional[List[str]] = None) -> str:
        stat1 = os.stat(path)
        resolved = PathValidator.safe_resolve(path, allowed_roots)
        try:
            stat2 = os.stat(resolved)
        except OSError:
            raise PermissionError("Access denied: path resolution failed after stat check")
        if stat1.st_ino != stat2.st_ino or stat1.st_dev != stat2.st_dev:
            audit("symlink_race_detected", "critical", {"path": path})
            raise PermissionError("Access denied: symlink race detected")
        return resolved

    @staticmethod
    def validate_glob_results(matches: List[str], allowed_roots: Optional[List[str]] = None) -> List[str]:
        if allowed_roots is None:
            allowed_roots = ALLOWED_ROOTS_DEFAULT
        safe_matches = []
        for m in matches:
            resolved = os.path.realpath(m)
            for root in allowed_roots:
                resolved_root = os.path.realpath(root)
                if resolved == resolved_root or resolved.startswith(resolved_root + os.sep):
                    safe_matches.append(m)
                    break
        return safe_matches


# ── Python Sandbox (AST-based) ───────────────────────────────────────────

FORBIDDEN_MODULES = {
    "os", "subprocess", "shutil", "socket", "ctypes", "signal",
    "multiprocessing", "threading", "importlib", "pkgutil", "pdb",
    "inspect", "code", "codeop", "compileall", "py_compile",
    "webbrowser", "antigravity", "turtle", "_io", "codecs",
    "pathlib", "glob", "fnmatch", "urllib", "urllib2", "httplib",
}

FORBIDDEN_ATTR_ACCESS = {
    "__class__", "__bases__", "__mro__", "__subclasses__",
    "__globals__", "__code__", "__closure__", "__func__",
    "__dict__", "__builtins__", "__builtin__",
    "__getattribute__", "__getattr__", "__setattr__",
    "__reduce__", "__reduce_ex__",
}

DANGEROUS_FUNCTIONS = {
    "exec", "eval", "compile", "__import__", "open",
    "input", "breakpoint", "help",
    "getattr", "setattr", "delattr",
    "globals", "locals", "vars",
}

SAFE_MODULES = {
    "math", "cmath", "decimal", "fractions", "random", "statistics",
    "json", "base64", "binascii", "struct",
    "itertools", "functools", "operator", "collections", "heapq", "bisect",
    "re", "string", "textwrap", "difflib", "unicodedata",
    "datetime", "time", "calendar",
    "typing", "enum", "dataclasses", "abc",
    "copy", "pprint", "reprlib",
    "array", "queue",
    "hashlib", "uuid", "secrets",
}


class CodeSandbox:
    class SandboxError(Exception):
        pass

    @staticmethod
    def get_attr_chain(node):
        chain = []
        while isinstance(node, ast.Attribute):
            chain.append(node.attr)
            node = node.value
        if isinstance(node, ast.Name):
            chain.append(node.id)
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            sub_chain = CodeSandbox.get_attr_chain(node.func)
            if sub_chain:
                return sub_chain
        elif isinstance(node, ast.Subscript):
            sub_chain = CodeSandbox.get_attr_chain(node.value)
            if sub_chain:
                return sub_chain
        return chain[::-1] if chain else None

    @staticmethod
    def check_code_safety(code):
        if not code or not code.strip():
            return None
        try:
            tree = ast.parse(code)
        except SyntaxError as e:
            raise CodeSandbox.SandboxError(f"Syntax error: {e}")

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    base = alias.name.split(".")[0]
                    if base in FORBIDDEN_MODULES:
                        raise CodeSandbox.SandboxError(f"Module '{alias.name}' is not allowed")
                    if base not in SAFE_MODULES:
                        raise CodeSandbox.SandboxError(f"Module '{alias.name}' not in sandbox allowlist")

            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    base = node.module.split(".")[0]
                    if base in FORBIDDEN_MODULES:
                        raise CodeSandbox.SandboxError(f"Module '{node.module}' is not allowed")
                    if base not in SAFE_MODULES:
                        raise CodeSandbox.SandboxError(f"Module '{node.module}' not in sandbox allowlist")

            elif isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name):
                    if node.func.id in DANGEROUS_FUNCTIONS:
                        raise CodeSandbox.SandboxError(f"Function '{node.func.id}()' is not allowed")
                elif isinstance(node.func, ast.Attribute):
                    chain = CodeSandbox.get_attr_chain(node.func)
                    if chain:
                        for part in chain:
                            if part in FORBIDDEN_ATTR_ACCESS:
                                raise CodeSandbox.SandboxError(f"Access to '{'.'.join(chain)}' is not allowed")

            elif isinstance(node, ast.Attribute):
                chain = CodeSandbox.get_attr_chain(node)
                if chain:
                    for part in chain:
                        if part in FORBIDDEN_ATTR_ACCESS:
                            raise CodeSandbox.SandboxError(f"Access to '{'.'.join(chain)}' is not allowed")

            elif isinstance(node, ast.Subscript):
                if isinstance(node.value, (ast.Attribute, ast.Call, ast.Subscript)):
                    chain = CodeSandbox.get_attr_chain(node.value)
                    if chain:
                        for part in chain:
                            if part in FORBIDDEN_ATTR_ACCESS:
                                raise CodeSandbox.SandboxError(f"Access to '{'.'.join(chain)}' via subscript is not allowed")

        return tree

    @staticmethod
    def create_safe_builtins():
        def safe_import(name, *args, **kwargs):
            base = name.split(".")[0]
            if base in FORBIDDEN_MODULES:
                raise CodeSandbox.SandboxError(f"Module '{name}' is not allowed")
            if base not in SAFE_MODULES:
                raise CodeSandbox.SandboxError(f"Module '{name}' is not in the allowed safe list")
            return __import__(name, *args, **kwargs)

        safe = {
            "abs": abs, "all": all, "any": any, "ascii": ascii,
            "bin": bin, "bool": bool, "bytearray": bytearray, "bytes": bytes,
            "callable": callable, "chr": chr, "complex": complex,
            "dict": dict, "divmod": divmod,
            "enumerate": enumerate,
            "filter": filter, "float": float, "format": format, "frozenset": frozenset,
            "hash": hash, "hex": hex,
            "id": id, "int": int, "isinstance": isinstance,
            "iter": iter,
            "len": len, "list": list, "map": map,
            "max": max, "min": min,
            "next": next, "object": object, "oct": oct, "ord": ord,
            "pow": pow, "print": print, "property": property,
            "range": range, "repr": repr, "reversed": reversed, "round": round,
            "set": set, "slice": slice, "sorted": sorted, "str": str, "sum": sum,
            "tuple": tuple, "type": type,
            "zip": zip,
            "True": True, "False": False, "None": None,
            "__import__": safe_import,
        }
        return safe


# ── SSRF Prevention ──────────────────────────────────────────────────────

class SSRFGuard:
    @classmethod
    def _resolve_all_ips(cls, hostname):
        try:
            addrinfo = socket.getaddrinfo(hostname, 80)
            return list(set(sockaddr[0] for _, _, _, _, sockaddr in addrinfo))
        except OSError:
            return []

    @classmethod
    def is_private_or_metadata(cls, hostname):
        if not hostname:
            return True
        try:
            addr = ipaddress.ip_address(hostname)
            if str(addr) in _CLOUD_METADATA_IPS:
                return True
            if any(addr in net for net in _PRIVATE_NETWORKS):
                return True
            return False
        except ValueError:
            pass
        ips = cls._resolve_all_ips(hostname)
        if not ips:
            return True
        for ip in ips:
            try:
                addr = ipaddress.ip_address(ip)
                if str(addr) in _CLOUD_METADATA_IPS:
                    return True
                if any(addr in net for net in _PRIVATE_NETWORKS):
                    return True
            except ValueError:
                return True
        return False

    @classmethod
    def validate_url(cls, url):
        if not url.startswith(("http://", "https://")):
            if "." not in url:
                raise ValueError("Invalid URL")
            url = "https://" + url
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https"):
            raise ValueError("Only HTTP/HTTPS URLs are allowed")
        if cls.is_private_or_metadata(parsed.hostname):
            raise ValueError("Access to internal or private network addresses is not allowed")
        return url

    @classmethod
    def check_dns_rebinding(cls, hostname):
        try:
            import dns.resolver
        except ImportError:
            return False
        try:
            answers = dns.resolver.resolve(hostname, "A")
            ips1 = sorted(str(r) for r in answers)
            time.sleep(0.5)
            answers = dns.resolver.resolve(hostname, "A")
            ips2 = sorted(str(r) for r in answers)
            if ips1 != ips2:
                audit("dns_rebinding_detected", "critical", {"hostname": hostname, "ips1": ips1, "ips2": ips2})
                return True
        except Exception:
            pass
        return False


# ── Web Security ─────────────────────────────────────────────────────────

class WebGuard:
    CSP_DEFAULT = (
        "default-src 'self'; "
        "script-src 'self'; "
        "style-src 'self' 'unsafe-inline'; "
        "connect-src 'self' ws:; "
        "img-src 'self' data:; "
        "font-src 'self'; "
        "frame-ancestors 'none'; "
        "base-uri 'self'"
    )

    @staticmethod
    def security_headers():
        return {
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": "DENY",
            "X-XSS-Protection": "1; mode=block",
            "Referrer-Policy": "no-referrer",
            "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
            "Permissions-Policy": "geolocation=(), microphone=(), camera=()",
        }

    @staticmethod
    def generate_csrf_token(secret_key: bytes) -> str:
        token = secrets.token_urlsafe(32)
        sig = hmac.new(secret_key, token.encode(), hashlib.sha256).hexdigest()
        return f"{token}.{sig}"

    @staticmethod
    def validate_csrf_token(token: str, secret_key: bytes, max_age: int = 3600) -> bool:
        if not token or "." not in token:
            return False
        parts = token.split(".")
        if len(parts) != 2:
            return False
        payload, sig = parts
        expected = hmac.new(secret_key, payload.encode(), hashlib.sha256).hexdigest()
        return hmac.compare_digest(sig, expected)

    @staticmethod
    def validate_origin(origin: str, allowed_origins: Set[str]) -> bool:
        if not origin:
            return False
        return origin in allowed_origins or any(
            origin.startswith(a) for a in allowed_origins
        )


# ── Output Sanitization ──────────────────────────────────────────────────

class Sanitizer:
    @staticmethod
    def sanitize_output(text: str) -> str:
        return SECRET_LEAK_PATTERNS.sub("[REDACTED]", text)

    @staticmethod
    def sanitize_path(path: str) -> str:
        home = os.path.expanduser("~")
        return path.replace(home, "~")


# ── Config Security ──────────────────────────────────────────────────────

class ConfigGuard:
    @staticmethod
    def has_plaintext_keys(config: Dict) -> List[str]:
        findings = []
        for provider, settings in config.get("providers", {}).items() if isinstance(config, dict) else []:
            if isinstance(settings, dict):
                for key, value in settings.items():
                    if "key" in key.lower() or "secret" in key.lower() or "token" in key.lower():
                        if isinstance(value, str) and len(value) > 8 and not value.startswith("$"):
                            findings.append(f"{provider}.{key}: plaintext key detected")
        return findings

    @staticmethod
    def validate_config(config: Dict) -> List[str]:
        issues = []
        if not isinstance(config, dict):
            return ["Config is not a valid JSON object"]
        for provider in config.get("providers", {}):
            settings = config["providers"][provider]
            if isinstance(settings, dict):
                for key in settings:
                    if "key" in key.lower() and isinstance(settings[key], str) and len(settings[key]) > 8:
                        if not settings[key].startswith("$"):
                            issues.append(f"Provider '{provider}' has plaintext key in '{key}'")
        return issues
