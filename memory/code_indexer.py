import os
import re
import json
from pathlib import Path


CODE_EXTS = {
    ".py", ".js", ".ts", ".jsx", ".tsx", ".java", ".go", ".rs",
    ".c", ".cpp", ".h", ".hpp", ".rb", ".php", ".swift", ".kt",
    ".scala", ".sql", ".html", ".css", ".scss", ".json", ".yaml",
    ".yml", ".toml", ".md", ".txt", ".ini", ".cfg", ".conf",
    ".sh", ".bat", ".ps1", ".xml", ".gradle", ".sbt", ".vue",
    ".svelte", ".astro",
}

IGNORE_DIRS = {
    "node_modules", ".git", "__pycache__", ".venv", "venv", "env",
    "dist", "build", ".next", ".nuxt", ".output", "target",
    "vendor", "bower_components", ".idea", ".vscode", ".DS_Store",
    "coverage", ".nyc_output", "tmp", "temp", "logs", ".tox",
    ".eggs", "eggs", "lib", "lib64", "bin", "include", "share",
}

IMPORT_PATTERNS = {
    ".py": [
        (r'^import\s+(\S+)', 1),
        (r'^from\s+(\S+)\s+import', 1),
    ],
    ".js": [
        (r'(?:import\s+(?:\*\s+as\s+)?\w+(?:\s*,\s*\{[^}]*\})?\s+from\s+[\'"])([^\'"]+)[\'"]', 1),
        (r'(?:const\s+\w+\s*=\s*require\s*\(\s*[\'"])([^\'"]+)[\'"]', 1),
        (r'(?:import\s+\{[^}]*\}\s+from\s+[\'"])([^\'"]+)[\'"]', 1),
    ],
    ".ts": [
        (r'(?:import\s+(?:\*\s+as\s+)?\w+(?:\s*,\s*\{[^}]*\})?\s+from\s+[\'"])([^\'"]+)[\'"]', 1),
        (r'(?:import\s+\{[^}]*\}\s+from\s+[\'"])([^\'"]+)[\'"]', 1),
        (r'(?:import\s+type\s+\{[^}]*\}\s+from\s+[\'"])([^\'"]+)[\'"]', 1),
    ],
    ".java": [
        (r'^import\s+(\S+);', 1),
    ],
    ".go": [
        (r'^import\s+"(\S+)"', 1),
        (r'^import\s+\(\s*$', 0),
        (r'^\s+"(\S+)"', 1),
    ],
    ".rs": [
        (r'^use\s+(\S+);', 1),
        (r'^extern\s+crate\s+(\S+);', 1),
    ],
    ".rb": [
        (r'^require\s+[\'"](\S+)[\'"]', 1),
        (r'^require_relative\s+[\'"](\S+)[\'"]', 1),
    ],
    ".php": [
        (r'^use\s+(\S+);', 1),
        (r'^include\s+[\'"](\S+)[\'"]', 1),
        (r'^require\s+[\'"](\S+)[\'"]', 1),
    ],
}

LANGUAGE_MAP = {}
for ext, lang in [
    (".py", "python"), (".js", "javascript"), (".ts", "typescript"),
    (".jsx", "jsx"), (".tsx", "tsx"), (".java", "java"), (".go", "go"),
    (".rs", "rust"), (".c", "c"), (".cpp", "cpp"), (".h", "c"),
    (".hpp", "cpp"), (".rb", "ruby"), (".php", "php"), (".swift", "swift"),
    (".kt", "kotlin"), (".scala", "scala"), (".sql", "sql"),
    (".html", "html"), (".css", "css"), (".scss", "scss"),
    (".json", "json"), (".yaml", "yaml"), (".yml", "yaml"),
    (".toml", "toml"), (".md", "markdown"), (".sh", "shell"),
    (".bat", "batch"), (".ps1", "powershell"), (".xml", "xml"),
    (".vue", "vue"), (".svelte", "svelte"), (".astro", "astro"),
    (".gradle", "gradle"), (".sbt", "scala"),
]:
    LANGUAGE_MAP[ext] = lang


def _get_language(path):
    return LANGUAGE_MAP.get(Path(path).suffix.lower(), "text")


def _detect_project_type(files):
    has = set()
    for f in files:
        name = Path(f).name
        if name in ("package.json",):
            has.add("node")
        if name in ("Cargo.toml",):
            has.add("rust")
        if name in ("pom.xml", "build.gradle", "build.gradle.kts"):
            has.add("java")
        if name in ("go.mod",):
            has.add("go")
        if name in ("Gemfile",):
            has.add("ruby")
        if name in ("composer.json",):
            has.add("php")
        if f.endswith(".csproj"):
            has.add("dotnet")
    if "pyproject.toml" in {Path(f).name for f in files}:
        has.add("python")
    for f in files:
        if f.endswith(".py"):
            has.add("python")
            break
    return has


