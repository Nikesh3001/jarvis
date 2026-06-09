import os
import sys
import subprocess
import tempfile
import ast
import io
import contextlib


FORBIDDEN_MODULES = {
    "os", "subprocess", "shutil", "socket", "ctypes", "signal",
    "multiprocessing", "threading", "importlib", "pkgutil", "pdb",
    "inspect", "code", "codeop", "compileall", "py_compile",
    "webbrowser", "antigravity", "turtle",
    "pathlib", "glob", "fnmatch",  # File system access
    "urllib", "urllib2", "httplib",  # Network access
    "_io", "codecs",  # Low-level I/O
}

FORBIDDEN_STRINGS = [
    "__import__", "__builtins__", "__subclasses__",
    "__class__", "__bases__", "__mro__", "__base__",
    "__globals__", "__code__", "__closure__", "__func__",
    "open(", "exec(", "eval(", "compile(",
    "getattr(", "setattr(", "delattr(",
    "os.", "subprocess.", "shutil.", "socket.", "ctypes.",
    "pathlib.", "glob.",  # File system access
    "__import__",  # Dynamic imports
    "globals(", "locals(",  # Scope inspection
    "vars(",  # Variable inspection
]

DANGEROUS_NAMES = {
    "exec", "eval", "compile", "__import__", "open",
    "input", "breakpoint", "help",
    "getattr", "setattr", "delattr",  # Attribute manipulation
    "globals", "locals", "vars",  # Scope inspection
}


class SandboxError(Exception):
    pass


def _check_code_safety(code):
    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        raise SandboxError(f"Syntax error: {e}")

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                module = alias.name.split(".")[0]
                if module in FORBIDDEN_MODULES:
                    raise SandboxError(f"Module '{alias.name}' is not allowed in sandbox")
        elif isinstance(node, ast.ImportFrom):
            module = node.module.split(".")[0] if node.module else ""
            if module in FORBIDDEN_MODULES:
                raise SandboxError(f"Module '{node.module}' is not allowed in sandbox")
        elif isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name) and node.func.id in DANGEROUS_NAMES:
                raise SandboxError(f"Function '{node.func.id}()' is not allowed in sandbox")
            if isinstance(node.func, ast.Attribute):
                if isinstance(node.func.value, ast.Name) and node.func.value.id == "builtins":
                    raise SandboxError("Access to 'builtins' module is not allowed")
        elif isinstance(node, ast.Attribute):
            if isinstance(node.value, ast.Name) and node.value.id in ("os", "subprocess", "shutil", "socket", "ctypes"):
                raise SandboxError(f"Access to '{node.value.id}.{node.attr}' is not allowed")

    return tree



class CodeInterpreter:
    def __init__(self):
        self.timeout = 30

    def run_code(self, code):
        if not code or not code.strip():
            return "No code to execute."
        if len(code) > 10000:
            return "Code too long (max 10000 chars)."

        try:
            tree = _check_code_safety(code)
        except SandboxError as e:
            return f"Sandbox blocked: {e}"

        safe_modules = {
            "math", "cmath", "decimal", "fractions", "random", "statistics",
            "json", "base64", "binascii", "struct",
            "itertools", "functools", "operator", "collections", "heapq", "bisect",
            "re", "string", "textwrap", "difflib", "unicodedata",
            "datetime", "time", "calendar",
            "typing", "enum", "dataclasses", "abc",
            "copy", "pprint", "reprlib",
            "array", "queue",
            "hashlib", "uuid", "secrets",
            "statistics",
        }

        def safe_import(name, *args, **kwargs):
            base = name.split(".")[0]
            if base in FORBIDDEN_MODULES:
                raise SandboxError(f"Module '{name}' is not allowed in sandbox")
            if base not in safe_modules:
                raise SandboxError(f"Module '{name}' is not in the allowed safe list")
            return __import__(name, *args, **kwargs)

        safe_builtins = {
            "abs": abs, "all": all, "any": any, "ascii": ascii,
            "bin": bin, "bool": bool, "bytearray": bytearray, "bytes": bytes,
            "callable": callable, "chr": chr, "complex": complex,
            "dict": dict, "divmod": divmod,
            "enumerate": enumerate,
            "filter": filter, "float": float, "format": format, "frozenset": frozenset,
            "hash": hash, "hex": hex,
            "id": id, "int": int, "isinstance": isinstance,
            "iter": iter,
            "len": len, "list": list, "map": map,
            "max": max, "min": min,
            "next": next, "object": object, "oct": oct, "ord": ord,
            "pow": pow, "print": print, "property": property,
            "range": range, "repr": repr, "reversed": reversed, "round": round,
            "set": set, "slice": slice, "sorted": sorted, "str": str, "sum": sum,
            "tuple": tuple, "type": type,
            "zip": zip,
            "True": True, "False": False, "None": None,
            "__import__": safe_import,
        }

        restricted_globals = {
            "__builtins__": safe_builtins,
        }

        stdout_capture = io.StringIO()
        stderr_capture = io.StringIO()

        try:
            compiled = compile(tree, "<sandbox>", "exec")
            with contextlib.redirect_stdout(stdout_capture), contextlib.redirect_stderr(stderr_capture):
                exec(compiled, restricted_globals, {})

            out = []
            stdout_text = stdout_capture.getvalue().strip()
            stderr_text = stderr_capture.getvalue().strip()
            if stdout_text:
                out.append(f"Output:\n{stdout_text[:5000]}")
            if stderr_text:
                out.append(f"Stderr:\n{stderr_text[:2000]}")
            if not out:
                out.append("Code executed (no output).")
            return "\n".join(out)
        except SandboxError as e:
            return f"Sandbox blocked at runtime: {e}"
        except Exception as e:
            return f"Code error: {type(e).__name__}: {e}"

    def get_tool_definitions(self):
        return [
            {"type": "function", "function": {"name": "run_code", "description": "Sandboxed Python exec (no os/subprocess/socket/file I/O)", "parameters": {"type": "object", "properties": {"code": {"type": "string", "description": "Code"}}, "required": ["code"]}}},
        ]

    def get_handler(self, name):
        handlers = {
            "run_code": self.run_code,
        }
        return handlers.get(name)
