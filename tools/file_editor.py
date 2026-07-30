import os
import shutil
import glob
from pathlib import Path

from core.ratelimit import check_rate


ALLOWED_ROOTS = [
    os.path.realpath(os.path.expanduser("~")),
]


def _safe_resolve(path):
    path = os.path.expanduser(path)
    path = os.path.abspath(path)
    try:
        resolved = os.path.realpath(path)
    except OSError:
        resolved = path
    for root in ALLOWED_ROOTS:
        if resolved == root or os.path.commonpath([resolved, root]) == root:
            return resolved
    raise PermissionError("Access denied: path is outside allowed directories")


class FileEditor:
    def write_file(self, path, content):
        if not check_rate("file_write", rate=1, burst=5):
            return "Rate limit exceeded. Please wait before writing more files."
        path = _safe_resolve(path)
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        return f"Written {len(content)} bytes to {path}"

    def edit_file(self, path, old_string, new_string):
        if not check_rate("file_edit", rate=1, burst=5):
            return "Rate limit exceeded. Please wait before editing more files."
        path = _safe_resolve(path)
        if not os.path.exists(path):
            return f"File not found: {path}"
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        if old_string not in content:
            return f"String not found in {path}"
        new_content = content.replace(old_string, new_string, 1)
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(new_content)
        os.replace(tmp, path)
        return f"Replaced 1 occurrence(s) in {path}"

    def append_file(self, path, content):
        if not check_rate("file_append", rate=1, burst=5):
            return "Rate limit exceeded. Please wait before appending to more files."
        path = _safe_resolve(path)
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with open(path, "a", encoding="utf-8") as f:
            f.write(content)
        return f"Appended {len(content)} bytes to {path}"

    def list_files(self, path="."):
        try:
            path = _safe_resolve(path)
        except PermissionError:
            return "Access denied"
        if not os.path.exists(path):
            return f"Path not found: {path}"
        items = []
        for entry in os.scandir(path):
            kind = "DIR" if entry.is_dir() else "FILE"
            size = entry.stat().st_size if entry.is_file() else 0
            items.append(f"[{kind}] {entry.name} ({size} bytes)")
        return f"Contents of {path}:\n" + "\n".join(items[:100])

    def move_file(self, src, dst):
        if not check_rate("file_move", rate=0.5, burst=3):
            return "Rate limit exceeded. Please wait before moving more files."
        src, dst = _safe_resolve(src), _safe_resolve(dst)
        Path(dst).parent.mkdir(parents=True, exist_ok=True)
        shutil.move(src, dst)
        return f"Moved {src} -> {dst}"

    def copy_file(self, src, dst):
        if not check_rate("file_copy", rate=0.5, burst=3):
            return "Rate limit exceeded. Please wait before copying more files."
        src, dst = _safe_resolve(src), _safe_resolve(dst)
        Path(dst).parent.mkdir(parents=True, exist_ok=True)
        if os.path.isdir(src):
            shutil.copytree(src, dst, dirs_exist_ok=True)
            return f"Copied directory {src} -> {dst}"
        shutil.copy2(src, dst)
        return f"Copied {src} -> {dst}"

    def delete_file(self, path):
        if not check_rate("file_delete", rate=0.5, burst=3):
            return "Rate limit exceeded. Please wait before deleting more files."
        path = _safe_resolve(path)
        if not os.path.exists(path):
            return f"File not found: {path}"
        if os.path.isdir(path):
            shutil.rmtree(path)
            return f"Deleted directory: {path}"
        os.remove(path)
        return f"Deleted file: {path}"

    def create_directory(self, path):
        path = _safe_resolve(path)
        os.makedirs(path, exist_ok=True)
        return f"Created directory: {path}"

    def find_files(self, pattern, path="."):
        try:
            path = _safe_resolve(path)
        except PermissionError:
            return "Access denied"
        matches = sorted(glob.glob(os.path.join(path, pattern), recursive=True))
        if not matches:
            return f"No files matching '{pattern}' in {path}"
        lines = [f"{i+1}. {m}" for i, m in enumerate(matches[:100])]
        return f"Found {len(matches)} file(s) in {path}:\n" + "\n".join(lines)

    def grep_files(self, pattern, path=".", include="*"):
        try:
            path = _safe_resolve(path)
        except PermissionError:
            return "Access denied"
        matches = []
        for file in glob.glob(os.path.join(path, "**", include), recursive=True):
            try:
                resolved_file = _safe_resolve(file)
            except PermissionError:
                continue
            if os.path.isfile(resolved_file):
                try:
                    with open(resolved_file, "r", encoding="utf-8", errors="replace") as f:
                        for i, line in enumerate(f, 1):
                            if pattern in line:
                                matches.append(f"{resolved_file}:{i}: {line.rstrip()[:200]}")
                except Exception:
                    pass
                if len(matches) >= 50:
                    break
        if not matches:
            return f"No matches for '{pattern}' in {path}"
        return f"Found {len(matches)} match(es):\n" + "\n".join(matches[:50])

    def file_info(self, path):
        try:
            path = _safe_resolve(path)
        except PermissionError:
            return "Access denied"
        if not os.path.exists(path):
            return f"File not found: {path}"
        stat = os.stat(path)
        lines = [
            f"Path: {os.path.abspath(path)}",
            f"Size: {stat.st_size} bytes",
            f"Modified: {stat.st_mtime}",
            f"Type: {'Directory' if os.path.isdir(path) else 'File'}",
        ]
        return "\n".join(lines)

    def get_tool_definitions(self):
        return [
            {"type": "function", "function": {"name": "write_file", "description": "Write file (creates dirs)", "parameters": {"type": "object", "properties": {"path": {"type": "string", "description": "Path"}, "content": {"type": "string", "description": "Content"}}, "required": ["path", "content"]}}},
            {"type": "function", "function": {"name": "edit_file", "description": "Find/replace in file", "parameters": {"type": "object", "properties": {"path": {"type": "string", "description": "Path"}, "old_string": {"type": "string", "description": "Old"}, "new_string": {"type": "string", "description": "New"}}, "required": ["path", "old_string", "new_string"]}}},
            {"type": "function", "function": {"name": "append_file", "description": "Append to a file", "parameters": {"type": "object", "properties": {"path": {"type": "string", "description": "Path"}, "content": {"type": "string", "description": "Content"}}, "required": ["path", "content"]}}},
            {"type": "function", "function": {"name": "list_files", "description": "List directory contents", "parameters": {"type": "object", "properties": {"path": {"type": "string", "description": "Directory path (use ~/ for home, e.g. ~/jarvis)", "default": "."}}, "required": []}}},
            {"type": "function", "function": {"name": "move_file", "description": "Move/rename file or dir", "parameters": {"type": "object", "properties": {"src": {"type": "string", "description": "Src"}, "dst": {"type": "string", "description": "Dst"}}, "required": ["src", "dst"]}}},
            {"type": "function", "function": {"name": "copy_file", "description": "Copy file or directory", "parameters": {"type": "object", "properties": {"src": {"type": "string", "description": "Src"}, "dst": {"type": "string", "description": "Dst"}}, "required": ["src", "dst"]}}},
            {"type": "function", "function": {"name": "delete_file", "description": "Permanently delete", "parameters": {"type": "object", "properties": {"path": {"type": "string", "description": "Path"}}, "required": ["path"]}}},
            {"type": "function", "function": {"name": "create_directory", "description": "Create dir (with parents)", "parameters": {"type": "object", "properties": {"path": {"type": "string", "description": "Path"}}, "required": ["path"]}}},
            {"type": "function", "function": {"name": "find_files", "description": "Find files by glob pattern", "parameters": {"type": "object", "properties": {"pattern": {"type": "string", "description": "Glob"}, "path": {"type": "string", "description": "Root", "default": "."}}, "required": ["pattern"]}}},
            {"type": "function", "function": {"name": "grep_files", "description": "Search text in files", "parameters": {"type": "object", "properties": {"pattern": {"type": "string", "description": "Text"}, "path": {"type": "string", "description": "Root", "default": "."}, "include": {"type": "string", "description": "Glob filter", "default": "*"}}, "required": ["pattern"]}}},
            {"type": "function", "function": {"name": "file_info", "description": "File/dir metadata", "parameters": {"type": "object", "properties": {"path": {"type": "string", "description": "Path"}}, "required": ["path"]}}},
        ]

    def get_handler(self, name):
        handlers = {
            "write_file": self.write_file, "edit_file": self.edit_file, "append_file": self.append_file,
            "list_files": self.list_files, "move_file": self.move_file, "copy_file": self.copy_file,
            "delete_file": self.delete_file, "create_directory": self.create_directory,
            "find_files": self.find_files, "grep_files": self.grep_files, "file_info": self.file_info,
        }
        return handlers.get(name)