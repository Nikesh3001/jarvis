#!/usr/bin/env python3
"""
FRIDAY Cybersecurity Console — Standalone pentest toolkit.

Access via:  python jarvis.py -cyber

Consolidates all offensive/defensive security tools into a focused
interactive REPL with categorized commands.
"""

import os
import sys
import atexit

try:
    import readline
except ImportError:
    try:
        import pyreadline3 as readline
    except ImportError:
        readline = None

# Persistent history
_histfile = os.path.join(os.path.expanduser("~"), ".friday_cyber_history")
if readline:
    try:
        readline.read_history_file(_histfile)
        readline.set_history_length(1000)
    except FileNotFoundError:
        pass
    def _save_history():
        try:
            readline.write_history_file(_histfile)
            # Restrict history file permissions (owner read/write only)
            try:
                os.chmod(_histfile, 0o600)
            except OSError:
                pass
        except Exception:
            pass
    atexit.register(_save_history)

from tools.security import SecurityTool
from tools.internet import InternetTools
from core.ssrf import validate_url, is_ssrf_blocked

VERSION = "3.5.0"

CYBER_BANNER = CYBER_BANNER_ASCII = r"""
  +=========================================================+
  |     __                _      _                          |
  |   / _|___  ___   ___(_) ___| |_ _   _                  |
  |  | |_/ __|/ _ \ / __| |/ _ \ __| | | |                 |
  |  |  _\__ \ (_) | (__| |  __/ |_| |_| |                 |
  |  |_| |___/\___/ \___|_|\___|\__|\__, |                 |
  |                                  |___/                  |
  |                                                         |
  |   fsociety Cybersecurity Console  *  v{ver}            |
  |   "Control is an illusion"  *  Elliot Alderson          |
  |                                                         |
  +=========================================================+

  Type 'help' for commands  |  'quit' to exit
""".format(ver=VERSION)

HELP_TEXT = """
  ┌─────────────────────────────────────────────────────────┐
  │  CYBERSECURITY COMMANDS                                  │
  ├─────────────────────────────────────────────────────────┤
  │                                                         │
  │  [RECON] Reconnaissance                                  │
  │    nmap <target> [ports] [type]     Port scan with nmap  │
  │    shodan <query>                   Search Shodan        │
  │    shodan-host <ip>                 Shodan host info     │
  │    dns <domain>                     DNS record lookup    │
  │    subdomain <domain>               Subdomain enum       │
  │    whois <domain>                   WHOIS lookup         │
  │    banner <host> <port>             Banner grab          │
  │    traceroute <target>              Network traceroute   │
  │                                                         │
  │  [EXPLOIT] Exploitation                                  │
  │    nikto <target> [port] [--ssl]   Web vuln scan        │
  │    sqlmap <url> [data]              SQL injection test   │
  │    hydra <target> <svc> <usr> <pwd> Brute-force login    │
  │    gobuster <url> [wordlist]        Dir brute-force      │
  │    ffuf <url>                       Web fuzzing (FUZZ)   │
  │                                                         │
  │  [WEB] Web Security                                     │
  │    headers <url>                    Security headers     │
  │    ssl <host> [port]                SSL/TLS check        │
  │    jina <url>                       Read page (Jina)     │
  │    semantic <query>                 AI search            │
  │                                                         │
  │  [SYS] System Security                                  │
  │    firewall                         Check firewall       │
  │    ports [target]                   Open ports           │
  │    services                         Running services     │
  │    listeners                        Listening ports      │
  │    updates                          Security updates     │
  │    best-practices                   Security audit       │
  │                                                         │
  │  [NET] Network                                          │
  │    ssh <host> <cmd> [user] [pass]   SSH command          │
  │    hash <file>                      File hash            │
  │    hash-id <hash>                   Identify hash type   │
  │                                                         │
  │  [META]                                                 │
  │    report [targets]                Generate HTML/PDF report│
  │    tools                            List all tools       │
  │    check                            Check tool installs  │
  │    help                             Show this help       │
  │    quit / exit / bye                Exit console         │
  │                                                         │
  │  [MSF] Metasploit                                       │
  │    msf <command>                   Run msfconsole cmd    │
  │    msfvenom <payload> <lhost> <lport>  Generate payload  │
  │    msf-script <path>               Run .rc resource file │
  │    msf-db                          Check DB status       │
  │                                                         │
  │  [DEV] Built-in Tools                                    │
  │    git <args>                      Run git commands      │
  │    python <code>                   Run Python code       │
  │    pip <args>                      Run pip commands      │
  └─────────────────────────────────────────────────────────┘
"""

