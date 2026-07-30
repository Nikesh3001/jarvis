import sys, os, time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from core.brain import BaseBrain


class TestBrainE2E(BaseBrain):
    def _default_fast(self): return "f"
    def _default_smart(self): return "s"
    def _default_deep(self): return "d"
    def chat(self, messages, tools_enabled=True):
        return {"message": {"role": "assistant", "content": "<think>\n**ANALYSIS:** The user asks about a topic. This is a factual question requiring clear explanation.\n**CONTEXT:** I have knowledge of this topic. No tools needed.\n**PLAN:** Break down the concept step by step. Use examples. Verify accuracy.\n**REASONING:** Start with fundamentals, build to complexity. Check for edge cases.\n**VERIFICATION:** Double-check facts. Consider alternative interpretations.\n**CONFIDENCE:** 8\n**IMPROVEMENT:** Could add visual metaphor next time for better intuition.\n</think>\nHere is the answer."}}
    def simple_chat(self, messages, on_token=None): return "test"
    def list_models(self): return ["m1"]


class TestBrainFullThinking(BaseBrain):
    def _default_fast(self): return "f"
    def _default_smart(self): return "s"
    def _default_deep(self): return "d"
    def chat(self, messages, tools_enabled=True):
        import random
        quality = random.choice(["full", "partial", "none"])
        if quality == "full":
            return {"message": {"role": "assistant", "content": "<think>\n**ANALYSIS:** User query requires detailed analysis of the problem space and requirements.\n**CONTEXT:** I have sufficient knowledge to answer this question thoroughly.\n**PLAN:** Step one: analyze. Step two: structure response. Step three: verify.\n**REASONING:** The key insight is that this requires careful consideration of tradeoffs.\n**VERIFICATION:** Check that all aspects of the query are addressed. Edge cases handled.\n**CONFIDENCE:** 9\n**IMPROVEMENT:** A diagram or code example could enhance understanding next time.\n</think>\nFull answer."}}
        elif quality == "partial":
            return {"message": {"role": "assistant", "content": "<think>\n**ANALYSIS:** Simple question.\n**PLAN:** Answer directly.\n**CONFIDENCE:** 5\n</think>\nPartial answer."}}
        else:
            return {"message": {"role": "assistant", "content": "No thinking here."}}
    def simple_chat(self, messages, on_token=None): return "test"
    def list_models(self): return ["m1"]


def test_thinking_pipeline_all_sections():
    b = TestBrainE2E({})
    result = b.chat([{"role": "user", "content": "test"}])
    cleaned = b._clean_content(result["message"]["content"])
    metrics = b._extract_thinking_metrics()
    assert metrics["has_analysis"], "ANALYSIS section required"
    assert metrics["has_plan"], "PLAN section required"
    assert metrics["has_verification"], "VERIFICATION section required"
    assert metrics["has_improvement"], "IMPROVEMENT section required"
    assert metrics["confidence"] >= 1, "Confidence must be set"
    assert metrics["reasoning_depth"] > 0, "Reasoning depth must be > 0"
    assert metrics["quality_score"] > 0, "Quality score must be > 0"
    assert "think" not in cleaned, "Think tags must be removed from content"


def test_thinking_quality_scoring():
    b = TestBrainFullThinking({})
    scores = []
    for _ in range(20):
        result = b.chat([{"role": "user", "content": "test"}])
        b._clean_content(result["message"]["content"])
        metrics = b._extract_thinking_metrics()
        scores.append(metrics["quality_score"])
    assert max(scores) > min(scores), "Quality scores should vary"
    assert any(s > 5 for s in scores), "Some scores should be high"
    assert any(s < 5 for s in scores) or all(s == 0 for s in scores), "Some scores should be low or zero"


def test_thinking_log_format():
    b = TestBrainE2E({})
    result = b.chat([{"role": "user", "content": "test query"}])
    b._clean_content(result["message"]["content"])
    metrics = b._extract_thinking_metrics()
    assert "reasoning_depth" in metrics
    assert "has_analysis" in metrics
    assert "has_plan" in metrics
    assert "has_verification" in metrics
    assert "has_improvement" in metrics
    assert "confidence" in metrics
    assert "quality_score" in metrics
    assert "sections" in metrics
    assert "section_words" in metrics


def test_thinking_section_word_counts():
    b = TestBrainE2E({})
    result = b.chat([{"role": "user", "content": "test"}])
    b._clean_content(result["message"]["content"])
    metrics = b._extract_thinking_metrics()
    sw = metrics.get("section_words", {})
    assert "analysis" in sw, "Analysis section words tracked"
    assert "improvement" in sw or sw == {}, "may be empty if no think tag"


