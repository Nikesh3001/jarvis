import os
import sys
import shlex
import subprocess
import tempfile
import re
import ast
from core.platform_utils import is_windows, is_linux, is_macos
from core.ratelimit import check_rate


_DANGEROUS_COMMANDS = re.compile(
    r"""
    (?:
        \b(?:format|diskpart|fdisk|parted|mkfs\.)\b.*?(?::|$)
        |
        \b(?:rd|rmdir)\s+.*?/s
        |
        \brm\s+.*?(?:-rf\s+/|--recursive\s+.*?--force\s+/|--no-preserve-root|-rf\s+~[/\\]|-rf\s+\$HOME[/\\])
        |
        \bdel\s+.*?(?:/f\s+/s|/f/s|/s\s+/f)
        |
        \b(?:shutdown|reboot|poweroff|halt|shut\s+down)\b
        |
        \bdd\s+.*?\b(?:if=|of=)
        |
        (?:^|\s)(?:>|>>?)\s*/dev/(?:sda|hda|nvme|mmcblk|sdb|sdc|sd[defgh])
        |
        \breg\s+(?:delete|add|import|copy|save|load|restore|compare|export)\b
        |
        \b(?:net\s+(?:user|localgroup|group|accounts|share|session))\b
        |
        \b(?:sc\s+delete|schtasks)\b
        |
        \b(?:wevtutil\s+(?:cl|clear-log|delete-log|export-log|import-log))\b
        |
        \b(?:cipher\s+/w:?|bcdedit)\b
        |
        \bfsutil\b
        |
        \bvssadmin\s+delete\b
        |
        \b(?:wmic\s+process\s+call\s+create|wmic\s+delete)\b
        |
        \b(?:chkdsk|defrag|sfc\s+/scannow|dism\s+/online\s+/cleanup-image)\b.*?(?:/f|fix)
        |
        \bformat\.com
        |
        \b(?:Invoke-Expression|iex|Invoke-Command|Invoke-WebRequest|Invoke-Item|Add-Type)\b
        |
        \b(?:[-])?EncodedCommand\b
        |
        \b(?:[-])?enc(?:odedcommand)?\b
        |
        \b[-]+ec\b
        |
        \bNew-Object\s+(?:System\.Net\.WebClient|Net\.WebClient|System\.Diagnostics\.Process|System\.Management\.Automation\.PSCredential)\b
        |
        \b(?:rm\s+(?:-rf\s+)?~[/\\]|rm\s+(?:-rf\s+)?\$HOME[/\\]|rm\s+(?:-rf\s+)?\$env:USERPROFILE[/\\])
        |
        \b(?:curl|wget|iwr|wget|Invoke-WebRequest)\s+.*?(?:-o|-outfile|>)
        |
        \b(?:certutil|bitsadmin|wmic)\s+.*?\b(?:url|cache|download|split|-f)\b
        |
        \becho\s+.*?\|.*?\b(?:powershell|cmd|sh|bash|wmic|mshta)\b
        |
        \b(?:mshta|rundll32|regsvr32|cscript|wscript|msiexec)\s+/[a-z]
        |
        \bStart-Process\s+.*?-FilePath\s+
        |
        \[System\.Reflection\.Assembly\]::Load
        |
        \b(?:python|python3|node|perl|ruby)\s+-[ce]\s+
        |
        \bbase64\s+(?:-d|--decode)\s*
        |
        \b(?:FromBase64String|Convert)\b.*?\b(?:FromBase64|ToBase64)\b
        |
        # Backtick command execution (dangerous patterns only)
        (?:\|\||&&)\s*`[^`]+`
        |
        # Double-pipe and double-ampersand chains with dangerous commands
        (?:\|\||&&)\s*(?:rm|del|format|shutdown|reboot|rd|rmdir|taskkill|kill)
        |
        # PowerShell download cradles
        (?:New-Object\s+Net\.WebClient|Invoke-WebRequest|Start-BitsTransfer)\s+.*?\b(?:Download|download)
        |
        # WMI lateral movement
        \bwmic\s+(?:node|computername)\s+
        |
        # Scheduled task persistence
        \bschtasks\s+(?:/create|/delete|/change)
        |
        # Service manipulation
        \bsc\s+(?:create|delete|config|start|stop)\s+
        |
        # Registry persistence
        \breg\s+add\s+.*?\\(?:Run|RunOnce)\b
        |
        # Base64 encoded command patterns
        (?:cmd|powershell|bash)\s+.*?-e\s+[A-Za-z0-9+/=]{20,}
    )
    """,
    re.IGNORECASE | re.VERBOSE
)

