import os
import sys
import shlex
import subprocess
import tempfile
import re
import json
from core.platform_utils import is_windows, is_linux, is_macos
from core.ratelimit import check_rate
from tools.code_interpreter import SandboxError


BLOCKED_CHAINING = re.compile(r'[;&|`]|\$\(|\$\{|\|\|')
BLOCKED_REDIRECT = re.compile(r'(?:^|[^a-zA-Z])[<>]{1,2}\s*(?:[\\/]|[a-zA-Z]:\\)')

SAFE_COMMANDS_WINDOWS = {
    "echo", "dir", "type", "more", "find", "findstr", "where",
    "whoami", "hostname", "ver", "systeminfo",
    "netstat", "ipconfig", "ping", "tracert", "nslookup",
    "date", "time", "tasklist",
    "cls", "help",
    "copy", "xcopy", "robocopy", "move", "mkdir", "rmdir",
    "sort", "tree", "fc",
}

SAFE_COMMANDS_UNIX = {
    "echo", "ls", "cat", "more", "less", "head", "tail",
    "grep", "find", "whereis", "which",
    "whoami", "hostname", "uname", "arch",
    "netstat", "ifconfig", "ping", "traceroute", "nslookup", "dig",
    "date", "time", "ps", "top", "htop",
    "clear", "pwd", "cal",
    "cp", "mv", "mkdir", "rmdir",
    "sort", "tree", "diff",
}

SAFE_COMMANDS_MACOS = SAFE_COMMANDS_UNIX | {"sw_vers", "system_profiler", "defaults", "diskutil"}

ALLOWED_CHAR_PATTERN = re.compile(r'^[a-zA-Z0-9_\-./:@%+,=~ ]+$')


def _get_allowed():
    if is_windows():
        return SAFE_COMMANDS_WINDOWS
    if is_macos():
        return SAFE_COMMANDS_MACOS
    return SAFE_COMMANDS_UNIX


def _check_command_safety(command):
    if not command or not command.strip():
        raise PermissionError("Empty command")
    if BLOCKED_CHAINING.search(command):
        raise PermissionError("Command chaining operators are blocked")
    if BLOCKED_REDIRECT.search(command):
        raise PermissionError("Output redirection to system paths blocked")
    parts = shlex.split(command)
    if not parts:
        raise PermissionError("Empty command")
    cmd_base = os.path.basename(parts[0].lower())
    allowed = _get_allowed()
    if cmd_base not in allowed:
        raise PermissionError(f"Command '{cmd_base}' is not in the allowed list")
    for p in parts:
        if p.lower() in ("sudo", "runas", "doas", "pkexec"):
            raise PermissionError("Privilege escalation commands are blocked")
    return parts


