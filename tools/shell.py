import os
import sys
import shlex
import subprocess
import tempfile
import re
import ast
import shutil
import threading
from core.platform_utils import is_windows, is_linux, is_macos
from core.ratelimit import check_rate


ALLOWED_COMMANDS = {
    "echo", "dir", "ls", "pwd", "cd", "type", "cat", "more", "less",
    "head", "tail", "find", "grep", "findstr", "where", "which",
    "whoami", "hostname", "ver", "systeminfo", "uname",
    "netstat", "ipconfig", "ifconfig", "ping", "tracert", "traceroute",
    "nslookup", "curl", "wget",
    "date", "time", "tasklist", "ps", "top",
    "cls", "clear", "help", "calc", "notepad",
    "copy", "xcopy", "robocopy", "move", "del", "erase", "mkdir", "rmdir",
    "sort", "more", "tree",
}


BLOCKED_PATTERNS = re.compile(
    r"(?:"
    r"rm\s+(?:-rf\s+)?[/~]|del\s+/[fs]|format\s|shutdown\s|reboot|poweroff|halt|"
    r"dd\s+.*(?:if=|of=)|mkfs\.|diskpart|fdisk|parted|"
    r"reg\s+(?:delete|add\s+.*\\Run)|schtasks\s+/create|sc\s+create|"
    r"Invoke-Expression|iex\s+|Invoke-Command|Invoke-WebRequest|"
    r"EncodedCommand|New-Object\s+(?:System|Com)|Start-Process|"
    r"certutil\s+.*-urlcache|bitsadmin\s+.*/download|"
    r"mshta|rundll32|regsvr32|cscript|wscript|msiexec\s+/|"
    r"wmic\s+|Add-Type|Add-MpPreference|Set-MpPreference|"
    r"Stop-Process|Restart-Computer|Stop-Computer|"
    r"Clear-EventLog|Remove-EventLog|"
    r"Get-ChildItem\s+.*\\\.git|Get-Content\s+.*\\\.git|"
    r"Remove-Item|rm\s+-recurse|rmdir\s+/[qs]|"
    r">\s*\\\\.\w+",
    r")",
    re.IGNORECASE
)


def _check_command_safety(command):
    if BLOCKED_PATTERNS.search(command):
        raise PermissionError("Command blocked: contains dangerous operations")
    parts = shlex.split(command)
    if not parts:
        raise PermissionError("Empty command")
    cmd_base = os.path.basename(parts[0].lower())
    parts_lower = [p.lower() for p in parts]
    for p in parts_lower:
        if p in ("sudo", "runas", "doas"):
            raise PermissionError("Privilege escalation commands are blocked")
    return parts


def _check_dangerous_code(code, language="python"):
    if language in ("batch", "powershell"):
        dangerous_patterns = re.compile(
            r"(?:Invoke-Expression|iex\b|Invoke-Command|Invoke-WebRequest|Add-Type|"
            r"Add-MpPreference|Set-MpPreference|Restart-Computer|Stop-Computer|"
            r"Stop-Process\s+-Name\s+(?:defender|security|firewall)|"
            r"EncodedCommand|New-Object\s+(?:System\.Net\.WebClient|System\.IO\.|System\.Diagnostics\.Process|System\.Management\.Automation\.PSObject)|"
            r"Start-Process\s+.*-FilePath\s+|"
            r"certutil\s+.*-urlcache|bitsadmin\s+.*/download|"
            r"wmic\s+process\s+delete|wmic\s+product\s+delete|"
            r"Register-ScheduledTask|Set-ScheduledTask|"
            r"Clear-EventLog|Remove-EventLog|"
            r"Get-WmiObject\s+win32_process\s+\|",
            re.IGNORECASE | re.VERBOSE
        )
        if dangerous_patterns.search(code):
            raise PermissionError(f"Script blocked: contains dangerous {language} operations")
    elif language in ("bash", "zsh"):
        dangerous_patterns = re.compile(
            r"(?:curl|wget)\s+.*?\|(?:bash|sh|zsh)\b|\beval\b|\bexec\b|"
            r"/tmp/.*(?:chmod|bash|sh)|"
            r"sudo\s|pkexec\s|chown\s|chmod\s+4\d{2}|"
            r"mount\s|umount\s|dd\s+|mkfs\.|fdisk\s|"
            r"/dev/\w+|/proc/\w+|>/dev/\w+|"
            r"wget\s+.*-O\s+/|curl\s+.*-o\s+/|"
            r"systemctl\s+(?:stop|disable|mask)\s+|"
            r"passwd\s|useradd\s|userdel\s|groupadd\s|groupdel\s",
            re.IGNORECASE | re.VERBOSE
        )
        if dangerous_patterns.search(code):
            raise PermissionError(f"Script blocked: contains dangerous {language} operations")
    elif language == "javascript":
        dangerous_patterns = re.compile(
            r"(?:require\s*\(\s*['\"](?:child_process|fs|os|net|cluster|worker_threads|vm)|"
            r"exec\s*\(|spawn\s*\(|fork\s*\(|"
            r"process\.(?:exit|kill|binding)|"
            r"global\.process|__dirname\s*\+\s*['\"/]|"
            r"eval\s*\(|Function\s*\(|"
            r"fetch\s*\(\s*['\"]file:)",
            re.IGNORECASE | re.VERBOSE
        )
        if dangerous_patterns.search(code):
            raise PermissionError(f"Script blocked: contains dangerous {language} operations")
    elif language == "python":
        sandbox_err = _check_python_sandbox(code)
        if sandbox_err:
            raise PermissionError(sandbox_err)

    if BLOCKED_PATTERNS.search(code):
        raise PermissionError("Script blocked: contains dangerous operations")