def _safe_int(val, default=0):
    """Parse an int safely, returning default on failure."""
    try:
        return int(val)
    except (ValueError, TypeError):
        return default


# ── Tool instance singletons ────────────────────────────────────────────
_sec = SecurityTool()
_net = InternetTools()


def _check(tool_name):
    """Check if a CLI tool is installed."""
    import shutil
    path = shutil.which(tool_name)
    return f"  ✅ {tool_name}: {path}" if path else f"  ❌ {tool_name}: NOT INSTALLED"


def cmd_tools(_args):
    """List all registered cybersecurity tools."""
    defs = _sec.get_tool_definitions()
    net_defs = _net.get_tool_definitions()
    print(f"\n  Security tools ({len(defs)}):")
    for d in defs:
        print(f"    {d['function']['name']:25s} {d['function']['description'][:50]}")
    print(f"\n  Internet tools ({len(net_defs)}):")
    for d in net_defs:
        print(f"    {d['function']['name']:25s} {d['function']['description'][:50]}")
    print(f"\n  Total: {len(defs) + len(net_defs)} tools\n")


def cmd_check(_args):
    """Check which CLI tools are installed."""
    print("\n  Tool Installation Check:")
    tools = ["nmap", "nikto", "sqlmap", "hydra", "gobuster", "ffuf",
             "whois", "traceroute", "yt-dlp", "gh", "paramiko",
             "msfconsole", "msfvenom", "git", "python", "pip"]
    for t in tools:
        if t in ("msfconsole", "msfvenom"):
            found = _sec.check_msf_installed(t)
            print(f"    {t:20s} {'[OK]' if found else '[MISSING]'}")
        else:
            print(_check(t))
    print()


# ── Command dispatch table ──────────────────────────────────────────────

COMMANDS = {
    # Recon
    "nmap":       lambda a: print(_sec.nmap_scan(a[0], a[1] if len(a) > 1 else None, a[2] if len(a) > 2 else "quick")),
    "shodan":     lambda a: print(_sec.shodan_search(" ".join(a))),
    "shodan-host": lambda a: print(_sec.shodan_host_info(a[0])),
    "dns":        lambda a: print(_sec.dns_lookup(a[0])),
    "subdomain":  lambda a: print(_sec.subdomain_enum(a[0])),
    "whois":      lambda a: print(_sec.whois_lookup(a[0])),
    "banner":     lambda a: print(_sec.banner_grab(a[0], _safe_int(a[1], 80))),
    "traceroute": lambda a: print(_sec.traceroute(a[0])),

    # Exploit
    "nikto":      lambda a: print(_sec.nikto_scan(a[0], _safe_int(a[1], 80) if len(a) > 1 else 80, any(x in a for x in ("--ssl", "-ssl")))),
    "sqlmap":     lambda a: print(_sec.sqlmap_scan(a[0], a[1] if len(a) > 1 else None)),
    "hydra":      lambda a: print(_sec.hydra_brute(a[0], a[1], a[2] if len(a) > 2 else None, None, a[3] if len(a) > 3 else None)),
    "gobuster":   lambda a: print(_sec.gobuster_scan(a[0], a[1] if len(a) > 1 else None)),
    "ffuf":       lambda a: print(_sec.ffuf_fuzz(a[0], a[1] if len(a) > 1 else None)),

    # Web
    "headers":    lambda a: print(_sec.web_headers_check(a[0])),
    "ssl":        lambda a: print(_sec.ssl_check(a[0], _safe_int(a[1], 443) if len(a) > 1 else 443)),
    "jina":       lambda a: print(_net.jina_read(a[0])),
    "semantic":   lambda a: print(_net.semantic_search(" ".join(a))),

    # System
    "firewall":       lambda a: print(_sec.check_firewall()),
    "ports":          lambda a: print(_sec.check_open_ports(a[0] if a else "127.0.0.1")),
    "services":       lambda a: print(_sec.check_running_services()),
    "listeners":      lambda a: print(_sec.check_listeners()),
    "updates":        lambda a: print(_sec.check_security_updates()),
    "best-practices": lambda a: print(_sec.security_best_practices()),

    # Network
    "ssh":        lambda a: print(_sec.ssh_command(a[0], a[1], a[2] if len(a) > 2 else None, _safe_int(a[3], 22) if len(a) > 3 else 22, a[4] if len(a) > 4 else None)),
    "hash":       lambda a: print(_sec.hash_file(a[0])),
    "hash-id":    lambda a: print(_sec.hash_identify(a[0])),

    # Metasploit
    "msf":        lambda a: print(_sec.msf_console(" ".join(a))),
    "msfvenom":   lambda a: print(_sec.msfvenom(a[0], a[1], a[2], a[3] if len(a) > 3 else "payload", a[4] if len(a) > 4 else "exe", a[5] if len(a) > 5 else "windows", a[6] if len(a) > 6 else "x64")) if len(a) >= 3 else print("Usage: msfvenom <payload> <lhost> <lport> [output] [format] [platform] [arch]"),
    "msf-script": lambda a: print(_sec.msf_resource(a[0])),
    "msf-db":     lambda a: print(_sec.msf_db_status()),

    # Built-in dev tools
    "git":        lambda a: _run_git(" ".join(a)),
    "python":     lambda a: _run_python(" ".join(a)),
    "pip":        lambda a: _run_pip(" ".join(a)),

    # Meta
    "report":     lambda a: print(_sec.generate_report(targets=a if a else None)),
    "tools":  cmd_tools,
    "check":  cmd_check,
    "help":   lambda a: print(HELP_TEXT),
}


