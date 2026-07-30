import os
import json
import base64
import hashlib
import sys
import platform as _platform
import secrets
from pathlib import Path
from typing import Optional, Dict


CRED_DIR = Path(__file__).parent.parent / ".credentials"
CRED_FILE = CRED_DIR / "vault.json"
MASTER_KEY_FILE = CRED_DIR / ".master"


class CredentialVault:
    def __init__(self):
        self._vault: Dict[str, str] = {}
        self._unlocked = False
        CRED_DIR.mkdir(parents=True, exist_ok=True)
        if CRED_FILE.exists():
            try:
                self._vault = json.loads(CRED_FILE.read_text(encoding="utf-8"))
            except Exception:
                self._vault = {}

    def _get_machine_id(self) -> str:
        parts = []
        hostname = _platform.node() or "unknown"
        user_home = os.path.expanduser("~")
        parts.append(hostname)
        parts.append(user_home)
        try:
            parts.append(str(os.stat(user_home).st_ino))
        except Exception:
            pass
        for p in ["/etc/machine-id", "/var/lib/dbus/machine-id"]:
            try:
                parts.append(Path(p).read_text().strip())
            except Exception:
                pass
        if sys.platform == "win32":
            try:
                r = __import__('subprocess').run(
                    ["powershell", "-NoProfile", "-Command",
                     "(Get-CimInstance Win32_ComputerSystemProduct).UUID"],
                    capture_output=True, text=True, timeout=5
                )
                if r.stdout.strip():
                    parts.append(r.stdout.strip())
            except Exception:
                pass
        return "|".join(parts)

    def _derive_machine_key(self) -> bytes:
        machine_id = self._get_machine_id()
        return hashlib.sha256(machine_id.encode()).digest()

    def _encrypt(self, plaintext: str) -> str:
        from cryptography.fernet import Fernet
        key = base64.urlsafe_b64encode(self._derive_machine_key()[:32])
        f = Fernet(key)
        return f.encrypt(plaintext.encode()).decode()

    def _decrypt(self, ciphertext: str) -> str:
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
            self._flush()
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
