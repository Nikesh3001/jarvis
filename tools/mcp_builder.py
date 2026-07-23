import os
import json
from pathlib import Path

from core.ratelimit import check_rate


class MCPBuilder:
    def _check_rate(self, op):
        return check_rate(f"mcp:{op}", rate=3, burst=5)

    def create_mcp_server(self, name, description, tools_list, output_dir=None):
        if not self._check_rate("create"):
            return "Rate limited"
        tools = []
        for t in tools_list:
            if isinstance(t, dict):
                tools.append(t)
            else:
                tools.append({"name": t, "description": f"Tool: {t}", "input_schema": {"type": "object", "properties": {}}})

        server_code = f'''import json
import sys
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("{name}")

TOOLS = {json.dumps(tools, indent=2)}


def handle_tool(name, args):
    logger.info(f"Tool called: {{name}} with args {{args}}")
    return {{"status": "ok", "tool": name, "result": f"Executed {{name}}"}}
'''

        if output_dir:
            out = Path(output_dir)
            out.mkdir(parents=True, exist_ok=True)
            server_path = out / f"{name}_server.py"
            server_path.write_text(server_code)
            config = {
                "name": name,
                "description": description,
                "tools": tools,
                "transport": "stdio",
            }
            config_path = out / "mcp.json"
            config_path.write_text(json.dumps(config, indent=2))
            readme = f"""# {name}

{description}

## Tools
{chr(10).join(f'- {t["name"]}: {t.get("description", "")}' for t in tools)}

## Usage
```bash
python {name}_server.py
```
"""
            readme_path = out / "README.md"
            readme_path.write_text(readme)
            return f"MCP server '{name}' created in {out}/ with {len(tools)} tool(s)"
        return server_code

    def evaluate_mcp(self, server_path):
        if not self._check_rate("evaluate"):
            return "Rate limited"
        if not os.path.exists(server_path):
            return f"Server not found: {server_path}"
        try:
            import ast
            with open(server_path) as f:
                tree = ast.parse(f.read())
            funcs = [n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)]
            return json.dumps({
                "file": server_path,
                "size_bytes": os.path.getsize(server_path),
                "functions": funcs,
                "function_count": len(funcs),
            }, indent=2)
        except Exception as e:
            return f"Evaluation failed: {e}"

    def list_connections(self):
        return json.dumps([
            {"name": "stdio", "description": "Standard input/output transport"},
            {"name": "sse", "description": "Server-Sent Events HTTP transport"},
            {"name": "websocket", "description": "WebSocket transport"},
        ], indent=2)

    def get_tool_definitions(self):
        return [
            {"type": "function", "function": {"name": "create_mcp_server", "description": "Create a Model Context Protocol (MCP) server with specified tools", "parameters": {"type": "object", "properties": {"name": {"type": "string", "description": "Server name"}, "description": {"type": "string", "description": "Server description"}, "tools_list": {"type": "array", "items": {"type": "object"}, "description": "List of tool definitions (name, description, input_schema)"}, "output_dir": {"type": "string", "description": "Output directory (optional)"}}, "required": ["name", "description", "tools_list"]}}},
            {"type": "function", "function": {"name": "evaluate_mcp", "description": "Evaluate an MCP server file for quality and structure", "parameters": {"type": "object", "properties": {"server_path": {"type": "string", "description": "Path to the server file"}}, "required": ["server_path"]}}},
            {"type": "function", "function": {"name": "list_connections", "description": "List available MCP connection types", "parameters": {"type": "object", "properties": {}}}},
        ]

    def get_handler(self, name):
        handlers = {
            "create_mcp_server": self.create_mcp_server,
            "evaluate_mcp": self.evaluate_mcp,
            "list_connections": self.list_connections,
        }
        return handlers.get(name)
