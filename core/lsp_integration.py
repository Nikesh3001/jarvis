import os
import re
import subprocess
import threading
from pathlib import Path
from typing import Dict, List, Optional, Any

LANGUAGE_SERVERS = {
    "python": {
        "name": "pyright",
        "command": ["pyright-langserver", "--stdio"],
        "args": {},
    },
    "javascript": {
        "name": "typescript-language-server",
        "command": ["typescript-language-server", "--stdio"],
        "args": {},
    },
    "typescript": {
        "name": "typescript-language-server",
        "command": ["typescript-language-server", "--stdio"],
        "args": {},
    },
    "go": {
        "name": "gopls",
        "command": ["gopls"],
        "args": {},
    },
    "rust": {
        "name": "rust-analyzer",
        "command": ["rust-analyzer"],
        "args": {},
    },
    "java": {
        "name": "jdtls",
        "command": ["jdtls"],
        "args": {},
    },
    "csharp": {
        "name": "omnisharp",
        "command": ["omnisharp"],
        "args": {},
    },
}

EXTENSION_MAP = {
    ".py": "python",
    ".js": "javascript",
    ".jsx": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".go": "go",
    ".rs": "rust",
    ".java": "java",
    ".cs": "csharp",
    ".rb": "ruby",
    ".php": "php",
    ".swift": "swift",
    ".kt": "kotlin",
    ".scala": "scala",
    ".dart": "dart",
}


def detect_language(filepath: str) -> Optional[str]:
    ext = os.path.splitext(filepath)[1].lower()
    return EXTENSION_MAP.get(ext)


def get_server_for_file(filepath: str) -> Optional[Dict]:
    lang = detect_language(filepath)
    if not lang:
        return None
    return LANGUAGE_SERVERS.get(lang)


class LSPServerManager:
    def __init__(self):
        self.servers = {}
        self._lock = threading.Lock()

    def start_server(self, language: str, workspace_root: str = ".") -> bool:
        config = LANGUAGE_SERVERS.get(language)
        if not config:
            return False
        try:
            proc = subprocess.Popen(
                config["command"],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=workspace_root,
            )
            with self._lock:
                self.servers[language] = {
                    "process": proc,
                    "config": config,
                    "workspace": workspace_root,
                }
            return True
        except FileNotFoundError:
            return False

    def stop_server(self, language: str) -> bool:
        with self._lock:
            server = self.servers.pop(language, None)
            if server and server["process"]:
                server["process"].terminate()
                return True
        return False

    def is_server_running(self, language: str) -> bool:
        with self._lock:
            return language in self.servers

    def get_diagnostics(self, filepath: str) -> List[Dict]:
        lang = detect_language(filepath)
        if not lang:
            return [{"severity": "error", "message": f"Unknown language for {filepath}"}]
        if not self.is_server_running(lang):
            started = self.start_server(lang, os.path.dirname(filepath))
            if not started:
                return [{"severity": "info", "message": f"LSP server '{lang}' not available. Install it for code intelligence."}]
        return self._request_diagnostics(filepath, lang)

    def _request_diagnostics(self, filepath: str, language: str) -> List[Dict]:
        with self._lock:
            server = self.servers.get(language)
            if not server:
                return [{"severity": "warn", "message": f"Server for {language} not running"}]
            proc = server["process"]
            if not proc or proc.poll() is not None:
                return [{"severity": "warn", "message": f"Server for {language} has terminated"}]

        try:
            content = Path(filepath).read_text(encoding="utf-8", errors="ignore")
            diagnostics = []
            lines = content.split("\n")
            for i, line in enumerate(lines[:100], 1):
                if len(line) > 120:
                    diagnostics.append({
                        "severity": "warn",
                        "message": f"Line {i} exceeds 120 characters ({len(line)})",
                        "line": i,
                    })
            return diagnostics
        except Exception:
            return [{"severity": "error", "message": f"Could not read {filepath}"}]

    def get_completions(self, filepath: str, line: int, column: int) -> List[Dict]:
        return [{"label": "completion", "detail": "LSP not fully connected"}]

    def get_hover_info(self, filepath: str, line: int, column: int) -> Optional[str]:
        return None

    def format_document(self, filepath: str) -> Optional[str]:
        lang = detect_language(filepath)
        if not lang:
            return None
        formatters = {
            "python": ["black", "-"],
            "javascript": ["prettier", "--stdin-filepath", filepath],
            "typescript": ["prettier", "--stdin-filepath", filepath],
        }
        cmd = formatters.get(lang)
        if not cmd:
            return None
        try:
            content = Path(filepath).read_text(encoding="utf-8", errors="ignore")
            result = subprocess.run(cmd, input=content, capture_output=True, text=True, timeout=15)
            if result.returncode == 0:
                return result.stdout
            return None
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return None

    def get_server_status(self) -> Dict[str, str]:
        with self._lock:
            status = {}
            for lang, server in self.servers.items():
                proc = server["process"]
                if proc and proc.poll() is None:
                    status[lang] = "running"
                else:
                    status[lang] = "stopped"
            return status

    def cleanup(self):
        with self._lock:
            for lang, server in list(self.servers.items()):
                if server["process"]:
                    server["process"].terminate()
            self.servers.clear()
