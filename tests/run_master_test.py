"""Master test runner: tests all JARVIS systems and trains thinking protocol.
Run: python tests/run_master_test.py
"""

import sys, os, time, json, subprocess, re
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

PASS = 0
FAIL = 0
TOTAL_TESTS = 0
RESULTS = []

def test(name, fn, *args, **kwargs):
    global PASS, FAIL, TOTAL_TESTS
    TOTAL_TESTS += 1
    try:
        fn(*args, **kwargs)
        PASS += 1
        RESULTS.append((name, "PASS", ""))
        print(f"  PASS  {name}")
    except Exception as e:
        FAIL += 1
        RESULTS.append((name, "FAIL", str(e)))
        print(f"  FAIL  {name}: {e}")

def run_pytest_suite():
    print("\n--- Running existing pytest suite ---")
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/", "-x", "--tb=short"],
        cwd=str(ROOT), capture_output=True, text=True, timeout=120
    )
    print(result.stdout[-2000:] if len(result.stdout) > 2000 else result.stdout)
    if result.stderr:
        print(result.stderr[-1000:])
    return result.returncode == 0

def test_thinking_training():
    print("\n--- Thinking Training ---")
    from core.thinking_protocol import validate_thinking, generate_thinking_section, ThinkingTrainer, REQUIRED_SECTIONS
    trainer = ThinkingTrainer()
    content_with_thinking = """<think>
**ANALYSIS:** The user asks about hash tables. This is a data structure question requiring explanation of the core mechanism, collision handling, and complexity analysis. The user likely wants intuition not just definition.
**CONTEXT:** I have deep knowledge of hash tables, collision resolution strategies, and time complexity analysis. No external tools needed.
**PLAN:** Start with analogy, explain core mechanism, cover collision handling, provide complexity analysis, show example.
**REASONING:** An analogy first builds intuition. Then layer in technical detail. Must distinguish average case O(1) from worst case O(n) as this is the most common point of confusion.
**VERIFICATION:** Check that analogy accurately represents mechanism. Verify complexity claims. Ensure example compiles and runs correctly. Would a beginner understand this?
**CONFIDENCE:** 9
**IMPROVEMENT:** Next time include visual diagram and mention how Python dict uses randomization to prevent hash collision DoS attacks.
</think>
A hash table maps keys to values using a hash function..."""
    v = validate_thinking(content_with_thinking)
    assert v["valid"], f"Validation should pass: {v['sections_missing']}"
    assert v["has_think_tags"]
    assert len(v["sections_found"]) == len(REQUIRED_SECTIONS)
    for s in ["ANALYSIS", "PLAN", "VERIFICATION", "IMPROVEMENT"]:
        assert v["section_word_counts"].get(s, 0) >= 30, f"{s} too short: {v['section_word_counts'].get(s, 0)}"
    assert v["passes_minimum"]
    content_no_thinking = "Direct answer without thinking."
    v2 = validate_thinking(content_no_thinking)
    assert not v2["has_think_tags"]
    assert not v2["valid"]
    generated = generate_thinking_section(analysis="Test analysis of the query requirements and constraints.")
    assert "<think>" in generated
    assert "</think>" in generated
    assert "**ANALYSIS:" in generated
    trainer.train_step(content_no_thinking, content_with_thinking)
    report = trainer.get_report()
    assert report["total_trained"] == 1
    assert report["improved_count"] == 1
    assert report["improvement_rate"] == 100.0
    suggestions = trainer.suggest_improvements(content_no_thinking)
    assert len(suggestions) > 0
    print(f"  PASS  Thinking protocol: {len(REQUIRED_SECTIONS)} sections, trainer works, suggestions generated")

def test_response_safety():
    print("\n--- Response Safety ---")
    from core.response_safety import safe_get, extract_response_content, ensure_result_dict
    d = {"a": {"b": "value"}}
    assert safe_get(d, "a", "b") == "value"
    assert safe_get(d, "x", "y") is None
    assert safe_get(d, "x", "y", default="fallback") == "fallback"
    assert safe_get(None, "x") is None
    response = {"message": {"role": "assistant", "content": "Hello"}}
    assert extract_response_content(response) == "Hello"
    assert extract_response_content({"message": {"role": "assistant", "content": None}}) == ""
    assert extract_response_content(None) == ""
    result = ensure_result_dict(None)
    assert result == {}
    assert ensure_result_dict({"key": "val"}) == {"key": "val"}
    assert ensure_result_dict("string") == {}
    print(f"  PASS  Response safety: safe_get, extract, ensure_result all work")

def test_session_manager():
    print("\n--- Session Manager ---")
    from core.session_manager import SessionManager, AgentSession
    import tempfile, shutil
    tmpdir = tempfile.mkdtemp()
    try:
        mgr = SessionManager(storage_dir=tmpdir)
        session = mgr.create_session(metadata={"user": "test"})
        assert session is not None
        assert session.session_id is not None
        session.add_message({"role": "user", "content": "hello"})
        session.add_message({"role": "assistant", "content": "hi"})
        assert len(session.get_conversation()) == 2
        loaded = mgr.get_session(session.session_id)
        assert loaded is not None
        assert len(loaded.get_conversation()) == 2
        sessions = mgr.list_sessions()
        assert len(sessions) >= 1
        mgr.delete_session(session.session_id)
        assert mgr.get_session(session.session_id) is None
        print(f"  PASS  Session manager: create, persist, list, delete")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)

