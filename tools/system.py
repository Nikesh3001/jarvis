import os, sys, time, datetime, json, subprocess, tempfile
from pathlib import Path

from core.platform_utils import is_windows, is_macos, is_linux, get_platform


class SystemTools:
    def __init__(self):
        self._psutil = None

    @property
    def psutil(self):
        if self._psutil is None:
            import psutil as _p
            self._psutil = _p
        return self._psutil

    def get_cpu(self):
        try:
            p = self.psutil
            freq = p.cpu_freq()
            freq_s = f"{freq.current:.0f} MHz" if freq else "N/A"
            return f"CPU: {p.cpu_percent(interval=0.5)}% used, {p.cpu_count(logical=True)} logical cores, freq {freq_s}"
        except Exception as e:
            return "CPU info failed"

    def get_memory(self):
        try:
            m = self.psutil.virtual_memory()
            return f"RAM: {m.percent}% used, {m.used // (1024**3)} GB / {m.total // (1024**3)} GB, {m.available // (1024**3)} GB free"
        except Exception as e:
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
        except Exception as e:
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
        except Exception as e:
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
        except Exception as e:
            return "Network info failed"

    def get_processes(self, top=10):
        try:
            p = self.psutil
            procs = sorted(p.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent']),
                          key=lambda p: p.info['cpu_percent'] or 0, reverse=True)[:top]
            lines = []
            for proc in procs:
                try:
                    lines.append(f"{proc.info['name']} (PID:{proc.info['pid']}) CPU:{proc.info['cpu_percent']:.1f}% MEM:{proc.info['memory_percent']:.1f}%")
                except Exception:
                    pass
            return "Top processes: " + " | ".join(lines)
        except Exception as e:
            return "Process list failed"

    def kill_process(self, name):
        try:
            killed = []
            for p in self.psutil.process_iter(['pid', 'name']):
                try:
                    if name.lower() in p.info['name'].lower():
                        p.terminate()
                        killed.append(p.info['name'])
                except Exception:
                    pass
            if killed:
                return f"Terminated {len(killed)} process(es): {', '.join(set(killed))}"
            return f"No process matching '{name}' found"
        except Exception as e:
            return "Kill process failed"

    def start_process(self, path):
        try:
            import subprocess as _sp
            if path.lower().endswith('.exe') or '.' not in os.path.basename(path):
                _sp.Popen([path], shell=False)
            elif is_windows():
                os.startfile(path)
            elif is_macos():
                _sp.Popen(["open", path], shell=False)
            else:
                _sp.Popen(["xdg-open", path], shell=False)
            return f"Started: {path}"
        except Exception as e:
            return "Start process failed"

    def take_screenshot(self):
        path = os.path.join(tempfile.gettempdir(), f"screenshot_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.png")
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
                if is_windows():
                    r = subprocess.run(["powershell", "-NoProfile", "-Command",
                        f"Add-Type -AssemblyName System.Windows.Forms; $s = [Windows.Forms.Screen]::PrimaryScreen.Bounds; $b = New-Object Drawing.Bitmap $s.Width,$s.Height; $g = [Drawing.Graphics]::FromImage($b); $g.CopyFromScreen(0,0,0,0,$s.Size); $b.Save('{path}'); $g.Dispose(); $b.Dispose()"],
                        capture_output=True, text=True, timeout=30)
                    return f"Screenshot saved to {path}"
                elif is_macos():
                    subprocess.run(["screencapture", path], timeout=30)
                    return f"Screenshot saved to {path}"
                else:
                    subprocess.run(["gnome-screenshot", "-f", path], timeout=30)
                    return f"Screenshot saved to {path}"
            except Exception as e:
                return "Screenshot failed"

    def _get_clipboard_fallback(self):
        if is_windows():
            r = subprocess.run(["powershell", "-NoProfile", "-Command",
                "Get-Clipboard | Select-Object -First 1"],
                capture_output=True, text=True, timeout=10)
            return r.stdout.strip()
        elif is_macos():
            r = subprocess.run(["pbpaste"], capture_output=True, text=True, timeout=10)
            return r.stdout.strip()
        else:
            r = subprocess.run(["xclip", "-selection", "clipboard", "-o"],
                capture_output=True, text=True, timeout=10)
            return r.stdout.strip()

    def _set_clipboard_fallback(self, text):
        if is_windows():
            subprocess.run(
                ["powershell", "-NoProfile", "-Command", "$input | Set-Clipboard"],
                input=text.encode('utf-8'), capture_output=True, timeout=10)
        elif is_macos():
            subprocess.run(["pbcopy"], input=text.encode(), timeout=10)
        else:
            subprocess.run(["xclip", "-selection", "clipboard"], input=text.encode(), timeout=10)
        return True

    def get_clipboard(self):
        try:
            import pyperclip
            text = pyperclip.paste()
            return f"Clipboard: {text[:500]}" if text else "Clipboard is empty"
        except ImportError:
            try:
                text = self._get_clipboard_fallback()
                return f"Clipboard: {text[:500]}" if text else "Clipboard is empty"
            except Exception as e:
                return "Clipboard failed"

    def set_clipboard(self, text):
        try:
            import pyperclip
            pyperclip.copy(text)
            return "Clipboard set"
        except ImportError:
            try:
                self._set_clipboard_fallback(text)
                return "Clipboard set"
            except Exception as e:
                return "Clipboard set failed"

    def _get_volume_windows(self):
        r = subprocess.run(["powershell", "-NoProfile", "-Command",
            r"Add-Type -TypeDefinition @' using System.Runtime.InteropServices; public class Audio { [DllImport(\"winmm.dll\")] public static extern int waveOutGetVolume(System.IntPtr h, out uint v); } '@; $v=0; [Audio]::waveOutGetVolume([IntPtr]::Zero,[ref]$v); $p=[math]::Round((($v -band 0xFFFF)/65535.0)*100); Write-Output $p"],
            capture_output=True, text=True, timeout=10)
        return r.stdout.strip()

    def _get_volume_macos(self):
        r = subprocess.run(["osascript", "-e", "output volume of (get volume settings)"],
            capture_output=True, text=True, timeout=10)
        return r.stdout.strip()

    def _get_volume_linux(self):
        r = subprocess.run(["amixer", "sget", "Master"], capture_output=True, text=True, timeout=10)
        for line in r.stdout.split('\n'):
            if '%' in line:
                return line.split('%')[0].split('[')[-1]
        return "?"

    def get_volume(self):
        try:
            vol = "?"
            if is_windows():
                vol = self._get_volume_windows()
            elif is_macos():
                vol = self._get_volume_macos()
            else:
                vol = self._get_volume_linux()
            return f"Volume: {vol}%" if vol and vol != "?" else f"Volume: {vol}"
        except Exception as e:
            return "Volume get failed"

    def _set_volume_windows(self, level):
        ps_code = f"Add-Type -TypeDefinition @' using System.Runtime.InteropServices; public class Audio {{ [DllImport(\"winmm.dll\")] public static extern int waveOutGetVolume(System.IntPtr h, out uint v); [DllImport(\"winmm.dll\")] public static extern int waveOutSetVolume(System.IntPtr h, uint v); }} '@; $v=[uint32](({level}/100.0)*65535); [Audio]::waveOutSetVolume([IntPtr]::Zero,($v -bor ($v -shl 16)))"
        encoded = __import__('base64').b64encode(ps_code.encode('utf-16-le')).decode()
        subprocess.run(["powershell", "-NoProfile", "-EncodedCommand", encoded],
            capture_output=True, text=True, timeout=10)

    def _set_volume_macos(self, level):
        subprocess.run(["osascript", "-e", f"set volume output volume {level}"], timeout=10)

    def _set_volume_linux(self, level):
        subprocess.run(["amixer", "sset", "Master", f"{level}%"], capture_output=True, timeout=10)

    def set_volume(self, level):
        level = max(0, min(100, int(level)))
        try:
            if is_windows():
                self._set_volume_windows(level)
            elif is_macos():
                self._set_volume_macos(level)
            else:
                self._set_volume_linux(level)
            return f"Volume set to {level}%"
        except Exception as e:
            return "Volume set failed"

    def mute_volume(self):
        try:
            if is_windows():
                subprocess.run(["powershell", "-NoProfile", "-Command",
                    "(New-Object -ComObject WScript.Shell).SendKeys([char]0xAD)"],
                    capture_output=True, text=True, timeout=5)
            elif is_macos():
                subprocess.run(["osascript", "-e", "set volume muted true"], timeout=5)
            else:
                subprocess.run(["amixer", "sset", "Master", "mute"], capture_output=True, timeout=5)
            return "Volume mute toggled"
        except Exception as e:
            return "Mute failed"

    def media_play_pause(self):
        try:
            if is_windows():
                subprocess.run(["powershell", "-NoProfile", "-Command",
                    "(New-Object -ComObject WScript.Shell).SendKeys([char]0xB0)"],
                    capture_output=True, text=True, timeout=5)
            elif is_macos():
                subprocess.run(["osascript", "-e", 'tell application "System Events" to key code 16'], timeout=5)
            else:
                subprocess.run(["playerctl", "play-pause"], capture_output=True, timeout=5)
            return "Play/Pause toggled"
        except Exception as e:
            return "Media key failed"

    def media_next(self):
        try:
            if is_windows():
                subprocess.run(["powershell", "-NoProfile", "-Command",
                    "(New-Object -ComObject WScript.Shell).SendKeys([char]0xB1)"],
                    capture_output=True, text=True, timeout=5)
            elif is_macos():
                subprocess.run(["osascript", "-e", 'tell application "System Events" to key code 17'], timeout=5)
            else:
                subprocess.run(["playerctl", "next"], capture_output=True, timeout=5)
            return "Next track"
        except Exception as e:
            return "Media key failed"

    def media_prev(self):
        try:
            if is_windows():
                subprocess.run(["powershell", "-NoProfile", "-Command",
                    "(New-Object -ComObject WScript.Shell).SendKeys([char]0xB2)"],
                    capture_output=True, text=True, timeout=5)
            elif is_macos():
                subprocess.run(["osascript", "-e", 'tell application "System Events" to key code 18'], timeout=5)
            else:
                subprocess.run(["playerctl", "previous"], capture_output=True, timeout=5)
            return "Previous track"
        except Exception as e:
            return "Media key failed"

    def list_wifi(self):
        try:
            if is_windows():
                r = subprocess.run(["netsh", "wlan", "show", "profiles"], capture_output=True, text=True, timeout=15)
                profiles = [l.split(":")[1].strip() for l in r.stdout.split('\n') if "All User Profile" in l]
                results = []
                for p in profiles[:15]:
                    results.append(p)
                if not results:
                    return "No WiFi profiles found"
                return "WiFi profiles: " + ", ".join(results)
            elif is_macos():
                r = subprocess.run(["/System/Library/PrivateFrameworks/Apple80211.framework/Versions/Current/Resources/airport", "-s"],
                    capture_output=True, text=True, timeout=15)
                return "WiFi networks:\n" + (r.stdout[:1000] if r.stdout else "No networks found")
            else:
                r = subprocess.run(["nmcli", "-t", "-f", "SSID,SECURITY", "device", "wifi", "list"],
                    capture_output=True, text=True, timeout=15)
                if r.returncode == 0 and r.stdout.strip():
                    nets = [l.split(":")[0] for l in r.stdout.strip().split('\n') if l and l.split(":")[0]]
                    return "WiFi networks: " + ", ".join(nets[:20])
                r2 = subprocess.run(["iwconfig"], capture_output=True, text=True, timeout=10)
                return "WiFi: " + r2.stdout[:500] if r2.stdout else "WiFi info unavailable"
        except Exception as e:
            return "WiFi list failed"

    def wifi_status(self):
        try:
            if is_windows():
                r = subprocess.run(["netsh", "wlan", "show", "interfaces"], capture_output=True, text=True, timeout=10)
                lines = r.stdout.split('\n')
                ssid = ""
                signal = ""
                for l in lines:
                    if "SSID" in l and "BSSID" not in l and ":" in l:
                        ssid = l.split(":")[1].strip()
                    if "Signal" in l and ":" in l:
                        signal = l.split(":")[1].strip()
                if ssid:
                    return f"WiFi: connected to '{ssid}' ({signal})"
                return "WiFi: not connected"
            elif is_macos():
                r = subprocess.run(["/System/Library/PrivateFrameworks/Apple80211.framework/Versions/Current/Resources/airport", "-I"],
                    capture_output=True, text=True, timeout=10)
                for line in r.stdout.split('\n'):
                    if "SSID" in line and ":" in line:
                        ssid = line.split(":")[1].strip()
                        return f"WiFi: connected to '{ssid}'"
                return "WiFi: not connected"
            else:
                r = subprocess.run(["nmcli", "-t", "-f", "TYPE,STATE,CONNECTION", "device", "status"],
                    capture_output=True, text=True, timeout=10)
                for line in r.stdout.strip().split('\n'):
                    parts = line.split(':')
                    if len(parts) >= 3 and 'wifi' in parts[0].lower() and 'connected' in parts[1].lower():
                        return f"WiFi: connected to '{parts[2]}'"
                return "WiFi: not connected"
        except Exception as e:
            return "WiFi status failed"

    def _list_windows_cross(self):
        try:
            import pygetwindow as gw
            wins = gw.getAllTitles()
            visible = [w for w in wins if w.strip()]
            if visible:
                return "Windows: " + " | ".join(visible[:20])
        except ImportError:
            pass
        if is_windows():
            r = subprocess.run(["powershell", "-NoProfile", "-Command",
                "Add-Type @' using System; using System.Runtime.InteropServices; public class Win {{ [DllImport(\"user32.dll\")] public static extern IntPtr GetForegroundWindow(); [DllImport(\"user32.dll\")] public static extern int GetWindowText(IntPtr h, System.Text.StringBuilder t, int c); }} '@; $procs = Get-Process | Where-Object {{ $_.MainWindowTitle -ne '' }} | Select-Object -First 20 MainWindowTitle; ($procs | ConvertTo-Json)"],
                capture_output=True, text=True, timeout=10)
            data = json.loads(r.stdout)
            if isinstance(data, dict):
                data = [data]
            titles = [d['MainWindowTitle'] for d in data if d.get('MainWindowTitle')]
            return "Windows: " + " | ".join(titles[:20]) if titles else "No windows with titles found"
        elif is_macos():
            r = subprocess.run(["osascript", "-e",
                'tell application "System Events" to get name of every process whose visible is true'],
                capture_output=True, text=True, timeout=10)
            apps = [a.strip() for a in r.stdout.strip().split(', ') if a.strip()]
            return "Windows: " + " | ".join(apps[:20]) if apps else "No windows found"
        else:
            r = subprocess.run(["wmctrl", "-l"], capture_output=True, text=True, timeout=10)
            if r.returncode == 0 and r.stdout.strip():
                wins = [l.split(None, 3)[-1] for l in r.stdout.strip().split('\n') if len(l.split(None, 3)) > 3]
                return "Windows: " + " | ".join(wins[:20]) if wins else "No windows found"
            try:
                r2 = subprocess.run(["xdotool", "getactivewindow", "getwindowname"], capture_output=True, text=True, timeout=5)
                if r2.stdout.strip():
                    return f"Active window: {r2.stdout.strip()}"
            except Exception:
                pass
            return "No window listing available (install wmctrl or xdotool)"

    def list_windows(self):
        try:
            return self._list_windows_cross()
        except Exception as e:
            return "Window list failed"

    def focus_window(self, title):
        try:
            import pygetwindow as gw
            wins = gw.getWindowsWithText(title)
            if wins:
                wins[0].activate()
                return f"Focused window: {wins[0].title}"
        except ImportError:
            pass
        if is_windows():
            ps_code = f"$h=Get-Process | Where-Object {{ $_.MainWindowTitle -like '*{title}*' }} | Select-Object -First 1 | ForEach-Object {{ $_.MainWindowHandle }}; if ($h -and $h -ne 0) {{ Add-Type @' using System; using System.Runtime.InteropServices; public class W {{ [DllImport(\"user32.dll\")] public static extern bool SetForegroundWindow(IntPtr h); }} '@; [W]::SetForegroundWindow($h) }}"
            encoded = __import__('base64').b64encode(ps_code.encode('utf-16-le')).decode()
            subprocess.run(["powershell", "-NoProfile", "-EncodedCommand", encoded],
                capture_output=True, text=True, timeout=10)
            return f"Attempted to focus: {title}"
        elif is_macos():
            safe_title = title.replace('"', '').replace("'", "")
            subprocess.run(["osascript", "-e",
                f'tell application "{safe_title}" to activate'],
                capture_output=True, timeout=10)
            return f"Attempted to focus: {title}"
        else:
            try:
                subprocess.run(["xdotool", "search", "--name", title, "windowactivate"],
                    capture_output=True, timeout=10)
                return f"Attempted to focus: {title}"
            except Exception:
                subprocess.run(["wmctrl", "-a", title], capture_output=True, timeout=10)
                return f"Attempted to focus: {title}"

    def lock_workstation(self):
        try:
            if is_windows():
                subprocess.run(["rundll32.exe", "user32.dll,LockWorkStation"], capture_output=True, text=True, timeout=5)
            elif is_macos():
                subprocess.run(["osascript", "-e", 'tell application "System Events" to keystroke "q" using {command down, control down}'],
                    capture_output=True, timeout=5)
            else:
                subprocess.run(["gnome-screensaver-command", "-l"], capture_output=True, timeout=5)
                subprocess.run(["xdg-screensaver", "lock"], capture_output=True, timeout=5)
            return "Workstation locked"
        except Exception as e:
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
            host = os.environ.get('COMPUTERNAME') or os.environ.get('HOSTNAME') or os.environ.get('HOST') or 'PC'
            return (f"System: {host}, Booted {boot}, "
                    f"CPU {cpu}%, RAM {mem.percent}% ({mem.used//(1024**3)}GB/{mem.total//(1024**3)}GB), "
                    f"Disk: " + " | ".join(disks))
        except Exception as e:
            return "System info failed"

    def get_installed_software(self):
        try:
            if is_windows():
                r = subprocess.run(["powershell", "-NoProfile", "-Command",
                    "Get-ItemProperty HKLM:\\Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\*, HKLM:\\Software\\Wow6432Node\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\* | Where-Object DisplayName | Select-Object -First 30 DisplayName,DisplayVersion | ConvertTo-Json"],
                    capture_output=True, text=True, timeout=30)
                data = json.loads(r.stdout)
                if isinstance(data, dict):
                    data = [data]
                names = [f"{d.get('DisplayName','?')} ({d.get('DisplayVersion','?')})" for d in data if d.get('DisplayName')]
                return "Software: " + " | ".join(names[:20]) if names else "Could not retrieve software list"
            elif is_macos():
                r = subprocess.run(["system_profiler", "SPApplicationsDataType", "-json"],
                    capture_output=True, text=True, timeout=60)
                data = json.loads(r.stdout)
                apps = data.get("SPApplicationsDataType", [])
                names = [a.get("_name", "?") for a in apps[:30] if a.get("_name")]
                return "Software: " + " | ".join(names[:20]) if names else "Could not retrieve software list"
            else:
                r = subprocess.run(["dpkg", "--get-selections"], capture_output=True, text=True, timeout=30)
                if r.returncode == 0:
                    pkgs = [l.split()[0] for l in r.stdout.strip().split('\n')[:30] if l.strip()]
                    return "Software: " + " | ".join(pkgs[:20]) if pkgs else "Could not retrieve software list"
                r2 = subprocess.run(["rpm", "-qa", "--queryformat", "%{NAME}\n"], capture_output=True, text=True, timeout=30)
                if r2.returncode == 0:
                    pkgs = [l.strip() for l in r2.stdout.strip().split('\n')[:30] if l.strip()]
                    return "Software: " + " | ".join(pkgs[:20]) if pkgs else "Could not retrieve software list"
                return "Software listing unavailable (install dpkg or rpm)"
        except Exception as e:
            return "Software list failed"

    def get_startup_programs(self):
        try:
            if is_windows():
                r = subprocess.run(["powershell", "-NoProfile", "-Command",
                    "Get-CimInstance Win32_StartupCommand | Select-Object Name,Command,User | ConvertTo-Json"],
                    capture_output=True, text=True, timeout=15)
                data = json.loads(r.stdout)
                if isinstance(data, dict):
                    data = [data]
                items = [f"{d.get('Name','?')} ({d.get('User','?')})" for d in data if d.get('Name')]
                return "Startup: " + " | ".join(items[:15]) if items else "No startup programs found"
            elif is_macos():
                r = subprocess.run(["osascript", "-e",
                    'tell application "System Events" to get name of every login item'],
                    capture_output=True, text=True, timeout=10)
                items = [a.strip() for a in r.stdout.strip().split(', ') if a.strip()]
                return "Startup: " + " | ".join(items[:15]) if items else "No startup programs found"
            else:
                items = []
                autostart = Path(os.path.expanduser("~/.config/autostart"))
                if autostart.exists():
                    items = [f.stem for f in autostart.iterdir() if f.suffix == '.desktop']
                for f in [Path("/etc/xdg/autostart"), Path(os.path.expanduser("~/.config/autostart"))]:
                    if f.exists():
                        items.extend([p.stem for p in f.iterdir() if p.suffix == '.desktop'])
                return "Startup: " + " | ".join(items[:15]) if items else "No startup programs found"
        except Exception as e:
            return "Startup list failed"

    def get_services(self):
        try:
            if is_windows():
                p = self.psutil
                svcs = []
                for s in p.win_service_iter():
                    try:
                        if s.status() == 'running':
                            svcs.append(s.name())
                    except Exception:
                        pass
                return f"Running services ({len(svcs)}): " + ", ".join(sorted(svcs)[:20]) + (" ..." if len(svcs) > 20 else "")
            elif is_macos():
                r = subprocess.run(["launchctl", "list"], capture_output=True, text=True, timeout=10)
                svcs = [l.split('\t')[2] if '\t' in l else l for l in r.stdout.strip().split('\n')[1:][:30] if l.strip()]
                return f"Running services ({len(svcs)}): " + ", ".join(sorted(svcs)[:20]) + (" ..." if len(svcs) > 20 else "")
            else:
                r = subprocess.run(["systemctl", "list-units", "--type=service", "--state=running", "--no-pager"],
                    capture_output=True, text=True, timeout=15)
                if r.returncode == 0:
                    svcs = [l.split()[0] for l in r.stdout.strip().split('\n') if l.strip() and '.service' in l][:30]
                    return f"Running services ({len(svcs)}): " + ", ".join(sorted(svcs)[:20]) + (" ..." if len(svcs) > 20 else "")
                r2 = subprocess.run(["service", "--status-all"], capture_output=True, text=True, timeout=15)
                svcs = [l.split()[-1] for l in r2.stdout.strip().split('\n') if '[ + ]' in l][:30]
                return f"Running services ({len(svcs)}): " + ", ".join(sorted(svcs)[:20]) + (" ..." if len(svcs) > 20 else "")
        except Exception as e:
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
        except Exception as e:
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
        except Exception as e:
            return "Connections failed"

    def explore_drives(self):
        try:
            if is_windows():
                r = subprocess.run(
                    ["powershell", "-NoProfile", "-Command",
                     "Get-PSDrive -PSProvider FileSystem | Select-Object Name, Root, Used, Free | ConvertTo-Json"],
                    capture_output=True, text=True, timeout=15
                )
                data = json.loads(r.stdout)
                if isinstance(data, dict):
                    data = [data]
                lines = []
                for d in data:
                    name = d.get("Name", "?")
                    root = d.get("Root", "?")
                    free = d.get("Free", 0)
                    used = d.get("Used", 0)
                    total = free + used
                    if total > 0:
                        pct = int(used / total * 100)
                    else:
                        pct = 0
                    lines.append(f"{root} ({name}:) {pct}% used - {free//(1024**3)}GB free / {total//(1024**3)}GB total")
                return "Drives:\n" + "\n".join(lines)
            elif is_macos():
                r = subprocess.run(["df", "-h"], capture_output=True, text=True, timeout=10)
                return "Drives:\n" + r.stdout[:1000]
            else:
                r = subprocess.run(["df", "-h"], capture_output=True, text=True, timeout=10)
                return "Drives:\n" + r.stdout[:1000]
        except Exception as e:
            return "Drive list failed"

    def find_installed_app(self, name):
        try:
            search = name.lower().strip()
            results = []
            if is_windows():
                import json as _json
                import base64 as _b64
                safe_search = search.replace('"', '`"').replace("'", "''")
                ps_script = (
                    '$search = "' + safe_search + '"\n'
                    '$results = @()\n'
                    '$results += Get-StartApps | Where-Object { $_.Name -like "*$search*" } | Select-Object Name, AppId\n'
                    '$results += Get-ItemProperty HKLM:\\Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\* | Where-Object { $_.DisplayName -like "*$search*" } | Select-Object @{n="Name";e={"$($_.DisplayName) - $($_.InstallLocation)"}}, @{n="AppId";e={"$($_.InstallLocation)"}}\n'
                    '$results += Get-ChildItem "C:\\ProgramData\\Microsoft\\Windows\\Start Menu\\Programs" -Recurse -Filter "*$search*.lnk" -ErrorAction SilentlyContinue | Select-Object @{n="Name";e={"$($_.BaseName)"}}, @{n="AppId";e={"$($_.FullName)"}}\n'
                    '$results | ConvertTo-Json'
                )
                encoded = _b64.b64encode(ps_script.encode('utf-16-le')).decode()
                r = subprocess.run(
                    ["powershell", "-NoProfile", "-EncodedCommand", encoded],
                    capture_output=True, text=True, timeout=15
                )
                if r.stdout.strip():
                    data = _json.loads(r.stdout)
                    if isinstance(data, dict):
                        data = [data]
                    for d in data:
                        app_name = d.get("Name")
                        path = d.get("AppId", "")
                        if app_name:
                            results.append(f"{app_name}: {path}")
                paths = os.environ.get("PATH", "").split(os.pathsep)
                for p_dir in paths:
                    try:
                        for f in os.listdir(p_dir):
                            if search in f.lower() and f.lower().endswith(".exe"):
                                results.append(f"{f}: {os.path.join(p_dir, f)}")
                    except Exception:
                        pass
            elif is_macos():
                r = subprocess.run(
                    ["mdfind", f"kMDItemKind == 'Application' && kMDItemDisplayName == '*{search}*'"],
                    capture_output=True, text=True, timeout=15
                )
                results = [f"App: {l}" for l in r.stdout.strip().split('\n')[:10] if l.strip()]
            seen = set()
            unique = []
            for r in results:
                if r not in seen:
                    seen.add(r)
                    unique.append(r)
            if unique:
                return "Found:\n" + "\n".join(f"  {r}" for r in unique[:15])
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
            {"type": "function", "function": {"name": "start_process", "description": "Launch app or file", "parameters": {"type": "object", "properties": {"path": {"type": "string", "description": "Path"}}, "required": ["path"]}}},
            {"type": "function", "function": {"name": "take_screenshot", "description": "Take screenshot", "parameters": {"type": "object", "properties": {}}}},
            {"type": "function", "function": {"name": "get_clipboard", "description": "Clipboard text", "parameters": {"type": "object", "properties": {}}}},
            {"type": "function", "function": {"name": "set_clipboard", "description": "Copy text to clipboard", "parameters": {"type": "object", "properties": {"text": {"type": "string", "description": "Text"}}, "required": ["text"]}}},
            {"type": "function", "function": {"name": "get_volume", "description": "System volume level", "parameters": {"type": "object", "properties": {}}}},
            {"type": "function", "function": {"name": "set_volume", "description": "Set volume 0-100", "parameters": {"type": "object", "properties": {"level": {"type": "integer", "description": "0-100"}}, "required": ["level"]}}},
            {"type": "function", "function": {"name": "mute_volume", "description": "Toggle mute", "parameters": {"type": "object", "properties": {}}}},
            {"type": "function", "function": {"name": "media_play_pause", "description": "Toggle play/pause", "parameters": {"type": "object", "properties": {}}}},
            {"type": "function", "function": {"name": "media_next", "description": "Next track", "parameters": {"type": "object", "properties": {}}}},
            {"type": "function", "function": {"name": "media_prev", "description": "Previous track", "parameters": {"type": "object", "properties": {}}}},
            {"type": "function", "function": {"name": "list_wifi", "description": "WiFi profiles + passwords", "parameters": {"type": "object", "properties": {}}}},
            {"type": "function", "function": {"name": "wifi_status", "description": "Current WiFi status", "parameters": {"type": "object", "properties": {}}}},
            {"type": "function", "function": {"name": "list_windows", "description": "Open window titles", "parameters": {"type": "object", "properties": {}}}},
            {"type": "function", "function": {"name": "focus_window", "description": "Focus window by title", "parameters": {"type": "object", "properties": {"title": {"type": "string", "description": "Title"}}, "required": ["title"]}}},
            {"type": "function", "function": {"name": "lock_workstation", "description": "Lock workstation", "parameters": {"type": "object", "properties": {}}}},
            {"type": "function", "function": {"name": "get_installed_software", "description": "Installed software list", "parameters": {"type": "object", "properties": {}}}},
            {"type": "function", "function": {"name": "get_startup_programs", "description": "Startup programs list", "parameters": {"type": "object", "properties": {}}}},
            {"type": "function", "function": {"name": "get_services", "description": "Running services list", "parameters": {"type": "object", "properties": {}}}},
            {"type": "function", "function": {"name": "get_active_connections", "description": "Active network connections", "parameters": {"type": "object", "properties": {}}}},
            {"type": "function", "function": {"name": "explore_drives", "description": "List all drives/volumes with free space info", "parameters": {"type": "object", "properties": {}}}},
            {"type": "function", "function": {"name": "find_installed_app", "description": "Search for an installed app by name across registry, PATH, Program Files, and Start Menu", "parameters": {"type": "object", "properties": {"name": {"type": "string", "description": "App name to search for"}}, "required": ["name"]}}},
        ]

    def get_handler(self, name):
        handlers = {
            "get_cpu": self.get_cpu,
            "get_memory": self.get_memory,
            "get_disk": self.get_disk,
            "get_battery": self.get_battery,
            "get_network": self.get_network,
            "get_system_info": self.get_system_info,
            "get_system_uptime": self.get_system_uptime,
            "get_processes": self.get_processes,
            "kill_process": self.kill_process,
            "start_process": self.start_process,
            "take_screenshot": self.take_screenshot,
            "get_clipboard": self.get_clipboard,
            "set_clipboard": self.set_clipboard,
            "get_volume": self.get_volume,
            "set_volume": self.set_volume,
            "mute_volume": self.mute_volume,
            "media_play_pause": self.media_play_pause,
            "media_next": self.media_next,
            "media_prev": self.media_prev,
            "list_wifi": self.list_wifi,
            "wifi_status": self.wifi_status,
            "list_windows": self.list_windows,
            "focus_window": self.focus_window,
            "lock_workstation": self.lock_workstation,
            "get_installed_software": self.get_installed_software,
            "get_startup_programs": self.get_startup_programs,
            "get_services": self.get_services,
            "get_active_connections": self.get_active_connections,
            "explore_drives": self.explore_drives,
            "find_installed_app": self.find_installed_app,
        }
        return handlers.get(name)
