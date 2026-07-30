#!/usr/bin/env python3
import os
import sys
import json
import subprocess
from pathlib import Path

CONFIG_PATH = Path(__file__).parent / "config.json"

SERVICES = [
    ("GROQ_API_KEY", "Groq (https://console.groq.com/keys)"),
]

PROVIDER_MAP = {
    "GROQ_API_KEY": "groq",
}


def _get_config():
    if CONFIG_PATH.exists():
        try:
            return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def _save_config(config):
    CONFIG_PATH.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
    _restrict_permissions(CONFIG_PATH)
    print(f"  [OK] Saved config to {CONFIG_PATH}")


def _restrict_permissions(path):
    try:
        if sys.platform == "win32":
            import getpass
            user = getpass.getuser()
            cmd = ["icacls", str(path), "/inheritance:r", "/grant", f"{user}:(R,W)"]
            subprocess.run(cmd, capture_output=True, timeout=10)
        else:
            path.chmod(0o600)
    except Exception:
        pass


def _store_in_vault(env_key, value):
    from core.credentials import get_vault
    vault = get_vault()
    if vault.store(env_key, value):
        provider = PROVIDER_MAP.get(env_key)
        if provider:
            config = _get_config()
            if "providers" not in config:
                config["providers"] = {}
            if provider not in config["providers"]:
                config["providers"][provider] = {}
            config["providers"][provider]["api_key_env"] = env_key
            if env_key in config["providers"].get(provider, {}):
                del config["providers"][provider][env_key]
            _save_config(config)
        return True
    return False


def _retrieve_from_vault(env_key):
    from core.credentials import get_vault
    vault = get_vault()
    val = vault.retrieve(env_key)
    if val:
        return val
    return os.environ.get(env_key)


def setup_key(service_name, prompt_text):
    print(f"\n  [{service_name}]")
    current = _retrieve_from_vault(service_name)
    if current:
        masked = current[:4] + "*" * (len(current) - 8) + current[-4:] if len(current) > 12 else "***"
        print(f"    Current key: {masked}")
        choice = input("    Overwrite? (y/N): ").strip().lower()
        if choice != 'y':
            print("    Skipped.")
            return True
    key = input(f"    Enter API key for {prompt_text}: ").strip()
    if not key:
        print("    No key entered. Skipping.")
        return False
    if _store_in_vault(service_name, key):
        print(f"    {service_name} stored securely in encrypted vault.")
        return True
    print(f"    ERROR: Failed to store key.")
    return False


def auto_detect_keys():
    config = _get_config()
    migrated = 0
    provider_keys = {
        "GROQ_API_KEY": ["providers", "groq", "api_key"],
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
        if val:
            existing = _retrieve_from_vault(env_key)
            if not existing:
                _store_in_vault(env_key, val)
                migrated += 1
    if migrated:
        print(f"  [OK] Auto-migrated {migrated} API key(s) to encrypted vault")
    return migrated


def main():
    print("\n  ============ FRIDAY KEY SETUP ============")
    print("  | Secure API Key Storage (cross-platform) |")
    print("  ===========================================\n")

    migrated = auto_detect_keys()
    if migrated:
        print(f"  Found {migrated} existing key(s) and migrated them securely.\n")

    all_success = True
    for env_key, prompt_text in SERVICES:
        if not setup_key(env_key, prompt_text):
            all_success = False

    print("\n  Verification:")
    all_ok = True
    for env_key, prompt_text in SERVICES:
        val = _retrieve_from_vault(env_key)
        if val:
            masked = val[:4] + "*" * (len(val) - 8) + val[-4:] if len(val) > 12 else "***"
            print(f"    {env_key}: {masked} [OK]")
        else:
            print(f"    {env_key}: not set [WARN]")
            all_ok = False

    if all_ok:
        print("\n  All keys configured. You can now run FRIDAY.")
    else:
        print("\n  Some keys are missing. FRIDAY may not work fully.")

    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