class CodeIndex:
    def __init__(self):
        self._chroma = None
        self._collection = None
        self._index_dir = Path(__file__).parent.parent / "code_index"

    def _lazy_init(self):
        if self._collection is not None:
            return
        import chromadb
        self._index_dir.mkdir(exist_ok=True)
        client = chromadb.PersistentClient(path=str(self._index_dir))
        try:
            self._collection = client.get_collection("code_index")
        except Exception:
            self._collection = client.create_collection("code_index")

    def _chunk_file(self, filepath, max_chunk=150, overlap=20):
        path = Path(filepath)
        ext = path.suffix.lower()
        if ext not in CODE_EXTS:
            return []
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except Exception:
            return []
        lines = text.splitlines()
        if not lines:
            return []
        language = _get_language(filepath)

        chunks = []
        if len(lines) <= max_chunk:
            chunk_text = "\n".join(lines)
            chunks.append({
                "text": chunk_text,
                "start": 1,
                "end": len(lines),
                "path": str(path),
                "language": language,
            })
            return chunks

        i = 0
        chunk_index = 0
        while i < len(lines):
            end = min(i + max_chunk, len(lines))
            chunk_lines = lines[i:end]
            chunk_text = "\n".join(chunk_lines)

            rel_start = i + 1
            rel_end = end

            chunks.append({
                "text": chunk_text,
                "start": rel_start,
                "end": rel_end,
                "path": str(path),
                "language": language,
                "chunk_index": chunk_index,
            })
            chunk_index += 1
            i += max_chunk - overlap

        return chunks

    def _scan_files(self, root_path):
        root = Path(root_path).resolve()
        if not root.is_dir():
            return []
        files = []
        try:
            for entry in root.iterdir():
                if entry.name in IGNORE_DIRS or entry.name.startswith("."):
                    continue
                if entry.is_dir():
                    files.extend(self._scan_files(str(entry)))
                elif entry.suffix.lower() in CODE_EXTS:
                    files.append(str(entry))
        except (OSError, PermissionError):
            pass
        return sorted(files)

    def _extract_symbols(self, text, language):
        symbols = []
        lines = text.splitlines()
        for i, line in enumerate(lines):
            stripped = line.strip()
            if language == "python":
                m = re.match(r'^(?:async\s+)?(?:def|class)\s+(\w+)', stripped)
                if m:
                    symbols.append((m.group(1), i + 1))
            elif language in ("javascript", "typescript", "jsx", "tsx"):
                m = re.match(r'^(?:export\s+)?(?:async\s+)?(?:function\s+\*?\s*(\w+)|class\s+(\w+)|const\s+(\w+)\s*=|let\s+(\w+)\s*=|var\s+(\w+)\s*=)', stripped)
                if m:
                    name = next(g for g in m.groups() if g)
                    symbols.append((name, i + 1))
                m = re.match(r'^(?:export\s+)?(?:default\s+)?(?:function\s+\*?\s*(\w+)|class\s+(\w+))', stripped)
                if m:
                    name = next(g for g in m.groups() if g)
                    symbols.append((name, i + 1))
            elif language == "java":
                m = re.match(r'^(?:public|private|protected|static)?\s*(?:class|interface|enum)\s+(\w+)', stripped)
                if m:
                    symbols.append((m.group(1), i + 1))
                m = re.match(r'^(?:public|private|protected|static)?\s+\w+\s+(\w+)\s*\(', stripped)
                if m:
                    symbols.append((m.group(1), i + 1))
            elif language == "go":
                m = re.match(r'^func\s+(?:\([^)]*\)\s+)?(\w+)', stripped)
                if m:
                    symbols.append((m.group(1), i + 1))
                m = re.match(r'^type\s+(\w+)\s+(?:struct|interface)', stripped)
                if m:
                    symbols.append((m.group(1), i + 1))
            elif language == "rust":
                m = re.match(r'^(?:pub\s+)?(?:fn|struct|enum|trait|impl|mod|type)\s+(\w+)', stripped)
                if m:
                    symbols.append((m.group(1), i + 1))
        return symbols

    def _is_allowed_path(self, root_path):
        """Restrict indexing to safe directories — never system dirs or sensitive paths."""
        resolved = Path(root_path).resolve()
        # Always allow indexing within the jarvis project itself
        jarvis_root = Path(__file__).parent.parent.resolve()
        if str(resolved).startswith(str(jarvis_root)):
            return True
        # Block all system directories
        blocked_prefixes = [
            "/etc", "/var", "/sys", "/proc", "/dev", "/boot", "/sbin", "/usr",
            "C:\\Windows", "C:\\Program Files", "C:\\ProgramData",
            "C:\\Users\\All Users", "C:\\ProgramData",
        ]
        for prefix in blocked_prefixes:
            try:
                resolved.relative_to(Path(prefix).resolve())
                return False
            except ValueError:
                continue
        # For external paths, only allow specific user project directories
        # Block the home directory itself and sensitive subdirs
        home = Path.home().resolve()
        try:
            resolved.relative_to(home)
            # Disallow indexing the home directory itself
            if resolved == home:
                return False
            # Block sensitive home subdirs
            sensitive = {".ssh", ".gnupg", ".aws", ".azure", ".config", ".local",
                        "AppData", "Documents", "Desktop", "Downloads", "Pictures",
                        "Videos", "Music", "Favorites", "Contacts", "Links",
                        "Saved Games", "Searches", "3D Objects"}
            try:
                rel = resolved.relative_to(home)
                top_dir = rel.parts[0] if rel.parts else ""
                if top_dir in sensitive:
                    return False
            except (ValueError, IndexError):
                pass
            return True
        except ValueError:
            return False

    def index_project(self, root_path, max_files=500, max_depth=10):
        if not self._is_allowed_path(root_path):
            return "Access denied: path is outside allowed directories for indexing"
        self._lazy_init()
        root = str(Path(root_path).resolve())
        files = self._scan_files(root)
        if not files:
            return f"No indexable files found in {root}"
        if len(files) > max_files:
            files = files[:max_files]

        count = 0
        ids = []
        documents = []
        metadatas = []

        for filepath in files:
            chunks = self._chunk_file(filepath)
            for chunk in chunks:
                chunk_id = f"{chunk['path']}:L{chunk['start']}-L{chunk['end']}"
                symbols = self._extract_symbols(chunk["text"], chunk["language"])
                ids.append(chunk_id)
                documents.append(chunk["text"])
                metadatas.append({
                    "file_path": chunk["path"],
                    "start_line": chunk["start"],
                    "end_line": chunk["end"],
                    "language": chunk["language"],
                    "project_root": root,
                    "symbols": json.dumps([s[0] for s in symbols]),
                    "chunk_index": chunk.get("chunk_index", 0),
                })
                count += 1

        if count > 0:
            batch_size = 100
            for i in range(0, count, batch_size):
                self._collection.upsert(
                    ids=ids[i:i + batch_size],
                    documents=documents[i:i + batch_size],
                    metadatas=metadatas[i:i + batch_size],
                )

        project_type = _detect_project_type(files)
        file_count = len(files)
        lang_counts = {}
        for f in files:
            lang = _get_language(f)
            lang_counts[lang] = lang_counts.get(lang, 0) + 1

        info = {
            "root": root,
            "files_indexed": file_count,
            "chunks_indexed": count,
            "project_types": list(project_type),
            "languages": lang_counts,
        }
        return info

    def search_code(self, query, n_results=10, project_root=None):
        self._lazy_init()
        where = None
        if project_root:
            where = {"project_root": str(Path(project_root).resolve())}

        try:
            results = self._collection.query(
                query_texts=[query],
                n_results=n_results,
                where=where,
            )
        except Exception:
            return []

        if not results["documents"] or not results["documents"][0]:
            return []

        output = []
        for doc, meta, dist in zip(
            results["documents"][0],
            results["metadatas"][0],
            results["distances"][0],
        ):
            path = meta.get("file_path", "?")
            start = meta.get("start_line", "?")
            end = meta.get("end_line", "?")
            symbols_json = meta.get("symbols", "[]")
            try:
                symbols = json.loads(symbols_json)
            except json.JSONDecodeError:
                symbols = []
            output.append({
                "file_path": path,
                "lines": f"{start}-{end}",
                "symbols": symbols,
                "score": round(1 - dist, 3),
                "preview": doc[:300],
            })
        return output

    def get_project_structure(self, root_path, max_depth=4, max_files=200):
        root = Path(root_path).resolve()
        if not root.is_dir():
            return "Not a directory"
        lines = []
        lines.append(f"[{root.name}]")
        file_count = 0

        def walk(dir_path, depth=0, prefix=""):
            nonlocal file_count
            if file_count >= max_files:
                return
            if depth > max_depth:
                return
            try:
                entries = sorted(dir_path.iterdir(), key=lambda e: (not e.is_dir(), e.name.lower()))
            except (OSError, PermissionError):
                return
            for i, entry in enumerate(entries):
                if file_count >= max_files:
                    return
                is_last = i == len(entries) - 1
                connector = "`- " if is_last else "|- "
                if entry.name in IGNORE_DIRS or entry.name.startswith("."):
                    continue
                try:
                    is_dir = entry.is_dir()
                except OSError:
                    continue
                if is_dir:
                    lines.append(f"{prefix}{connector}{entry.name}/")
                    next_prefix = prefix + ("   " if is_last else "|  ")
                    walk(entry, depth + 1, next_prefix)
                elif entry.suffix.lower() in CODE_EXTS:
                    lang = _get_language(entry)
                    lines.append(f"{prefix}{connector}{entry.name}  ({lang})")
                    file_count += 1

        walk(root)
        lines.append(f"\n{file_count} files shown")
        return "\n".join(lines)

    def get_dependencies(self, root_path, target_file=None):
        root = Path(root_path).resolve()
        files = self._scan_files(str(root))
        imports = {}
        for filepath in files:
            if target_file and filepath != target_file:
                continue
            if not target_file:
                rel = str(Path(filepath).relative_to(root))
            else:
                rel = filepath
            ext = Path(filepath).suffix.lower()
            try:
                text = Path(filepath).read_text(encoding="utf-8", errors="replace")
            except Exception:
                continue
            deps = []
            patterns = IMPORT_PATTERNS.get(ext, [])
            for pattern, group_idx in patterns:
                for m in re.finditer(pattern, text, re.MULTILINE):
                    dep = m.group(group_idx).strip()
                    if dep and not deps or dep != deps[-1]:
                        deps.append(dep)
            if deps:
                imports[rel] = deps

        if target_file:
            if not imports:
                return {"file": target_file, "imports": []}
            return {"file": target_file, "imports": next(iter(imports.values()))}

        return imports

    def read_multiple_files(self, paths, max_lines_per_file=200, max_total_lines=5000):
        results = []
        total = 0
        for path in paths:
            p = Path(path)
            if not p.exists():
                results.append(f"# {path}\nFile not found")
                continue
            if not p.is_file():
                results.append(f"# {path}\nNot a file")
                continue
            try:
                text = p.read_text(encoding="utf-8", errors="replace")
            except Exception as e:
                results.append(f"# {path}\nError: {e}")
                continue
            lines = text.splitlines()
            if len(lines) > max_lines_per_file:
                text = "\n".join(lines[:max_lines_per_file])
                text += f"\n... ({len(lines) - max_lines_per_file} more lines)"
            total += len(lines)
            header = f"# {path}"
            lang = _get_language(path)
            results.append(f"{header}  ({lang})")
            results.append(text)
            if total >= max_total_lines:
                results.append(f"\n... (truncated at {max_total_lines} total lines)")
                break
        return "\n\n".join(results)

    def refresh_index(self, root_path):
        info = self.index_project(root_path)
        return info

    def get_tool_definitions(self):
        return [
            {
                "type": "function",
                "function": {
                    "name": "index_project",
                    "description": "Index a project directory for code search: scan all code files, chunk them, and store embeddings for semantic search",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "path": {"type": "string", "description": "Absolute path to the project root directory"}
                        },
                        "required": ["path"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "search_code",
                    "description": "Semantically search indexed code by natural language query. Returns relevant code chunks with file paths and line numbers",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {"type": "string", "description": "What to search for in natural language"},
                            "project_root": {"type": "string", "description": "Optional: restrict search to a specific project directory"}
                        },
                        "required": ["query"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_project_structure",
                    "description": "Get a tree view of a project directory showing files organized by language type",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "path": {"type": "string", "description": "Absolute path to the project root directory"}
                        },
                        "required": ["path"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_dependencies",
                    "description": "Analyze imports/dependencies between files in a project. Returns a map of each file to its external imports",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "path": {"type": "string", "description": "Absolute path to the project root directory"}
                        },
                        "required": ["path"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "read_project_files",
                    "description": "Read multiple source files at once for project context. Provide paths as a comma-separated list",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "paths": {"type": "string", "description": "Comma-separated list of file paths to read"}
                        },
                        "required": ["paths"]
                    }
                }
            },
        ]

    def get_handler(self, name):
        def list_to_str(lst):
            if isinstance(lst, list):
                return "\n".join(str(item) for item in lst)
            return str(lst)

        handlers = {
            "index_project": lambda path: list_to_str(self.index_project(path)),
            "search_code": lambda query, project_root=None: list_to_str(self.search_code(query, project_root=project_root)),
            "get_project_structure": lambda path: self.get_project_structure(path),
            "get_dependencies": lambda path: list_to_str(self.get_dependencies(path)),
            "read_project_files": lambda paths: self._read_files_wrapper(paths),
        }
        return handlers.get(name)

    def _safe_resolve(self, path):
        try:
            resolved = Path(path).resolve()
            if not resolved.exists():
                return None
            return str(resolved)
        except (OSError, RuntimeError):
            return None

    def _read_files_wrapper(self, paths_str):
        import shlex
        paths = [p.strip() for p in paths_str.replace(",", "\n").split("\n") if p.strip()]
        safe_paths = []
        for p in paths:
            resolved = self._safe_resolve(p)
            if resolved:
                safe_paths.append(resolved)
        if not safe_paths:
            return "No valid file paths provided"
        return self.read_multiple_files(safe_paths)
