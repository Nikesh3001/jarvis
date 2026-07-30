import os, sys, time, datetime, json, subprocess, tempfile
from pathlib import Path

from core.guardian import PathValidator
from core.platform_utils import (
    is_windows, is_macos, is_linux, get_platform, get_hostname,
    take_screenshot_cli, get_clipboard_text, set_clipboard_text,
    get_volume, set_volume, mute_volume,
    media_play_pause, media_next, media_prev,
    list_wifi, wifi_status,
    list_windows_titles, focus_window, lock_workstation,
    get_installed_software, get_startup_programs,
    get_running_services, explore_drives, find_installed_app,
    normalize_path, open_file,
)


class SystemTools:
    def __init__(self):
        self._psutil = None
        self.safe_mode = True

    @property
    def psutil(self):
        if self._psutil is None:
            import psutil as _p
            self._psutil = _p
        return self._psutil

    def get_cpu(self):
        try:
            p = self.psutil
            return f"CPU: {p.cpu_percent(interval=0.1)}% used, {p.cpu_count(logical=True)} logical cores"
        except Exception:
            return "CPU info failed"

    def get_memory(self):
        try:
            m = self.psutil.virtual_memory()
            return f"RAM: {m.percent}% used, {m.used // (1024**3)} GB / {m.total // (1024**3)} GB, {m.available // (1024**3)} GB free"
        except Exception:
            return "Memory info failed"

    def get_disk(self):
        try:
            parts = []
            for p in self.psutil.disk_partitions():
                try:
                    u = self.psutil.disk_usage(p.mountpoint)
                    parts.append(f"{p.mountpoint} {u.percent}% used ({u.free // (1024**3)} GB free)")
                except Exception:
                    parts.append(f"{p.mountpoint} ?")
            return "Disk: " + " | ".join(parts)
        except Exception:
            return "Disk info failed"

    def get_battery(self):
        try:
            b = self.psutil.sensors_battery()
            if not b:
                return "No battery detected (desktop system)"
            plug = "plugged in" if b.power_plugged else "on battery"
            secs = int(b.secsleft) if b.secsleft != -1 else None
            time_s = f", {secs // 60} min remaining" if secs else ""
            return f"Battery: {b.percent}%, {plug}{time_s}"
        except Exception:
            return "Battery info failed"

    def get_network(self):
        try:
            p = self.psutil
            ifaces = []
            for name, addrs in p.net_if_addrs().items():
                ips = [a.address for a in addrs if a.family == 2]
                if ips:
                    ifaces.append(f"{name} ({', '.join(ips)})")
            stats = p.net_if_stats()
            lines = []
            for name in ifaces:
                up = "up" if name.split(" ")[0] in stats and stats[name.split(" ")[0]].isup else "?"
                lines.append(f"{name} [{up}]")
            conns = len(p.net_connections())
            return f"Network: " + "; ".join(lines) + f" | Connections: {conns}"
        except Exception:
            return "Network info failed"

    def get_processes(self, top=10):
        try:
            import heapq
            p = self.psutil
            procs = heapq.nlargest(top, p.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent']),
                          key=lambda p: p.info['cpu_percent'] or 0)
            lines = []
            for proc in procs:
                try:
                    lines.append(f"{proc.info['name']} (PID:{proc.info['pid']}) CPU:{proc.info['cpu_percent']:.1f}% MEM:{proc.info['memory_percent']:.1f}%")
                except Exception:
                    pass
            return "Top processes: " + " | ".join(lines)
        except Exception:
            return "Process list failed"

    def kill_process(self, name):
        try:
            name_lower = name.lower().strip()
            killed = []
            protected = {'system', 'svchost', 'csrss', 'winlogon', 'lsass', 'services',
                         'smss', 'wininit', 'dwm', 'fontdrvhost', 'searchindexer'}
            for p in self.psutil.process_iter(['pid', 'name']):
                try:
                    pname = p.info['name'].lower()
                    if pname == name_lower or pname.startswith(name_lower + '.'):
                        if pname in protected:
                            continue
                        p.terminate()
                        killed.append(p.info['name'])
                except Exception:
                    pass
            if killed:
                return f"Terminated {len(killed)} process(es): {', '.join(set(killed))}"
            return f"No process matching '{name}' found"
        except Exception:
            return "Kill process failed"

    def start_process(self, path):
        try:
            path = str(path)
            if any(c in path for c in '<>|`&\n\r\x00'):
                return "Start process failed: invalid characters in path"
            resolved = PathValidator.safe_resolve(path)
            if not os.path.exists(resolved):
                return f"Start process failed: path not found: {path}"
            parts = os.path.splitext(resolved)
            ext = parts[1].lower() if parts[1] else ""
            if ext in ('.exe', '.com', '.bat', '.cmd', '.app', '') or os.access(resolved, os.X_OK):
                subprocess.Popen([resolved], shell=False)
            else:
                open_file(resolved)
            return f"Started: {path}"
        except PermissionError as e:
            return str(e)
        except Exception as e:
            return "Start process failed"

    def take_screenshot(self):
        import secrets as _secrets
        token = _secrets.token_hex(12)
        path = os.path.join(tempfile.gettempdir(), f"friday_ss_{token}.png")
        try:
            import pyautogui
            pyautogui.screenshot(path)
            return f"Screenshot saved to {path}"
        except ImportError:
            try:
                import mss
                with mss.mss() as sct:
                    sct.shot(output=path)
                return f"Screenshot saved to {path}"
            except ImportError:
                pass
        try:
            result = take_screenshot_cli(path)
            if result and os.path.exists(result):
                return f"Screenshot saved to {result}"
            return "Screenshot failed"
        except Exception:
            return "Screenshot failed"

    def get_clipboard(self):
        if self.safe_mode:
            return "Clipboard access blocked by safe mode. Disable safe mode first."
        try:
            import pyperclip
            text = pyperclip.paste()
            return f"Clipboard: {text[:500]}" if text else "Clipboard is empty"
        except ImportError:
            try:
                text = get_clipboard_text()
                return f"Clipboard: {text[:500]}" if text else "Clipboard is empty"
            except Exception:
                return "Clipboard failed"

    def set_clipboard(self, text):
        if self.safe_mode:
            return "Clipboard access blocked by safe mode. Disable safe mode first."
        try:
            import pyperclip
            pyperclip.copy(text)
            return "Clipboard set"
        except ImportError:
            try:
                set_clipboard_text(text)
                return "Clipboard set"
            except Exception:
                return "Clipboard set failed"

    def get_volume(self):
        try:
            vol = get_volume()
            return f"Volume: {vol}%" if vol and vol != "?" else f"Volume: {vol}"
        except Exception:
            return "Volume get failed"

    def set_volume(self, level):
        try:
            level = max(0, min(100, int(level)))
            set_volume(level)
            return f"Volume set to {level}%"
        except Exception:
            return "Volume set failed"

    def mute_volume(self):
        try:
            mute_volume()
            return "Volume mute toggled"
        except Exception:
            return "Mute failed"

    def media_play_pause(self):
        try:
            media_play_pause()
            return "Play/Pause toggled"
        except Exception:
            return "Media key failed"

    def media_next(self):
        try:
            media_next()
            return "Next track"
        except Exception:
            return "Media key failed"

    def media_prev(self):
        try:
            media_prev()
            return "Previous track"
        except Exception:
            return "Media key failed"

    def list_wifi(self):
        try:
            nets = list_wifi()
            if nets:
                return "WiFi profiles: " + ", ".join(nets)
            return "No WiFi profiles found"
        except Exception:
            return "WiFi list failed"

    def wifi_status(self):
        try:
            status = wifi_status()
            if status:
                extra = f" ({status.get('signal', '')})" if status.get('signal') else ""
                return f"WiFi: connected to '{status['ssid']}'{extra}"
            return "WiFi: not connected"
        except Exception:
            return "WiFi status failed"

    def list_windows(self):
        try:
            titles = list_windows_titles()
            if titles:
                return "Windows: " + " | ".join(titles[:20])
            return "No windows with titles found"
        except Exception:
            return "Window list failed"

    def focus_window(self, title):
        try:
            focus_window(title)
            return f"Attempted to focus: {title}"
        except Exception:
            return "Focus window failed"

    def lock_workstation(self):
        try:
            lock_workstation()
            return "Workstation locked"
        except Exception:
            return "Lock failed"

    def get_system_info(self):
        try:
            p = self.psutil
            boot = datetime.datetime.fromtimestamp(p.boot_time()).strftime("%Y-%m-%d %H:%M:%S")
            cpu = p.cpu_percent(interval=0.3)
            mem = p.virtual_memory()
            disks = []
            for part in p.disk_partitions():
                try:
                    u = p.disk_usage(part.mountpoint)
                    disks.append(f"{part.mountpoint} {u.percent}% ({u.free//(1024**3)}GB free)")
                except Exception:
                    disks.append(f"{part.mountpoint} ?")
            host = get_hostname()
            return (f"System: {host}, Booted {boot}, "
                    f"CPU {cpu}%, RAM {mem.percent}% ({mem.used//(1024**3)}GB/{mem.total//(1024**3)}GB), "
                    f"Disk: " + " | ".join(disks))
        except Exception:
            return "System info failed"

    def get_installed_software(self):
        try:
            items = get_installed_software()
            return "Software: " + " | ".join(items[:20]) if items else "Could not retrieve software list"
        except Exception:
            return "Software list failed"

    def get_startup_programs(self):
        try:
            items = get_startup_programs()
            return "Startup: " + " | ".join(items[:15]) if items else "No startup programs found"
        except Exception:
            return "Startup list failed"

    def get_services(self):
        try:
            svcs = get_running_services()
            return f"Running services ({len(svcs)}): " + ", ".join(sorted(svcs)[:20]) + (" ..." if len(svcs) > 20 else "")
        except Exception:
            return "Services failed"

    def get_system_uptime(self):
        try:
            secs = int(time.time() - self.psutil.boot_time())
            days, secs = divmod(secs, 86400)
            hrs, secs = divmod(secs, 3600)
            mins = secs // 60
            parts = []
            if days:
                parts.append(f"{days}d")
            if hrs:
                parts.append(f"{hrs}h")
            parts.append(f"{mins}m")
            return "Uptime: " + " ".join(parts)
        except Exception:
            return "Uptime failed"

    def get_active_connections(self):
        try:
            p = self.psutil
            conns = p.net_connections()
            by_state = {}
            for c in conns:
                by_state[c.status] = by_state.get(c.status, 0) + 1
            summary = ", ".join(f"{s}: {n}" for s, n in sorted(by_state.items()))
            remotes = sorted(set(f"{c.raddr.ip}:{c.raddr.port}" for c in conns if c.raddr and c.raddr.ip),
                           key=lambda x: x.split(':')[0])[:5]
            remote_s = ", ".join(remotes) if remotes else "none"
            return f"Connections ({len(conns)}): {summary} | Remote: {remote_s}"
        except Exception:
            return "Connections failed"

    def explore_drives(self):
        try:
            lines = explore_drives()
            if lines:
                return "Drives:\n" + "\n".join(lines)
            return "Drive list failed"
        except Exception:
            return "Drive list failed"

    def find_installed_app(self, name):
        try:
            results = find_installed_app(name)
            if results:
                return "Found:\n" + "\n".join(f"  {r}" for r in results[:15])
            return f"No app found matching '{name}'"
        except Exception:
            return "App search failed"

    def get_all_tool_definitions(self):
        return [
            {"type": "function", "function": {"name": "get_cpu", "description": "CPU usage percent", "parameters": {"type": "object", "properties": {}}}},
            {"type": "function", "function": {"name": "get_memory", "description": "RAM usage percent", "parameters": {"type": "object", "properties": {}}}},
            {"type": "function", "function": {"name": "get_disk", "description": "Disk usage all drives", "parameters": {"type": "object", "properties": {}}}},
            {"type": "function", "function": {"name": "get_battery", "description": "Battery percent and status", "parameters": {"type": "object", "properties": {}}}},
            {"type": "function", "function": {"name": "get_network", "description": "Network ifaces, IPs, connections", "parameters": {"type": "object", "properties": {}}}},
            {"type": "function", "function": {"name": "get_system_info", "description": "Full system info", "parameters": {"type": "object", "properties": {}}}},
            {"type": "function", "function": {"name": "get_system_uptime", "description": "Uptime", "parameters": {"type": "object", "properties": {}}}},
            {"type": "function", "function": {"name": "get_processes", "description": "Top processes by CPU", "parameters": {"type": "object", "properties": {"top": {"type": "integer", "description": "Count", "default": 10}}}}},
            {"type": "function", "function": {"name": "kill_process", "description": "Kill process by name", "parameters": {"type": "object", "properties": {"name": {"type": "string", "description": "Process name"}}, "required": ["name"]}}},
            {"type": "function", "function": {"name": "take_screenshot", "description": "Take screenshot", "parameters": {"type": "object", "properties": {}}}},
            {"type": "function", "function": {"name": "get_clipboard", "description": "Clipboard text", "parameters": {"type": "object", "properties": {}}}},
            {"type": "function", "function": {"name": "set_clipboard", "description": "Copy text to clipboard", "parameters": {"type": "object", "properties": {"text": {"type": "string", "description": "Text"}}, "required": ["text"]}}},
            {"type": "function", "function": {"name": "get_volume", "description": "System volume level", "parameters": {"type": "object", "properties": {}}}},
            {"type": "function", "function": {"name": "set_volume", "description": "Set volume 0-100", "parameters": {"type": "object", "properties": {"level": {"type": "integer", "description": "0-100"}}, "required": ["level"]}}},
            {"type": "function", "function": {"name": "mute_volume", "description": "Toggle mute", "parameters": {"type": "object", "properties": {}}}},
            {"type": "function", "function": {"name": "media_play_pause", "description": "Toggle play/pause", "parameters": {"type": "object", "properties": {}}}},
            {"type": "function", "function": {"name": "media_next", "description": "Next track", "parameters": {"type": "object", "properties": {}}}},
            {"type": "function", "function": {"name": "media_prev", "description": "Previous track", "parameters": {"type": "object", "properties": {}}}},
            {"type": "function", "function": {"name": "list_wifi", "description": "List saved WiFi profile names/SSIDs", "parameters": {"type": "object", "properties": {}}}},
            {"type": "function", "function": {"name": "wifi_status", "description": "Current WiFi status", "parameters": {"type": "object", "properties": {}}}},
            {"type": "function", "function": {"name": "list_windows", "description": "Open window titles", "parameters": {"type": "object", "properties": {}}}},
            {"type": "function", "function": {"name": "focus_window", "description": "Focus window by title", "parameters": {"type": "object", "properties": {"title": {"type": "string", "description": "Title"}}, "required": ["title"]}}},
            {"type": "function", "function": {"name": "lock_workstation", "description": "Lock workstation", "parameters": {"type": "object", "properties": {}}}},
            {"type": "function", "function": {"name": "get_installed_software", "description": "Installed software list", "parameters": {"type": "object", "properties": {}}}},
            {"type": "function", "function": {"name": "get_startup_programs", "description": "Startup programs list", "parameters": {"type": "object", "properties": {}}}},
            {"type": "function", "function": {"name": "get_services", "description": "Running services list", "parameters": {"type": "object", "properties": {}}}},
            {"type": "function", "function": {"name": "get_active_connections", "description": "Active network connections", "parameters": {"type": "object", "properties": {}}}},
            {"type": "function", "function": {"name": "explore_drives", "description": "List all drives/volumes with free space info", "parameters": {"type": "object", "properties": {}}}},
            {"type": "function", "function": {"name": "find_installed_app", "description": "Search for an installed app by name", "parameters": {"type": "object", "properties": {"name": {"type": "string", "description": "App name to search for"}}, "required": ["name"]}}},
        ]

    def get_handler(self, name):
        handlers = {
            "get_cpu": self.get_cpu, "get_memory": self.get_memory,
            "get_disk": self.get_disk, "get_battery": self.get_battery,
            "get_network": self.get_network, "get_system_info": self.get_system_info,
            "get_system_uptime": self.get_system_uptime,
            "get_processes": self.get_processes, "kill_process": self.kill_process,
            "take_screenshot": self.take_screenshot,
            "get_clipboard": self.get_clipboard, "set_clipboard": self.set_clipboard,
            "get_volume": self.get_volume, "set_volume": self.set_volume,
            "mute_volume": self.mute_volume, "media_play_pause": self.media_play_pause,
            "media_next": self.media_next, "media_prev": self.media_prev,
            "list_wifi": self.list_wifi, "wifi_status": self.wifi_status,
            "list_windows": self.list_windows, "focus_window": self.focus_window,
            "lock_workstation": self.lock_workstation,
            "get_installed_software": self.get_installed_software,
            "get_startup_programs": self.get_startup_programs,
            "get_services": self.get_services,
            "get_active_connections": self.get_active_connections,
            "explore_drives": self.explore_drives,
            "find_installed_app": self.find_installed_app,
        }
        return handlers.get(name)
