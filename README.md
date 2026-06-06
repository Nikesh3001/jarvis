# JARVIS • FRIDAY — Terminal AI Assistant

A dual-personality voice AI assistant for your terminal. Powered by **Ollama** (local models).

## Features

- **Dual AI**: JARVIS (male voice) / FRIDAY (female voice) — switch anytime
- **Local AI**: Uses Ollama models (phi4-mini, qwen3) — no internet needed for AI
- **Voice Input**: Speak naturally, wake words "Hey Jarvis" / "Hey Friday"
- **Voice Output**: Natural TTS via Microsoft Edge voices
- **System Control**: Open apps, take screenshots, control volume, run commands
- **System Monitoring**: CPU, RAM, disk, processes, network info
- **Permission System**: Sensitive actions ask for approval
- **Legal & Ethical**: No destructive actions without consent

## Requirements

- Python 3.10+
- [Ollama](https://ollama.ai) running locally with at least one model
- A working microphone

## Install

```bash
cd jarvis
pip install -r requirements.txt
```

## Run

```bash
python jarvis.py
```

## Usage

| Say | Action |
|-----|--------|
| "Hey Jarvis" / "Hey Friday" | Wake up |
| "Open chrome" / "Screenshot" | System tasks |
| "System info" / "Running processes" | Monitor |
| "Search Python tutorials" | Web search |
| "Switch to Friday" / "Change voice" | Toggle mode |
| "List models" | Switch Ollama model |
| "Help" | Show commands |
| "Goodbye" | Exit |

## Configuration

Edit `config.json` to set default model:
```json
{"model": "phi4-mini:latest"}
```