def _check_python_sandbox(code):
    FORBIDDEN_MODULES = {"os", "subprocess", "shutil", "socket", "ctypes", "signal",
                         "multiprocessing", "threading", "importlib", "pkgutil", "pdb",
                         "inspect", "code", "codeop", "compileall", "py_compile",
                         "webbrowser", "antigravity", "turtle"}
    FORBIDDEN_STRINGS = ["__import__", "__builtins__", "__subclasses__",
                         "open(", "exec(", "eval(", "compile(",
                         "os.", "subprocess.", "shutil.", "socket.", "ctypes."]
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return "Syntax error in script"
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                module = alias.name.split(".")[0]
                if module in FORBIDDEN_MODULES:
                    return f"Module '{alias.name}' not allowed in sandboxed Python scripts"
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                module = node.module.split(".")[0]
                if module in FORBIDDEN_MODULES:
                    return f"Module '{node.module}' not allowed in sandboxed Python scripts"
    for forbidden in FORBIDDEN_STRINGS:
        if forbidden in code:
            return f"Code contains forbidden pattern: '{forbidden}'"
    return None


class ShellCommander:
    def run_command(self, command, timeout=60):
        if not check_rate("shell_run_command", rate=5, burst=10):
            return "Rate limit exceeded. Please wait before running more commands."
        try:
            _check_command_safety(command)
            if is_windows():
                r = subprocess.run(
                    ["cmd", "/c", command],
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                )
            else:
                r = subprocess.run(
                    ["sh", "-c", command],
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                )
            out = []
            if r.stdout.strip():
                out.append(f"stdout:\n{r.stdout.strip()[:5000]}")
            if r.stderr.strip():
                out.append(f"stderr:\n{r.stderr.strip()[:2000]}")
            result = "\n".join(out) if out else "Command completed (no output)"
            return f"Exit code: {r.returncode}\n{result}"
        except PermissionError as e:
            return str(e)
        except subprocess.TimeoutExpired:
            return f"Command timed out after {timeout}s"
        except Exception as e:
            return f"Command execution failed: {type(e).__name__}"

    def _run_powershell(self, command, timeout=60):
        try:
            _check_command_safety(command)
            r = subprocess.run(
                ["powershell", "-NoProfile", "-Command", command],
                capture_output=True, text=True, timeout=timeout,
            )
            out = []
            if r.stdout.strip():
                out.append(f"stdout:\n{r.stdout.strip()[:5000]}")
            if r.stderr.strip():
                out.append(f"stderr:\n{r.stderr.strip()[:2000]}")
            result = "\n".join(out) if out else "Command completed (no output)"
            return f"Exit code: {r.returncode}\n{result}"
        except PermissionError as e:
            return str(e)
        except subprocess.TimeoutExpired:
            return f"Command timed out after {timeout}s"
        except Exception as e:
            return f"PowerShell execution failed: {type(e).__name__}"

    def _run_bash(self, command, timeout=60):
        try:
            _check_command_safety(command)
            r = subprocess.run(
                ["bash", "-c", command],
                capture_output=True, text=True, timeout=timeout,
            )
            out = []
            if r.stdout.strip():
                out.append(f"stdout:\n{r.stdout.strip()[:5000]}")
            if r.stderr.strip():
                out.append(f"stderr:\n{r.stderr.strip()[:2000]}")
            result = "\n".join(out) if out else "Command completed (no output)"
            return f"Exit code: {r.returncode}\n{result}"
        except PermissionError as e:
            return str(e)
        except subprocess.TimeoutExpired:
            return f"Command timed out after {timeout}s"
        except Exception as e:
            return f"Shell execution failed: {type(e).__name__}"

    def run_powershell(self, command, timeout=60):
        if not is_windows():
            return "PowerShell is only available on Windows."
        return self._run_powershell(command, timeout)

    def run_shell(self, command, timeout=60):
        if is_windows():
            return self._run_powershell(command, timeout)
        return self._run_bash(command, timeout)

    def run_script(self, code, language="python", timeout=30):
        suffix = {"python": ".py", "powershell": ".ps1", "batch": ".bat", "bash": ".sh", "zsh": ".sh", "javascript": ".js"}
        ext = suffix.get(language, ".py")
        if language in ("powershell", "batch") and not is_windows():
            return f"'{language}' scripts are only supported on Windows."
        if language in ("bash", "zsh") and is_windows():
            return f"'{language}' scripts are only supported on Unix (Linux/macOS)."
        try:
            _check_dangerous_code(code, language)
        except PermissionError as e:
            return str(e)
        with tempfile.NamedTemporaryFile(suffix=ext, mode="w", delete=False, encoding="utf-8") as f:
            f.write(code)
            tmp = f.name
        try:
            interpreter = {
                "python": sys.executable, "powershell": "powershell", "batch": "cmd",
                "bash": "bash", "zsh": "zsh", "javascript": "node",
            }
            cmd = interpreter.get(language, sys.executable)
            r = subprocess.run([cmd, tmp], capture_output=True, text=True, timeout=timeout)
            out = []
            if r.stdout.strip():
                out.append(f"Output:\n{r.stdout.strip()[:5000]}")
            if r.stderr.strip():
                out.append(f"Error:\n{r.stderr.strip()[:2000]}")
            return "\n".join(out) if out else "Script completed (no output)"
        except subprocess.TimeoutExpired:
            return f"Script timed out after {timeout}s"
        except Exception as e:
            return f"Script execution failed: {type(e).__name__}"
        finally:
            try:
                os.unlink(tmp)
            except Exception:
                pass

    def get_tool_definitions(self):
        tools = [
            {"type": "function", "function": {"name": "run_command", "description": "Run any shell command (dangerous ops blocked)", "parameters": {"type": "object", "properties": {"command": {"type": "string", "description": "Cmd"}, "timeout": {"type": "integer", "description": "Secs", "default": 60}}, "required": ["command"]}}},
            {"type": "function", "function": {"name": "run_script", "description": "Run temp file (py/ps1/bat/sh/js)", "parameters": {"type": "object", "properties": {"code": {"type": "string", "description": "Code"}, "language": {"type": "string", "description": "python/powershell/batch/bash/zsh/javascript", "default": "python"}, "timeout": {"type": "integer", "description": "Secs", "default": 30}}, "required": ["code"]}}},
        ]
        tools.append({"type": "function", "function": {"name": "run_shell", "description": "Run native shell command (dangerous ops blocked)", "parameters": {"type": "object", "properties": {"command": {"type": "string", "description": "Cmd"}, "timeout": {"type": "integer", "description": "Secs", "default": 60}}, "required": ["command"]}}})
        if is_windows():
            tools.append({"type": "function", "function": {"name": "run_powershell", "description": "Run PowerShell command (Windows only)", "parameters": {"type": "object", "properties": {"command": {"type": "string", "description": "Cmd"}, "timeout": {"type": "integer", "description": "Secs", "default": 60}}, "required": ["command"]}}})
        return tools

    def get_handler(self, name):
        handlers = {"run_command": self.run_command, "run_shell": self.run_shell, "run_script": self.run_script}
        if is_windows():
            handlers["run_powershell"] = self.run_powershell
        return handlers.get(name)