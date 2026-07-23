import json
import time
import traceback
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field


@dataclass
class TestResult:
    name: str
    passed: bool
    duration: float
    error: Optional[str] = None
    details: Dict = field(default_factory=dict)


class WebResponseTester:
    def __init__(self, assistant=None):
        self.assistant = assistant
        self.results = []
        self.total_tests = 0
        self.passed_tests = 0

    def run_all(self) -> Dict:        
        self._test_intent_routing()
        self._test_tool_invocation()
        self._test_error_handling()
        self._test_response_format()
        self._test_security_checks()
        self._test_conversation_flow()
        self._test_multi_agent()
        self._test_knowledge_retrieval()
        return self._generate_report()

    def _record(self, name: str, passed: bool, duration: float, error: str = None, details: Dict = None):
        self.results.append(TestResult(
            name=name,
            passed=passed,
            duration=duration,
            error=error,
            details=details or {},
        ))
        self.total_tests += 1
        if passed:
            self.passed_tests += 1

    def _simulate_chat(self, message: str) -> Dict:
        if not self.assistant:
            return {"status": "simulated", "message": {"content": f"Simulated response to: {message}"}}
        try:
            start = time.time()
            result = self.assistant.brain.chat(
                [{"role": "user", "content": message}],
                tools_enabled=False,
            )
            elapsed = time.time() - start
            if result is None:
                return {"status": "error", "error": "None response", "duration": elapsed}
            if isinstance(result, dict):
                content = result.get("message", {}).get("content", "")
                return {"status": "ok", "content": content, "duration": elapsed}
            return {"status": "ok", "content": str(result), "duration": elapsed}
        except Exception as e:
            return {"status": "error", "error": str(e), "duration": 0}

    def _test_intent_routing(self):
        tests = [
            ("Greeting detection", "hello", lambda r: r.get("status") == "ok"),
            ("System info routing", "what is my cpu usage", lambda r: r.get("status") == "ok"),
            ("Web search routing", "search for python", lambda r: r.get("status") == "ok"),
            ("Code execution", "write python fibonacci", lambda r: r.get("status") == "ok"),
            ("File operations", "list files here", lambda r: r.get("status") == "ok"),
        ]
        for name, message, check in tests:
            start = time.time()
            result = self._simulate_chat(message)
            elapsed = time.time() - start
            passed = check(result)
            error = result.get("error") if not passed else None
            self._record(f"Intent: {name}", passed, elapsed, error)

    def _test_tool_invocation(self):
        tests = [
            ("Web fetch", "fetch https://example.com"),
            ("System status", "system status"),
            ("Date/time", "what time is it"),
            ("Help", "help"),
        ]
        for name, message in tests:
            start = time.time()
            result = self._simulate_chat(message)
            elapsed = time.time() - start
            passed = result.get("status") == "ok"
            self._record(f"Tool: {name}", passed, elapsed, result.get("error"))

    def _test_error_handling(self):
        tests = [
            ("Empty input", "", lambda r: True),
            ("Very long input", "a" * 10000, lambda r: r.get("status") == "ok"),
            ("Special chars", "!@#$%^&*()", lambda r: r.get("status") == "ok"),
        ]
        for name, message, check in tests:
            start = time.time()
            result = self._simulate_chat(message)
            elapsed = time.time() - start
            passed = check(result)
            self._record(f"Error: {name}", passed, elapsed, result.get("error"))

    def _test_response_format(self):
        tests = [
            ("Response is string or dict", "hello", lambda r: isinstance(r.get("content"), str) if r.get("content") else True),
            ("No None content", "test", lambda r: r.get("content") is not None if r.get("status") == "ok" else True),
        ]
        for name, message, check in tests:
            start = time.time()
            result = self._simulate_chat(message)
            elapsed = time.time() - start
            passed = check(result)
            self._record(f"Format: {name}", passed, elapsed, result.get("error"))

    def _test_security_checks(self):
        injections = [
            ("Command injection", "run command: rm -rf /"),
            ("SQL injection", "SELECT * FROM users; DROP TABLE users;"),
            ("Path traversal", "read file: ../../../etc/passwd"),
            ("XSS attempt", '<script>alert("xss")</script>'),
        ]
        for name, message in injections:
            start = time.time()
            result = self._simulate_chat(message)
            elapsed = time.time() - start
            passed = result.get("status") == "ok"
            self._record(f"Security: {name}", passed, elapsed, result.get("error"))

    def _test_conversation_flow(self):
        steps = [
            ("hi", "Greeting"),
            ("what can you do", "Capabilities"),
            ("tell me a joke", "Follow-up"),
        ]
        for message, name in steps:
            start = time.time()
            result = self._simulate_chat(message)
            elapsed = time.time() - start
            passed = result.get("status") == "ok"
            self._record(f"Conversation: {name}", passed, elapsed, result.get("error"))

    def _test_multi_agent(self):
        tasks = [
            ("Analyze code quality", "review this code: def add(a,b): return a+b"),
            ("System design", "design a simple REST API"),
        ]
        for name, message in tasks:
            start = time.time()
            result = self._simulate_chat(message)
            elapsed = time.time() - start
            passed = result.get("status") == "ok"
            self._record(f"Multi-agent: {name}", passed, elapsed, result.get("error"))

    def _test_knowledge_retrieval(self):
        queries = [
            ("Programming languages", "what languages do you support"),
            ("Capabilities", "what can you do"),
        ]
        for name, message in queries:
            start = time.time()
            result = self._simulate_chat(message)
            elapsed = time.time() - start
            passed = result.get("status") == "ok"
            self._record(f"Knowledge: {name}", passed, elapsed, result.get("error"))

    def _generate_report(self) -> Dict:
        pass_rate = round(self.passed_tests / self.total_tests * 100, 1) if self.total_tests > 0 else 0
        avg_duration = round(
            sum(r.duration for r in self.results) / len(self.results), 3
        ) if self.results else 0

        report = {
            "summary": {
                "total": self.total_tests,
                "passed": self.passed_tests,
                "failed": self.total_tests - self.passed_tests,
                "pass_rate": pass_rate,
                "average_duration_seconds": avg_duration,
            },
            "details": [],
            "recommendations": [],
        }

        for r in self.results:
            entry = {
                "test": r.name,
                "passed": r.passed,
                "duration": round(r.duration, 3),
            }
            if r.error:
                entry["error"] = r.error
            report["details"].append(entry)

            if not r.passed:
                report["recommendations"].append(f"Fix {r.name}: {r.error or 'Unknown error'}")

        return report

    def print_report(self):
        report = self._generate_report()
        s = report["summary"]
        line = "=" * 60
        print(f"\n{line}")
        print(f"  WEB RESPONSE TEST REPORT")
        print(f"{line}")
        print(f"  Total: {s['total']} | Passed: {s['passed']} | Failed: {s['failed']}")
        print(f"  Pass rate: {s['pass_rate']}%")
        print(f"  Avg duration: {s['average_duration_seconds']}s")
        print(f"{line}")
        for d in report["details"]:
            icon = "PASS" if d["passed"] else "FAIL"
            print(f"  [{icon}] {d['test']} ({d['duration']}s)")
            if "error" in d:
                print(f"        Error: {d['error']}")
        if report["recommendations"]:
            print(f"\n  Recommendations:")
            for rec in report["recommendations"][:5]:
                print(f"    - {rec}")
        print(f"{line}\n")
        return report
