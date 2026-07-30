import os
import sys
import time
import json
import base64
import tempfile
import subprocess
import shutil
import platform as _platform
from pathlib import Path


def is_windows():
    return sys.platform == "win32"


def is_macos():
    return sys.platform == "darwin"


def is_linux():
    return sys.platform.startswith("linux")


def get_platform():
    if is_windows():
        return "windows"
    if is_macos():
        return "darwin"
    return "linux"


def get_platform_display():
    return f"{get_platform().capitalize()} {_platform.machine()}"


def get_hostname():
    return os.environ.get("COMPUTERNAME") or os.environ.get("HOSTNAME") or os.environ.get("HOST") or _platform.node() or "localhost"


def get_username():
    return os.environ.get("USERNAME") or os.environ.get("USER") or "user"


def get_home():
    return str(Path.home())


def normalize_path(path):
    path = str(path)
    path = path.replace("\\", "/")
    return path


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
            os.path.join(os.path.expanduser("~"), "AppData", "Local", "Google", "Chrome", "Application", "chrome.exe"),
            os.path.join(os.environ.get("PROGRAMFILES", ""), "Google", "Chrome", "Application", "chrome.exe") if os.environ.get("PROGRAMFILES") else "",
            os.path.join(os.environ.get("PROGRAMFILES(X86)", ""), "Google", "Chrome", "Application", "chrome.exe") if os.environ.get("PROGRAMFILES(X86)") else "",
        ]:
            if candidate and os.path.exists(candidate):
                return candidate
        return None
    if is_macos():
        paths = [
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
            os.path.expanduser("~/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"),
        ]
        for p in paths:
            if os.path.exists(p):
                return p
        which = shutil.which("google-chrome") or shutil.which("chrome")
        return which
    for candidate in ["google-chrome", "google-chrome-stable", "chromium", "chromium-browser", "chrome"]:
        which = shutil.which(candidate)
        if which:
            return which
    return None


def find_browser():
    chrome = find_chrome()
    if chrome:
        return chrome
    if is_windows():
        edge = shutil.which("msedge") or os.path.join(os.environ.get("PROGRAMFILES(X86)", ""), "Microsoft", "Edge", "Application", "msedge.exe")
        if edge and os.path.exists(edge):
            return edge
        firefox = shutil.which("firefox")
        if firefox:
            return firefox
    if is_macos():
        for app in ["Safari", "Firefox", "Brave Browser"]:
            path = f"/Applications/{app}.app/Contents/MacOS/{app.split()[0].lower()}"
            if os.path.exists(path):
                return path
            path2 = f"/Applications/{app}.app/Contents/MacOS/{app.replace(' ', '')}"
            if os.path.exists(path2):
                return path2
    if is_linux():
        for b in ["firefox", "firefox-esr", "brave-browser", "chromium"]:
            which = shutil.which(b)
            if which:
                return which
    return shutil.which("x-www-browser") or shutil.which("www-browser")


def open_file(path):
    path = str(path)
    if is_windows():
        os.startfile(path)
        return True
    if is_macos():
        subprocess.Popen(["open", path])
        return True
    subprocess.Popen(["xdg-open", path])
    return True


