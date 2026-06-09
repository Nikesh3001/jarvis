# Jarvis Security Notes — Audit 2026-06-07

**Risk Rating: CRITICAL** — Jarvis has near-total control of your system.

---

## What Jarvis Can Access

### 🖥️ OS / System (full access)
| Tool | File | What it does |
|------|------|--------------|
| `get_cpu`, `get_memory`, `get_disk`, `get_battery` | `tools/system.py:18-44` | Reads CPU %, RAM, disk usage, battery |
| `get_network`, `get_active_connections` | `tools/system.py:59-73,600-613` | Lists network IPs, active TCP connections with remote IPs |
| `get_processes`, `kill_process` | `tools/system.py:75-106` | Lists top CPU processes, **terminates any process by name** |
| `start_process` | `tools/system.py:108-121` | **Launches ANY executable or file** |
| `take_screenshot` | `tools/system.py:123-150` | Captures full screen |
| `get_clipboard`, `set_clipboard` | `tools/system.py:177-199` | **Reads/writes clipboard** (passwords, tokens) |
| `list_wifi`, `wifi_status` | `tools/system.py:313-371` | Enumerates WiFi profiles, shows connection status |
| `get_services`, `get_startup_programs` | `tools/system.py:522-577` | Lists running services, startup programs |
| `lock_workstation` | `tools/system.py:452-464` | Locks the PC |
| `find_installed_app` | `tools/system.py:653-713` | Searches Registry, PATH, Start Menu for installed software |

### ⌨️ GUI Automation (full control)
| Tool | File | What it does |
|------|------|--------------|
| `send_keys`, `press_key`, `hotkey` | `tools/automator.py` | **Simulates keyboard** — can type into any window, press any key combo |
| `click`, `scroll` | `tools/automator.py` | **Controls mouse** — clicks anywhere on screen |
| `launch_app` | `tools/automator.py` | Launches any app by name or path |
| `browse_url` | `tools/automator.py` | Opens URLs in Chrome (including `file:///`) |

GUI automation is gated by **Safe Mode** (enabled by default) which requires the user to say "safe mode off" or "trust me" to disable.

### 🐚 Shell / Script Execution
| Tool | File | What it does |
|------|------|--------------|
| `run_command`, `run_shell` | `tools/shell.py` | **Executes arbitrary OS commands** through PowerShell |
| `run_powershell` | `tools/shell.py` | Runs PowerShell commands directly |
| `run_script` (python/bash/powershell/batch/javascript) | `tools/shell.py` | **Writes code to disk and executes via interpreter** |

**Protection:** A 70-pattern blocklist regex blocks destructive commands (rm -rf, shutdown, diskpart, etc.) but is **bypassable**.

### 📄 Files (full read/write/delete under C:\Users\nikes)
| Tool | File | What it does |
|------|------|--------------|
| `read_file` | `tools/files.py` | Reads text files, PDFs, DOCX, images (OCR), spreadsheets |
| `write_file`, `edit_file`, `append_file` | `tools/file_editor.py` | **Creates/modifies any file** under home directory |
| `delete_file` | `tools/file_editor.py` | **Permanently deletes files or directories** (recursive) |
| `copy_file`, `move_file` | `tools/file_editor.py` | Copies/moves files or directories |
| `grep_files` | `tools/file_editor.py` | Searches file contents for text patterns (could find secrets) |

**Protection:** Path allowlist restricts all operations to `C:\Users\nikes`. Symlink race detection on critical operations.

### 🌐 Network
| Tool | File | What it does |
|------|------|--------------|
| `web_search` | `tools/web.py` | DuckDuckGo search |
| `web_fetch` | `tools/web.py` | Fetches any HTTP/HTTPS URL |
| `scrape_url`, `extract_links`, `check_site_status` | `tools/scraper.py` | Scrapes/extracts content from any URL |
| `git_clone`, `git_push`, `git_pull` | `tools/git_ops.py` | Clones/pushes/pulls git repos (can exfiltrate data) |

**Protection:** SSRF module blocks private IPs (RFC 1918, loopback, link-local) and cloud metadata endpoints. DNS rebinding detection (requires `dnspython`).

### 🐍 Python Sandbox (run_code)
| File | Lines | What it allows |
|------|-------|----------------|
| `tools/code_interpreter.py` | 36-160 | Executes Python in restricted sandbox |

**Protection:** AST-level scan blocks dangerous modules (os, subprocess, socket, ctypes). Custom `__import__` only allows ~35 safe modules. **Non-Python scripts bypass this entirely.**