class ShellCommander:
    def _execute(self, cmd_list, timeout):
        try:
            r = subprocess.run(cmd_list, capture_output=True, text=True, timeout=timeout)
            out = []
            if r.stdout.strip():
                out.append(f"stdout:\n{r.stdout.strip()[:5000]}")
            if r.stderr.strip():
                out.append(f"stderr:\n{r.stderr.strip()[:2000]}")
            result = "\n".join(out) if out else "Command completed (no output)"
            return f"Exit code: {r.returncode}\n{result}"
        except subprocess.TimeoutExpired:
            return f"Command timed out after {timeout}s"
        except Exception as e:
            return f"Execution failed: {type(e).__name__}"

    def run_command(self, command, timeout=60):
        if not check_rate("shell_run_command", rate=5, burst=10):
            return "Rate limit exceeded. Please wait before running more commands."
        try:
            parts = _check_command_safety(command)
            if is_windows():
                return self._execute(["cmd", "/c", command], timeout)
            if is_macos():
                return self._execute(["zsh", "-c", command], timeout)
            return self._execute(parts, timeout)
        except PermissionError as e:
            return str(e)

    def run_shell(self, command, timeout=60):
        if is_windows():
            return self._run_powershell(command, timeout)
        if is_macos():
            return self._run_zsh(command, timeout)
        return self._run_bash(command, timeout)

    def _run_powershell(self, command, timeout=60):
        try:
            _check_command_safety(command)
            return self._execute(["powershell", "-NoProfile", "-Command", command], timeout)
        except PermissionError as e:
            return str(e)

    def _run_bash(self, command, timeout=60):
        try:
            _check_command_safety(command)
            return self._execute(["bash", "-c", command], timeout)
        except PermissionError as e:
            return str(e)

    def _run_zsh(self, command, timeout=60):
        try:
            _check_command_safety(command)
            return self._execute(["zsh", "-c", command], timeout)
        except PermissionError as e:
            return str(e)

    def run_powershell(self, command, timeout=60):
        if not is_windows():
            return "PowerShell is only available on Windows."
        return self._run_powershell(command, timeout)

    def run_bash(self, command, timeout=60):
        return self._run_bash(command, timeout)

    def run_zsh(self, command, timeout=60):
        if not is_macos():
            return "Zsh is recommended on macOS."
        return self._run_zsh(command, timeout)

    def run_script(self, code, language="python", timeout=30):
        if language != "python":
            return f"Only Python scripts are supported for security reasons."

        from tools.code_interpreter import _check_code_safety
        try:
            _check_code_safety(code)
        except SandboxError as e:
            return f"Sandbox blocked: {e}"

        wrapper = rf"""import sys, json, builtins as _b
SAFE = {json.dumps(["math","json","re","random","datetime","time","collections","itertools","functools","hashlib","uuid","decimal","fractions","statistics","enum","typing","dataclasses","copy","pprint","string","textwrap","difflib","base64","binascii","struct","array","queue","secrets"])}
_orig = _b.__import__
def _safe_import(name, *a, **kw):
    base = name.split('.')[0]
    if base not in SAFE:
        raise ImportError(f"module '{{name}}' not in safe list")
    return _orig(name, *a, **kw)
_b.__import__ = _safe_import
_b.type = None
_b.open = None
exec({json.dumps(code)})
"""
        try:
            r = subprocess.run(
                [sys.executable, "-I", "-c", wrapper],
                capture_output=True, text=True, timeout=timeout,
                env={**os.environ, "PYTHONPATH": ""}
            )
            out = []
            if r.stdout.strip():
                out.append(f"Output:\n{r.stdout.strip()[:5000]}")
            if r.stderr.strip():
                err = r.stderr.strip()[:2000]
                if "Error:" in err or "Exception" in err:
                    out.append(f"Error:\n{err}")
            return "\n".join(out) if out else "Script completed (no output)"
        except subprocess.TimeoutExpired:
            return f"Script timed out after {timeout}s"
        except Exception as e:
            return f"Script execution failed: {type(e).__name__}: {e}"

    def get_tool_definitions(self):
        tools = [
            {"type": "function", "function": {"name": "run_command", "description": "Run a shell command (safe commands only, no chaining)", "parameters": {"type": "object", "properties": {"command": {"type": "string", "description": "Command to execute"}, "timeout": {"type": "integer", "description": "Timeout in seconds", "default": 60}}, "required": ["command"]}}},
            {"type": "function", "function": {"name": "run_shell", "description": "Run a native shell command (PowerShell on Windows, bash/zsh on Unix)", "parameters": {"type": "object", "properties": {"command": {"type": "string", "description": "Command"}, "timeout": {"type": "integer", "default": 60}}, "required": ["command"]}}},
        ]
        if is_windows():
            tools.append({"type": "function", "function": {"name": "run_powershell", "description": "Run a PowerShell command (Windows only)", "parameters": {"type": "object", "properties": {"command": {"type": "string", "description": "PowerShell command"}, "timeout": {"type": "integer", "default": 60}}, "required": ["command"]}}})
        return tools

    def get_handler(self, name):
        handlers = {"run_command": self.run_command, "run_shell": self.run_shell}
        if is_windows():
            handlers["run_powershell"] = self.run_powershell
        return handlers.get(name)