def launch_app(name):
    if is_windows():
        r = subprocess.run(
            ["powershell", "-NoProfile", "-Command", f"Start-Process '{name}'"],
            capture_output=True, text=True, timeout=15
        )
        return r.returncode == 0
    if is_macos():
        r = subprocess.run(["open", "-a", name], capture_output=True, timeout=15)
        return r.returncode == 0
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
        if is_macos():
            safe_msg = _escape_applescript(message)
            safe_title = _escape_applescript(title)
            subprocess.run(
                ["osascript", "-e", f'display notification "{safe_msg}" with title "{safe_title}"'],
                capture_output=True, timeout=5
            )
            return True
        subprocess.run(
            ["notify-send", title, message, "-t", str(duration * 1000)],
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
    import secrets
    token = secrets.token_hex(12)
    return os.path.join(tempfile.gettempdir(), f"friday_screenshot_{token}.png")


def take_screenshot_cli(path):
    if is_windows():
        import secrets
        token = secrets.token_hex(12)
        path = path or os.path.join(tempfile.gettempdir(), f"friday_ss_{token}.png")
        ps_code = (
            f'Add-Type -AssemblyName System.Windows.Forms; '
            f'$s = [Windows.Forms.Screen]::PrimaryScreen.Bounds; '
            f'$b = New-Object Drawing.Bitmap $s.Width,$s.Height; '
            f'$g = [Drawing.Graphics]::FromImage($b); '
            f'$g.CopyFromScreen(0,0,0,0,$s.Size); '
            f'$b.Save("{path}"); $g.Dispose(); $b.Dispose()'
        )
        subprocess.run(["powershell", "-NoProfile", "-Command", ps_code],
                       capture_output=True, text=True, timeout=30)
        return path if os.path.exists(path) else None
    if is_macos():
        subprocess.run(["screencapture", path], timeout=30)
        return path if os.path.exists(path) else None
    subprocess.run(["gnome-screenshot", "-f", path], timeout=30)
    return path if os.path.exists(path) else None


def get_clipboard_text():
    if is_windows():
        r = subprocess.run(["powershell", "-NoProfile", "-Command", "Get-Clipboard | Select-Object -First 1"],
                           capture_output=True, text=True, timeout=10)
        return r.stdout.strip()
    if is_macos():
        r = subprocess.run(["pbpaste"], capture_output=True, text=True, timeout=10)
        return r.stdout.strip()
    r = subprocess.run(["xclip", "-selection", "clipboard", "-o"],
                       capture_output=True, text=True, timeout=10)
    return r.stdout.strip()


def set_clipboard_text(text):
    if is_windows():
        subprocess.run(["powershell", "-NoProfile", "-Command", "$input | Set-Clipboard"],
                       input=text.encode('utf-8'), capture_output=True, timeout=10)
    elif is_macos():
        subprocess.run(["pbcopy"], input=text.encode(), timeout=10)
    else:
        subprocess.run(["xclip", "-selection", "clipboard"], input=text.encode(), timeout=10)
    return True


def get_volume():
    if is_windows():
        ps_code = (
            'Add-Type -TypeDefinition \'using System.Runtime.InteropServices; '
            'public class Audio { [DllImport("winmm.dll")] public static extern int waveOutGetVolume'
            '(System.IntPtr h, out uint v); }\' ; '
            '$v=0; [void][Audio]::waveOutGetVolume([IntPtr]::Zero,[ref]$v); '
            'Write-Output ([math]::Round((($v -band 0xFFFF)/65535.0)*100))'
        )
        r = subprocess.run(["powershell", "-NoProfile", "-Command", ps_code],
                           capture_output=True, text=True, timeout=10)
        return r.stdout.strip()
    if is_macos():
        r = subprocess.run(["osascript", "-e", "output volume of (get volume settings)"],
                           capture_output=True, text=True, timeout=10)
        return r.stdout.strip()
    r = subprocess.run(["amixer", "sget", "Master"], capture_output=True, text=True, timeout=10)
    for line in r.stdout.split('\n'):
        if '%' in line:
            return line.split('%')[0].split('[')[-1]
    return "?"


def set_volume(level):
    level = max(0, min(100, int(level)))
    if is_windows():
        ps_code = (
            'Add-Type -TypeDefinition \'using System.Runtime.InteropServices; '
            'public class Audio { [DllImport("winmm.dll")] public static extern int waveOutGetVolume'
            '(System.IntPtr h, out uint v); [DllImport("winmm.dll")] public static extern int '
            'waveOutSetVolume(System.IntPtr h, uint v); }\' ; '
            f'$v=[uint32]({level}/100.0*65535); '
            '[Audio]::waveOutSetVolume([IntPtr]::Zero,($v -bor ($v -shl 16)))'
        )
        subprocess.run(["powershell", "-NoProfile", "-Command", ps_code],
                       capture_output=True, text=True, timeout=10)
    elif is_macos():
        subprocess.run(["osascript", "-e", f"set volume output volume {level}"], timeout=10)
    else:
        subprocess.run(["amixer", "sset", "Master", f"{level}%"], capture_output=True, timeout=10)
    return True


def mute_volume():
    if is_windows():
        subprocess.run(["powershell", "-NoProfile", "-Command",
                       "(New-Object -ComObject WScript.Shell).SendKeys([char]0xAD)"],
                       capture_output=True, text=True, timeout=5)
    elif is_macos():
        subprocess.run(["osascript", "-e", "set volume muted true"], timeout=5)
    else:
        subprocess.run(["amixer", "sset", "Master", "mute"], capture_output=True, timeout=5)
    return True


def media_play_pause():
    if is_windows():
        subprocess.run(["powershell", "-NoProfile", "-Command",
                       "(New-Object -ComObject WScript.Shell).SendKeys([char]0xB0)"],
                       capture_output=True, text=True, timeout=5)
    elif is_macos():
        subprocess.run(["osascript", "-e", 'tell application "System Events" to key code 16'], timeout=5)
    else:
        subprocess.run(["playerctl", "play-pause"], capture_output=True, timeout=5)
    return True


def media_next():
    if is_windows():
        subprocess.run(["powershell", "-NoProfile", "-Command",
                       "(New-Object -ComObject WScript.Shell).SendKeys([char]0xB1)"],
                       capture_output=True, text=True, timeout=5)
    elif is_macos():
        subprocess.run(["osascript", "-e", 'tell application "System Events" to key code 17'], timeout=5)
    else:
        subprocess.run(["playerctl", "next"], capture_output=True, timeout=5)
    return True


def media_prev():
    if is_windows():
        subprocess.run(["powershell", "-NoProfile", "-Command",
                       "(New-Object -ComObject WScript.Shell).SendKeys([char]0xB2)"],
                       capture_output=True, text=True, timeout=5)
    elif is_macos():
        subprocess.run(["osascript", "-e", 'tell application "System Events" to key code 18'], timeout=5)
    else:
        subprocess.run(["playerctl", "previous"], capture_output=True, timeout=5)
    return True


def list_wifi():
    if is_windows():
        r = subprocess.run(["netsh", "wlan", "show", "profiles"], capture_output=True, text=True, timeout=15)
        profiles = [l.split(":")[1].strip() for l in r.stdout.split('\n') if "All User Profile" in l]
        return profiles[:15]
    if is_macos():
        r = subprocess.run([
            "/System/Library/PrivateFrameworks/Apple80211.framework/Versions/Current/Resources/airport", "-s"
        ], capture_output=True, text=True, timeout=15)
        lines = r.stdout.strip().split('\n')
        networks = []
        for line in lines[1:]:
            parts = line.split()
            if parts:
                networks.append(parts[0])
        return networks[:20]
    r = subprocess.run(["nmcli", "-t", "-f", "SSID", "device", "wifi", "list"],
                       capture_output=True, text=True, timeout=15)
    if r.returncode == 0 and r.stdout.strip():
        nets = [l.strip() for l in r.stdout.strip().split('\n') if l.strip()]
        return nets[:20]
    return []


def wifi_status():
    if is_windows():
        r = subprocess.run(["netsh", "wlan", "show", "interfaces"], capture_output=True, text=True, timeout=10)
        ssid = ""
        signal = ""
        for l in r.stdout.split('\n'):
            if "SSID" in l and "BSSID" not in l and ":" in l:
                ssid = l.split(":")[1].strip()
            if "Signal" in l and ":" in l:
                signal = l.split(":")[1].strip()
        return {"ssid": ssid, "signal": signal} if ssid else None
    if is_macos():
        r = subprocess.run(["/System/Library/PrivateFrameworks/Apple80211.framework/Versions/Current/Resources/airport", "-I"],
                           capture_output=True, text=True, timeout=10)
        for line in r.stdout.split('\n'):
            if "SSID" in line and ":" in line:
                return {"ssid": line.split(":")[1].strip(), "signal": ""}
        return None
    r = subprocess.run(["nmcli", "-t", "-f", "TYPE,STATE,CONNECTION", "device", "status"],
                       capture_output=True, text=True, timeout=10)
    for line in r.stdout.strip().split('\n'):
        parts = line.split(':')
        if len(parts) >= 3 and 'wifi' in parts[0].lower() and 'connected' in parts[1].lower():
            return {"ssid": parts[2], "signal": ""}
    return None


def list_windows_titles():
    try:
        import pygetwindow as gw
        wins = gw.getAllTitles()
        visible = [w for w in wins if w.strip()]
        if visible:
            return visible[:20]
    except ImportError:
        pass
    if is_windows():
        r = subprocess.run(["powershell", "-NoProfile", "-Command",
            "Get-Process | Where-Object { $_.MainWindowTitle -ne '' } | Select-Object -First 20 -ExpandProperty MainWindowTitle"],
            capture_output=True, text=True, timeout=10)
        return [l.strip() for l in r.stdout.strip().splitlines() if l.strip()]
    if is_macos():
        r = subprocess.run(["osascript", "-e",
            'tell application "System Events" to get name of every process whose visible is true'],
            capture_output=True, text=True, timeout=10)
        return [a.strip() for a in r.stdout.strip().split(', ') if a.strip()]
    r = subprocess.run(["wmctrl", "-l"], capture_output=True, text=True, timeout=10)
    if r.returncode == 0 and r.stdout.strip():
        wins = [l.split(None, 3)[-1] for l in r.stdout.strip().split('\n') if len(l.split(None, 3)) > 3]
        return wins[:20] if wins else []
    return []


def focus_window(title):
    try:
        import pygetwindow as gw
        wins = gw.getWindowsWithText(title)
        if wins:
            wins[0].activate()
            return True
    except ImportError:
        pass
    if is_windows():
        ps_code = (
            f'$t="*{title}*"; '
            f'$h=Get-Process | Where-Object {{ $_.MainWindowTitle -like $t }} | '
            f'Select-Object -First 1 | ForEach-Object {{ $_.MainWindowHandle }}; '
            f'if ($h -and $h -ne 0) {{ '
            f'Add-Type @\' using System; using System.Runtime.InteropServices; '
            f'public class W {{ [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr h); }}'
            f'\'@; [W]::SetForegroundWindow($h) }}'
        )
        subprocess.run(["powershell", "-NoProfile", "-Command", ps_code],
                       capture_output=True, text=True, timeout=10)
    elif is_macos():
        safe_title = title.replace('\\', '\\\\').replace('"', '\\"').replace("'", "\\'").replace('\n', '\\n')
        subprocess.run(["osascript", "-e", f'tell application "{safe_title}" to activate'],
                       capture_output=True, timeout=10)
    else:
        try:
            subprocess.run(["xdotool", "search", "--name", title, "windowactivate"],
                           capture_output=True, timeout=10)
        except Exception:
            subprocess.run(["wmctrl", "-a", title], capture_output=True, timeout=10)
    return True


def lock_workstation():
    if is_windows():
        subprocess.run(["rundll32.exe", "user32.dll,LockWorkStation"], capture_output=True, text=True, timeout=5)
    elif is_macos():
        subprocess.run(["osascript", "-e",
                       'tell application "System Events" to keystroke "q" using {command down, control down}'],
                       capture_output=True, timeout=5)
    else:
        subprocess.run(["gnome-screensaver-command", "-l"], capture_output=True, timeout=5)
        subprocess.run(["xdg-screensaver", "lock"], capture_output=True, timeout=5)
    return True


def get_installed_software():
    if is_windows():
        r = subprocess.run(["powershell", "-NoProfile", "-Command",
            "Get-ItemProperty HKLM:\\Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\*, "
            "HKLM:\\Software\\Wow6432Node\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\* | "
            "Where-Object DisplayName | Select-Object -First 30 DisplayName,DisplayVersion | ConvertTo-Json"],
            capture_output=True, text=True, timeout=30)
        try:
            data = json.loads(r.stdout)
            if isinstance(data, dict):
                data = [data]
            if isinstance(data, list):
                return [f"{d.get('DisplayName','?')} ({d.get('DisplayVersion','?')})" for d in data if isinstance(d, dict) and d.get('DisplayName')]
        except Exception:
            pass
        return []
    if is_macos():
        r = subprocess.run(["system_profiler", "SPApplicationsDataType", "-json"],
                           capture_output=True, text=True, timeout=60)
        try:
            data = json.loads(r.stdout)
            apps = data.get("SPApplicationsDataType", [])
            return [a.get("_name", "?") for a in apps[:30] if a.get("_name")]
        except Exception:
            return []
    for cmd, flag in [("dpkg", "--get-selections"), ("rpm", "-qa")]:
        r = subprocess.run([cmd, flag], capture_output=True, text=True, timeout=30)
        if r.returncode == 0:
            return [l.split()[0] for l in r.stdout.strip().split('\n')[:30] if l.strip()]
    return []


def get_startup_programs():
    if is_windows():
        r = subprocess.run(["powershell", "-NoProfile", "-Command",
            "Get-CimInstance Win32_StartupCommand | Select-Object Name,Command,User | ConvertTo-Json"],
            capture_output=True, text=True, timeout=15)
        try:
            data = json.loads(r.stdout)
            if isinstance(data, dict):
                data = [data]
            if isinstance(data, list):
                return [f"{d.get('Name','?')} ({d.get('User','?')})" for d in data if isinstance(d, dict) and d.get('Name')]
        except Exception:
            pass
        return []
    if is_macos():
        r = subprocess.run(["osascript", "-e",
                           'tell application "System Events" to get name of every login item'],
                           capture_output=True, text=True, timeout=10)
        return [a.strip() for a in r.stdout.strip().split(', ') if a.strip()]
    items = []
    for d in [Path(os.path.expanduser("~/.config/autostart")), Path("/etc/xdg/autostart")]:
        if d.exists():
            items.extend([p.stem for p in d.iterdir() if p.suffix == '.desktop'])
    return items


def get_running_services():
    if is_windows():
        r = subprocess.run(["powershell", "-NoProfile", "-Command",
            "Get-Service | Where-Object Status -eq Running | Select-Object -First 30 -ExpandProperty Name"],
            capture_output=True, text=True, timeout=15)
        return [l.strip() for l in r.stdout.strip().splitlines() if l.strip()]
    if is_macos():
        r = subprocess.run(["launchctl", "list"], capture_output=True, text=True, timeout=10)
        svcs = [l.split('\t')[2] if '\t' in l else l for l in r.stdout.strip().split('\n')[1:][:30] if l.strip()]
        return svcs
    r = subprocess.run(["systemctl", "list-units", "--type=service", "--state=running", "--no-pager"],
                       capture_output=True, text=True, timeout=15)
    if r.returncode == 0:
        return [l.split()[0] for l in r.stdout.strip().split('\n') if l.strip() and '.service' in l][:30]
    return []


def explore_drives():
    if is_windows():
        r = subprocess.run(["powershell", "-NoProfile", "-Command",
            "Get-PSDrive -PSProvider FileSystem | Select-Object Name, Root, Used, Free | ConvertTo-Json"],
            capture_output=True, text=True, timeout=15)
        try:
            data = json.loads(r.stdout)
            if isinstance(data, dict):
                data = [data]
            if isinstance(data, list):
                lines = []
                for d in data:
                    name = d.get("Name", "?")
                    root = d.get("Root", "?")
                    free = d.get("Free", 0)
                    used = d.get("Used", 0)
                    total = free + used
                    pct = int(used / total * 100) if total > 0 else 0
                    lines.append(f"{root} ({name}:) {pct}% used - {free//(1024**3)}GB free / {total//(1024**3)}GB total")
                return lines
        except Exception:
            pass
        return []
    r = subprocess.run(["df", "-h"], capture_output=True, text=True, timeout=10)
    return [l.strip() for l in r.stdout.strip().split('\n')[:20] if l.strip()]


def find_installed_app(search):
    search = search.lower().strip()
    results = []
    if is_windows():
        ps_script = (
            f'$search = "{search}"\n'
            f'$results = @()\n'
            f'$results += Get-StartApps | Where-Object {{ $_.Name -like "*$search*" }} | '
            f'Select-Object Name, AppId\n'
            f'$results += Get-ItemProperty HKLM:\\Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\* | '
            f'Where-Object {{ $_.DisplayName -like "*$search*" }} | '
            f'Select-Object @{{n="Name";e="{{$($_.DisplayName) - $($_.InstallLocation)"}}}}, '
            f'@{{n="AppId";e="{{$($_.InstallLocation)"}}}}\n'
            f'$results | ConvertTo-Json'
        )
        r = subprocess.run(["powershell", "-NoProfile", "-Command", ps_script],
                           capture_output=True, text=True, timeout=15)
        if r.stdout.strip():
            try:
                data = json.loads(r.stdout)
                if isinstance(data, dict):
                    data = [data]
                if isinstance(data, list):
                    for d in data:
                        name = d.get("Name")
                        path = d.get("AppId", "")
                        if name:
                            results.append(f"{name}: {path}")
            except Exception:
                pass
        paths = os.environ.get("PATH", "").split(os.pathsep)
        for p_dir in paths:
            try:
                for f in os.listdir(p_dir):
                    if search in f.lower():
                        ext = os.path.splitext(f)[1].lower()
                        if ext in ('.exe', '.com', '.bat', '.cmd', '') or not ext:
                            results.append(f"{f}: {os.path.join(p_dir, f)}")
            except Exception:
                pass
    elif is_macos():
        r = subprocess.run(["mdfind", f"kMDItemKind == 'Application' && kMDItemDisplayName == '*{search}*'"],
                           capture_output=True, text=True, timeout=15)
        results = [f"App: {l}" for l in r.stdout.strip().split('\n')[:10] if l.strip()]
    else:
        paths = os.environ.get("PATH", "").split(os.pathsep)
        for p_dir in paths:
            try:
                for f in os.listdir(p_dir):
                    if search in f.lower() and os.access(os.path.join(p_dir, f), os.X_OK):
                        results.append(f"{f}: {os.path.join(p_dir, f)}")
            except Exception:
                pass
    seen = set()
    unique = []
    for r in results:
        if r not in seen:
            seen.add(r)
            unique.append(r)
    return unique[:15]


def get_disk_path():
    return os.path.expanduser("~") if is_windows() else "/"


def get_idle_seconds():
    if is_windows():
        try:
            import ctypes
            from ctypes import wintypes
            class LASTINPUTINFO(ctypes.Structure):
                _fields_ = [("cbSize", wintypes.UINT), ("dwTime", wintypes.DWORD)]
            lii = LASTINPUTINFO()
            lii.cbSize = ctypes.sizeof(LASTINPUTINFO)
            if ctypes.windll.user32.GetLastInputInfo(ctypes.byref(lii)):
                tick = ctypes.windll.kernel32.GetTickCount()
                return (tick - lii.dwTime) // 1000
        except Exception:
            pass
        return 0
    if is_macos():
        r = subprocess.run(["ioreg", "-c", "IOHIDSystem"], capture_output=True, text=True, timeout=5)
        for line in r.stdout.split('\n'):
            if "HIDIdleTime" in line:
                try:
                    ns = int(line.split('=')[-1].strip())
                    return int(ns / 1000000000)
                except Exception:
                    pass
        return 0
    try:
        r = subprocess.run(["xprintidle"], capture_output=True, text=True, timeout=5)
        if r.stdout.strip():
            return int(r.stdout.strip()) // 1000
    except Exception:
        pass
    try:
        r = subprocess.run(["loginctl", "show-session", "1", "-p", "IdleSinceHint"],
                          capture_output=True, text=True, timeout=5)
        if r.stdout.strip():
            return 0
    except Exception:
        pass
    return 0


def get_tts_engine():
    if is_windows():
        try:
            subprocess.run(["powershell", "-NoProfile", "-Command",
                           "Add-Type -AssemblyName System.Speech; $s=New-Object System.Speech.Synthesis.SpeechSynthesizer; $s.GetInstalledVoices().Count"],
                          capture_output=True, text=True, timeout=5)
            return "sapi"
        except Exception:
            pass
        return "sapi"
    if is_macos():
        return "say"
    for tts in ["espeak", "espeak-ng", "festival"]:
        if shutil.which(tts):
            return tts
    return None


def speak_text(text, engine=None):
    engine = engine or get_tts_engine()
    if engine == "sapi":
        escaped = text.replace("'", "''")
        subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             f"Add-Type -AssemblyName System.Speech; $s=New-Object System.Speech.Synthesis.SpeechSynthesizer; $s.Speak('{escaped}')"],
            capture_output=True, timeout=30
        )
    elif engine == "say":
        subprocess.run(["say", text], capture_output=True, timeout=30)
    elif engine in ("espeak", "espeak-ng"):
        subprocess.run([engine, text], capture_output=True, timeout=30)
    return True


