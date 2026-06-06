import os
import sys
import shlex
import subprocess
import tempfile
from core.platform_utils import is_windows, is_linux, is_macos


DANGEROUS_PATTERNS = [
    "format ", "format:",
    "rd /s", "rmdir /s", "rm -rf /", "rm -rf --no-preserve-root",
    "del /f /s", "del /f/s",
    "format.com", "diskpart",
    "shutdown /r", "shutdown /s", "shutdown -r", "shutdown -h", "shutdown -P",
    "reboot", "poweroff", "halt",
    "dd if=", "dd of=",
    "> /dev/sda", "> /dev/hda",
    "mkfs.", "fdisk", "parted",
    "reg delete ", "reg add ", "reg import ",
    "net user ", "net localgroup ", "net group ",
    "sc delete ", "schtasks ",
    "wevtutil cl", "wevtutil clear",
    "cipher /w:", "cipher /w",
    "bcdedit ",
    "fsutil ",
    "vssadmin delete",
    "wmic ",
]


def _check_dangerous(command):
    cmd_lower = command.lower()
    for pattern in DANGEROUS_PATTERNS:
        if pattern in cmd_lower:
            raise PermissionError(f"Command blocked: contains dangerous pattern '{pattern.strip()}'")


class ShellCommander:
    def run_command(self, command, timeout=60):
        try:
            _check_dangerous(command)
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
            _check_dangerous(code)
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
        except PermissionError:
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
