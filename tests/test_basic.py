"""Basic tests for Jarvis brain module."""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from core.brain import BaseBrain


class TestBrain(BaseBrain):
    def _default_fast(self):
        return "fast-model"

    def _default_smart(self):
        return "smart-model"

    def _default_deep(self):
        return "deep-model"

    def chat(self, messages, tools_enabled=True):
        return {"message": {"role": "assistant", "content": "test"}}

    def simple_chat(self, messages, on_token=None):
        return "test"

    def list_models(self):
        return ["test-model"]


def test_base_brain_init():
    b = TestBrain({"models": {"fast": "f", "smart": "s", "deep": "d"}})
    assert b.fast_model == "f"
    assert b.smart_model == "s"
    assert b.deep_model == "d"
    assert b.current_model == "s"
    assert b.max_tool_rounds == 3


def test_base_brain_defaults():
    b = TestBrain({})
    assert b.fast_model == "fast-model"
    assert b.smart_model == "smart-model"
    assert b.deep_model == "deep-model"


def test_select_model():
    b = TestBrain({})
    assert b.select_model("") == b.smart_model
    assert b.select_model("hello") == b.fast_model
    assert b.select_model("write a python function") == b.deep_model
    assert b.select_model("research this") == b.deep_model


def test_register_tools():
    b = TestBrain({})
    tools = [{"function": {"name": "test_tool", "description": "Test",
                           "parameters": {"type": "object", "properties": {}}}}]
    b.register_tools(tools, lambda n: lambda: "ok")
    assert "test_tool" in b.tool_registry
    assert len(b.tool_definitions) == 1


def test_clean_content():
    b = TestBrain({})
    assert b._clean_content("hello") == "hello"
    assert b._clean_content("<think>hidden</think>shown") == "shown"
    assert b._clean_content("") == ""


def test_health_check():
    b = TestBrain({})
    hc = b.health_check()
    assert hc["status"] == "OK"
    assert hc["provider"] == "TestBrain"
    assert hc["tools_registered"] == 0


def test_get_stats():
    b = TestBrain({})
    stats = b.get_stats()
    assert "calls" in stats
    assert "errors" in stats
    assert "tokens" in stats


def test_chat_with_tools_no_tools():
    b = TestBrain({})
    result = b.chat_with_tools([{"role": "user", "content": "hello"}])
    assert result == "test"


def test_relevant_tools_greeting():
    b = TestBrain({})
    tools = [
        {"function": {"name": "run_code", "description": "Test",
                      "parameters": {"type": "object", "properties": {}}}},
        {"function": {"name": "web_search", "description": "Test",
                      "parameters": {"type": "object", "properties": {}}}},
    ]
    b.register_tools(tools, lambda n: lambda: "ok")
    assert b._relevant_tools([{"role": "user", "content": "hi there"}]) == []
    code_tools = b._relevant_tools([{"role": "user", "content": "run code"}])
    assert len(code_tools) > 0, "Should find tools for code query"
    assert code_tools[0]["function"]["name"] == "run_code"
