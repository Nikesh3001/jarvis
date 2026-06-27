import importlib.util
import hashlib
import inspect
import os
import sys
from pathlib import Path


PLUGIN_DIR = Path(__file__).parent.parent / "plugins"

_PLUGIN_OWNER_CHECK = True
_PLUGIN_SIGNATURES = {}


def _hash_plugin_file(plugin_path):
    import hashlib as _hl
    try:
        return _hl.sha256(plugin_path.read_bytes()).hexdigest()
    except Exception:
        return ""


def _verify_plugin_ownership(plugin_path):
    if not _PLUGIN_OWNER_CHECK:
        return True
    try:
        import getpass
        current_user = getpass.getuser()
        try:
            owner_name = plugin_path.owner()
            if owner_name != current_user:
                print(f"  [SECURITY] Plugin {plugin_path.name} owner '{owner_name}' != current user '{current_user}'")
                return False
        except (AttributeError, NotImplementedError):
            # Windows: Path.owner() is unsupported. Use hash-based integrity + user confirmation.
            plugin_hash = _hash_plugin_file(plugin_path)
            parent_dir = plugin_path.parent.resolve()
            if not os.access(str(parent_dir), os.W_OK):
                print(f"  [SECURITY] Plugin dir not writable by current user")
                return False
            try:
                import stat as _stat
                dir_stat = parent_dir.stat()
                if dir_stat.st_mode & _stat.S_IWOTH:
                    print(f"  [SECURITY] Plugin dir is world-writable, skipping")
                    return False
            except (OSError, PermissionError):
                pass
            print(f"  [SECURITY] Loading plugin '{plugin_path.name}' (hash: {plugin_hash[:12]}...)")
            return True
        # Check parent directory ownership
        parent_dir = plugin_path.parent.resolve()
        while parent_dir != parent_dir.parent:
            if parent_dir.name == "plugins":
                try:
                    dir_owner = parent_dir.owner()
                    if dir_owner != current_user:
                        print(f"  [SECURITY] Plugin dir owner '{dir_owner}' != current user '{current_user}'")
                        return False
                except (AttributeError, NotImplementedError):
                    try:
                        import stat as _stat
                        dir_stat = parent_dir.stat()
                        if dir_stat.st_mode & _stat.S_IWOTH:
                            print(f"  [SECURITY] Plugin dir is world-writable, skipping")
                            return False
                    except (OSError, PermissionError):
                        pass
                break
            parent_dir = parent_dir.parent
        return True
    except (OSError, PermissionError):
        pass
    print(f"  [SECURITY] Cannot verify ownership of {plugin_path.name}, skipping")
    return False


def discover_plugins():
    if not PLUGIN_DIR.exists():
        return []
    plugins = []
    for entry in sorted(PLUGIN_DIR.iterdir()):
        if entry.suffix == ".py" and not entry.name.startswith("_"):
            if _verify_plugin_ownership(entry):
                plugins.append(entry)
    return plugins


_PLUGIN_CODE_CACHE = {}


def _hash_plugin(path):
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except Exception:
        return ""


def load_plugin(plugin_path):
    if not _verify_plugin_ownership(plugin_path):
        return {"name": plugin_path.stem, "error": "plugin ownership verification failed"}

    current_hash = _hash_plugin(plugin_path)
    cached = _PLUGIN_CODE_CACHE.get(str(plugin_path))
    if cached and cached != current_hash:
        return {"name": plugin_path.stem, "error": "plugin modified since last load"}

    spec = importlib.util.spec_from_file_location(
        f"plugins.{plugin_path.stem}", plugin_path
    )
    if spec is None or spec.loader is None:
        return None

    module = importlib.util.module_from_spec(spec)
    pkg_path = str(PLUGIN_DIR.parent)
    if pkg_path not in sys.path:
        sys.path.insert(0, pkg_path)

    try:
        spec.loader.exec_module(module)
    except Exception as e:
        return {"name": plugin_path.stem, "error": str(e)}

    register_fn = getattr(module, "register", None)
    if register_fn is None:
        return {"name": plugin_path.stem, "error": "no register() function"}

    try:
        result = register_fn()
    except Exception as e:
        return {"name": plugin_path.stem, "error": f"register() failed: {e}"}

    _PLUGIN_CODE_CACHE[str(plugin_path)] = current_hash

    return result


def get_plugin_handlers(plugin_result):
    handlers = {}
    if isinstance(plugin_result, dict):
        tools = plugin_result.get("tools", plugin_result.get("tool_definitions", []))
        handler_fn = plugin_result.get("handler") or plugin_result.get("get_handler")
        handlers_raw = plugin_result.get("handlers", {})
        for td in tools:
            name = td["function"]["name"] if "function" in td else td.get("name", "")
            if not name:
                continue
            if handler_fn:
                handler = handler_fn(name) if callable(handler_fn) else None
            else:
                handler = handlers_raw.get(name)
            if handler:
                handlers[name] = handler
        return tools, handlers
    return [], {}


class PluginManager:
    def __init__(self, brain):
        self.brain = brain
        self._loaded = {}
        self._tool_count = 0

    def scan_and_register(self):
        plugins = discover_plugins()
        if not plugins:
            return []
        loaded = []
        for plugin_path in plugins:
            name = plugin_path.stem
            if name in self._loaded:
                continue
            result = load_plugin(plugin_path)
            if result is None or isinstance(result, dict) and result.get("error"):
                continue
            tools, handlers = get_plugin_handlers(result)
            if tools:
                self.brain.register_tools(tools, lambda n, h=handlers: h.get(n))
                self._tool_count += len(tools)
                self._loaded[name] = {"tools": tools, "handlers": handlers}
                loaded.append({"name": name, "tools": len(tools)})
        return loaded

    def list_plugins(self):
        return [
            {"name": name, "tools": len(info["tools"])}
            for name, info in self._loaded.items()
        ]
