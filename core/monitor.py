import os
import sys
import time
import threading
import datetime
import subprocess
from core.platform_utils import is_windows, is_macos, is_linux


class ProactiveMonitor:
    def __init__(self, assistant):
        self.assistant = assistant
        self.running = False
        self.thread = None
        self.interval = 30
        self.last_suggestion_time = 0
        self.suggestion_cooldown = 300
        self.event_log = []
        self.max_events = 100
        try:
            import psutil as _p
            self._psutil = _p
        except ImportError:
            self._psutil = None

    def start(self):
        if self.running:
            return
        self.running = True
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()
        print("[MONITOR] Proactive monitoring started")

    def stop(self):
        self.running = False
        if hasattr(self, '_stop_event'):
            self._stop_event.set()

    def _run(self):
        if not hasattr(self, '_stop_event'):
            self._stop_event = threading.Event()
        while self.running:
            try:
                self._check_resources()
                self._check_idle_suggestions()
            except Exception:
                pass
            self._stop_event.wait(timeout=self.interval)
            if not self.running:
                return

    def _check_resources(self):
        try:
            mem = self._psutil.virtual_memory()
            if mem.percent > 90:
                self._log_event("HIGH_MEMORY", f"RAM at {mem.percent}%")
            cpu = self._psutil.cpu_percent(interval=0)
            if cpu > 90:
                self._log_event("HIGH_CPU", f"CPU at {cpu}%")
            for part in self._psutil.disk_partitions():
                if 'network' in part.opts or part.fstype in ('cifs', 'nfs', 'autofs', 'smb'):
                    continue
                try:
                    usage = self._psutil.disk_usage(part.mountpoint)
                    if usage.percent > 95:
                        self._log_event("LOW_DISK", f"{part.mountpoint} at {usage.percent}%")
                except Exception:
                    pass
        except Exception:
            pass

    def _get_idle_secs(self):
        try:
            if is_windows():
                import ctypes
                class LASTINPUTINFO(ctypes.Structure):
                    _fields_ = [("cbSize", ctypes.c_uint), ("dwTime", ctypes.c_uint)]
                lii = LASTINPUTINFO()
                lii.cbSize = ctypes.sizeof(LASTINPUTINFO)
                ctypes.windll.user32.GetLastInputInfo(ctypes.byref(lii))
                return (ctypes.windll.kernel32.GetTickCount() - lii.dwTime) // 1000
            elif is_macos():
                r = subprocess.run(["ioreg", "-c", "IOHIDSystem"],
                    capture_output=True, text=True, timeout=5)
                for line in r.stdout.split('\n'):
                    if "HIDIdleTime" in line:
                        ns = int(line.split('=')[1].strip().strip('"'))
                        return int(ns / 1000000000)
                return 0
            else:
                r = subprocess.run(["xprintidle"], capture_output=True, text=True, timeout=5)
                if r.returncode == 0:
                    return int(r.stdout.strip()) // 1000
                r2 = subprocess.run(["loginctl", "show-session", "-p", "IdleHint"],
                    capture_output=True, text=True, timeout=5)
                return 0
        except Exception:
            return 0

    def _check_idle_suggestions(self):
        now = time.time()
        if now - self.last_suggestion_time < self.suggestion_cooldown:
            return
        try:
            idle_secs = self._get_idle_secs()
            if idle_secs > 1800:
                print(f"[MONITOR] System idle for {idle_secs // 60} minutes")
                self.last_suggestion_time = now
        except Exception:
            pass

    def _log_event(self, event_type, message):
        entry = {
            "time": datetime.datetime.now().isoformat(),
            "type": event_type,
            "message": message,
        }
        self.event_log.append(entry)
        if len(self.event_log) > self.max_events:
            self.event_log.pop(0)
        print(f"[MONITOR] {event_type}: {message}")

    def get_events(self, count=10):
        if not self.event_log:
            return "No events recorded."
        lines = [f"{e['time']} [{e['type']}] {e['message']}" for e in self.event_log[-count:]]
        return "Recent system events:\n" + "\n".join(lines)

    def get_status(self):
        try:
            mem = self._psutil.virtual_memory()
            cpu = self._psutil.cpu_percent(interval=0)
            uptime_secs = int(time.time() - self.psutil.boot_time())
            days, rem = divmod(uptime_secs, 86400)
            hours, rem = divmod(rem, 3600)
            mins = rem // 60
            return (f"Monitor status: running={self.running}, "
                    f"CPU={cpu}%, RAM={mem.percent}%, "
                    f"Uptime={days}d {hours}h {mins}m, "
                    f"Events tracked={len(self.event_log)}")
        except Exception as e:
            return f"Monitor status error: {e}"
