import threading
import time
import json
import uuid
from datetime import datetime
from pathlib import Path

class AgentSession:
    def __init__(self, session_id, config=None):
        self.id = session_id
        self.created_at = time.time()
        self.last_active = time.time()
        self.config = config or {}
        self.messages = []
        self.tools_used = []
        self.files_modified = {}
        self.metadata = {
            "project": config.get("project", "unknown"),
            "branch": config.get("branch", "main"),
            "model": config.get("model", "smart"),
        }
        self._lock = threading.Lock()

    def add_message(self, role, content, metadata=None):
        with self._lock:
            self.messages.append({
                "role": role,
                "content": content,
                "timestamp": datetime.now().isoformat(),
                "metadata": metadata or {},
            })
            self.last_active = time.time()

    def get_context(self, max_messages=50):
        with self._lock:
            return self.messages[-max_messages:]

    def record_tool_use(self, tool_name, args, result):
        with self._lock:
            self.tools_used.append({
                "tool": tool_name,
                "args": args,
                "result": str(result)[:200],
                "timestamp": datetime.now().isoformat(),
            })

    def track_file_change(self, filepath, change_type):
        with self._lock:
            self.files_modified[filepath] = {
                "type": change_type,
                "timestamp": datetime.now().isoformat(),
            }

    def to_dict(self):
        return {
            "id": self.id,
            "created_at": datetime.fromtimestamp(self.created_at).isoformat(),
            "last_active": datetime.fromtimestamp(self.last_active).isoformat(),
            "message_count": len(self.messages),
            "tools_used_count": len(self.tools_used),
            "files_changed": len(self.files_modified),
            "metadata": self.metadata,
        }


class SessionManager:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, storage_dir=None):
        if hasattr(self, '_initialized'):
            return
        self._initialized = True
        self.sessions = {}
        self.active_session_id = None
        self.storage_dir = storage_dir or Path(__file__).parent.parent / "conversations"
        self.storage_dir.mkdir(exist_ok=True)
        self._lock = threading.Lock()
        self._load_sessions()

    def create_session(self, config=None):
        session_id = str(uuid.uuid4())[:8]
        session = AgentSession(session_id, config)
        with self._lock:
            self.sessions[session_id] = session
            self.active_session_id = session_id
        return session

    def get_session(self, session_id=None):
        sid = session_id or self.active_session_id
        if not sid:
            return self.create_session()
        with self._lock:
            return self.sessions.get(sid)

    def list_sessions(self):
        with self._lock:
            return {sid: s.to_dict() for sid, s in self.sessions.items()}

    def switch_session(self, session_id):
        with self._lock:
            if session_id in self.sessions:
                self.active_session_id = session_id
                return True
        return False

    def close_session(self, session_id):
        with self._lock:
            if session_id in self.sessions:
                self._save_session(session_id)
                del self.sessions[session_id]
                if self.active_session_id == session_id:
                    self.active_session_id = next(iter(self.sessions)) if self.sessions else None
                return True
        return False

    def _save_session(self, session_id):
        session = self.sessions.get(session_id)
        if not session:
            return
        path = self.storage_dir / f"{session_id}.json"
        try:
            path.write_text(json.dumps(session.to_dict(), indent=2))
        except Exception:
            pass

    def _load_sessions(self):
        if not self.storage_dir.exists():
            return
        for f in sorted(self.storage_dir.glob("*.json"))[:20]:
            try:
                data = json.loads(f.read_text())
                sid = f.stem
                session = AgentSession(sid, data.get("metadata", {}))
                session.created_at = datetime.fromisoformat(data.get("created_at", datetime.now().isoformat())).timestamp()
                session.last_active = datetime.fromisoformat(data.get("last_active", datetime.now().isoformat())).timestamp()
                with self._lock:
                    self.sessions[sid] = session
            except Exception:
                pass

    def get_tool_definitions(self):
        return []

    def get_handler(self, name):
        return None

    def save_all(self):
        with self._lock:
            for sid in list(self.sessions.keys()):
                self._save_session(sid)