def get_firewall_status():
    if is_windows():
        r = subprocess.run(["powershell", "-NoProfile", "-Command",
            "Get-NetFirewallProfile | Select-Object Name, Enabled | ConvertTo-Json"],
            capture_output=True, text=True, timeout=15)
        try:
            data = json.loads(r.stdout)
            if isinstance(data, dict):
                data = [data]
            if isinstance(data, list):
                return "\n".join(f"  {d.get('Name','?')}: {'Enabled' if d.get('Enabled') else 'Disabled'}" for d in data)
        except Exception:
            pass
        return "Firewall status unavailable"
    if is_macos():
        r = subprocess.run(["/usr/libexec/ApplicationFirewall/socketfilterfw", "--getglobalstate"],
                          capture_output=True, text=True, timeout=10)
        return r.stdout.strip() or "Firewall status unavailable"
    r = subprocess.run(["ufw", "status"], capture_output=True, text=True, timeout=10)
    if r.returncode == 0:
        return r.stdout.strip()[:500]
    r2 = subprocess.run(["iptables", "-L", "-n"], capture_output=True, text=True, timeout=10)
    if r2.returncode == 0:
        return r2.stdout.strip()[:500]
    return "Firewall status unavailable"


def get_security_updates():
    if is_windows():
        r = subprocess.run(["powershell", "-NoProfile", "-Command",
            "Get-HotFix | Sort-Object InstalledOn -Descending | Select-Object -First 10 "
            "HotFixId,InstalledOn | ConvertTo-Json"],
            capture_output=True, text=True, timeout=30)
        try:
            data = json.loads(r.stdout)
            if isinstance(data, dict):
                data = [data]
            if isinstance(data, list):
                return [f"{d.get('HotFixId','?')} ({d.get('InstalledOn','?')})" for d in data if isinstance(d, dict)]
        except Exception:
            pass
        return []
    if is_macos():
        r = subprocess.run(["softwareupdate", "--list"], capture_output=True, text=True, timeout=30)
        return [l.strip() for l in r.stdout.split('\n') if 'recommended' in l.lower() or '*' in l][:10]
    r = subprocess.run(["apt", "list", "--upgradable"], capture_output=True, text=True, timeout=30)
    if r.returncode == 0:
        return [l.strip() for l in r.stdout.strip().split('\n')[1:][:10] if l.strip()]
    r2 = subprocess.run(["yum", "check-update"], capture_output=True, text=True, timeout=30)
    if r2.returncode == 0:
        return [l.strip() for l in r2.stdout.strip().split('\n')[:10] if l.strip()]
    r3 = subprocess.run(["dnf", "check-update"], capture_output=True, text=True, timeout=30)
    if r3.returncode == 0:
        return [l.strip() for l in r3.stdout.strip().split('\n')[:10] if l.strip()]
    return []