### 🧩 Plugins & MCP Servers
| System | File | What it can do |
|--------|------|----------------|
| Plugin loader | `core/plugin_manager.py` | **Executes any Python code** from `plugins/*.py` |
| MCP servers | `core/mcp_client.py` | Spawns subprocesses (node, npx, python, deno, bun) |

**Protection:** Plugin ownership check fails silently on Windows (no protection there). MCP command allowlist but `npx` and `python` are inherently dangerous.

---

## API Keys & Credentials

| Key | Where stored | Encryption |
|-----|-------------|------------|
| Groq | `config.json` → `providers.groq.api_key` | **PLAINTEXT** |
| OpenAI | `config.json` → `providers.openai.api_key` | **PLAINTEXT** |
| Anthropic | `config.json` → `providers.anthropic.api_key` | **PLAINTEXT** |
| Gemini | `config.json` → `providers.gemini.api_key` | **PLAINTEXT** |
| Conversation key | `.conversation_key` | **PLAINTEXT** (it IS the key) |

**Risk:** Anyone with user-level access (or malware running as user) can read all API keys from `config.json`.

---

## Network Endpoints Contacted

| Endpoint | Module | Purpose |
|----------|--------|---------|
| `api.groq.com` | `core/brain.py` | LLM inference |
| `api.openai.com` | `core/brain.py` | LLM inference |
| `api.anthropic.com` | `core/brain.py` | LLM inference |
| `generativelanguage.googleapis.com` | `core/brain.py` | LLM inference |
| `localhost:11434` | `core/brain.py` | Local Ollama LLM |
| `duckduckgo.com` | `tools/web.py` | Web search |
| `en.wikipedia.org` | `tools/news.py` | Wikipedia API |
| `news.google.com` | `tools/news.py` | Google News RSS |
| `query1.finance.yahoo.com` | `tools/stocks.py` | Yahoo Finance |
| Any user-supplied URL | `tools/web.py`, `tools/scraper.py` | Web fetch/scrape |
| Any git URL | `tools/git_ops.py` | Git operations |

---

## Data Stored on Disk

| Path | Data | Encryption | Risk |
|------|------|-----------|------|
| `config.json` | API keys (Groq, OpenAI, Anthropic, Gemini) | None → **PLAINTEXT** | 🔴 Critical |
| `.conversation_key` | Fernet encryption key | None → **PLAINTEXT** | 🔴 Critical |
| `conversations/session_*.json` | Chat history | Fernet (key is local) | 🟡 Medium |
| `memory_store/` | Vector embeddings of remembered data | None | 🟡 Medium |
| `code_index/` | Source code index | None | 🟡 Medium |
| `user_profile.json` | Preferences, request history, usage stats | None | 🟢 Low |
| `plans/plan_*.json` | Plan data | None | 🟢 Low |

---

## Key Security Gaps

### 🔴 Critical
1. **API keys in plaintext** — `config.json` stores all 4 API keys unencrypted
2. **Encryption key unsecured** — `.conversation_key` sits next to the data it encrypts
3. **Plugins on Windows are unchecked** — any `.py` file in `plugins/` is loaded and executed
4. **Code indexer scans ANY path** — `index_project()` has no path restriction

### 🟡 High
5. **Shell blocklist is bypassable** — use `${HOME}`, command substitution, URL encoding
6. **Non-Python scripts bypass sandbox** — `run_script("batch")` or `run_script("javascript")` has no restrictions
7. **Safe mode is voice-disableable** — user can say "safe mode off" to disable all GUI automation guards
8. **Git push can exfiltrate** — data can be pushed to attacker repos
9. **No authentication** — anyone with microphone or keyboard access controls the system

### 🟢 Medium/Low
10. **Clipboard access unrestricted** — never gated by safe mode
11. **Process killer has no protections** — can terminate security software
12. **Port scanning localhost available** — service discovery
13. **DNS rebinding check requires optional library** — without `dnspython`, check is skipped
14. **Rate limits are per-process** — reset on restart

---

## Recommended Mitigations

1. **Run `python setup_keys.py`** to store keys with restricted permissions
2. **Use Windows Credential Manager** instead of config.json for API keys
3. **Be cautious what you say in voice mode** — LLM can trigger destructive actions
4. **Keep Safe Mode ON** unless you explicitly need GUI automation
5. **Audit `plugins/` directory** regularly for unexpected files
6. **Monitor `conversations/` and `memory_store/`** for sensitive data leakage
7. **Don't store passwords in clipboard** while Jarvis is running
