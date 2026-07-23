"""Tests for AlgorithmGenerator tools."""

import sys, os, unittest
from unittest.mock import MagicMock
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from tools.algorithm_generator import AlgorithmGenerator


class TestInit(unittest.TestCase):
    def test_init_without_brain(self):
        ag = AlgorithmGenerator()
        self.assertIsNone(ag._brain)

    def test_init_with_brain(self):
        mock_brain = MagicMock()
        ag = AlgorithmGenerator(brain=mock_brain)
        self.assertIs(ag._brain, mock_brain)


class TestAnalyzeComplexity(unittest.TestCase):
    def setUp(self):
        self.ag = AlgorithmGenerator()

    def test_constant_time(self):
        code = "def foo():\n    return 42"
        result = self.ag.analyze_complexity(code)
        self.assertIn("O(1)", result)

    def test_linear_time(self):
        code = "def foo(n):\n    for i in range(n):\n        print(i)"
        result = self.ag.analyze_complexity(code)
        self.assertIn("O(n)", result)

    def test_nested_loops(self):
        code = "def foo(n):\n    for i in range(n):\n        for j in range(n):\n            print(i,j)"
        result = self.ag.analyze_complexity(code)
        self.assertIn("O(n^2)", result)

    def test_double_nested_loops(self):
        code = "def foo(n):\n    for i in range(n):\n        for j in range(n):\n            for k in range(n):\n                print(i,j,k)"
        result = self.ag.analyze_complexity(code)
        self.assertIn("O(n^", result)

    def test_while_loop(self):
        code = "def foo(n):\n    while n > 0:\n        n -= 1"
        result = self.ag.analyze_complexity(code)
        self.assertIn("O(n)", result)

    def test_recursive_detection(self):
        code = "def fib(n):\n    if n < 2:\n        return n\n    return fib(n-1) + fib(n-2)"
        result = self.ag.analyze_complexity(code)
        self.assertIn("recursive", result.lower())

    def test_syntax_error(self):
        code = "def foo(:\n    pass"
        result = self.ag.analyze_complexity(code)
        self.assertIn("Syntax error", result)

    def test_no_loops_no_recursion(self):
        code = "def foo(a, b):\n    return a + b"
        result = self.ag.analyze_complexity(code)
        self.assertIn("O(1)", result)

    def test_while_with_nested_for(self):
        code = "def foo(n):\n    i = 0\n    while i < n:\n        for j in range(n):\n            print(i,j)\n        i += 1"
        result = self.ag.analyze_complexity(code)
        self.assertIn("nested", result.lower())


class TestCallLlm(unittest.TestCase):
    def test_no_brain_returns_message(self):
        ag = AlgorithmGenerator()
        result = ag._call_llm("system", "user")
        self.assertEqual(result, "Algorithm generation requires a configured AI brain.")

    def test_with_brain_returns_content(self):
        mock_brain = MagicMock()
        mock_brain.chat_with_tools.return_value = {"message": {"content": "result"}}
        ag = AlgorithmGenerator(brain=mock_brain)
        result = ag._call_llm("system", "user")
        self.assertEqual(result, "result")

    def test_with_brain_non_dict_response(self):
        mock_brain = MagicMock()
        mock_brain.chat_with_tools.return_value = "plain string"
        ag = AlgorithmGenerator(brain=mock_brain)
        result = ag._call_llm("system", "user")
        self.assertEqual(result, "plain string")


class TestToolDefinitions(unittest.TestCase):
    def setUp(self):
        self.ag = AlgorithmGenerator()

    def test_returns_list(self):
        defs = self.ag.get_tool_definitions()
        self.assertIsInstance(defs, list)

    def test_has_four_tools(self):
        defs = self.ag.get_tool_definitions()
        self.assertEqual(len(defs), 4)

    def test_each_tool_has_required_structure(self):
        defs = self.ag.get_tool_definitions()
        for d in defs:
            self.assertIn("type", d)
            self.assertEqual(d["type"], "function")
            self.assertIn("function", d)
            fn = d["function"]
            self.assertIn("name", fn)
            self.assertIn("description", fn)
            self.assertIn("parameters", fn)
            self.assertIn("properties", fn["parameters"])

    def test_tool_names(self):
        defs = self.ag.get_tool_definitions()
        names = [d["function"]["name"] for d in defs]
        self.assertIn("generate_algorithm", names)
        self.assertIn("optimize_algorithm", names)
        self.assertIn("benchmark_algorithm", names)
        self.assertIn("analyze_complexity", names)


class TestHandlerRegistry(unittest.TestCase):
    def setUp(self):
        self.ag = AlgorithmGenerator()

    def test_all_tool_names_have_handlers(self):
        defs = self.ag.get_tool_definitions()
        for d in defs:
            name = d["function"]["name"]
            handler = self.ag.get_handler(name)
            self.assertIsNotNone(handler, f"No handler for {name}")
            self.assertTrue(callable(handler), f"Handler for {name} not callable")

    def test_unknown_handler_returns_none(self):
        self.assertIsNone(self.ag.get_handler("nonexistent_tool"))

    def test_generate_handler_signature(self):
        handler = self.ag.get_handler("generate_algorithm")
        code = handler.__code__
        self.assertIn("desc", code.co_varnames[:code.co_argcount])

    def test_optimize_handler_signature(self):
        handler = self.ag.get_handler("optimize_algorithm")
        code = handler.__code__
        self.assertIn("code", code.co_varnames[:code.co_argcount])

    def test_benchmark_handler_signature(self):
        handler = self.ag.get_handler("benchmark_algorithm")
        code = handler.__code__
        self.assertIn("code", code.co_varnames[:code.co_argcount])

    def test_analyze_handler_signature(self):
        handler = self.ag.get_handler("analyze_complexity")
        code = handler.__code__
        self.assertIn("code", code.co_varnames[:code.co_argcount])


class TestRateLimit(unittest.TestCase):
    def test_check_rate_key_format(self):
        from core.ratelimit import check_rate
        result = check_rate("algo:generate", rate=100, burst=100)
        self.assertTrue(result)


class TestCheckWrapper(unittest.TestCase):
    def setUp(self):
        self.ag = AlgorithmGenerator()

    def test_check_generate_no_brain(self):
        result = self.ag._check("generate", "sort a list", "python", "")
        self.assertIn("requires a configured AI brain", result)

    def test_check_analyze_constant_time(self):
        result = self.ag._check("analyze", "def foo():\n    return 1")
        self.assertIn("O(1)", result)

    def test_check_optimize_no_brain(self):
        result = self.ag._check("optimize", "def foo():\n    return 1", "speed")
        self.assertIn("requires a configured AI brain", result)

    def test_check_unknown_action(self):
        result = self.ag._check("unknown", "code")
        self.assertIn("Algorithm Error", result)


if __name__ == "__main__":
    unittest.main()