def test_project_analyzer():
    print("\n--- Project Analyzer ---")
    from core.project_analyzer import ProjectAnalyzer
    import tempfile
    tmpdir = tempfile.mkdtemp()
    try:
        pa = ProjectAnalyzer()
        (Path(tmpdir) / "package.json").write_text('{"name": "test", "version": "1.0.0"}')
        (Path(tmpdir) / "README.md").write_text("# Test Project")
        profile = pa.analyze_project(tmpdir)
        assert profile is not None
        assert "language" in profile
        agents_md = pa.generate_agents_md(tmpdir)
        assert agents_md is not None
        assert len(agents_md) > 0
        print(f"  PASS  Project analyzer: detect, profile, AGENTS.md")
    finally:
        import shutil
        shutil.rmtree(tmpdir, ignore_errors=True)

def test_brain_body_structure():
    print("\n--- Opencode Body Structure ---")
    from core.brain import BaseBrain
    class TestBrain(BaseBrain):
        def _default_fast(self): return "f"
        def _default_smart(self): return "s"
        def _default_deep(self): return "d"
        def chat(self, messages, tools_enabled=True):
            return {"message": {"role": "assistant", "content": "<think>\n**ANALYSIS:** Test analysis.\n**PLAN:** Test plan.\n**VERIFICATION:** Test verification.\n**CONFIDENCE:** 8\n**IMPROVEMENT:** Test improvement.\n**CONTEXT:** Test context.\n**REASONING:** Test reasoning.\n</think>\nThe answer here.\n```python\nprint('hello')\n```"}}
        def simple_chat(self, messages, on_token=None): return "test"
        def list_models(self): return ["m1"]
    b = TestBrain({})
    response_text = "<think>\n**ANALYSIS:** Test analysis.\n**PLAN:** Test plan.\n**VERIFICATION:** Test verif.\n**IMPROVEMENT:** Test improv.\n**CONTEXT:** Test context.\n**REASONING:** Test reason.\n**CONFIDENCE:** 8\n</think>\nThe answer is X.\n```python\nprint('hello')\n```"
    body = b.parse_body_structure(response_text)
    assert "thinking" in body
    assert "<think>" in body["thinking"]
    assert "response" in body
    assert "The answer is X" in body["response"]
    assert "code" in body
    assert "print" in body["code"]
    assert "metadata" in body
    print(f"  PASS  Body structure: thinking, response, code, metadata extracted")

def test_training_pipeline_exists():
    print("\n--- Training Pipeline ---")
    from core.train_thinking import TRAINING_QUERIES, MIN_WORDS_PER_SECTION, MAX_ATTEMPTS
    assert len(TRAINING_QUERIES) >= 10
    assert len(MIN_WORDS_PER_SECTION) >= 4
    assert MAX_ATTEMPTS >= 2
    print(f"  PASS  Training pipeline: {len(TRAINING_QUERIES)} queries, {len(MIN_WORDS_PER_SECTION)} sections, {MAX_ATTEMPTS} max attempts")

def test_web_response_tester():
    print("\n--- Web Response Tester ---")
    from core.web_response_test import WebResponseTester
    tester = WebResponseTester()
    assert tester is not None
    print(f"  PASS  Web response tester initialized")

def run_thinking_training_loop():
    print("\n========== THINKING TRAINING LOOP ==========")
    from core.train_thinking import ThinkingTrainingSession
    session = ThinkingTrainingSession()
    score = session.run()
    print(f"\n  FINAL SCORE: {score}/100")
    if score >= 95:
        print("  STATUS: PASSED - thinking protocol mastered")
    elif score >= 80:
        print("  STATUS: ADEQUATE - needs more training iterations")
    else:
        print("  STATUS: FAILING - significant training required")
    return score

if __name__ == "__main__":
    print("=" * 60)
    print("  JARVIS MASTER TEST SUITE")
    print("=" * 60)

    test("Thinking validation full sections", test_thinking_training)
    test("Response safety utilities", test_response_safety)
    test("Session manager CRUD", test_session_manager)
    test("Project analyzer detection", test_project_analyzer)
    test("Opencode body structure parse", test_brain_body_structure)
    test("Training pipeline config", test_training_pipeline_exists)
    test("Web response tester init", test_web_response_tester)

    print(f"\n{'=' * 60}")
    print(f"  UNIT TESTS: {PASS}/{TOTAL_TESTS} passed")
    if FAIL > 0:
        print(f"  FAILURES:")
        for name, status, err in RESULTS:
            if status == "FAIL":
                print(f"    {name}: {err[:200]}")
    print(f"{'=' * 60}")

    if FAIL == 0:
        pytest_ok = run_pytest_suite()
        training_score = run_thinking_training_loop()

        print(f"\n{'=' * 60}")
        print(f"  FINAL VERDICT")
        print(f"{'=' * 60}")
        print(f"  Pytest suite:      {'PASS' if pytest_ok else 'FAIL'}")
        print(f"  Thinking training: {training_score:.1f}/100")
        print(f"{'=' * 60}")

    sys.exit(0 if FAIL == 0 else 1)
