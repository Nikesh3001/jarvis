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


def find_chrome():
    if is_windows():
        import winreg
        try:
            key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\chrome.exe")
            path, _ = winreg.QueryValueEx(key, "")
            winreg.CloseKey(key)
            return path
        except (OSError, ImportError):
            pass
        for candidate in [
            os.path.expanduser("~\\AppData\\Local\\Google\\Chrome\\Application\\chrome.exe"),
            os.environ.get("PROGRAMFILES", "") + "\\Google\\Chrome\\Application\\chrome.exe",
            os.environ.get("PROGRAMFILES(X86)", "") + "\\Google\\Chrome\\Application\\chrome.exe",
        ]:
            if os.path.exists(candidate):
                return candidate
        return None
    elif is_macos():
        paths = [
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
            os.path.expanduser("~/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"),
        ]
        for p in paths:
            if os.path.exists(p):
                return p
        which = shutil.which("google-chrome") or shutil.which("chrome")
        return which
    else:
        for candidate in ["google-chrome", "google-chrome-stable", "chromium", "chromium-browser", "chrome"]:
            which = shutil.which(candidate)
            if which:
                return which
        return None


def get_platform():
    if is_windows():
        return "windows"
    elif is_macos():
        return "darwin"
    return "linux"


def open_file(path):
    if is_windows():
        safe = path.replace("\u0027", "\u0027\u0027")
        r = subprocess.run(
            ["powershell", "-NoProfile", "-Command", "Start-Process \u0027" + safe + "\u0027"],
            capture_output=True, text=True, timeout=15
        )
        return r.returncode == 0
    elif is_macos():
        subprocess.Popen(["open", path])
    else:
        subprocess.Popen(["xdg-open", path])


def launch_app(name):
    if is_windows():
        safe = name.replace("\u0027", "\u0027\u0027")
        r = subprocess.run(
            ["powershell", "-NoProfile", "-Command", "Start-Process \u0027" + safe + "\u0027"],
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
    return os.path.join(tempfile.gettempdir(), f"friday_screenshot_{__import__('secrets').token_hex(4)}_{int(time.time())}.png")