def _run_git(args):
    import subprocess
    try:
        r = subprocess.run(["git"] + args.split(), capture_output=True, text=True, timeout=30)
        out = r.stdout.strip()[:3000] if r.stdout.strip() else ""
        err = r.stderr.strip()[:1000] if r.stderr.strip() else ""
        if out:
            print(out)
        if err:
            print(f"Error: {err}")
        if not out and not err:
            print("Git command completed (no output)")
    except FileNotFoundError:
        print("Git is not installed or not in PATH")
    except subprocess.TimeoutExpired:
        print("Git command timed out")
    except Exception as e:
        print(f"Git error: {e}")


def _run_python(code):
    import subprocess
    try:
        r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=15)
        out = r.stdout.strip()[:3000] if r.stdout.strip() else ""
        err = r.stderr.strip()[:1000] if r.stderr.strip() else ""
        if out:
            print(out)
        if err:
            print(f"Error: {err}")
        if not out and not err:
            print("Python code executed (no output)")
    except subprocess.TimeoutExpired:
        print("Python code timed out")
    except Exception as e:
        print(f"Python error: {e}")


def _run_pip(args):
    import subprocess
    try:
        r = subprocess.run([sys.executable, "-m", "pip"] + args.split(), capture_output=True, text=True, timeout=60)
        out = r.stdout.strip()[:3000] if r.stdout.strip() else ""
        err = r.stderr.strip()[:1000] if r.stderr.strip() else ""
        if out:
            print(out)
        if err:
            print(f"Error: {err}")
        if not out and not err:
            print("Pip command completed (no output)")
    except FileNotFoundError:
        print("Python/pip is not installed")
    except subprocess.TimeoutExpired:
        print("Pip command timed out")
    except Exception as e:
        print(f"Pip error: {e}")


def process_command(line):
    """Parse and execute a cyber console command."""
    line = line.strip()
    if not line:
        return True

    parts = line.split()
    cmd = parts[0].lower()
    args = parts[1:]

    if cmd in ("quit", "exit", "bye", "q"):
        return False

    handler = COMMANDS.get(cmd)
    if handler:
        try:
            handler(args)
        except Exception as e:
            print(f"  Error: {e}")
    else:
        # Try as a security tool function name directly (simple positional passthrough)
        handler = _sec.get_handler(cmd)
        if handler:
            try:
                print(handler(*args) if args else handler())
            except TypeError as e:
                print(f"  Usage error: {e}")
            except Exception as e:
                print(f"  Error: {e}")
        else:
            print(f"  Unknown command: '{cmd}'. Type 'help' for available commands.")

    return True


def run_cyber_console():
    """Run the interactive cybersecurity console."""
    print(CYBER_BANNER)
    print("  ⚠️  AUTHORIZED USE ONLY. All actions are logged.")
    print("  Type 'help' for commands.\n")

    while True:
        try:
            line = input("\033[96m  cyber>\033[0m ").strip()
            if not process_command(line):
                break
        except (EOFError, KeyboardInterrupt):
            print("\n  Goodbye.")
            break

    print("\n  [CYBER] Console session ended.\n")


if __name__ == "__main__":
    run_cyber_console()