def _check_dangerous(command):
    if _DANGEROUS_COMMANDS.search(command):
        raise PermissionError("Command blocked: contains dangerous operations")


def _check_python_sandbox(code):
    """Module-level Python sandbox check."""
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
            pass
    for forbidden in FORBIDDEN_STRINGS:
        if forbidden in code:
            return f"Code contains forbidden pattern: '{forbidden}'"
    return None


def _check_dangerous_code(code, language="python"):
    """Check script code for dangerous operations before execution."""
    _check_dangerous(code)
    if language in ("batch", "powershell"):
        dangerous_patterns = re.compile(
            r"""(?:
                \b(?:Invoke-Expression|iex|Invoke-Command|Invoke-WebRequest|Invoke-Item|Add-Type)\b
                |\b(?:[-])?EncodedCommand\b
                |\b(?:[-])?enc(?:odedcommand)?\b
                |\b[-]+ec\b
                |\bNew-Object\s+(?:System\.Net\.WebClient|Net\.WebClient|System\.Diagnostics\.Process)\b
                |\b(?:curl|wget|iwr)\s+.*?(?:-o|-outfile|>)\b
                |\b(?:certutil|bitsadmin)\s+.*?\b(?:url|cache|download|split|-f)\b
                |\bStart-Process\s+.*?-FilePath\s+\b
            )""",
            re.IGNORECASE | re.VERBOSE
        )
        if dangerous_patterns.search(code):
            raise PermissionError(f"Script blocked: contains dangerous {language} operations")
    elif language in ("bash", "zsh"):
        dangerous_patterns = re.compile(
            r"""(?:
                \b(?:curl|wget)\s+.*?\|(?:bash|sh)\b
                |\beval\b
                |\bexec\b
                |\bbase64\s+--decode\s*\|
                |\b/tmp/\b.*\b(?:chmod|bash|sh)\b
            )""",
            re.IGNORECASE | re.VERBOSE
        )
        if dangerous_patterns.search(code):
            raise PermissionError(f"Script blocked: contains dangerous {language} operations")
    elif language == "javascript":
        dangerous_patterns = re.compile(
            r"""(?:
                \brequire\s*\(\s*['"](?:child_process|fs|os|net|http|https|dgram|cluster)\b
                |\bexec\s*\(
                |\bspawn\s*\(
                |\bfs\s*\.\s*(?:writeFile|readFile|unlink|rmdir|chmod)\b
                |\bprocess\s*\.\s*(?:exit|env|argv)\b
            )""",
            re.IGNORECASE | re.VERBOSE
        )
        if dangerous_patterns.search(code):
            raise PermissionError(f"Script blocked: contains dangerous {language} operations")
    elif language == "python":
        sandbox_err = _check_python_sandbox(code)
        if sandbox_err:
            raise PermissionError(sandbox_err)


class ShellCommander:
    def run_command(self, command, timeout=60):
        if not check_rate("shell_run_command", rate=5, burst=10):
            return "Rate limit exceeded. Please wait before running more commands."
        try:
            _check_dangerous(command)
            if is_windows():
                r = subprocess.run(
                    command,
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                )
            else:
                cmd_parts = shlex.split(command)
                r = subprocess.run(
                    cmd_parts,
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
        except Exception:
            return "Command execution failed"

    def _run_powershell(self, command, timeout=60):
        try:
            _check_dangerous(command)
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
        except Exception:
            return "PowerShell execution failed"

    def _run_bash(self, command, timeout=60):
        try:
            _check_dangerous(command)
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
        except Exception:
            return "Shell execution failed"

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
        except PermissionError as e:
            return str(e)
        except subprocess.TimeoutExpired:
            return f"Script timed out after {timeout}s"
        except Exception:
            return "Script execution failed"
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
