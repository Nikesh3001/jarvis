# JARVIS / FRIDAY — Terminal AI Assistant

A dual-personality voice AI assistant for your terminal with full system control, cybersecurity toolkit, and web dashboard. Powered by **Groq** (cloud) or **Ollama** (local).

## Features

- **Dual Personality**: JARVIS (male) / FRIDAY (female) — switch anytime
- **AI Backends**: Groq API (cloud) or local Ollama models
- **Voice I/O**: Wake words ("Hey Jarvis" / "Hey Friday"), natural TTS via Edge voices
- **System Control**: Open apps, screenshots, volume, clipboard, media keys, WiFi, processes
- **System Monitoring**: CPU, RAM, disk, battery, network, running services, security audit
- **Web Dashboard**: Browser-based UI at `http://localhost:8080` with real-time chat, system status, tool listing
- **Code Sandbox**: Safe Python execution with restricted builtins — no os/subprocess/socket/file I/O
- **Multi-Language IDE**: Lint, format, scaffold, and run code for 25+ languages (Python, JS, Go, Rust, Java, C++, Ruby, PHP, and more)
- **File Editor**: Read, write, edit, search, copy, move, delete files with path traversal protection
- **Git Integration**: Clone, commit, push, pull, branch, status — with URL injection protection
- **Shell Access**: Command execution with extensive blocklist for dangerous patterns
- **Automation**: Browser automation, GUI interaction, scheduled tasks (via `automator.py`)
- **Plugin System**: Hot-loadable Python plugins with hash-based integrity verification
- **Memory & Code Index**: Conversation persistence (encrypted), vector code search
- **Multi-Agent**: Sub-agents for parallel research and complex task decomposition
- **Deep Research**: Iterative web search with source analysis and structured reports
- **Cybersecurity Console**: Standalone pentest toolkit with 30+ tools

### Cybersecurity Console

Access via `python jarvis.py -cyber` or web UI at `http://localhost:8081`.

| Category | Tools |
|----------|-------|
| **Recon** | nmap, shodan, dns, subdomain, whois, banner grab, traceroute |
| **Exploit** | nikto, sqlmap, hydra, gobuster, ffuf |
| **Web** | Security headers, SSL/TLS check, Jina web reader, semantic search |
| **System** | Firewall check, port scan, services, listeners, updates, best-practices audit |
| **Network** | SSH (key-based), file hashing, hash identification |
| **Metasploit** | msfconsole, msfvenom (gated behind safe-mode), .rc scripts |
| **Dev** | Git, Python, pip (all sandboxed) |
| **Internet** | YouTube transcripts/search, GitHub repo/issue viewer, RSS feeds, Jina Reader |

All external target inputs (nmap, hydra, gobuster, ffuf, nikto, SQLMap) are validated through SSRF protection — internal/private addresses are blocked by default.

## Requirements

- Python 3.10+
- A Groq API key (free at https://console.groq.com) — **or** [Ollama](https://ollama.ai) running locally
- A working microphone (for voice mode)
- Optional: nmap, nikto, hydra, sqlmap, gobuster, ffuf, msfconsole for pentest tools

## Quick Start

```bash
git clone https://github.com/Nikesh3001/jarvis.git
cd jarvis
pip install -r requirements.txt
python setup_keys.py          # Configure your API key securely
python jarvis.py              # Launch in text mode
python jarvis.py -cyber       # Launch cybersecurity console
python -m web.server          # Launch web dashboard on :8080
python -m web.cyber_server    # Launch cyber web UI on :8081
```

## Security

This system has near-total control of the PC (keyboard/mouse automation, full filesystem, clipboard, screenshots). Security is a top priority:

| Layer | Protection |
|-------|-----------|
| **Safe Mode** | Default ON — blocks clipboard, screenshots, msfvenom, automator actions. Requires typed username + "YES DANGER" to disable |
| **API Auth** | All web endpoints require `FRIDAY_API_KEY` env var or query param `api_key` |
| **SSRF Protection** | DNS/rebinding-aware validation blocks requests to private/internal IPs |
| **Shell Injection** | No `shell=True` — all subprocess calls use argument lists. Blocklist of 20+ dangerous patterns |
| **Code Sandbox** | AST-level analysis blocks dangerous modules, meta-programming, and runtime exploits |
| **Plugin Integrity** | SHA-256 hash cache with HMAC verification detects tampering between loads |
| **Rate Limiting** | Token-bucket per operation — persisted with HMAC integrity to `.rate_state` |
| **Conversation Encryption** | Fernet (AES) encrypted sessions with key from `.conversation_key` — API keys/passwords redacted before storage |
| **Credential Management** | API keys stored in Windows Credential Manager or macOS Keychain — config.json is fallback only |
| **Path Traversal** | All file operations resolve through `os.path.realpath` and validate against allowed roots |
| **Git URL Safety** | Only HTTPS allowed for clone/remote — injection patterns and ext:: protocol blocked |

## Configuration

API keys are stored securely via `setup_keys.py`:
```bash
python setup_keys.py
```
Keys are stored first in OS keychain (Windows Credential Manager / macOS Keychain), with config.json as encrypted fallback.

For Ollama local mode, set `"provider": "ollama"` in `config.json`:
```json
{
  "provider": "ollama",
  "models": {
    "fast": "phi4-mini:latest",
    "smart": "qwen3:latest"
  }
}
```

## Architecture

```
jarvis/
├── core/              # Assistant, Brain (Groq/Ollama), Speech, SSRF, Ratelimit, Plugins, Multi-agent
├── tools/             # System, Shell, Code Interpreter, File Editor, Languages, Git, Security,
│                      # Internet, Scraper, Automator, Web, Files, Planner, News, Stocks, Report
├── web/               # FastAPI dashboard (+ cyber web UI with static assets)
├── memory/            # Vector store, code indexer, conversation history
├── plugins/           # Python hot-load plugins
└── conversations/     # Encrypted session storage
```

## Commands

| Say / Type | Action |
|------------|--------|
| "Hey Jarvis" / "Hey Friday" | Wake up |
| "Open Chrome" / "Screenshot" | System tasks |
| "System info" / "Running processes" | System monitoring |
| "Safe mode on" / "Safe mode off" | Toggle safety |
| "List models" | Switch AI model |
| "Help" | Show all commands |
| "Goodbye" / "Exit" | Shut down |
| `python jarvis.py -cyber` | Launch pentest console |
