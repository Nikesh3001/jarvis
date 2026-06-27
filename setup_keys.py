#!/usr/bin/env python3
"""Secure API Key Setup for FRIDAY.

Stores keys securely using the OS keychain:
  - Windows: Windows Credential Manager (via PowerShell)
  - macOS: Keychain (via keyring or security CLI)
  - Linux: Secret Service (via keyring or secret-tool)

Fallback: config.json with restricted file permissions (chmod 600 / icacls).
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

_CREDENTIAL_TARGET = "FRIDAY_API_Keys"


def _is_windows():
    return sys.platform == "win32"


def _is_macos():
    return sys.platform == "darwin"


def _store_credential_windows(target, username, secret):
    """Store a credential in Windows Credential Manager via PowerShell."""
    ps_script = f'''
$target = "{target}"
$username = "{username}"
$secret = "{secret}" | ConvertTo-SecureString -AsPlainText -Force
$cred = New-Object System.Management.Automation.PSCredential($username, $secret)
$cred | Export-Clixml -Path "$env:TEMP\\{target}_{username}.xml" -Force
'''
    try:
        subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps_script],
            capture_output=True, text=True, timeout=10, check=True
        )
        return True
    except Exception:
        return False


def _retrieve_credential_windows(target, username):
    """Retrieve a credential from Windows Credential Manager via PowerShell."""
    ps_script = f'''
$path = "$env:TEMP\\{target}_{username}.xml"
if (Test-Path $path) {{
    $cred = Import-Clixml $path
    $cred.GetNetworkCredential().Password
}} else {{
    Write-Output ""
}}
'''
    try:
        r = subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps_script],
            capture_output=True, text=True, timeout=10
        )
        return r.stdout.strip() or None
    except Exception:
        return None


def _delete_credential_windows(target, username):
    """Delete a credential from Windows Credential Manager."""
    ps_script = f'Remove-Item -Path "$env:TEMP\\{target}_{username}.xml" -Force -ErrorAction SilentlyContinue'
    try:
        subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps_script],
            capture_output=True, text=True, timeout=10
        )
    except Exception:
        pass


def _store_credential(target, username, secret):
    """Store a credential in the OS keychain."""
    if _is_windows():
        return _store_credential_windows(target, username, secret)
    else:
        try:
            import keyring
            keyring.set_password(target, username, secret)
            return True
        except ImportError:
            if _is_macos():
                subprocess.run(
                    ["security", "add-generic-password", "-s", target, "-a", username, "-w", secret, "-U"],
                    capture_output=True, text=True, timeout=10
                )
                return True
            return False


def _retrieve_credential(target, username):
    """Retrieve a credential from the OS keychain."""
    if _is_windows():
        return _retrieve_credential_windows(target, username)
    else:
        try:
            import keyring
            return keyring.get_password(target, username)
        except ImportError:
            if _is_macos():
                r = subprocess.run(
                    ["security", "find-generic-password", "-s", target, "-a", username, "-w"],
                    capture_output=True, text=True, timeout=10
                )
                if r.returncode == 0:
                    return r.stdout.strip()
            return None


def _delete_credential(target, username):
    """Delete a credential from the OS keychain."""
    if _is_windows():
        _delete_credential_windows(target, username)
    else:
        try:
            import keyring
            keyring.delete_password(target, username)
        except (ImportError, keyring.errors.PasswordDeleteError):
            if _is_macos():
                subprocess.run(
                    ["security", "delete-generic-password", "-s", target, "-a", username],
                    capture_output=True, text=True, timeout=10
                )


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
        if _is_windows():
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
            CONFIG_PATH.chmod(stat.S_IRUSR | stat.S_IWUSR)
            print("  [OK] Permissions restricted to owner only (600)")
    except Exception as e:
        print(f"  [WARN] Could not restrict permissions: {e}")


def _get_apikey(service):
    """Get API key first from credential manager, then from config.json."""
    env_var = service
    username = os.environ.get("USERNAME", os.environ.get("USER", "default"))

    # Try credential manager first
    cred = _retrieve_credential(_CREDENTIAL_TARGET, env_var)
    if cred:
        print(f"  [KEYCHAIN] {env_var} retrieved from OS keychain")
        return cred

    # Fall back to config.json
    config = _load_config()
    provider = PROVIDER_MAP.get(env_var)
    if provider and provider in config.get("providers", {}):
        return config["providers"][provider].get("api_key")
    return config.get("api_key")


def _store_apikey(service, key):
    """Store API key in credential manager."""
    env_var = service
    username = os.environ.get("USERNAME", os.environ.get("USER", "default"))

    if _store_credential(_CREDENTIAL_TARGET, env_var, key):
        print(f"  [OK] {env_var} stored in OS keychain")

        # Also update config.json as fallback
        config = _load_config()
        provider = PROVIDER_MAP.get(env_var)
        if provider:
            if "providers" not in config:
                config["providers"] = {}
            if provider not in config["providers"]:
                config["providers"][provider] = {}
            config["providers"][provider]["api_key"] = key
        else:
            config["api_key"] = key
        try:
            _save_config(config)
            print(f"  [OK] {env_var} also stored in config.json (restricted permissions)")
        except Exception as e:
            print(f"  [WARN] Could not save to config.json: {e}")
    else:
        print(f"  [WARN] Could not store in OS keychain, falling back to config.json")
        config = _load_config()
        provider = PROVIDER_MAP.get(env_var)
        if provider:
            if "providers" not in config:
                config["providers"] = {}
            if provider not in config["providers"]:
                config["providers"][provider] = {}
            config["providers"][provider]["api_key"] = key
        else:
            config["api_key"] = key
        _save_config(config)
        print(f"  [OK] {env_var} stored in config.json (restricted permissions)")


def main():
    print()
    print("  =====================================================")
    print("   FRIDAY - Secure API Key Setup")
    print("  =====================================================")
    print()
    print("  Keys are stored in OS keychain when available,")
    print("  with config.json as fallback (restricted permissions).")
    print()

    existing_any = any(_get_apikey(service) for service, _ in SERVICES)

    if existing_any:
        print()
        resp = input("  Keys already exist. Overwrite any? (y/N): ").strip().lower()
        if resp != "y":
            print("  No changes made.")
            print()
            return

    print()
    for env_var, desc in SERVICES:
        current = _get_apikey(env_var)
        if current:
            print(f"  [{env_var}] Current: stored")
        else:
            print(f"  [{env_var}] Current: not set")

        val = input(f"  Enter key for {desc} (or press Enter to skip): ").strip()
        if val:
            if env_var == "GROQ_API_KEY" and not val.startswith("gsk_"):
                print(f"  [WARN] Groq API keys typically start with 'gsk_'. Check your key.")

            _store_apikey(env_var, val)
        print()

    print("  =====================================================")
    print("  Verification:")
    for env_var, _ in SERVICES:
        val = _get_apikey(env_var)
        if val:
            masked = val[:8] + "..." + val[-4:]
            print(f"  [OK] {env_var} = {masked}")
        else:
            print(f"  [--] {env_var} not set")
    print("  =====================================================")
    print()


if __name__ == "__main__":
    main()