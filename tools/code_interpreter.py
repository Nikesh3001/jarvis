import os
import sys
import subprocess
import tempfile
import ast


class CodeInterpreter:
    def __init__(self):
        self.timeout = 60

    def run_code(self, code):
        if not code or not code.strip():
            return "No code to execute."
        if len(code) > 10000:
            return "Code too long (max 10000 chars)."

        tmpdir = tempfile.mkdtemp(prefix="friday_code_")
        tmpfile = os.path.join(tmpdir, "script.py")
        try:
            with open(tmpfile, "w", encoding="utf-8") as f:
                f.write(code)

            r = subprocess.run(
                [sys.executable, "-c", code],
                capture_output=True, text=True, timeout=self.timeout,
            )
            out = []
            if r.stdout.strip():
                out.append(f"Output:\n{r.stdout.strip()[:5000]}")
            if r.stderr.strip():
                out.append(f"Error:\n{r.stderr.strip()[:2000]}")
            if not out:
                out.append("Code executed (no output).")
            return "\n".join(out)
        except subprocess.TimeoutExpired:
            return f"Code timed out after {self.timeout}s"
        except subprocess.CalledProcessError as e:
            return f"Code error (exit {e.returncode}): {e.stderr[:2000] if e.stderr else str(e)}"
        except Exception as e:
            return f"Sandbox error: {e}"
        finally:
            try:
                import shutil
                shutil.rmtree(tmpdir, ignore_errors=True)
            except Exception:
                pass

    def get_tool_definitions(self):
        return [
            {"type": "function", "function": {"name": "run_code", "description": "Sandboxed Python exec", "parameters": {"type": "object", "properties": {"code": {"type": "string", "description": "Code"}}, "required": ["code"]}}},
        ]

    def get_handler(self, name):
        handlers = {
            "run_code": self.run_code,
        }
        return handlers.get(name)
