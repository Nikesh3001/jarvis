import json
import subprocess
import threading
import time
from pathlib import Path


class MCPClient:
    def __init__(self, name="jarvis"):
        self._process = None
        self._read_thread = None
        self._pending = {}
        self._lock = threading.Lock()
        self._msg_id = 0
        self._buffer = ""
        self._server_info = {}
        self._capabilities = {}
        self._tools_cache = None
        self.name = name

    def connect_stdio(self, command, args=None):
        args = args or []
        self._process = subprocess.Popen(
            [command] + args,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
        )
        self._read_thread = threading.Thread(target=self._reader, daemon=True)
        self._read_thread.start()

        result = self._request("initialize", {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": self.name, "version": "1.0.0"},
        })
        self._server_info = result.get("serverInfo", {})
        self._capabilities = result.get("capabilities", {})
        self._request("notifications/initialized", {})
        self._tools_cache = None
        return self._server_info

    def _reader(self):
        while self._process and self._process.poll() is None:
            try:
                line = self._process.stdout.readline()
                if not line:
                    break
                self._buffer += line
                try:
                    msg = json.loads(self._buffer.strip())
                    self._buffer = ""
                except json.JSONDecodeError:
                    # Prevent buffer from growing indefinitely
                    if len(self._buffer) > 65536:
                        self._buffer = ""
                    continue
                msg_id = msg.get("id")
                if msg_id is not None:
                    with self._lock:
                        cb = self._pending.pop(msg_id, None)
                        if cb:
                            cb(msg)
            except Exception:
                break

    def _request(self, method, params=None, timeout=30):
        with self._lock:
            self._msg_id += 1
            msg_id = self._msg_id
            event = threading.Event()
            result_container = [None]

            def cb(resp):
                result_container[0] = resp.get("result", {})
                event.set()

            self._pending[msg_id] = cb

        request = {
            "jsonrpc": "2.0",
            "id": msg_id,
            "method": method,
        }
        if params:
            request["params"] = params

        self._write(request)
        event.wait(timeout=timeout)

        if result_container[0] is None:
            with self._lock:
                self._pending.pop(msg_id, None)
        return result_container[0] or {}

    def _write(self, data):
        if self._process and self._process.stdin:
            self._process.stdin.write(json.dumps(data) + "\n")
            self._process.stdin.flush()

    def list_tools(self):
        if self._tools_cache is not None:
            return self._tools_cache
        result = self._request("tools/list")
        tools = result.get("tools", [])
        self._tools_cache = tools
        return tools

    def call_tool(self, name, arguments=None):
        result = self._request("tools/call", {
            "name": name,
            "arguments": arguments or {},
        })
        content = result.get("content", [])
        parts = []
        for c in content:
            if c.get("type") == "text":
                parts.append(c.get("text", ""))
            elif c.get("type") == "resource":
                parts.append(str(c.get("resource", "")))
        return "\n".join(parts)

    def invalidate_cache(self):
        self._tools_cache = None

    def close(self):
        if self._process:
            self._process.terminate()
            self._process.wait(timeout=5)
            self._process = None

    def __del__(self):
        self.close()
