"""Example plugin - system info tools.

To create a plugin:
1. Create a .py file in the plugins/ directory
2. Define a register() function that returns:
   {
     "tools": [tool_definition_dict, ...],
     "handler": function(name) -> callable | None,
   }
   OR
   {
     "tools": [tool_definition_dict, ...],
     "handlers": { "tool_name": callable, ... },
   }

Use the @tool decorator from core.tool_decorator for convenience:
   from core.tool_decorator import tool, Tool
"""

import datetime
import os
import subprocess


def register():
    tools = [
        {
            "type": "function",
            "function": {
                "name": "uptime",
                "description": "Get system uptime and current time",
                "parameters": {
                    "type": "object",
                    "properties": {},
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "disk_usage",
                "description": "Get disk usage for a given path",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "Path to check disk usage (default: C:\\)",
                        }
                    },
                },
            },
        },
    ]

    def handler(name):
        handlers = {
            "uptime": lambda: f"Current time: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "disk_usage": _disk_usage,
        }
        return handlers.get(name)

    return {"tools": tools, "handler": handler}


def _disk_usage(path="C:\\"):
    try:
        drive_letter = path[0].upper()
        if not drive_letter.isascii() or not drive_letter.isalpha():
            return "Error: invalid drive letter"
        result = subprocess.run(
            ["wmic", "logicaldisk", "where", f"name='{drive_letter}:'", "get", "size,freespace"],
            capture_output=True, text=True, timeout=15
        )
        return result.stdout.strip()
    except Exception:
        return "Disk usage check failed"