def get_nmap_path():
    which = shutil.which("nmap")
    if which:
        return which
    candidates = [
        r"C:\Program Files (x86)\Nmap\nmap.exe",
        r"C:\Program Files\Nmap\nmap.exe",
        r"C:\nmap\nmap.exe",
    ]
    for c in candidates:
        if os.path.exists(c):
            return c
    return None


def get_chrome_profiles():
    """List Chrome profiles across platforms."""
    if is_windows():
        local_state = os.path.expandvars(
            r"%LOCALAPPDATA%\Google\Chrome\User Data\Local State"
        )
    elif is_macos():
        local_state = os.path.expanduser(
            "~/Library/Application Support/Google/Chrome/Local State"
        )
    else:
        local_state = os.path.expanduser(
            "~/.config/google-chrome/Local State"
        )
    try:
        with open(local_state, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get("profile", {}).get("info_cache", {})
    except Exception:
        return {}


def list_installed_apps(limit=50):
    """List installed applications across platforms."""
    if is_windows():
        try:
            r = subprocess.run(
                ["powershell", "-NoProfile", "-Command",
                 f"Get-StartApps | Select-Object -First {limit} Name | ConvertTo-Json"],
                capture_output=True, text=True, timeout=15
            )
            try:
                data = json.loads(r.stdout)
                if isinstance(data, dict):
                    data = [data]
                if isinstance(data, list):
                    return [d["Name"] for d in data if isinstance(d, dict) and d.get("Name")]
            except (json.JSONDecodeError, TypeError):
                pass
        except Exception:
            pass
        return []
    elif is_macos():
        try:
            r = subprocess.run(
                ["ls", "/Applications"],
                capture_output=True, text=True, timeout=10
            )
            if r.returncode == 0:
                apps = [a.replace(".app", "") for a in r.stdout.strip().split("\n") if a.endswith(".app")]
                return apps[:limit]
        except Exception:
            pass
        return []
    else:
        try:
            paths = [
                "/usr/share/applications",
                os.path.expanduser("~/.local/share/applications"),
            ]
            apps = set()
            for p in paths:
                if os.path.isdir(p):
                    for f in os.listdir(p):
                        if f.endswith(".desktop"):
                            name = f.replace(".desktop", "").replace("-", " ").title()
                            apps.add(name)
            return sorted(apps)[:limit]
        except Exception:
            pass
        return []


def find_installed_app(exe_name):
    """Find an installed app by executable name, cross-platform."""
    which = shutil.which(exe_name)
    if which:
        return which
    if is_windows():
        exe = exe_name if exe_name.lower().endswith(".exe") else exe_name + ".exe"
        known_dirs = [
            os.path.expandvars(r"%ProgramFiles%"),
            os.path.expandvars(r"%ProgramFiles(x86)%"),
            os.path.expandvars(r"%LOCALAPPDATA%\Programs"),
            os.path.expandvars(r"%AppData%"),
        ]
        for d in known_dirs:
            for root, dirs, files in os.walk(d):
                if exe in files:
                    return os.path.join(root, exe)
        return None
    elif is_macos():
        app_name = exe_name.replace(".app", "") + ".app"
        for d in ["/Applications", os.path.expanduser("~/Applications")]:
            p = os.path.join(d, app_name)
            if os.path.isdir(p):
                return p
        return None
    else:
        return None
