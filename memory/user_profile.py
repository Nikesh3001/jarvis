"""User profile tracking for personalized interactions.

NOTE: This module records user activity (requests, tool usage, preferences)
for personalization. The profile is stored locally on this machine only.
"""
import json
import os
from pathlib import Path


PROFILE_PATH = Path(__file__).parent.parent / "user_profile.json"

_CONSENT_SHOWN = False


def _show_consent():
    global _CONSENT_SHOWN
    if not _CONSENT_SHOWN:
        _CONSENT_SHOWN = True
        print("  [INFO] User profile tracking active: stores request history locally")
        print("  [INFO] Data is stored at: user_profile.json (delete to reset)")


class UserProfile:
    def __init__(self):
        _show_consent()
        self._data = self._load()

    def _load(self):
        if PROFILE_PATH.exists():
            try:
                return json.loads(PROFILE_PATH.read_text(encoding="utf-8"))
            except Exception:
                pass
        return {
            "name": "User",
            "preferences": {},
            "tools_used": {},
            "common_requests": [],
            "session_count": 0,
        }

    def _save(self):
        try:
            PROFILE_PATH.write_text(
                json.dumps(self._data, indent=2), encoding="utf-8"
            )
        except Exception:
            pass

    def get_summary(self):
        prefs = self._data.get("preferences", {})
        tools = self._data.get("tools_used", {})
        top_tools = sorted(tools.items(), key=lambda x: -x[1])[:5]
        lines = [
            f"User: {self._data.get('name', 'User')}",
            f"Sessions: {self._data.get('session_count', 0)}",
        ]
        if prefs:
            lines.append(f"Preferences: {json.dumps(prefs)}")
        if top_tools:
            lines.append(f"Top tools: {', '.join(f'{t}({c})' for t, c in top_tools)}")
        return "\n".join(lines)

    def record_tool_use(self, tool_name):
        tools = self._data["tools_used"]
        tools[tool_name] = tools.get(tool_name, 0) + 1
        self._save()

    def set_preference(self, key, value):
        self._data["preferences"][key] = value
        self._save()

    def get_preference(self, key, default=None):
        return self._data["preferences"].get(key, default)

    def record_session(self):
        self._data["session_count"] = self._data.get("session_count", 0) + 1
        self._save()

    def record_request(self, request_text):
        reqs = self._data["common_requests"]
        reqs.append(request_text[:100])
        if len(reqs) > 50:
            reqs[:] = reqs[-50:]
        self._save()

    def learn_from_conversation(self, messages):
        summary = self._auto_summarize(messages)
        if summary:
            self._data["last_summary"] = summary
            self._save()

    def _auto_summarize(self, messages):
        key_moments = []
        for m in messages[-20:]:
            role = m.get("role", "")
            content = (m.get("content", "") or "")[:200]
            if role == "user":
                key_moments.append(f"asked: {content}")
            elif role == "assistant":
                key_moments.append(f"responded: {content}")
        if not key_moments:
            return None
        return " | ".join(key_moments[-10:])
