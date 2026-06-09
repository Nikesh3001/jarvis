#!/usr/bin/env python3
"""Secure API Key Setup for FRIDAY.

Stores keys in config.json with restricted file permissions.
On Windows: uses icacls to restrict to current user only.
On Unix: uses chmod 600.

WARNING: config.json stores keys in plaintext. For production use,
consider Windows Credential Manager or a keyring library.
"""
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


def _load_config():
    if CONFIG_PATH.exists():
        try:
            return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def _save_config(config):
    CONFIG_PATH.write_text(json.dumps(config, indent=2), encoding="utf-8")
    _restrict_permissions()


def _restrict_permissions():
    """Restrict config.json to current user only."""
    try:
        if sys.platform == "win32":
            user = os.environ.get("USERNAME", "")
            if user:
                cmd = [
                    "icacls", str(CONFIG_PATH),
                    "/inheritance:r",
                    "/grant", f"{user}:(R,W)"
                ]
                subprocess.run(cmd, capture_output=True, text=True, timeout=10)
                print(f"  [OK] Permissions restricted to user '{user}' only")
        else:
            import stat
            CONFIG_PATH.chmod(stat.S_IRUSR | stat.S_IWUSR)  # 600
            print("  [OK] Permissions restricted to owner only (600)")
    except Exception as e:
        print(f"  [WARN] Could not restrict permissions: {e}")
        print(f"  [WARN] Manually set config.json permissions to user-only")


def _get_apikey_from_config(service):
    config = _load_config()
    provider = PROVIDER_MAP.get(service)
    if provider and provider in config.get("providers", {}):
        return config["providers"][provider].get("api_key")
    return config.get("api_key")


def main():
    print()
    print("  =====================================================")
    print("   FRIDAY - Secure API Key Setup")
    print("  =====================================================")
    print()
    print("  Keys are stored in config.json with restricted")
    print("  file permissions (user-only read/write).")
    print()
    print("  WARNING: config.json stores keys in PLAINTEXT.")
    print("  For better security, use Windows Credential Manager")
    print("  or a keyring library in production.")
    print()

    config = _load_config()

    existing_any = any(_get_apikey_from_config(service) for service, _ in SERVICES)

    if existing_any:
        print()
        resp = input("  Keys already exist. Overwrite any? (y/N): ").strip().lower()
        if resp != "y":
            print("  No changes made.")
            print()
            return

    print()
    for env_var, desc in SERVICES:
        current = _get_apikey_from_config(env_var)
        if current:
            print(f"  [{env_var}] Current: stored")
        else:
            print(f"  [{env_var}] Current: not set")

        val = input(f"  Enter key for {desc} (or press Enter to skip): ").strip()
        if val:
            # Basic validation: Groq keys start with gsk_
            if env_var == "GROQ_API_KEY" and not val.startswith("gsk_"):
                print(f"  [WARN] Groq API keys typically start with 'gsk_'. Check your key.")

            provider = PROVIDER_MAP.get(env_var)
            if provider:
                if "providers" not in config:
                    config["providers"] = {}
                if provider not in config["providers"]:
                    config["providers"][provider] = {}
                config["providers"][provider]["api_key"] = val
            else:
                config["api_key"] = val
            try:
                _save_config(config)
                print(f"  [OK] {env_var} stored in config.json (restricted permissions)")
            except Exception as e:
                print(f"  [FAIL] Could not store {env_var}: {e}")
        print()

    print("  =====================================================")
    print("  Verification:")
    config = _load_config()
    for env_var, _ in SERVICES:
        val = _get_apikey_from_config(env_var)
        if val:
            masked = val[:8] + "..." + val[-4:]
            print(f"  [OK] {env_var} = {masked}")
        else:
            print(f"  [--] {env_var} not set")
    print("  =====================================================")
    print()


if __name__ == "__main__":
    main()
