import os
import sys
import subprocess
import tempfile
import ast
import json
import re


FORBIDDEN_MODULES = {
    "os", "subprocess", "shutil", "socket", "ctypes", "signal",
    "multiprocessing", "threading", "importlib", "pkgutil", "pdb",
    "inspect", "code", "codeop", "compileall", "py_compile",
    "webbrowser", "antigravity", "turtle",
    "pathlib", "glob", "fnmatch",
    "urllib", "urllib2", "httplib",
    "_io", "codecs",
}

FORBIDDEN_AST_PATTERNS = [
    "__import__", "__builtins__", "__subclasses__",
    "__class__", "__bases__", "__mro__", "__base__",
    "__globals__", "__code__", "__closure__", "__func__",
    "__getattribute__", "__getattr__", "__setattr__",
    "__reduce__", "__reduce_ex__", "__init__",
    "__format__", "__hash__",
]

DANGEROUS_NAMES = {
    "exec", "eval", "compile", "__import__", "open",
    "input", "breakpoint", "help",
    "getattr", "setattr", "delattr",
    "globals", "locals", "vars",
}

SAFE_MODULES = [
    "math", "cmath", "decimal", "fractions", "random", "statistics",
    "json", "base64", "binascii", "struct",
    "itertools", "functools", "operator", "collections", "heapq", "bisect",
    "re", "string", "textwrap", "difflib", "unicodedata",
    "datetime", "time", "calendar",
    "typing", "enum", "dataclasses", "abc",
    "copy", "pprint", "reprlib",
    "array", "queue",
    "hashlib", "uuid", "secrets",
]


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
                if isinstance(node.func.value, ast.Attribute):
                    chain = []
                    cur = node.func
                    while isinstance(cur, ast.Attribute):
                        chain.append(cur.attr)
                        cur = cur.value
                    if isinstance(cur, ast.Name) and cur.id == "type":
                        raise SandboxError("Meta-programming patterns are blocked")
                    if isinstance(cur, ast.Attribute) and any(p in chain for p in FORBIDDEN_AST_PATTERNS):
                        raise SandboxError("Meta-programming patterns are blocked")

    for forbidden in FORBIDDEN_AST_PATTERNS:
        pattern = re.compile(
            r'\(\s*\)\s*\.\s*(?:__getattribute__|__getattr__)\s*\('
            r'|\b' + re.escape(forbidden) + r'\b'
        )
        if pattern.search(code):
            raise SandboxError(f"Code contains forbidden pattern")

    return tree


class CodeInterpreter:
    def __init__(self):
        self.timeout = 10

    def run_code(self, code):
        if not code or not code.strip():
            return "No code to execute."
        if len(code) > 10000:
            return "Code too long (max 10000 chars)."

        try:
            _check_code_safety(code)
        except SandboxError as e:
            return f"Sandbox blocked: {e}"

        safe_mods = json.dumps(sorted(SAFE_MODULES))
        safe_builtins = json.dumps([
            'abs','all','any','bin','bool','bytes','callable','chr','complex',
            'dict','dir','divmod','enumerate','filter','float','format','frozenset',
            'hash','hex','id','int','isinstance','issubclass','iter','len','list',
            'map','max','min','next','object','oct','ord','pow','print','range',
            'repr','reversed','round','set','slice','sorted','str','sum','super',
            'tuple','type','zip',
            'True','False','None',
            'Exception','ValueError','TypeError','KeyError','IndexError',
            'AttributeError','StopIteration','RuntimeError','ZeroDivisionError',
            'ArithmeticError','OverflowError','MemoryError',
        ])
        wrapper = (
            'import sys, json\n'
            '_b = __builtins__\n'
            f'restricted = {{k: getattr(_b, k) for k in {safe_builtins}}}\n'
            f'SAFE = {safe_mods}\n'
            '_orig = _b.__import__\n'
            'def _safe_import(name, *a, **kw):\n'
            '    base = name.split(".")[0]\n'
            '    if base not in SAFE:\n'
            '        raise ImportError(f"module {name} not in safe list")\n'
            '    return _orig(name, *a, **kw)\n'
            "restricted['__import__'] = _safe_import\n"
            'exec({}, restricted)\n'.format(json.dumps(code))
        )
        try:
            r = subprocess.run(
                [sys.executable, "-I", "-c", wrapper],
                capture_output=True, text=True, timeout=self.timeout,
                env={**os.environ, "PYTHONPATH": ""}
            )
            out = []
            if r.stdout.strip():
                out.append(f"Output:\n{r.stdout.strip()[:5000]}")
            if r.stderr.strip():
                stderr = r.stderr.strip()[:2000]
                if "Error:" in stderr or "Exception" in stderr:
                    out.append(f"Error:\n{stderr}")
            return "\n".join(out) if out else "Code executed (no output)."
        except subprocess.TimeoutExpired:
            return f"Code execution timed out after {self.timeout}s"
        except Exception as e:
            return f"Execution failed: {type(e).__name__}: {e}"

    def get_tool_definitions(self):
        return [
            {"type": "function", "function": {"name": "run_code", "description": "Sandboxed Python exec (safe modules only, no os/subprocess/socket/file I/O)", "parameters": {"type": "object", "properties": {"code": {"type": "string", "description": "Python code to execute"}}, "required": ["code"]}}},
        ]

    def get_handler(self, name):
        handlers = {
            "run_code": self.run_code,
        }
        return handlers.get(name)