def test_relevant_tools_filtering():
    b = TestBrainE2E({})
    tools = [
        {"function": {"name": "web_search", "description": "Search web",
                      "parameters": {"type": "object", "properties": {}}}},
        {"function": {"name": "run_code", "description": "Execute code",
                      "parameters": {"type": "object", "properties": {}}}},
        {"function": {"name": "get_time", "description": "Get current time",
                      "parameters": {"type": "object", "properties": {}}}},
    ]
    b.register_tools(tools, lambda n: lambda: "ok")
    code_tools = b._relevant_tools([{"role": "user", "content": "write a python program"}])
    assert len(code_tools) > 0, "Should select tools for code query"
    names = [t["function"]["name"] for t in code_tools]
    assert "run_code" in names, "run_code should be relevant"


def test_error_sanitization():
    from core.brain import _sanitize_error
    cases = [
        ("sk-proj-ABC123DEF456GHI789JKL", "[REDACTED_KEY]"),
        ("gsk_a1b2c3d4e5f6g7h8i9j0k1l2", "[REDACTED_KEY]"),
        ("org_01ktayn60ae0xt41e0s2ebv4rs", "[REDACTED_ORG]"),
        ("rate_limit in 30m36.864s", "rate_limit in [REDACTED_TIME]"),
        ("normal error message", "normal error message"),
    ]
    for case_input, expected in cases:
        result = _sanitize_error(case_input)
        assert expected in result, f"'{case_input}' did not produce '{expected}'"


def test_rate_checker():
    from core.ratelimit import check_rate
    assert check_rate("test_checker", rate=100, burst=200), "Should allow first call"
    assert check_rate("test_checker2", rate=0, burst=0) is False, "Should deny zero-burst"


def test_caching_mechanism():
    from core.response_cache import ResponseCache
    cache = ResponseCache(max_size=10, default_ttl=60)
    msgs = [{"role": "user", "content": "hello"}]
    result = {"message": {"role": "assistant", "content": "hi"}}
    assert cache.get(msgs) is None, "Cache should miss on first get"
    cache.set(msgs, result)
    cached = cache.get(msgs)
    assert cached == result, "Cache should hit after set"
    assert cache.stats()["active"] == 1
    cache.invalidate()
    assert cache.get(msgs) is None, "Cache should miss after invalidate"


def test_caching_hit_tracker():
    from core.response_cache import ResponseCache
    cache = ResponseCache()
    tracker = cache.hit_rate_tracker()
    assert tracker.rate() == 0.0
    tracker.record_hit()
    tracker.record_miss()
    assert tracker.rate() == 0.5
    assert tracker.report()["hits"] == 1
    assert tracker.report()["misses"] == 1


def test_caching_ttl_expiry():
    from core.response_cache import ResponseCache
    cache = ResponseCache(default_ttl=0)
    cache.set([{"role": "user", "content": "x"}], "y")
    time.sleep(0.01)
    assert cache.get([{"role": "user", "content": "x"}]) is None


def test_caching_max_size():
    from core.response_cache import ResponseCache
    cache = ResponseCache(max_size=3)
    for i in range(5):
        cache.set([{"role": "user", "content": str(i)}], f"result{i}")
    stats = cache.stats()
    assert stats["size"] <= 3, f"Cache should evict, got {stats['size']}"


def test_web_artifact_component():
    from tools.web_artifacts import WebArtifactBuilder
    w = WebArtifactBuilder()
    html = w.create_component(name="test", html_content="<p>hello</p>")
    assert "<title>test</title>" in html
    assert "<p>hello</p>" in html
    assert "</html>" in html


def test_web_artifact_dashboard():
    from tools.web_artifacts import WebArtifactBuilder
    w = WebArtifactBuilder()
    html = w.create_dashboard(title="Stats", widgets=[
        {"type": "value", "title": "CPU", "data": "45%", "color": "#00ff00"},
        {"type": "list", "title": "Services", "data": ["nginx", "postgres"]},
    ])
    assert "Stats" in html
    assert "CPU" in html
    assert "45%" in html
    assert "nginx" in html


def test_web_artifact_interactive():
    from tools.web_artifacts import WebArtifactBuilder
    w = WebArtifactBuilder()
    html = w.create_interactive_artifact(title="App", components=[
        {"name": "form1", "type": "form", "content": "<input name='name'>"},
        {"name": "data1", "type": "data", "content": "some data"},
    ])
    assert "App" in html
    assert "form1" in html
    assert "some data" in html


def test_gif_builder_roundtrip():
    from tools.gif_builder import GIFBuilder
    import tempfile, os
    builder = GIFBuilder(width=16, height=16, fps=5)
    for _ in range(3):
        frame = [[(255, 0, 0) for _ in range(16)] for _ in range(16)]
        builder.add_frame(frame)
    tmp = tempfile.NamedTemporaryFile(suffix=".gif", delete=False)
    tmp.close()
    try:
        builder.save(tmp.name, num_colors=16)
        assert os.path.getsize(tmp.name) > 0
        with open(tmp.name, "rb") as f:
            assert f.read(3) == b"GIF"
    finally:
        os.unlink(tmp.name)


