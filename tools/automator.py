import os
import json
import subprocess
import webbrowser
from pathlib import Path

from core.platform_utils import is_windows, is_macos, is_linux, find_chrome, open_file, launch_app as xlaunch, notify

DEFAULT_PROFILE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "config", "chrome_default_profile.json")


class Automator:
    def launch_app(self, name_or_path, **kwargs):
        target = name_or_path
        if not target:
            return "No app name provided."
        try:
            if "chrome" in target.lower():
                chrome = self._find_chrome()
                if chrome:
                    cmd = [chrome]
                    cmd.append("chrome://newtab")
                    subprocess.Popen(cmd, shell=False)
                    return f"Launched Chrome"
            if os.path.exists(target):
                open_file(target)
                return f"Launched: {target}"
            if xlaunch(target):
                return f"Launched: {target}"
            if self._find_chrome():
                url = f"https://{target}" if not target.startswith(("http://", "https://")) else target
                self._open_with_chrome(url)
                return f"Opened in Chrome: {url}"
            return f"Could not launch: {target}"
        except Exception as e:
            return "Launch failed"

    def open_file(self, path):
        try:
            path = os.path.expanduser(path)
            from core.platform_utils import open_file as xopen
            xopen(path)
            return f"Opened: {path}"
        except Exception as e:
            return "Open failed"

    def open_folder(self, path):
        try:
            path = os.path.expanduser(path)
            from core.platform_utils import open_file as xopen
            xopen(path)
            return f"Opened folder: {path}"
        except Exception as e:
            return "Folder open failed"

    def _find_chrome(self):
        return find_chrome()

    def _load_default_profile(self):
        try:
            p = Path(DEFAULT_PROFILE_FILE)
            if p.exists():
                return json.loads(p.read_text()).get("profile")
        except Exception:
            pass
        return None

    def _save_default_profile(self, profile):
        try:
            p = Path(DEFAULT_PROFILE_FILE)
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(json.dumps({"profile": profile}))
        except Exception:
            pass

    def set_default_profile(self, profile):
        if self._resolve_chrome_profile(profile):
            self._save_default_profile(profile)
            return f"Default Chrome profile set to: {profile}"
        return f"Profile '{profile}' not found"

    def get_default_profile(self):
        return self._load_default_profile()

    def _list_chrome_profiles(self):
        try:
            ls = os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\User Data\Local State")
            with open(ls, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data.get("profile", {}).get("info_cache", {})
        except Exception:
            return {}

    def _resolve_chrome_profile(self, name_hint):
        profiles = self._list_chrome_profiles()
        if not profiles or not name_hint:
            return None
        name_lower = name_hint.lower()
        # try exact match first
        for dir_name, info in profiles.items():
            if name_lower == info.get("name", "").lower():
                return dir_name
        # try substring match
        for dir_name, info in profiles.items():
            if name_lower in info.get("name", "").lower():
                return dir_name
        # try matching parts of the name
        parts = name_lower.split()
        for dir_name, info in profiles.items():
            pname = info.get("name", "").lower()
            if all(p in pname for p in parts):
                return dir_name
        return None

    def _open_with_chrome(self, url, profile=None):
        chrome = self._find_chrome()
        if not chrome:
            return False
        cmd = [chrome]
        if profile:
            resolved = self._resolve_chrome_profile(profile)
            if resolved:
                cmd.extend(["--profile-directory", resolved])
        cmd.append(url)
        subprocess.Popen(cmd, shell=False)
        return True

    def browse_url(self, url):
        try:
            if not url.startswith(("http://", "https://")):
                url = "https://" + url
            if self._open_with_chrome(url):
                return f"Opened Chrome: {url}"
            if url.startswith(("http://", "https://")):
                webbrowser.open(url)
                return f"Opened browser: {url}"
            return f"Cannot open: invalid URL scheme"
        except Exception:
            return "Browser error"

    def search_web(self, query):
        try:
            url = f"https://www.google.com/search?q={__import__('urllib').parse.quote(query)}"
            if self._open_with_chrome(url):
                return f"Searched Google in Chrome: {query}"
            webbrowser.open(url)
            return f"Searched web for: {query}"
        except Exception as e:
            return "Search failed"

    def send_keys(self, text):
        try:
            import pyautogui
            pyautogui.write(text, interval=0.01)
            return f"Typed: {text[:100]}"
        except ImportError:
            return "pyautogui not installed. Run: pip install pyautogui"
        except Exception as e:
            return "Type failed"

    def press_key(self, key):
        try:
            import pyautogui
            pyautogui.press(key)
            return f"Pressed: {key}"
        except ImportError:
            return "pyautogui not installed"
        except Exception as e:
            return "Key failed"

    def hotkey(self, *keys):
        try:
            import pyautogui
            pyautogui.hotkey(*keys)
            return f"Hotkey: {'+'.join(keys)}"
        except ImportError:
            return "pyautogui not installed"
        except Exception as e:
            return "Hotkey failed"

    def click(self, x=None, y=None, button="left"):
        try:
            import pyautogui
            if x is not None and y is not None:
                pyautogui.click(x, y, button=button)
                return f"Clicked at ({x}, {y})"
            pyautogui.click(button=button)
            return "Clicked"
        except ImportError:
            return "pyautogui not installed"
        except Exception as e:
            return "Click failed"

    def mouse_position(self):
        try:
            import pyautogui
            x, y = pyautogui.position()
            return f"Mouse position: ({x}, {y})"
        except ImportError:
            return "pyautogui not installed"
        except Exception as e:
            return "Mouse position failed"

    def scroll(self, clicks):
        try:
            import pyautogui
            pyautogui.scroll(clicks)
            return f"Scrolled {clicks} clicks"
        except ImportError:
            return "pyautogui not installed"
        except Exception as e:
            return "Scroll failed"

    def screenshot(self, region=None):
        try:
            import pyautogui
            path = os.path.join(os.environ["TEMP"], f"friday_screenshot_{int(__import__('time').time())}.png")
            if region:
                im = pyautogui.screenshot(region=region)
            else:
                im = pyautogui.screenshot()
            im.save(path)
            return f"Screenshot saved: {path}"
        except ImportError:
            return "pyautogui not installed"
        except Exception as e:
            return "Screenshot failed"

    def get_clipboard(self):
        try:
            import pyperclip
            text = pyperclip.paste()
            return f"Clipboard: {text[:500]}" if text else "Clipboard is empty"
        except ImportError:
            return "pyperclip not installed"
        except Exception as e:
            return "Clipboard failed"

    def set_clipboard(self, text):
        try:
            import pyperclip
            pyperclip.copy(text)
            return "Clipboard set"
        except ImportError:
            return "pyperclip not installed"
        except Exception as e:
            return "Clipboard failed"

    def notify(self, title, message, duration=5):
        try:
            ok = notify(title, message, duration)
            if ok:
                return f"Notification sent: {title}"
            if is_windows():
                safe_title = title.replace("'", "''")
                safe_message = message.replace("'", "''")
                ps_code = f"New-BurntToastNotification -Text '{safe_title}', '{safe_message}'"
                encoded = __import__('base64').b64encode(ps_code.encode('utf-16-le')).decode()
                r = subprocess.run(
                    ["powershell", "-NoProfile", "-EncodedCommand", encoded],
                    capture_output=True, text=True, timeout=5
                )
                if r.returncode == 0:
                    return f"Notification sent: {title}"
            return f"Notification attempted: {title}"
        except Exception:
            return "Notification failed"

    def list_apps(self):
        try:
            r = subprocess.run(
                ["powershell", "-NoProfile", "-Command",
                 "Get-StartApps | Select-Object -First 50 Name | ConvertTo-Json"],
                capture_output=True, text=True, timeout=15
            )
            import json
            data = json.loads(r.stdout)
            if isinstance(data, dict):
                data = [data]
            names = [d["Name"] for d in data if d.get("Name")]
            return "Installed apps:\n" + "\n".join(f"  {i+1}. {n}" for i, n in enumerate(names))
        except Exception as e:
            return "Apps list failed"

    def list_all_apps(self, search=None):
        try:
            all_apps = set()
            ps_cmds = [
                "Get-StartApps | Select-Object Name | ConvertTo-Json",
                "Get-ItemProperty HKLM:\\Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\* | Where-Object DisplayName | Select-Object DisplayName | ConvertTo-Json",
                "Get-ChildItem 'C:\\ProgramData\\Microsoft\\Windows\\Start Menu\\Programs' -Recurse -Filter '*.lnk' -ErrorAction SilentlyContinue | Select-Object BaseName | ConvertTo-Json",
                "[Environment]::GetEnvironmentVariable('PATH','User') -split ';' | Where-Object { $_ } | Get-ChildItem -Filter '*.exe' -ErrorAction SilentlyContinue | Select-Object BaseName | ConvertTo-Json",
            ]
            import json
            for cmd in ps_cmds:
                try:
                    r = subprocess.run(
                        ["powershell", "-NoProfile", "-Command", cmd],
                        capture_output=True, text=True, timeout=15
                    )
                    if r.stdout.strip():
                        data = json.loads(r.stdout)
                        if isinstance(data, dict):
                            data = [data]
                        for d in data:
                            name = d.get("Name") or d.get("DisplayName") or d.get("BaseName")
                            if name and name.strip():
                                all_apps.add(name.strip())
                except Exception:
                    pass
            sorted_apps = sorted(all_apps, key=str.lower)
            if search:
                search_lower = search.lower()
                sorted_apps = [a for a in sorted_apps if search_lower in a.lower()]
            count = len(sorted_apps)
            shown = sorted_apps[:60]
            result = f"Apps found: {count}\n" + "\n".join(f"  {i+1}. {n}" for i, n in enumerate(shown))
            if count > 60:
                result += f"\n  ... and {count - 60} more"
            return result
        except Exception as e:
            return "Apps list failed"

    def get_tool_definitions(self):
        return [
            {"type": "function", "function": {"name": "launch_app", "description": "Launch app by name or executable path (e.g. chrome, notepad, calculator, git, code, spotify). Tries Start Menu, PATH, and common locations.", "parameters": {"type": "object", "properties": {"name_or_path": {"type": "string", "description": "App name or path"}}, "required": ["name_or_path"]}}},
            {"type": "function", "function": {"name": "open_file", "description": "Open file with default app", "parameters": {"type": "object", "properties": {"path": {"type": "string", "description": "File path"}}, "required": ["path"]}}},
            {"type": "function", "function": {"name": "open_folder", "description": "Open folder in Explorer", "parameters": {"type": "object", "properties": {"path": {"type": "string", "description": "Folder path"}}, "required": ["path"]}}},
            {"type": "function", "function": {"name": "browse_url", "description": "Open URL in Chrome browser", "parameters": {"type": "object", "properties": {"url": {"type": "string", "description": "Full URL (https://...)"}}, "required": ["url"]}}},
            {"type": "function", "function": {"name": "search_web", "description": "Google search in browser", "parameters": {"type": "object", "properties": {"query": {"type": "string", "description": "Search query"}}, "required": ["query"]}}},
            {"type": "function", "function": {"name": "send_keys", "description": "Type text via simulated keyboard", "parameters": {"type": "object", "properties": {"text": {"type": "string", "description": "Text to type"}}, "required": ["text"]}}},
            {"type": "function", "function": {"name": "press_key", "description": "Press a single keyboard key (enter, tab, esc, up, down, ctrl, alt, shift, win)", "parameters": {"type": "object", "properties": {"key": {"type": "string", "description": "Key name"}}, "required": ["key"]}}},
            {"type": "function", "function": {"name": "hotkey", "description": "Press keyboard combination (e.g. ctrl+c, alt+tab, win+r)", "parameters": {"type": "object", "properties": {"keys": {"type": "array", "items": {"type": "string"}, "description": "Array of keys"}}, "required": ["keys"]}}},
            {"type": "function", "function": {"name": "click", "description": "Mouse click. If no coords, clicks current mouse position.", "parameters": {"type": "object", "properties": {"x": {"type": "integer", "description": "X coordinate (optional)"}, "y": {"type": "integer", "description": "Y coordinate (optional)"}}}}},
            {"type": "function", "function": {"name": "mouse_position", "description": "Get current mouse cursor position", "parameters": {"type": "object", "properties": {}}}},
            {"type": "function", "function": {"name": "scroll", "description": "Scroll mouse wheel (positive = up, negative = down)", "parameters": {"type": "object", "properties": {"clicks": {"type": "integer", "description": "Number of scroll clicks"}}, "required": ["clicks"]}}},
            {"type": "function", "function": {"name": "screenshot", "description": "Take a screenshot of the screen", "parameters": {"type": "object", "properties": {}}}},
            {"type": "function", "function": {"name": "get_clipboard", "description": "Get text from clipboard", "parameters": {"type": "object", "properties": {}}}},
            {"type": "function", "function": {"name": "set_clipboard", "description": "Copy text to clipboard", "parameters": {"type": "object", "properties": {"text": {"type": "string", "description": "Text to copy"}}, "required": ["text"]}}},
            {"type": "function", "function": {"name": "notify", "description": "Show Windows notification toast", "parameters": {"type": "object", "properties": {"title": {"type": "string", "description": "Notification title"}, "message": {"type": "string", "description": "Notification body text"}}, "required": ["title", "message"]}}},
            {"type": "function", "function": {"name": "list_apps", "description": "Show installed apps from Start Menu", "parameters": {"type": "object", "properties": {}}}},
            {"type": "function", "function": {"name": "list_all_apps", "description": "Search all installed apps including Start Menu, registry, PATH, and Program Files. Optionally filter by name.", "parameters": {"type": "object", "properties": {"search": {"type": "string", "description": "Optional search term to filter apps"}}}}},
            {"type": "function", "function": {"name": "set_default_profile", "description": "Set default Chrome profile", "parameters": {"type": "object", "properties": {"profile": {"type": "string", "description": "Profile name"}}, "required": ["profile"]}}},
            {"type": "function", "function": {"name": "get_default_profile", "description": "Show current default Chrome profile", "parameters": {"type": "object", "properties": {}}}},
        ]

    def get_handler(self, name):
        handlers = {
            "launch_app": self.launch_app, "open_file": self.open_file, "open_folder": self.open_folder,
            "browse_url": self.browse_url, "search_web": self.search_web,
            "send_keys": self.send_keys, "press_key": self.press_key, "hotkey": self.hotkey,
            "click": self.click, "mouse_position": self.mouse_position, "scroll": self.scroll,
            "screenshot": self.screenshot, "get_clipboard": self.get_clipboard, "set_clipboard": self.set_clipboard,
            "notify": self.notify, "list_apps": self.list_apps, "list_all_apps": self.list_all_apps,
            "set_default_profile": self.set_default_profile, "get_default_profile": self.get_default_profile,
        }
        return handlers.get(name)
