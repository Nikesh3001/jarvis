import os
import json
import subprocess
import socket
from datetime import datetime
from core.platform_utils import is_windows, is_macos, is_linux


class SecurityTool:
    def __init__(self):
        self._psutil = None

    @property
    def psutil(self):
        if self._psutil is None:
            import psutil as _p
            self._psutil = _p
        return self._psutil

    def check_firewall(self):
        try:
            if is_windows():
                r = subprocess.run(
                    ["powershell", "-NoProfile", "-Command",
                     "Get-NetFirewallProfile | Select-Object Name, Enabled | ConvertTo-Json"],
                    capture_output=True, text=True, timeout=15
                )
                data = json.loads(r.stdout)
                if isinstance(data, dict):
                    data = [data]
                lines = []
                for p in data:
                    status = "ON" if p.get("Enabled") else "OFF"
                    lines.append(f"  {p['Name']}: {status}")
                return "Firewall status:\n" + "\n".join(lines)
            elif is_macos():
                r = subprocess.run(["/usr/libexec/ApplicationFirewall/socketfilterfw", "--getglobalstate"],
                    capture_output=True, text=True, timeout=10)
                return f"Firewall: {r.stdout.strip()}" if r.stdout else "Firewall status unknown"
            else:
                r = subprocess.run(["ufw", "status"], capture_output=True, text=True, timeout=10)
                if r.returncode == 0:
                    return f"Firewall:\n{r.stdout.strip()[:500]}"
                r2 = subprocess.run(["iptables", "-L", "-n"], capture_output=True, text=True, timeout=10)
                if r2.returncode == 0:
                    chains = [l for l in r2.stdout.split('\n') if l.startswith('Chain')]
                    return f"Firewall chains ({len(chains)}): {', '.join(chains)[:500]}"
                return "Firewall check unavailable"
        except Exception:
            return "Firewall check failed"

    def check_open_ports(self, common_only=True):
        try:
            if common_only:
                ports = [21, 22, 23, 25, 53, 80, 110, 135, 139, 143, 443, 445, 993, 995, 1433, 1521, 3306, 3389, 5432, 6379, 8080, 8443, 27017]
            else:
                ports = range(1, 1024)
            open_ports = []
            for port in ports:
                try:
                    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    sock.settimeout(0.5)
                    result = sock.connect_ex(("127.0.0.1", port))
                    sock.close()
                    if result == 0:
                        try:
                            service = socket.getservbyport(port)
                        except Exception:
                            service = "unknown"
                        open_ports.append(f"{port}/{service}")
                except Exception:
                    pass
            if open_ports:
                return f"Open ports on localhost: {', '.join(open_ports[:20])}"
            return "No common open ports detected on localhost."
        except Exception:
            return "Port scan error"

    def check_listeners(self):
        try:
            connections = self.psutil.net_connections()
            listeners = [c for c in connections if c.status == "LISTEN"]
            if not listeners:
                return "No listening services found."
            seen = set()
            lines = []
            for c in listeners:
                key = f"{c.laddr.port}"
                if key not in seen:
                    seen.add(key)
                    try:
                        proc = self.psutil.Process(c.pid) if c.pid else None
                        name = proc.name() if proc else "unknown"
                    except Exception:
                        name = "unknown"
                    lines.append(f"  Port {c.laddr.port} ({name})")
            return "Listening services:\n" + "\n".join(sorted(lines)[:20])
        except Exception:
            return "Listener check failed"

    def check_security_updates(self):
        try:
            if is_windows():
                r = subprocess.run(
                    ["powershell", "-NoProfile", "-Command",
                     "Get-HotFix | Sort-Object InstalledOn -Descending | Select-Object -First 10 HotFixID, InstalledOn, Description | ConvertTo-Json"],
                    capture_output=True, text=True, timeout=30
                )
                data = json.loads(r.stdout)
                if isinstance(data, dict):
                    data = [data]
                if not data:
                    return "No security update history found."
                lines = ["Recent security updates:"]
                for u in data[:10]:
                    hid = u.get("HotFixID", "?")
                    date = u.get("InstalledOn", "?")
                    desc = u.get("Description", "?")
                    lines.append(f"  {hid} ({date}) — {desc}")
                return "\n".join(lines)
            elif is_macos():
                r = subprocess.run(["softwareupdate", "--list"], capture_output=True, text=True, timeout=60)
                if "No new software available" in r.stdout:
                    return "System is up to date."
                updates = [l.strip() for l in r.stdout.split('\n') if 'recommended' in l.lower() or 'Label' in l]
                return "Available updates:\n" + "\n".join(updates[:10]) if updates else "Could not check updates"
            else:
                r = subprocess.run(["apt", "list", "--upgradable"], capture_output=True, text=True, timeout=30)
                if r.returncode == 0:
                    pkgs = [l.split('/')[0] for l in r.stdout.strip().split('\n')[1:] if l.strip()][:15]
                    if pkgs:
                        return f"Available updates ({len(pkgs)}): {', '.join(pkgs)}"
                    return "System is up to date."
                r2 = subprocess.run(["dnf", "check-update"], capture_output=True, text=True, timeout=30)
                if r2.returncode in (0, 100):
                    pkgs = [l.split()[0] for l in r2.stdout.strip().split('\n') if l.strip() and '.' in l][:15]
                    return f"Available updates ({len(pkgs)}): {', '.join(pkgs)}" if pkgs else "System is up to date."
                return "Update check unavailable (install apt or dnf)"
        except Exception:
            return "Update check failed"

    def check_running_services(self):
        try:
            if is_windows():
                svcs = []
                for s in self.psutil.win_service_iter():
                    try:
                        if s.status() == "running":
                            svcs.append(s.name())
                    except Exception:
                        pass
                total = len(svcs)
                return f"Running services: {total}. Key services: {', '.join(sorted(svcs)[:15])}"
            elif is_macos():
                r = subprocess.run(["launchctl", "list"], capture_output=True, text=True, timeout=10)
                lines = [l for l in r.stdout.strip().split('\n') if l.strip()][:20]
                return f"LaunchAgents ({len(lines)}): {', '.join(lines[:15])}"
            else:
                r = subprocess.run(["systemctl", "list-units", "--type=service", "--state=running", "--no-pager"],
                    capture_output=True, text=True, timeout=15)
                lines = [l.split()[0] for l in r.stdout.split('\n')[1:] if l.strip() and '.service' in l][:15]
                return f"Running services ({len(lines)}): {', '.join(lines)}"
        except Exception:
            return "Services check failed"

    def security_best_practices(self):
        try:
            practices = []
            firewall = self.check_firewall()
            if "ON" in firewall or "enabled" in firewall.lower() or "active" in firewall.lower():
                practices.append("+ Firewall is enabled")
            else:
                practices.append("- Firewall may be disabled")

            listeners = self.check_listeners()
            listen_count = len([l for l in listeners.split("\n") if l.strip().startswith("  Port")])
            if listen_count > 20:
                practices.append(f"! {listen_count} listening services -- review for unnecessary services")
            else:
                practices.append(f"+ {listen_count} listening services -- within normal range")

            mem = self.psutil.virtual_memory()
            if mem.percent > 90:
                practices.append("! High memory usage -- close unused applications")
            else:
                practices.append(f"+ Memory usage at {mem.percent}%")

            for part in self.psutil.disk_partitions():
                try:
                    usage = self.psutil.disk_usage(part.mountpoint)
                    if usage.percent > 95:
                        practices.append(f"! {part.mountpoint} disk nearly full ({usage.percent}%)")
                except Exception:
                    pass

            os_name = "macOS" if is_macos() else "Linux" if is_linux() else "Windows"
            practices.append(f"* Keep {os_name} updated for security patches")
            practices.append("* Use strong, unique passwords and a password manager")
            if is_windows():
                practices.append("* Enable BitLocker for disk encryption")
            elif is_macos():
                practices.append("* Enable FileVault for disk encryption")
            else:
                practices.append("* Enable LUKS/dm-crypt for disk encryption")
            practices.append("* Review startup/login items regularly")

            return "Security Best Practices:\n" + "\n".join(practices)
        except Exception:
            return "Security check failed"

    def get_tool_definitions(self):
        return [
            {"type": "function", "function": {"name": "check_firewall", "description": "Firewall profile status", "parameters": {"type": "object", "properties": {}}}},
            {"type": "function", "function": {"name": "check_open_ports", "description": "Scan open TCP ports", "parameters": {"type": "object", "properties": {"common_only": {"type": "boolean", "description": "Common only", "default": True}}}}},
            {"type": "function", "function": {"name": "check_listeners", "description": "Listening services", "parameters": {"type": "object", "properties": {}}}},
            {"type": "function", "function": {"name": "check_security_updates", "description": "Recent Windows updates", "parameters": {"type": "object", "properties": {}}}},
            {"type": "function", "function": {"name": "security_best_practices", "description": "Security assessment", "parameters": {"type": "object", "properties": {}}}},
        ]

    def get_handler(self, name):
        handlers = {
            "check_firewall": self.check_firewall,
            "check_open_ports": self.check_open_ports,
            "check_listeners": self.check_listeners,
            "check_security_updates": self.check_security_updates,
            "security_best_practices": self.security_best_practices,
        }
        return handlers.get(name)
