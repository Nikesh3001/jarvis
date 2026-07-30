"""
Comprehensive security tools inspired by CAI (Cybersecurity AI) framework.
Provides network scanning, Shodan, DNS/WHOIS, SSL analysis, SSH, packet capture,
hashing, and web security analysis using established Python libraries.

Capabilities mapped from CAI:
  - Reconnaissance: port scanning, Shodan search, DNS/WHOIS, subdomain enum
  - Network: packet capture, traceroute, banner grabbing
  - Web Security: HTTP header analysis, SSL/TLS checks
  - Forensics: file hashing, hash identification
  - SSH/Remote: command execution via paramiko
"""

import hashlib
import json
import os
import re
import shutil
import socket
import ssl
import struct
import subprocess
import tempfile
import time
from datetime import datetime
from urllib.parse import urlparse

from core.platform_utils import is_windows, is_macos, is_linux
from core.ratelimit import check_rate


class SecurityTool:
    def __init__(self):
        self._psutil = None
        self._nmap = None
        self._paramiko = None
        self._httpx = None
        self._dns_resolver = None
        self._whois = None
        self.safe_mode = True

    # ── Lazy imports ──────────────────────────────────────────────────

    @property
    def psutil(self):
        if self._psutil is None:
            import psutil as _p
            self._psutil = _p
        return self._psutil

    def _get_nmap(self):
        if self._nmap is None:
            try:
                import nmap
                self._nmap = nmap.PortScanner()
            except Exception:
                # nmap.PortScanner() raises PortScannerError when binary missing
                self._nmap = None
                return None
        return self._nmap

    def _get_paramiko(self):
        if self._paramiko is None:
            try:
                import paramiko
                self._paramiko = paramiko
            except ImportError:
                return None
        return self._paramiko

    def _get_httpx(self):
        if self._httpx is None:
            try:
                import httpx
                self._httpx = httpx
            except ImportError:
                return None
        return self._httpx

    def _get_dns_resolver(self):
        if self._dns_resolver is None:
            try:
                import dns.resolver
                self._dns_resolver = dns.resolver
            except ImportError:
                return None
        return self._dns_resolver

    def _get_whois(self):
        if self._whois is None:
            try:
                import whois
                self._whois = whois
            except ImportError:
                return None
        return self._whois

    def _find_tool(self, tool):
        """Find a tool on PATH or in WSL."""
        if shutil.which(tool):
            return [tool]
        try:
            if self._in_wsl(tool):
                return ["wsl", "--", tool]
        except Exception:
            pass
        return None

    def _in_wsl(self, tool):
        rc = subprocess.call(["wsl", "--", "which", tool],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=10)
        return rc == 0

    def _run_cmd(self, cmd, timeout=30):
        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=timeout
            )
            return result.stdout.strip(), result.stderr.strip(), result.returncode
        except FileNotFoundError:
            return "", "Command not found", 1
        except subprocess.TimeoutExpired:
            return "", "Command timed out", 1
        except Exception as e:
            return "", str(e), 1

    # ── Existing tools (preserved) ────────────────────────────────────

    def check_firewall(self):
        from core.platform_utils import get_firewall_status
        try:
            status = get_firewall_status()
            if status and status != "Firewall status unavailable":
                return f"Firewall: {status}"
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
                    status2 = "ON" if p.get("Enabled") else "OFF"
                    lines.append(f"  {p['Name']}: {status2}")
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

    def check_open_ports(self, target="127.0.0.1", common_only=True):
        if not check_rate("port_scan", rate=0.05, burst=1):
            return "Rate limit exceeded. Port scans are rate-limited."
        try:
            from core.ssrf import is_ssrf_blocked
            # Allow loopback for local scanning (pentest tool)
            is_loopback = target in ('localhost', '127.0.0.1', '::1', '0.0.0.0')
            if not is_loopback:
                try:
                    import ipaddress
                    is_loopback = ipaddress.ip_address(target).is_loopback
                except (ValueError, TypeError):
                    pass
            if not is_loopback and is_ssrf_blocked(target):
                return "Blocked: cannot scan internal/private addresses (use nmap_scan for authorized pentests)"
            if common_only:
                ports = [21, 22, 23, 25, 53, 80, 110, 135, 139, 143, 443, 445,
                         993, 995, 1433, 1521, 3306, 3389, 5432, 6379, 8080, 8443, 27017]
                open_ports = []
            else:
                return "Full port scan disabled for performance. Use common_only=True (default)."
            for port in ports:
                try:
                    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    sock.settimeout(0.5)
                    result = sock.connect_ex((target, port))
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
                return f"Open ports on {target}: {', '.join(open_ports[:20])}"
            return f"No common open ports detected on {target}."
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
        from core.platform_utils import get_security_updates
        try:
            updates = get_security_updates()
            if updates:
                return "Recent security updates:\n" + "\n".join(f"  {u}" for u in updates)
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
                return "Update check unavailable"
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

    # ── Reconnaissance: Nmap Scanning ─────────────────────────────────

    def nmap_scan(self, target, ports=None, scan_type="quick"):
        """Scan a target using nmap. Requires nmap binary installed on the system."""
        if not check_rate("nmap_scan", rate=0.1, burst=1):
            return "Rate limit exceeded. Nmap scans are rate-limited for safety."

        nm = self._get_nmap()
        if nm is None:
            # Fallback: direct subprocess call
            return self._nmap_subprocess(target, ports, scan_type)

        try:
            args = {
                "quick": "-sV -T4",
                "full": "-sV -sC -O -T4",
                "stealth": "-sS -T2",
                "udp": "-sU -T4",
                "version": "-sV",
            }.get(scan_type, "-sV -T4")

            if ports:
                args += f" -p {ports}"

            nm.scan(target, arguments=args)

            if not nm.all_hosts():
                return f"No hosts found for {target}."

            lines = [f"🔍 Nmap scan: {target} ({scan_type})\n"]
            for host in nm.all_hosts():
                state = nm[host].state()
                lines.append(f"Host: {host} ({state})")
                for proto in nm[host].all_protocols():
                    lines.append(f"  Protocol: {proto}")
                    ports_dict = nm[host][proto]
                    for port in sorted(ports_dict.keys()):
                        port_info = ports_dict[port]
                        service = port_info.get("name", "unknown")
                        version = port_info.get("version", "")
                        product = port_info.get("product", "")
                        state_str = port_info.get("state", "unknown")
                        svc_str = f"{product} {version}".strip()
                        lines.append(f"    {port}/{proto} {state_str} - {service} {svc_str}")
                if "osmatch" in nm[host]:
                    for os_match in nm[host]["osmatch"][:2]:
                        lines.append(f"  OS: {os_match.get('name', 'unknown')} ({os_match.get('accuracy', '?')}%)")

            result = "\n".join(lines)
            if len(result) > 4000:
                result = result[:4000] + "\n...[truncated]"
            return result
        except Exception as e:
            return f"Nmap scan error: {e}"

    @staticmethod
    def _find_nmap():
        from core.platform_utils import get_nmap_path
        found = get_nmap_path()
        if found:
            return found
        try:
            if subprocess.call(["wsl", "--", "which", "nmap"],
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=10) == 0:
                return "nmap_wsl"
        except Exception:
            pass
        return None

    def _nmap_subprocess(self, target, ports, scan_type):
        """Fallback nmap via subprocess."""
        nmap_path = self._find_nmap()
        if not nmap_path:
            return (
                "nmap is not installed or not in PATH.\n"
                "  Install:\n"
                "    Windows: https://nmap.org/download.html\n"
                "    Linux:   sudo apt install nmap\n"
                "    macOS:   brew install nmap"
            )

        if nmap_path == "nmap_wsl":
            args = ["wsl", "--", "nmap"]
        else:
            args = [nmap_path]
        if scan_type == "quick":
            args.extend(["-sV", "-T4"])
        elif scan_type == "full":
            args.extend(["-sV", "-sC", "-O", "-T4"])
        elif scan_type == "stealth":
            args.extend(["-sS", "-T2"])
        elif scan_type == "udp":
            args.extend(["-sU", "-T4"])
        else:
            args.extend(["-sV", "-T4"])

        if ports:
            args.extend(["-p", str(ports)])

        args.append(target)

        stdout, stderr, rc = self._run_cmd(args, timeout=120)
        if rc != 0 and not stdout:
            return f"Nmap failed: {stderr[:300]}"
        output = stdout[:4000] if stdout else "No output"
        return f"🔍 Nmap scan: {target}\n\n{output}"

    # ── Reconnaissance: Shodan ────────────────────────────────────────

    def shodan_search(self, query, max_results=5):
        """Search Shodan for internet-connected devices."""
        api_key = os.environ.get("SHODAN_API_KEY")
        if not api_key:
            return ("Shodan requires an API key. Get a free one at https://account.shodan.io/\n"
                    "Then set: $env:SHODAN_API_KEY=\"your-key\" (PowerShell) or export SHODAN_API_KEY=... (Linux/Mac)")

        try:
            httpx = self._get_httpx()
            if httpx is None:
                return "httpx not installed. Install: pip install httpx"

            url = f"https://api.shodan.io/shodan/host/search?key={api_key}&query={query}&page=1"
            response = httpx.get(url, timeout=15)
            data = response.json()

            matches = data.get("matches", [])
            total = data.get("total", 0)

            if not matches:
                return f"No Shodan results for \"{query}\". Total matches: {total}"

            lines = [f"🔍 Shodan search: \"{query}\" (total: {total})\n"]
            for i, match in enumerate(matches[:max_results]):
                ip = match.get("ip_str", "N/A")
                port = match.get("port", "?")
                org = match.get("org", "N/A")
                hostnames = match.get("hostnames", [])
                country = match.get("location", {}).get("country_name", "N/A")
                product = match.get("product", "N/A")
                banner = (match.get("data", "") or "")[:100]
                vulns = match.get("vulns", [])

                lines.append(f"  {i+1}. {ip}:{port}")
                lines.append(f"     Org: {org} | Country: {country}")
                lines.append(f"     Product: {product}")
                if hostnames:
                    lines.append(f"     Hostnames: {', '.join(hostnames[:3])}")
                if vulns:
                    lines.append(f"     ⚠️  Vulns: {', '.join(vulns[:5])}")
                if banner:
                    lines.append(f"     Banner: {banner}")
                lines.append("")

            return "\n".join(lines)
        except Exception as e:
            return f"Shodan search error: {e}"

    def shodan_host_info(self, ip):
        """Get detailed Shodan info for a specific IP."""
        api_key = os.environ.get("SHODAN_API_KEY")
        if not api_key:
            return ("Shodan requires an API key. Set: $env:SHODAN_API_KEY=\"your-key\"")

        try:
            httpx = self._get_httpx()
            if httpx is None:
                return "httpx not installed. Install: pip install httpx"

            url = f"https://api.shodan.io/shodan/host/{ip}?key={api_key}"
            response = httpx.get(url, timeout=15)
            if response.status_code == 404:
                return f"No Shodan data found for {ip}."
            data = response.json()

            lines = [f"📡 Shodan host: {ip}\n"]
            lines.append(f"  Organization: {data.get('org', 'N/A')}")
            lines.append(f"  OS: {data.get('os', 'N/A')}")
            lines.append(f"  ISP: {data.get('isp', 'N/A')}")

            ports = data.get("ports", [])
            if ports:
                lines.append(f"  Open ports: {', '.join(str(p) for p in ports)}")

            vulns = data.get("vulns", [])
            if vulns:
                lines.append(f"  ⚠️  Known CVEs: {', '.join(vulns[:10])}")

            hostnames = data.get("hostnames", [])
            if hostnames:
                lines.append(f"  Hostnames: {', '.join(hostnames[:5])}")

            for service in data.get("data", [])[:5]:
                port = service.get("port", "?")
                product = service.get("product", "N/A")
                transport = service.get("transport", "tcp")
                lines.append(f"\n  Port {port}/{transport}: {product}")
                banner = (service.get("data", "") or "")[:200]
                if banner:
                    lines.append(f"    Banner: {banner}")

            return "\n".join(lines)
        except Exception as e:
            return f"Shodan host info error: {e}"

    # ── Reconnaissance: DNS ───────────────────────────────────────────

    def dns_lookup(self, domain):
        """Perform DNS record lookup for a domain."""
        if not check_rate("dns_lookup", rate=1, burst=5):
            return "Rate limit exceeded."
        resolver = self._get_dns_resolver()
        if resolver is None:
            return "dnspython not installed. Install: pip install dnspython"

        record_types = ["A", "AAAA", "MX", "NS", "TXT", "CNAME", "SOA"]
        lines = [f"🌐 DNS records for {domain}:\n"]

        for rtype in record_types:
            try:
                answers = resolver.resolve(domain, rtype)
                for rdata in answers:
                    if rtype == "MX":
                        lines.append(f"  {rtype}: {rdata.exchange} (priority {rdata.preference})")
                    elif rtype == "SOA":
                        lines.append(f"  {rtype}: {rdata.mname} admin={rdata.rname}")
                    else:
                        lines.append(f"  {rtype}: {rdata.to_text()}")
            except (resolver.NoAnswer, resolver.NXDOMAIN):
                pass
            except Exception:
                pass

        if len(lines) == 1:
            return f"No DNS records found for {domain}."
        return "\n".join(lines)

    def subdomain_enum(self, domain):
        """Enumerate subdomains using DNS brute force with common subdomain names."""
        if not check_rate("subdomain_enum", rate=0.2, burst=2):
            return "Rate limit exceeded."
        resolver = self._get_dns_resolver()
        if resolver is None:
            return "dnspython not installed. Install: pip install dnspython"

        common_subdomains = [
            "www", "mail", "ftp", "localhost", "webmail", "smtp", "pop", "ns1", "ns2",
            "ns3", "dns", "dns1", "dns2", "mx", "mx1", "mx2", "gateway", "router",
            "admin", "test", "dev", "staging", "api", "app", "beta", "demo", "stage",
            "portal", "vpn", "remote", "blog", "shop", "store", "cdn", "media",
            "static", "assets", "img", "images", "support", "help", "docs", "wiki",
            "git", "gitlab", "jenkins", "ci", "cd", "monitor", "grafana", "kibana",
            "db", "mysql", "postgres", "redis", "mongo", "elastic", "search",
            "backup", "bak", "old", "new", "v2", "v3", "internal", "intranet",
            "corp", "office", "hr", "crm", "erp", "login", "sso", "auth",
        ]

        found = []
        lines = [f"🔍 Subdomain enumeration for {domain}:\n"]

        for sub in common_subdomains:
            fqdn = f"{sub}.{domain}"
            try:
                answers = resolver.resolve(fqdn, "A")
                ips = [str(rdata) for rdata in answers]
                found.append((fqdn, ips))
                lines.append(f"  ✅ {fqdn} → {', '.join(ips)}")
            except (resolver.NoAnswer, resolver.NXDOMAIN, resolver.NoNameservers):
                pass
            except Exception:
                pass

        if not found:
            return f"No subdomains found for {domain} (tested {len(common_subdomains)} names)."

        lines.insert(1, f"  Found {len(found)} subdomains:\n")
        return "\n".join(lines)

    # ── Reconnaissance: WHOIS ─────────────────────────────────────────

    def whois_lookup(self, domain):
        """Perform WHOIS lookup for domain/IP registration info."""
        if not check_rate("whois_lookup", rate=0.5, burst=3):
            return "Rate limit exceeded."
        whois_lib = self._get_whois()
        if whois_lib is None:
            # Fallback: subprocess whois
            stdout, stderr, rc = self._run_cmd(["whois", domain], timeout=15)
            if rc == 0 and stdout:
                output = stdout[:3000]
                return f"📋 WHOIS: {domain}\n\n{output}"
            return "whois not available. Install: pip install python-whois or apt install whois"

        try:
            w = whois.whois(domain)
            lines = [f"📋 WHOIS: {domain}\n"]

            if w.domain_name:
                lines.append(f"  Domain: {w.domain_name}")
            if w.registrar:
                lines.append(f"  Registrar: {w.registrar}")
            if w.creation_date:
                dates = w.creation_date if isinstance(w.creation_date, list) else [w.creation_date]
                lines.append(f"  Created: {dates[0]}")
            if w.expiration_date:
                dates = w.expiration_date if isinstance(w.expiration_date, list) else [w.expiration_date]
                lines.append(f"  Expires: {dates[0]}")
            if w.name_servers:
                ns = w.name_servers if isinstance(w.name_servers, list) else [w.name_servers]
                lines.append(f"  Name servers: {', '.join(str(n) for n in ns[:4])}")
            if w.org:
                lines.append(f"  Organization: {w.org}")
            if w.country:
                lines.append(f"  Country: {w.country}")
            if w.emails:
                emails = w.emails if isinstance(w.emails, list) else [w.emails]
                lines.append(f"  Emails: {', '.join(str(e) for e in emails[:3])}")

            return "\n".join(lines)
        except Exception as e:
            return f"WHOIS error: {e}"

    # ── Network: Banner Grabbing ──────────────────────────────────────

    def banner_grab(self, host, port, timeout=5):
        """Grab service banner from a host:port."""
        if not check_rate("banner_grab", rate=0.5, burst=3):
            return "Rate limit exceeded."
        try:
            from core.ssrf import is_ssrf_blocked
            if is_ssrf_blocked(host):
                return "Blocked: cannot grab banners from internal/private addresses"
            try:
                port = int(port)
            except (ValueError, TypeError):
                return f"Invalid port: {port}"
            if port < 1 or port > 65535:
                return "Invalid port: must be 1-65535"
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(timeout)
            sock.connect((host, port))
            # Try to receive data (some services send a banner)
            try:
                banner = sock.recv(1024).decode("utf-8", errors="replace").strip()
            except socket.timeout:
                banner = "(no banner received)"
            sock.close()

            if banner:
                return f"📡 Banner {host}:{port}\n  {banner[:500]}"
            return f"📡 Banner {host}:{port}\n  (no banner received — service may require a request)"
        except Exception as e:
            return f"Banner grab error: {e}"

    # ── Network: Traceroute ───────────────────────────────────────────

    def traceroute(self, target, max_hops=15):
        """Perform traceroute to a target."""
        try:
            import re as _re
            if not _re.match(r'^[a-zA-Z0-9.\-:]+$', target):
                return "Invalid target format"
            if is_windows():
                stdout, stderr, rc = self._run_cmd(
                    ["tracert", "-d", "-h", str(max_hops), target], timeout=60
                )
            else:
                stdout, stderr, rc = self._run_cmd(
                    ["traceroute", "-n", "-m", str(max_hops), target], timeout=60
                )

            if rc == 0 and stdout:
                return f"🗺️ Traceroute to {target}:\n\n{stdout[:2000]}"
            elif stderr:
                return f"Traceroute error: {stderr[:300]}"
            return "Traceroute unavailable"
        except Exception:
            return "Traceroute failed"

    # ── Web Security: HTTP Headers ────────────────────────────────────

    def web_headers_check(self, url):
        """Analyze HTTP security headers of a website."""
        try:
            if not url.startswith(("http://", "https://")):
                url = "https://" + url

            from core.ssrf import validate_url
            url = validate_url(url)

            httpx = self._get_httpx()
            if httpx is None:
                return "httpx not installed. Install: pip install httpx"

            with httpx.Client(follow_redirects=True, timeout=15,
                                  headers={"User-Agent": "Mozilla/5.0"}) as client:
                response = client.get(url)
                headers = dict(response.headers)

            lines = [f"🔒 HTTP Security Headers: {url}\n"]
            lines.append(f"  Status: {response.status_code}\n")

            # Check security headers
            security_headers = {
                "strict-transport-security": ("HSTS", "Protects against protocol downgrade attacks"),
                "content-security-policy": ("CSP", "Prevents XSS and injection attacks"),
                "x-frame-options": ("X-Frame-Options", "Prevents clickjacking"),
                "x-content-type-options": ("X-Content-Type-Options", "Prevents MIME sniffing"),
                "x-xss-protection": ("X-XSS-Protection", "Legacy XSS filter"),
                "referrer-policy": ("Referrer-Policy", "Controls referrer information leakage"),
                "permissions-policy": ("Permissions-Policy", "Controls browser features"),
                "cross-origin-opener-policy": ("COOP", "Cross-origin isolation"),
                "cross-origin-resource-policy": ("CORP", "Cross-origin resource policy"),
            }

            found = []
            missing = []
            for header, (name, desc) in security_headers.items():
                if header in headers:
                    found.append(f"  ✅ {name}: {headers[header][:100]}")
                else:
                    missing.append(f"  ❌ {name} — {desc}")

            if found:
                lines.extend(found)
            if missing:
                lines.append(f"\n  Missing ({len(missing)}):")
                lines.extend(missing)

            # Show all headers
            lines.append(f"\n  All headers ({len(headers)}):")
            for k, v in sorted(headers.items()):
                lines.append(f"    {k}: {v[:80]}")

            return "\n".join(lines)
        except Exception as e:
            return f"Header check error: {e}"

    # ── Web Security: SSL/TLS Check ───────────────────────────────────

    def ssl_check(self, host, port=443):
        """Check SSL/TLS certificate details for a host."""
        try:
            from core.ssrf import is_ssrf_blocked
            if is_ssrf_blocked(host):
                return "Blocked: cannot check SSL for internal/private addresses"

            context = ssl.create_default_context()
            with socket.create_connection((host, int(port)), timeout=10) as sock:
                with context.wrap_socket(sock, server_hostname=host) as ssock:
                    cert = ssock.getpeercert()
                    cipher = ssock.cipher()
                    version = ssock.version()

            lines = [f"🔒 SSL/TLS Certificate: {host}:{port}\n"]

            subject = dict(x[0] for x in cert.get("subject", []))
            issuer = dict(x[0] for x in cert.get("issuer", []))

            lines.append(f"  Subject: {subject.get('commonName', 'N/A')}")
            lines.append(f"  Organization: {subject.get('organizationName', 'N/A')}")
            lines.append(f"  Issuer: {issuer.get('organizationName', 'N/A')} ({issuer.get('commonName', 'N/A')})")

            not_before = cert.get("notBefore", "N/A")
            not_after = cert.get("notAfter", "N/A")
            lines.append(f"  Valid from: {not_before}")
            lines.append(f"  Valid until: {not_after}")

            # Check expiry
            try:
                from email.utils import parsedate_to_datetime
                expiry = parsedate_to_datetime(not_after)
                days_left = (expiry - datetime.now(expiry.tzinfo)).days
                if days_left < 0:
                    lines.append(f"  ⚠️  EXPIRED {abs(days_left)} days ago!")
                elif days_left < 30:
                    lines.append(f"  ⚠️  Expiring in {days_left} days!")
                else:
                    lines.append(f"  ✅ Valid for {days_left} more days")
            except Exception:
                pass

            san = cert.get("subjectAltName", [])
            if san:
                dns_names = [v for t, v in san if t == "DNS"]
                ip_addrs = [v for t, v in san if t == "IP Address"]
                if dns_names:
                    lines.append(f"  SAN DNS: {', '.join(dns_names[:5])}")
                if ip_addrs:
                    lines.append(f"  SAN IP: {', '.join(ip_addrs[:3])}")

            if cipher:
                lines.append(f"  Cipher: {cipher[0]} ({cipher[1]}-{cipher[2]})")
            if version:
                lines.append(f"  TLS Version: {version}")

            return "\n".join(lines)
        except Exception as e:
            return f"SSL check error: {e}"

    # ── Forensics: File Hashing ───────────────────────────────────────

    def hash_file(self, file_path, algorithms=None):
        """Calculate file hashes using multiple algorithms."""
        if not os.path.exists(file_path):
            return f"File not found: {file_path}"

        if algorithms is None:
            algorithms = ["md5", "sha1", "sha256"]

        try:
            hashes = {}
            for algo in algorithms:
                h = hashlib.new(algo)
                with open(file_path, "rb") as f:
                    for chunk in iter(lambda: f.read(8192), b""):
                        h.update(chunk)
                hashes[algo] = h.hexdigest()

            size = os.path.getsize(file_path)
            lines = [f"🔐 File hashes: {os.path.basename(file_path)}"]
            lines.append(f"  Size: {size:,} bytes ({size/1024:.1f} KB)\n")
            for algo, digest in hashes.items():
                lines.append(f"  {algo.upper()}: {digest}")

            return "\n".join(lines)
        except Exception as e:
            return f"Hash error: {e}"

    def hash_identify(self, hash_string):
        """Identify the type of a hash based on its format."""
        h = hash_string.strip().lower()
        lines = [f"🔍 Hash identification: {h}\n"]

        # Length-based identification
        patterns = {
            32: ("MD5", "128-bit, commonly used for checksums"),
            40: ("SHA-1", "160-bit, deprecated for security use"),
            64: ("SHA-256", "256-bit, widely used for integrity verification"),
            96: ("SHA-384", "384-bit, high-security hash"),
            128: ("SHA-512", "512-bit, high-security hash"),
        }

        if len(h) in patterns:
            name, desc = patterns[len(h)]
            lines.append(f"  Likely: {name} ({desc})")
        else:
            lines.append(f"  Unknown hash length: {len(h)} characters")

        # Check for common prefixes
        prefixes = {
            "$2a$": "bcrypt", "$2b$": "bcrypt", "$2y$": "bcrypt",
            "$argon2": "Argon2", "$pbkdf2": "PBKDF2",
            "$6$": "SHA-512 crypt", "$5$": "SHA-256 crypt",
            "$1$": "MD5 crypt",
        }
        for prefix, name in prefixes.items():
            if h.startswith(prefix):
                lines.append(f"  Detected format: {name}")

        # Check if it looks like hex
        is_hex = all(c in "0123456789abcdef" for c in h)
        lines.append(f"  Format: {'Hexadecimal' if is_hex else 'Non-standard'}")

        return "\n".join(lines)

    # ── SSH/Remote ────────────────────────────────────────────────────

    def ssh_command(self, host, command, username=None, port=22, key_file=None):
        """Execute a command on a remote host via SSH (key-based auth only, no passwords)."""
        paramiko = self._get_paramiko()
        if paramiko is None:
            return "paramiko not installed. Install: pip install paramiko"

        if not check_rate("ssh_command", rate=0.1, burst=1):
            return "Rate limit exceeded. SSH commands are rate-limited for safety."

        try:
            from core.ssrf import is_ssrf_blocked
            if is_ssrf_blocked(host):
                return "Blocked: cannot SSH to internal/private addresses"

            client = paramiko.SSHClient()
            client.set_missing_host_key_policy(paramiko.WarningPolicy())

            connect_kwargs = {"hostname": host, "port": int(port), "timeout": 10}
            if username:
                connect_kwargs["username"] = username
            if key_file:
                connect_kwargs["key_filename"] = key_file

            client.connect(**connect_kwargs)

            stdin, stdout, stderr = client.exec_command(command, timeout=30)
            out = stdout.read().decode("utf-8", errors="replace").strip()
            err = stderr.read().decode("utf-8", errors="replace").strip()
            exit_code = stdout.channel.recv_exit_status()
            client.close()

            lines = [f"SSH {host}: {command}\n"]
            if out:
                lines.append(f"  Output:\n{out[:3000]}")
            if err:
                lines.append(f"  Stderr:\n{err[:1000]}")
            lines.append(f"  Exit code: {exit_code}")
            return "\n".join(lines)
        except Exception as e:
            return f"SSH error: {e}"

    # ── Existing security_best_practices (already above) ──────────────

    # ── Exploitation: Nikto Web Scanner ─────────────────────────────

    def nikto_scan(self, target, port=80, ssl=False):
        """Scan a web server with Nikto for vulnerabilities. Requires nikto installed."""
        if not check_rate("nikto_scan", rate=0.05, burst=1):
            return "Rate limit exceeded. Nikto scans are rate-limited for safety."

        nikto_cmd = self._find_tool("nikto")
        if not nikto_cmd:
            return (
                "nikto not installed. Install:\n"
                "  Linux: sudo apt install nikto\n"
                "  macOS: brew install nikto\n"
                "  Windows: https://cirt.net/Nikto2"
            )

        try:
            from core.ssrf import validate_url
            url = f"{'https' if ssl else 'http'}://{target}:{port}/"
            validate_url(url)
        except ValueError as e:
            return f"Blocked: {e}"

        args = nikto_cmd + ["-h", target, "-p", str(port)]
        if ssl:
            args.append("-ssl")

        try:
            stdout, stderr, rc = self._run_cmd(args, timeout=300)
            output = stdout[:5000] if stdout else stderr[:2000] if stderr else "No output"
            lines = [f"Nikto scan: {target}:{port}\n"]
            lines.append(output)
            if rc != 0 and not stdout:
                lines.append(f"\nNote: nikto exited with code {rc}")
            return "\n".join(lines)
        except Exception as e:
            return f"Nikto scan error: {e}"

    # ── Exploitation: SQLMap SQL Injection ───────────────────────────

    def sqlmap_scan(self, url, data=None, level=1, risk=1):
        """Test a URL for SQL injection with SQLMap. Requires sqlmap installed."""
        if not check_rate("sqlmap_scan", rate=0.05, burst=1):
            return "Rate limit exceeded. SQLMap scans are rate-limited for safety."

        sqlmap_cmd = self._find_tool("sqlmap") or self._find_tool("sqlmap.py")
        if not sqlmap_cmd:
            return (
                "sqlmap not installed. Install:\n"
                "  pip install sqlmap\n"
                "  Or: git clone https://github.com/sqlmapproject/sqlmap.git"
            )

        try:
            from core.ssrf import validate_url
            validate_url(url)
        except ValueError as e:
            return f"Blocked: {e}"

        args = sqlmap_cmd + ["-u", url, "--batch", "--level", str(level), "--risk", str(risk)]
        if data:
            args.extend(["--data", data])

        try:
            stdout, stderr, rc = self._run_cmd(args, timeout=300)
            output = stdout[:5000] if stdout else stderr[:2000] if stderr else "No output"
            lines = [f"SQLMap scan: {url}\n"]
            lines.append(output)
            if rc != 0 and not stdout:
                lines.append(f"\nNote: sqlmap exited with code {rc}")
            return "\n".join(lines)
        except Exception as e:
            return f"SQLMap scan error: {e}"

    # ── Exploitation: Hydra Brute Force ──────────────────────────────

    def hydra_brute(self, target, service, username=None, userlist=None, passwordlist=None, port=None):
        """Brute-force login with Hydra. Requires hydra installed."""
        if not check_rate("hydra_brute", rate=0.05, burst=1):
            return "Rate limit exceeded. Hydra attacks are rate-limited for safety."

        if not self._find_tool("hydra"):
            return (
                "hydra not installed. Install:\n"
                "  Linux: sudo apt install hydra\n"
                "  macOS: brew install hydra\n"
                "  Windows: https://www.thc.org/thc-hydra/"
            )

        if not username and not userlist:
            return "Error: provide either username or userlist for brute-force"
        if not passwordlist:
            return "Error: provide passwordlist for brute-force"

        VALID_SERVICES = {
            "ssh", "ftp", "telnet", "http", "https", "smtp", "pop3",
            "imap", "smb", "rdp", "vnc", "mysql", "mssql", "postgres",
            "mongodb", "redis", "svn", "ldap", "snmp", "smb2"
        }
        if service.lower() not in VALID_SERVICES:
            return f"Invalid service '{service}'. Valid: {', '.join(sorted(VALID_SERVICES))}"

        try:
            from core.ssrf import is_ssrf_blocked
            if is_ssrf_blocked(target):
                return "Blocked: cannot brute-force internal/private addresses"
        except Exception:
            pass

        args = self._find_tool("hydra")
        if username:
            args.extend(["-l", username])
        elif userlist:
            args.extend(["-L", userlist])
        args.extend(["-P", passwordlist])
        if port:
            args.extend(["-s", str(port)])
        args.extend([target, service])

        try:
            stdout, stderr, rc = self._run_cmd(args, timeout=300)
            output = stdout[:5000] if stdout else stderr[:2000] if stderr else "No output"
            lines = [f"Hydra brute-force: {target} ({service})\n"]
            lines.append(output)
            return "\n".join(lines)
        except Exception as e:
            return f"Hydra error: {e}"

    # ── Exploitation: Gobuster Directory Brute ───────────────────────

    def gobuster_scan(self, url, wordlist=None, extensions=None, threads=10):
        """Directory brute-force with Gobuster. Requires gobuster installed."""
        if not check_rate("gobuster_scan", rate=0.05, burst=1):
            return "Rate limit exceeded. Gobuster scans are rate-limited for safety."

        gobuster_cmd = self._find_tool("gobuster")
        if not gobuster_cmd:
            return (
                "gobuster not installed. Install:\n"
                "  Linux: sudo apt install gobuster\n"
                "  macOS: brew install gobuster\n"
                "  Go: go install github.com/OJ/gobuster/v3@latest"
            )

        try:
            from core.ssrf import validate_url
            validate_url(url)
        except ValueError as e:
            return f"Blocked: {e}"

        wl = wordlist or self._default_wordlist()
        if not wl:
            return "No wordlist found. Provide one via wordlist param or install seclists."

        args = gobuster_cmd + ["dir", "-u", url, "-w", wl, "-t", str(threads), "--no-error"]
        if extensions:
            args.extend(["-x", extensions])

        try:
            stdout, stderr, rc = self._run_cmd(args, timeout=300)
            output = stdout[:5000] if stdout else stderr[:2000] if stderr else "No output"
            lines = [f"Gobuster dir scan: {url}\n  Wordlist: {wl}\n"]
            lines.append(output)
            return "\n".join(lines)
        except Exception as e:
            return f"Gobuster error: {e}"

    # ── Exploitation: FFUF Web Fuzzer ────────────────────────────────

    def ffuf_fuzz(self, url, wordlist=None, filters=None, matchers=None, threads=40):
        """Web fuzzer with FFUF. Requires ffuf installed."""
        if not check_rate("ffuf_fuzz", rate=0.05, burst=1):
            return "Rate limit exceeded. FFUF scans are rate-limited for safety."

        ffuf_cmd = self._find_tool("ffuf")
        if not ffuf_cmd:
            return (
                "ffuf not installed. Install:\n"
                "  Linux: sudo apt install ffuf\n"
                "  macOS: brew install ffuf\n"
                "  Go: go install github.com/ffuf/ffuf/v2@latest"
            )

        try:
            from core.ssrf import validate_url
            validate_url(url)
        except ValueError as e:
            return f"Blocked: {e}"

        if "FUZZ" not in url:
            return "URL must contain 'FUZZ' placeholder (e.g. http://target/FUZZ)"

        wl = wordlist or self._default_wordlist()
        if not wl:
            return "No wordlist found. Provide one via wordlist param or install seclists."

        args = ffuf_cmd + ["-u", url, "-w", wl, "-t", str(threads)]
        if filters:
            args.extend(["-fc", str(filters)])
        if matchers:
            args.extend(["-mc", str(matchers)])

        try:
            stdout, stderr, rc = self._run_cmd(args, timeout=300)
            output = stdout[:5000] if stdout else stderr[:2000] if stderr else "No output"
            lines = [f"FFUF fuzz: {url}\n  Wordlist: {wl}\n"]
            lines.append(output)
            return "\n".join(lines)
        except Exception as e:
            return f"FFUF error: {e}"

    # ── Metasploit Integration ─────────────────────────────────────────

    def _find_msf(self, tool="msfconsole"):
        return self._find_tool(tool)

    @staticmethod
    def check_msf_installed(tool="msfconsole"):
        if shutil.which(tool):
            return True
        try:
            return subprocess.call(["wsl", "--", "which", tool],
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=10) == 0
        except Exception:
            return False

    def _check_msf(self, tool="msfconsole"):
        found = self._find_msf(tool)
        if not found:
            msg = f"{tool} not installed"
            if tool == "msfconsole":
                msg += ". Install: https://www.metasploit.com/"
            return None, msg
        return found, None

    def msf_console(self, command, resource_script=None):
        """Execute a Metasploit console command or run a resource script."""
        found, err = self._check_msf("msfconsole")
        if not found:
            return err
        if not check_rate("msf_console", rate=0.1, burst=2):
            return "Rate limit exceeded."
        import re as _re
        if not _re.match(r'^[a-zA-Z0-9\s_.\-/]+$', command):
            return "Invalid command format"
        try:
            if resource_script:
                args = found + ["-q", "-r", resource_script, "-x", command]
            else:
                args = found + ["-q", "-x", command]
            stdout, stderr, rc = self._run_cmd(args, timeout=60)
            output = stdout[:5000] if stdout else stderr[:2000] if stderr else "(no output)"
            return f"Metasploit: {command}\n\n{output}"
        except Exception as e:
            return f"msfconsole error: {e}"

    def msfvenom(self, payload, lhost, lport, output="payload", format="exe", platform="windows", arch="x64"):
        """Generate a payload with msfvenom."""
        if self.safe_mode:
            return ("Payload generation blocked by safe mode. "
                    "This is a potentially dangerous operation that creates executable payloads. "
                    "Disable safe mode first (requires explicit user confirmation).")
        found, err = self._check_msf("msfvenom")
        if not found:
            return err
        if not check_rate("msfvenom", rate=0.1, burst=2):
            return "Rate limit exceeded."
        import getpass as _gp
        import datetime as _dt
        _user = _gp.getuser()
        _ts = _dt.datetime.now().isoformat()
        print(f"  [AUDIT] msfvenom payload generated by {_user} at {_ts}: {payload} LHOST={lhost} LPORT={lport} -> {output}")

        args = found + [
            "-p", payload,
            f"LHOST={lhost}",
            f"LPORT={lport}",
            "-f", format,
            "-o", output,
            "--platform", platform,
            "-a", arch,
        ]
        try:
            stdout, stderr, rc = self._run_cmd(args, timeout=120)
            if rc == 0:
                return f"Payload generated: {output}\n{stdout[:1000] if stdout else ''}"
            return f"msfvenom error: {stderr[:2000]}"
        except Exception as e:
            return f"msfvenom error: {e}"

    def msf_resource(self, script_path):
        """Run a Metasploit resource (.rc) script."""
        found, err = self._check_msf("msfconsole")
        if not found:
            return err
        if not os.path.isfile(script_path):
            return f"Resource script not found: {script_path}"
        args = found + ["-q", "-r", script_path]
        try:
            stdout, stderr, rc = self._run_cmd(args, timeout=300)
            output = stdout[:5000] if stdout else stderr[:2000] if stderr else "(no output)"
            return f"Metasploit resource: {script_path}\n\n{output}"
        except Exception as e:
            return f"msfresource error: {e}"

    def msf_db_status(self):
        """Check Metasploit database connection status."""
        found, err = self._check_msf("msfconsole")
        if not found:
            return err
        stdout, stderr, rc = self._run_cmd(found + ["-q", "-x", "db_status; exit"], timeout=30)
        return stdout[:2000] if stdout else stderr[:1000] if stderr else "db_status: unknown"

    @staticmethod
    def _default_wordlist():
        """Find a common wordlist on the system."""
        candidates = [
            "/usr/share/wordlists/dirb/common.txt",
            "/usr/share/dirb/wordlists/common.txt",
            "/usr/share/seclists/Discovery/Web-Content/common.txt",
            "/usr/share/seclists/Discovery/Web-Content/raft-small-words.txt",
            "C:/Tools/wordlists/common.txt",
        ]
        for path in candidates:
            if os.path.isfile(path):
                return path
        return None

    def generate_report(self, targets=None, output_dir=None, scans=None):
        """Generate an automated pentest report from scan results.

        scans: list of dicts like [{"tool": "nmap", "target": "x", "output": "..."}]
        Or pass scans=None to run a basic scan suite automatically.
        """
        from tools.report import PentestReport

        if not targets:
            targets = ["127.0.0.1"]

        report = PentestReport(
            title="FRIDAY Automated Pentest Report",
            targets=targets,
        )

        if scans:
            # User-provided scan results
            for s in scans:
                report.add_result(
                    tool=s.get("tool", "unknown"),
                    output=s.get("output", ""),
                    target=s.get("target"),
                    severity=s.get("severity"),
                )
        else:
            # Run basic scan suite automatically
            scan_tools = [
                ("check_firewall", {}, None),
                ("check_open_ports", {"target": targets[0]}, targets[0]),
                ("check_running_services", {}, None),
                ("check_listeners", {}, None),
                ("security_best_practices", {}, None),
            ]
            for tool_name, kwargs, tgt in scan_tools:
                handler = self.get_handler(tool_name)
                if handler:
                    try:
                        output = handler(**kwargs)
                        report.add_result(tool=tool_name, output=output, target=tgt)
                    except Exception as e:
                        report.add_result(tool=tool_name, output=f"Scan failed: {e}", target=tgt, severity="info")

        result = report.generate(output_dir=output_dir)
        paths = []
        if result.get("html"):
            paths.append(result["html"])
        if result.get("pdf"):
            paths.append(result["pdf"])

        lines = [f"📄 Pentest report generated ({len(report.results)} findings)"]
        lines.append(f"  HTML: {result.get('html', 'N/A')}")
        if result.get("pdf"):
            lines.append(f"  PDF:  {result['pdf']}")
        elif result.get("pdf_note"):
            lines.append(f"  PDF:  {result['pdf_note']}")
        return "\n".join(lines)

    def get_tool_definitions(self):
        return [
            # ── Existing ──
            {"type": "function", "function": {"name": "check_firewall", "description": "Check firewall profile status on this system", "parameters": {"type": "object", "properties": {}}}},
            {"type": "function", "function": {"name": "check_open_ports", "description": "Scan open TCP ports on a target (default: localhost)", "parameters": {"type": "object", "properties": {
                "target": {"type": "string", "description": "Target IP or hostname", "default": "127.0.0.1"},
                "common_only": {"type": "boolean", "description": "Scan common ports only", "default": True}
            }}}},
            {"type": "function", "function": {"name": "check_running_services", "description": "List all running services on this system", "parameters": {"type": "object", "properties": {}}}},
            {"type": "function", "function": {"name": "check_listeners", "description": "List all listening services on this system", "parameters": {"type": "object", "properties": {}}}},
            {"type": "function", "function": {"name": "check_security_updates", "description": "Check for available security updates", "parameters": {"type": "object", "properties": {}}}},
            {"type": "function", "function": {"name": "security_best_practices", "description": "Run a security best practices assessment", "parameters": {"type": "object", "properties": {}}}},
            # ── Reconnaissance ──
            {"type": "function", "function": {"name": "nmap_scan", "description": "Scan a target with nmap for ports, services, and OS detection. Requires nmap installed.", "parameters": {"type": "object", "properties": {
                "target": {"type": "string", "description": "Target IP, hostname, or CIDR range"},
                "ports": {"type": "string", "description": "Port range (e.g. '1-1000', '80,443', '22')"},
                "scan_type": {"type": "string", "description": "Scan type: quick, full, stealth, udp, version", "default": "quick"}
            }, "required": ["target"]}}},
            {"type": "function", "function": {"name": "shodan_search", "description": "Search Shodan for internet-connected devices by query (e.g. 'apache country:US')", "parameters": {"type": "object", "properties": {
                "query": {"type": "string", "description": "Shodan search query"},
                "max_results": {"type": "integer", "description": "Max results", "default": 5}
            }, "required": ["query"]}}},
            {"type": "function", "function": {"name": "shodan_host_info", "description": "Get detailed Shodan info for a specific IP address", "parameters": {"type": "object", "properties": {
                "ip": {"type": "string", "description": "IP address to look up"}
            }, "required": ["ip"]}}},
            {"type": "function", "function": {"name": "dns_lookup", "description": "Perform DNS record lookup for a domain (A, AAAA, MX, NS, TXT, CNAME, SOA records)", "parameters": {"type": "object", "properties": {
                "domain": {"type": "string", "description": "Domain name to look up"}
            }, "required": ["domain"]}}},
            {"type": "function", "function": {"name": "subdomain_enum", "description": "Enumerate subdomains for a domain using DNS brute force", "parameters": {"type": "object", "properties": {
                "domain": {"type": "string", "description": "Base domain to enumerate"}
            }, "required": ["domain"]}}},
            {"type": "function", "function": {"name": "whois_lookup", "description": "Perform WHOIS lookup for domain registration info", "parameters": {"type": "object", "properties": {
                "domain": {"type": "string", "description": "Domain or IP to look up"}
            }, "required": ["domain"]}}},
            # ── Network ──
            {"type": "function", "function": {"name": "banner_grab", "description": "Grab service banner from a host:port to identify running services", "parameters": {"type": "object", "properties": {
                "host": {"type": "string", "description": "Target host"},
                "port": {"type": "integer", "description": "Target port"}
            }, "required": ["host", "port"]}}},
            {"type": "function", "function": {"name": "traceroute", "description": "Perform traceroute to map network path to a target", "parameters": {"type": "object", "properties": {
                "target": {"type": "string", "description": "Target host or IP"},
                "max_hops": {"type": "integer", "description": "Max hops", "default": 15}
            }, "required": ["target"]}}},
            # ── Web Security ──
            {"type": "function", "function": {"name": "web_headers_check", "description": "Analyze HTTP security headers of a website (HSTS, CSP, X-Frame-Options, etc.)", "parameters": {"type": "object", "properties": {
                "url": {"type": "string", "description": "URL to check"}
            }, "required": ["url"]}}},
            {"type": "function", "function": {"name": "ssl_check", "description": "Check SSL/TLS certificate details, expiry, cipher, and protocol version", "parameters": {"type": "object", "properties": {
                "host": {"type": "string", "description": "Hostname to check"},
                "port": {"type": "integer", "description": "Port (default 443)", "default": 443}
            }, "required": ["host"]}}},
            # ── Forensics ──
            {"type": "function", "function": {"name": "hash_file", "description": "Calculate MD5, SHA-1, SHA-256 hashes for a file", "parameters": {"type": "object", "properties": {
                "file_path": {"type": "string", "description": "Path to file"},
                "algorithms": {"type": "array", "items": {"type": "string"}, "description": "Hash algorithms (default: md5, sha1, sha256)"}
            }, "required": ["file_path"]}}},
            {"type": "function", "function": {"name": "hash_identify", "description": "Identify the type/format of a hash string", "parameters": {"type": "object", "properties": {
                "hash_string": {"type": "string", "description": "Hash to identify"}
            }, "required": ["hash_string"]}}},
            # ── SSH ──
            {"type": "function", "function": {"name": "ssh_command", "description": "Execute a command on a remote host via SSH (key-based auth only)", "parameters": {"type": "object", "properties": {
                "host": {"type": "string", "description": "Remote host"},
                "command": {"type": "string", "description": "Command to execute"},
                "username": {"type": "string", "description": "SSH username"},
                "port": {"type": "integer", "description": "SSH port", "default": 22},
                "key_file": {"type": "string", "description": "Path to SSH private key file"}
            }, "required": ["host", "command"]}}},
            {"type": "function", "function": {"name": "generate_report", "description": "Generate an automated pentest report (HTML/PDF) from scan results. Provide scan results or run basic scan suite automatically.", "parameters": {"type": "object", "properties": {
                "targets": {"type": "array", "items": {"type": "string"}, "description": "Target IPs/hostnames to scan"},
                "output_dir": {"type": "string", "description": "Output directory (default: ~/friday_reports)"},
                "scans": {"type": "array", "items": {"type": "object"}, "description": "Pre-collected scan results: [{tool, target, output, severity}]"}
            }}}},
            # ── Metasploit ──
            {"type": "function", "function": {"name": "msf_console", "description": "Run Metasploit console command", "parameters": {"type": "object", "properties": {
                "command": {"type": "string", "description": "Metasploit command to run"},
                "resource_script": {"type": "string", "description": "Path to .rc resource script"}
            }, "required": ["command"]}}},
            {"type": "function", "function": {"name": "msfvenom", "description": "Generate payload with msfvenom", "parameters": {"type": "object", "properties": {
                "payload": {"type": "string", "description": "Payload (e.g. windows/x64/meterpreter/reverse_tcp)"},
                "lhost": {"type": "string", "description": "Listener IP"},
                "lport": {"type": "string", "description": "Listener port"},
                "output": {"type": "string", "description": "Output filename", "default": "payload"},
                "format": {"type": "string", "description": "Output format: exe/elf/py/ps1/raw", "default": "exe"},
                "platform": {"type": "string", "description": "Target platform: windows/linux/osx", "default": "windows"},
                "arch": {"type": "string", "description": "Architecture: x64/x86", "default": "x64"}
            }, "required": ["payload", "lhost", "lport"]}}},
            {"type": "function", "function": {"name": "msf_resource", "description": "Run a Metasploit resource (.rc) script", "parameters": {"type": "object", "properties": {
                "script_path": {"type": "string", "description": "Path to .rc script"}
            }, "required": ["script_path"]}}},
            {"type": "function", "function": {"name": "msf_db_status", "description": "Check Metasploit database connection", "parameters": {"type": "object", "properties": {}}}},
            # ── Exploitation ──
            {"type": "function", "function": {"name": "nikto_scan", "description": "Scan a web server for vulnerabilities with Nikto", "parameters": {"type": "object", "properties": {
                "target": {"type": "string", "description": "Target host or IP"},
                "port": {"type": "integer", "description": "Web server port", "default": 80},
                "ssl": {"type": "boolean", "description": "Use HTTPS", "default": False}
            }, "required": ["target"]}}},
            {"type": "function", "function": {"name": "sqlmap_scan", "description": "Test a URL for SQL injection with SQLMap", "parameters": {"type": "object", "properties": {
                "url": {"type": "string", "description": "Target URL with parameters"},
                "data": {"type": "string", "description": "POST data string"},
                "level": {"type": "integer", "description": "Test level 1-5", "default": 1},
                "risk": {"type": "integer", "description": "Risk level 1-3", "default": 1}
            }, "required": ["url"]}}},
            {"type": "function", "function": {"name": "hydra_brute", "description": "Brute-force login credentials with THC Hydra", "parameters": {"type": "object", "properties": {
                "target": {"type": "string", "description": "Target host or IP"},
                "service": {"type": "string", "description": "Service: ssh/ftp/telnet/http/https/smtp/pop3/imap/mysql/smb/rdp/vnc"},
                "username": {"type": "string", "description": "Single username to test"},
                "userlist": {"type": "string", "description": "Path to username list file"},
                "passwordlist": {"type": "string", "description": "Path to password list file"},
                "port": {"type": "integer", "description": "Service port (auto-detected if omitted)"}
            }, "required": ["target", "service"]}}},
            {"type": "function", "function": {"name": "gobuster_scan", "description": "Directory brute-force with Gobuster", "parameters": {"type": "object", "properties": {
                "url": {"type": "string", "description": "Target URL (e.g. http://target/)"},
                "wordlist": {"type": "string", "description": "Path to wordlist file"},
                "extensions": {"type": "string", "description": "File extensions to scan (e.g. php,html,txt)"},
                "threads": {"type": "integer", "description": "Number of threads", "default": 10}
            }, "required": ["url"]}}},
            {"type": "function", "function": {"name": "ffuf_fuzz", "description": "Web fuzzer with FFUF (URL must contain FUZZ placeholder)", "parameters": {"type": "object", "properties": {
                "url": {"type": "string", "description": "Target URL with FUZZ (e.g. http://target/FUZZ)"},
                "wordlist": {"type": "string", "description": "Path to wordlist file"},
                "filters": {"type": "string", "description": "Filter by HTTP status code (e.g. 404)"},
                "matchers": {"type": "string", "description": "Match HTTP status code (e.g. 200,301)"},
                "threads": {"type": "integer", "description": "Number of threads", "default": 40}
            }, "required": ["url"]}}},
        ]

    def get_handler(self, name):
        handlers = {
            "check_firewall": self.check_firewall,
            "check_open_ports": self.check_open_ports,
            "check_listeners": self.check_listeners,
            "check_security_updates": self.check_security_updates,
            "check_running_services": self.check_running_services,
            "security_best_practices": self.security_best_practices,
            "nmap_scan": self.nmap_scan,
            "shodan_search": self.shodan_search,
            "shodan_host_info": self.shodan_host_info,
            "dns_lookup": self.dns_lookup,
            "subdomain_enum": self.subdomain_enum,
            "whois_lookup": self.whois_lookup,
            "banner_grab": self.banner_grab,
            "traceroute": self.traceroute,
            "web_headers_check": self.web_headers_check,
            "ssl_check": self.ssl_check,
            "hash_file": self.hash_file,
            "hash_identify": self.hash_identify,
            "ssh_command": self.ssh_command,
            "nikto_scan": self.nikto_scan,
            "sqlmap_scan": self.sqlmap_scan,
            "hydra_brute": self.hydra_brute,
            "gobuster_scan": self.gobuster_scan,
            "ffuf_fuzz": self.ffuf_fuzz,
            "generate_report": self.generate_report,
            "msf_console": self.msf_console,
            "msfvenom": self.msfvenom,
            "msf_resource": self.msf_resource,
            "msf_db_status": self.msf_db_status,
        }
        return handlers.get(name)
