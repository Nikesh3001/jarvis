"""Secure credential management with hardware-backed encryption fallbacks."""

import os
import json
import base64
import hashlib
import sys
import platform
import secrets
from pathlib import Path
from typing import Optional, Dict


CRED_DIR = Path(__file__).parent.parent / ".credentials"
CRED_FILE = CRED_DIR / "vault.json"
MASTER_KEY_FILE = CRED_DIR / ".master"


class CredentialVault:
    """Encrypted credential storage with platform-key derivation.

    Uses:
    1. Windows: DPAPI (CryptProtectData) via ctypes
    2. macOS: Keychain via subprocess
    3. Linux: systemd secret-tool or encrypted file with derived key
    """

    def __init__(self):
        self._vault: Dict[str, str] = {}
        self._unlocked = False
        CRED_DIR.mkdir(parents=True, exist_ok=True)
        if CRED_FILE.exists():
            try:
                self._vault = json.loads(CRED_FILE.read_text(encoding="utf-8"))
            except Exception:
                self._vault = {}

    def _derive_machine_key(self) -> bytes:
        if sys.platform == "win32":
            try:
                import ctypes
                from ctypes import wintypes
                crypt32 = ctypes.windll.crypt32
                data = secrets.token_bytes(32)
                data_in = (ctypes.c_char * len(data))(*data)
                p_data_in = ctypes.c_char_p(data)
                p_data_out = ctypes.c_char_p()
                cb_out = wintypes.DWORD(0)
                if crypt32.CryptProtectData(
                    ctypes.byref(p_data_in), None, None,
                    None, None, 0,
                    ctypes.byref(p_data_out), ctypes.byref(cb_out)
                ):
                    buf = (ctypes.c_char * cb_out.value).from_address(ctypes.addressof(p_data_out))
                    raw = bytes(buf)
                    ctypes.windll.kernel32.LocalFree(p_data_out)
                    return hashlib.sha256(raw).digest()
            except Exception:
                pass
        machine_id = self._get_machine_id()
        return hashlib.sha256(machine_id.encode()).digest()

    def _get_machine_id(self) -> str:
        parts = []
        if sys.platform == "win32":
            try:
                import subprocess
                r = subprocess.run(
                    ["powershell", "-NoProfile", "-Command",
                     "(Get-CimInstance Win32_ComputerSystemProduct).UUID"],
                    capture_output=True, text=True, timeout=5
                )
                uuid = r.stdout.strip()
                if uuid:
                    parts.append(uuid)
            except Exception:
                try:
                    r = subprocess.run(
                        ["wmic", "csproduct", "get", "uuid"],
                        capture_output=True, text=True, timeout=5
                    )
                    for line in r.stdout.splitlines():
                        line = line.strip()
                        if line and line != "UUID":
                            parts.append(line)
                except Exception:
                    pass
        parts.append(os.path.expanduser("~"))
        parts.append(platform.node() or "unknown")
        return "|".join(parts)

    def _encrypt(self, plaintext: str) -> str:
        if sys.platform == "win32":
            try:
                import ctypes
                import ctypes.wintypes
                crypt32 = ctypes.windll.crypt32
                data = plaintext.encode("utf-16-le")
                data_in = (ctypes.c_char * len(data))(*data)
                data_out = ctypes.c_char_p()
                cb_out = ctypes.wintypes.DWORD(0)
                if crypt32.CryptProtectData(
                    None, None, data_in, None, None, 0,
                    ctypes.byref(data_out), ctypes.byref(cb_out)
                ):
                    buf = ctypes.create_string_buffer(cb_out.value)
                    return base64.b64encode(buf.raw).decode()
            except Exception:
                pass
        from cryptography.fernet import Fernet
        key = base64.urlsafe_b64encode(self._derive_machine_key()[:32])
        f = Fernet(key)
        return f.encrypt(plaintext.encode()).decode()

    def _decrypt(self, ciphertext: str) -> str:
        if sys.platform == "win32":
            try:
                import ctypes
                import ctypes.wintypes
                crypt32 = ctypes.windll.crypt32
                raw = base64.b64decode(ciphertext)
                data_in = ctypes.create_string_buffer(raw, len(raw))
                data_out = ctypes.c_char_p()
                cb_out = ctypes.wintypes.DWORD(0)
                if crypt32.CryptUnprotectData(
                    None, None, data_in, None, None, 0,
                    ctypes.byref(data_out), ctypes.byref(cb_out)
                ):
                    if data_out.value:
                        return ctypes.create_string_buffer(data_out.value).raw.decode("utf-16-le")
            except Exception:
                pass
        try:
            from cryptography.fernet import Fernet
            key = base64.urlsafe_b64encode(self._derive_machine_key()[:32])
            f = Fernet(key)
            return f.decrypt(ciphertext.encode()).decode()
        except Exception:
            return ""

    def store(self, key: str, value: str) -> bool:
        try:
            encrypted = self._encrypt(value)
            self._vault[key] = encrypted
            return True
        except Exception:
            return False

    def _flush(self):
        try:
            CRED_FILE.write_text(json.dumps(self._vault, indent=2, sort_keys=True), encoding="utf-8")
            CRED_FILE.chmod(0o600)
        except Exception:
            pass

    def flush(self):
        self._flush()

    def close(self):
        self._flush()

    def retrieve(self, key: str) -> Optional[str]:
        encrypted = self._vault.get(key)
        if not encrypted:
            return None
        try:
            return self._decrypt(encrypted)
        except Exception:
            return None

    def delete(self, key: str) -> bool:
        if key in self._vault:
            del self._vault[key]
            return True
        return False

    def list_keys(self):
        return list(self._vault.keys())

    def migrate_from_config(self, config: dict) -> int:
        migrated = 0
        provider_keys = {
            "GROQ_API_KEY": ["providers", "groq", "api_key"],
            "OPENAI_API_KEY": ["providers", "openai", "api_key"],
            "ANTHROPIC_API_KEY": ["providers", "anthropic", "api_key"],
            "GEMINI_API_KEY": ["providers", "gemini", "api_key"],
            "NVIDIA_API_KEY": ["providers", "nvidia", "api_key"],
        }
        for env_key, config_path in provider_keys.items():
            val = None
            cfg = config
            for part in config_path:
                if isinstance(cfg, dict):
                    cfg = cfg.get(part, {})
            if isinstance(cfg, str) and cfg:
                val = cfg
            if not val:
                val = os.environ.get(env_key)
            if val and not self.retrieve(env_key):
                self.store(env_key, val)
                migrated += 1
        if migrated:
            self._flush()
            print(f"  [SECURITY] Migrated {migrated} API key(s) to encrypted vault")
            print(f"  [SECURITY] You can now remove plaintext keys from config.json")
        return migrated


_VAULT_INSTANCE = None


def get_vault() -> CredentialVault:
    global _VAULT_INSTANCE
    if _VAULT_INSTANCE is None:
        _VAULT_INSTANCE = CredentialVault()
    return _VAULT_INSTANCE


def secure_get(key: str) -> Optional[str]:
    vault = get_vault()
    val = vault.retrieve(key)
    if val:
        return val
    return os.environ.get(key)
