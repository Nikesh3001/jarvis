import re
import ast
from typing import Dict, List, Optional, Any

def safe_get(data, *keys, default=None):
    if data is None:
        return default
    current = data
    for key in keys:
        if isinstance(current, dict):
            current = current.get(key, default)
        else:
            return default
    return current if current is not None else default

def extract_response_content(response: Any) -> str:
    if response is None:
        return ""
    if isinstance(response, str):
        return response
    if isinstance(response, dict):
        msg = response.get("message")
        if isinstance(msg, dict):
            content = msg.get("content", "")
            return content if content else ""
        content = response.get("content")
        if isinstance(content, str):
            return content
    return str(response)

def ensure_result_dict(result: Any) -> Dict:
    if result is None:
        return {}
    if isinstance(result, dict):
        return result
    return {}

def validate_code_safety(code: str) -> List[str]:
    warnings = []
    dangerous = [
        ("__import__", "Dynamic imports blocked"),
        ("eval(", "eval() blocked"),
        ("exec(", "exec() blocked"),
        ("compile(", "compile() blocked"),
        ("os.system", "os.system blocked"),
        ("subprocess", "subprocess limited"),
        ("shutil.rmtree", "Destructive file ops flagged"),
        ("pathlib.Path.unlink", "File deletion flagged"),
    ]
    for pattern, msg in dangerous:
        if pattern in code:
            warnings.append(msg)
    return warnings

def sanitize_path(path: str) -> Optional[str]:
    if not path:
        return None
    path = path.strip().strip("'\"").replace("\\", "/")
    if ".." in path.split("/"):
        return None
    return path

def validate_message_structure(msg: Any) -> bool:
    if msg is None:
        return False
    if isinstance(msg, dict):
        return "role" in msg and "content" in msg
    return False
