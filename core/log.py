"""Structured logging with rotation, levels, and optional JSON output."""

import os
import sys
import json
import time
import logging
import threading
from pathlib import Path
from typing import Optional
from datetime import datetime


_LOG_DIR = Path(__file__).parent.parent / "logs"
_LOG_FILE = _LOG_DIR / "jarvis.log"
_MAX_BYTES = 10 * 1024 * 1024
_BACKUP_COUNT = 5

_LEVEL_MAP = {
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARN": logging.WARNING,
    "ERROR": logging.ERROR,
    "CRITICAL": logging.CRITICAL,
}

_LOG_INIT_LOCK = threading.Lock()
_LOGGER: Optional[logging.Logger] = None


class JSONFormatter(logging.Formatter):
    def format(self, record):
        log_entry = {
            "timestamp": datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "line": record.lineno,
        }
        if hasattr(record, "extra"):
            log_entry["extra"] = record.extra
        if record.exc_info and record.exc_info[0]:
            log_entry["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_entry)


class ConsoleFormatter(logging.Formatter):
    COLORS = {
        "DEBUG": "\033[36m",
        "INFO": "\033[32m",
        "WARNING": "\033[33m",
        "ERROR": "\033[31m",
        "CRITICAL": "\033[41m",
    }
    RESET = "\033[0m"

    def format(self, record):
        color = self.COLORS.get(record.levelname, "")
        ts = datetime.fromtimestamp(record.created).strftime("%H:%M:%S")
        return f"{color}[{ts}] [{record.levelname:^8}] {record.getMessage()}{self.RESET}"


def _rotating_write(path: Path, text: str):
    """Simple log rotation - rotate if file exceeds max bytes."""
    if path.exists() and path.stat().st_size > _MAX_BYTES:
        for i in range(_BACKUP_COUNT - 1, 0, -1):
            backup = path.with_suffix(f".{i}.log")
            prev = path.with_suffix(f".{i - 1}.log" if i > 1 else ".log")
            if backup.exists():
                backup.unlink()
            if prev.exists():
                prev.rename(backup)
        path.rename(path.with_suffix(".1.log"))
    with path.open("a", encoding="utf-8") as f:
        f.write(text + "\n")


class DualHandler(logging.Handler):
    """Writes to both rotating log file and console."""

    def __init__(self, json_output: bool = False):
        super().__init__()
        self.json_output = json_output
        _LOG_DIR.mkdir(parents=True, exist_ok=True)

    def emit(self, record):
        try:
            if self.json_output:
                fmt = JSONFormatter()
                formatted = fmt.format(record)
            else:
                fmt = ConsoleFormatter()
                formatted = fmt.format(record)
            _rotating_write(_LOG_FILE, formatted)
            if record.levelno >= logging.WARNING or not self.json_output:
                print(formatted, file=sys.stderr if record.levelno >= logging.WARNING else sys.stdout)
        except Exception:
            pass


def get_logger(name: str = "jarvis", level: str = "INFO", json_output: bool = False) -> logging.Logger:
    global _LOGGER
    with _LOG_INIT_LOCK:
        if _LOGGER is not None:
            return _LOGGER.getChild(name)

        logger = logging.getLogger(name)
        logger.setLevel(_LEVEL_MAP.get(level.upper(), logging.INFO))
        logger.handlers.clear()

        handler = DualHandler(json_output=json_output)
        logger.addHandler(handler)

        _LOGGER = logger
        return logger


def set_level(level: str):
    lvl = _LEVEL_MAP.get(level.upper(), logging.INFO)
    if _LOGGER:
        _LOGGER.setLevel(lvl)


log = get_logger()
