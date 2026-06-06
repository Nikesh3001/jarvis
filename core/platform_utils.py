import os
import sys
import time
import tempfile
import subprocess
import shutil
from pathlib import Path


def is_windows():
    return sys.platform == "win32"


def is_macos():
    return sys.platform == "darwin"


def is_linux():
    return sys.platform == "linux" or sys.platform == "linux2"


def get_platform():
    if is_windows():
        return "windows"
    if is_macos():
        return "macos"
    return "linux"


def find_chrome():
    paths = []
    if is_windows():
        paths = [
            os.path.expandvars(r"%ProgramFiles%\Google\Chrome\Application\chrome.exe"),
            os.path.expandvars(r"%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe"),
            os.path.expandvars(r"%LocalAppData%\Google\Chrome\Application\chrome.exe"),
        ]
    elif is_macos():
        paths = [
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
            os.path.expanduser("~/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"),
        ]
    else:
        paths = [
            "/usr/bin/google-chrome",
            "/usr/bin/google-chrome-stable",
            "/usr/bin/chromium",
            "/usr/bin/chromium-browser",
            shutil.which("google-chrome") or "",
            shutil.which("google-chrome-stable") or "",
            shutil.which("chromium") or "",
            shutil.which("chromium-browser") or "",
        ]
    for p in paths:
        if p and os.path.exists(p):
            return p
    which = shutil.which("chrome") or shutil.which("google-chrome") or shutil.which("chromium")
    if which:
        return which
    return None


def open_file(path):
    if is_windows():
        os.startfile(path)
    elif is_macos():
        subprocess.Popen(["open", path])
    else:
        subprocess.Popen(["xdg-open", path])


def launch_app(name):
    if is_windows():
        r = subprocess.run(
            ["powershell", "-NoProfile", "-Command", "& $args[0]", "--", name],
            capture_output=True, text=True, timeout=15
        )
        return r.returncode == 0
    elif is_macos():
        r = subprocess.run(["open", "-a", name], capture_output=True, timeout=15)
        return r.returncode == 0
    else:
        which = shutil.which(name)
        if which:
            subprocess.Popen([which])
            return True
        return False


def _escape_applescript(s):
    escaped = s.replace('\\', '\\\\')
    escaped = escaped.replace('"', '\\"')
    escaped = escaped.replace('\n', '\\n')
    escaped = escaped.replace('\r', '\\r')
    escaped = escaped.replace('\t', '\\t')
    return escaped


def notify(title, message, duration=5):
    try:
        if is_windows():
            import ctypes
            ctypes.windll.user32.MessageBoxW(0, message, title, 0)
            return True
        elif is_macos():
            safe_msg = _escape_applescript(message)
            safe_title = _escape_applescript(title)
            subprocess.run(
                ["osascript", "-e", f'display notification "{safe_msg}" with title "{safe_title}"'],
                capture_output=True, timeout=5
            )
            return True
        else:
            subprocess.run(
                ["notify-send", title, message, f"-t", str(duration * 1000)],
                capture_output=True, timeout=5
            )
            return True
    except Exception:
        return False


def get_default_shell():
    if is_windows():
        return "powershell"
    return os.environ.get("SHELL", "/bin/bash")


def screenshot_path():
    return os.path.join(tempfile.gettempdir(), f"friday_screenshot_{int(time.time())}.png")