def test_gif_analysis():
    from tools.gif_builder import GIFBuilder
    import tempfile, os
    builder = GIFBuilder(width=32, height=32, fps=10)
    for _ in range(5):
        frame = [[(0, 255, 0) for _ in range(32)] for _ in range(32)]
        builder.add_frame(frame)
    tmp = tempfile.NamedTemporaryFile(suffix=".gif", delete=False)
    tmp.close()
    try:
        builder.save(tmp.name)
        analysis = builder._handle_analyze_gif(tmp.name)
        assert "32x32" in analysis
        assert "GIF" in analysis
    finally:
        os.unlink(tmp.name)


def test_mcp_builder_creates_tools():
    from tools.mcp_builder import MCPBuilder
    m = MCPBuilder()
    defs = m.get_tool_definitions()
    assert len(defs) >= 3
    names = [d["function"]["name"] for d in defs]
    assert "create_mcp_server" in names


def test_office_tools_loaded():
    from tools.office import OfficeTools
    o = OfficeTools()
    defs = o.get_tool_definitions()
    assert len(defs) >= 8
    names = [d["function"]["name"] for d in defs]
    assert "docx_add_comment" in names
    assert "pptx_add_slide" in names


def test_web_testing_tools_loaded():
    from tools.web_testing import WebTestingTools
    w = WebTestingTools()
    defs = w.get_tool_definitions()
    assert len(defs) >= 2
    names = [d["function"]["name"] for d in defs]


def test_swarm_agent_messaging():
    from core.agent_swarm import SwarmAgent, AgentSwarm, SwarmMessage
    b = TestBrainE2E({})
    swarm = AgentSwarm(brain=b)
    agent = SwarmAgent(name="test_agent", title="Test Agent", focus="testing", persona="tester", brain=b, swarm=swarm)
    assert agent.name == "test_agent"
    assert agent.focus == "testing"
    assert agent.persona == "tester"
    msg = SwarmMessage(sender="user", recipient="test_agent", msg_type="direct", subject="hello", content="hello world")
    agent.receive(msg)
    assert len(agent.inbox) == 1
    assert agent.inbox[0].content == "hello world"


def test_sanitize_error_edge_cases():
    from core.brain import _sanitize_error
    assert _sanitize_error("") == ""
    assert _sanitize_error(None) == "None"
    long = "x" * 5000
    assert len(_sanitize_error(long)) <= 1024
    assert _sanitize_error(42) == "42"
    assert _sanitize_error("normal text with no secrets") == "normal text with no secrets"


def test_conversation_encryption_roundtrip():
    from core.assistant import _encrypt_data, _decrypt_data
    try:
        data = "Hello, this is a secret message!"
        encrypted = _encrypt_data(data)
        assert encrypted != data
        decrypted = _decrypt_data(encrypted)
        assert decrypted == data
    except RuntimeError as e:
        if "cryptography" in str(e):
            import pytest
            pytest.skip("cryptography not installed")


def test_brain_models():
    b = TestBrainE2E({"models": {"fast": "f1", "smart": "s1", "deep": "d1"}})
    assert b.fast_model == "f1"
    assert b.smart_model == "s1"
    assert b.deep_model == "d1"
    assert b.current_model == "s1"
    assert b.select_model("") == "s1"
    assert b.select_model("hello") == "f1"
    assert b.select_model("write code") == "d1"


def test_tool_registration_validation():
    b = TestBrainE2E({})
    handlers = {}
    defs = [
        {"function": {"name": "tool1", "description": "desc1",
                      "parameters": {"type": "object", "properties": {}}}},
        {"function": {"name": "tool2", "description": "desc2",
                      "parameters": {"type": "object", "properties": {}}}},
    ]
    handlers["tool1"] = lambda: "ok1"
    handlers["tool2"] = lambda: "ok2"
    b.register_tools(defs, lambda n: handlers.get(n))
    assert "tool1" in b.tool_registry
    assert "tool2" in b.tool_registry
    assert len(b.tool_definitions) == 2


def test_health_check_returns_system_data():
    b = TestBrainE2E({})
    hc = b.health_check()
    assert hc["status"] == "OK"
    assert "total_calls" in hc
    assert "total_errors" in hc
    assert "tools_registered" in hc


def test_telemetry_tracking():
    b = TestBrainE2E({})
    stats = b.get_stats()
    assert stats["calls"] == 0
    b._telemetry["calls"] += 1
    b._telemetry["tokens"] += 100
    stats = b.get_stats()
    assert stats["calls"] == 1
    assert stats["tokens"] == 100
