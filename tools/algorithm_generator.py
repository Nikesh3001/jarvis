import ast
import time as _time
import textwrap
from core.ratelimit import check_rate


_ALGORITHM_PROMPT = """You are an elite algorithm engineer. Generate production-quality algorithm implementations.

For each algorithm, include:
1. **Implementation** with complete, working code
2. **Time & space complexity** analysis (Big O)
3. **Edge cases** handled
4. **Usage examples**

Generate clean, idiomatic code with type hints. Use pure Python with no external deps.
Focus on correctness, efficiency, and readability."""

_OPTIMIZE_PROMPT = """You are an algorithm optimization expert. Analyze the given code and:
1. Identify performance bottlenecks
2. Suggest specific optimizations
3. Provide the optimized implementation
4. Explain the improvement (before/after complexity)
5. Note any tradeoffs (memory vs speed, readability vs performance)"""

_BENCHMARK_PROMPT = """You are a benchmarking specialist. Given an algorithm implementation:
1. Generate representative test inputs of increasing sizes
2. Measure execution time for each size
3. Report results (input size → time)
4. Fit to complexity class (O(n), O(n log n), O(n^2), etc.)
5. Identify any performance anomalies"""


class AlgorithmGenerator:
    def __init__(self, brain=None):
        self._brain = brain

    def generate(self, description, language="python", constraints=""):
        topic = textwrap.dedent(f"""
        Generate a {language} algorithm implementation for:
        {description}

        Constraints and requirements:
        {constraints or "None specified"}

        Provide complete working code with complexity analysis and usage examples.
        """).strip()
        return self._call_llm(_ALGORITHM_PROMPT, topic)

    def optimize(self, code, goal="speed"):
        safe_code = code[:500]
        topic = textwrap.dedent(f"""
        Optimize the following code for {goal}:

        ```python
        {safe_code}
        ```
        === END OF USER CODE ===

        Analyze bottlenecks, provide optimized code, explain the improvement.
        """).strip()
        return self._call_llm(_OPTIMIZE_PROMPT, topic)

    def benchmark(self, code, input_sizes=None, timeout=10):
        if input_sizes is None:
            input_sizes = [10, 100, 1000]
        safe_code = code[:500]
        topic = textwrap.dedent(f"""
        Given this algorithm implementation:

        ```python
        {safe_code}
        ```
        === END OF USER CODE ===

        Benchmark it with input sizes: {input_sizes}
        Generate test harness, measure execution time, report results.
        """).strip()
        return self._call_llm(_BENCHMARK_PROMPT, topic)

    def analyze_complexity(self, code):
        try:
            tree = ast.parse(code)
        except SyntaxError as e:
            return f"Syntax error in code: {e}"
        loops = 0
        nested_loops = 0
        recursive_calls = 0
        loop_nodes = [n for n in ast.walk(tree) if isinstance(n, (ast.For, ast.While))]
        for node in loop_nodes:
            is_nested = False
            for other in loop_nodes:
                if other is not node and node in set(ast.walk(other)):
                    is_nested = True
                    break
            if is_nested:
                nested_loops += 1
            else:
                loops += 1
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                for child in ast.walk(tree):
                    if isinstance(child, ast.FunctionDef) and child.name == node.func.id:
                        for sub in ast.walk(child):
                            if isinstance(sub, ast.Call) and isinstance(sub.func, ast.Name) and sub.func.id == child.name:
                                recursive_calls += 1
        result_parts = [f"Loops: {loops}, Nested loops: {nested_loops}, Recursive calls: {recursive_calls}"]
        if recursive_calls > 0:
            result_parts.append("Likely complexity: O(2^n) or O(n!) — recursive")
        elif nested_loops > 1:
            result_parts.append(f"Likely complexity: O(n^{nested_loops + 1}) — multiply nested loops")
        elif nested_loops == 1:
            result_parts.append("Likely complexity: O(n^2) — nested loops")
        elif loops > 0:
            result_parts.append("Likely complexity: O(n) — single loop (unless divide-and-conquer)")
        else:
            result_parts.append("Likely complexity: O(1) — constant time")
        return "\n".join(result_parts)

    def _call_llm(self, system_prompt, user_message):
        if self._brain is None:
            return "Algorithm generation requires a configured AI brain."
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ]
        result = self._brain.chat_with_tools(messages, on_speak=lambda t: None)
        if isinstance(result, dict):
            return result.get("message", {}).get("content", str(result))
        return str(result)

    def get_tool_definitions(self):
        return [
            {
                "type": "function",
                "function": {
                    "name": "generate_algorithm",
                    "description": "Generate a complete algorithm implementation from a natural language description. Returns working code with complexity analysis and usage examples.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "description": {"type": "string", "description": "What the algorithm should do (natural language)"},
                            "language": {"type": "string", "description": "Programming language (default: python)", "default": "python"},
                            "constraints": {"type": "string", "description": "Performance constraints or requirements (optional)", "default": ""},
                        },
                        "required": ["description"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "optimize_algorithm",
                    "description": "Analyze an algorithm implementation and return optimized version with performance improvement analysis.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "code": {"type": "string", "description": "The algorithm source code to optimize"},
                            "goal": {"type": "string", "description": "Optimization goal: speed, memory, or readability", "enum": ["speed", "memory", "readability"], "default": "speed"},
                        },
                        "required": ["code"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "benchmark_algorithm",
                    "description": "Benchmark an algorithm implementation with test inputs of increasing size and report performance results.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "code": {"type": "string", "description": "The algorithm source code to benchmark"},
                            "input_sizes": {"type": "string", "description": "Comma-separated input sizes to test (default: 10,100,1000)", "default": "10,100,1000"},
                        },
                        "required": ["code"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "analyze_complexity",
                    "description": "Analyze the time and space complexity of an algorithm implementation via AST analysis.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "code": {"type": "string", "description": "The algorithm source code to analyze"},
                        },
                        "required": ["code"],
                    },
                },
            },
        ]

    def get_handler(self, name):
        handlers = {
            "generate_algorithm": lambda desc, lang="python", constr="": self._check("generate", desc, lang, constr),
            "optimize_algorithm": lambda code, goal="speed": self._check("optimize", code, goal),
            "benchmark_algorithm": lambda code, input_sizes="10,100,1000": self._check("benchmark", code, input_sizes),
            "analyze_complexity": lambda code: self._check("analyze", code),
        }
        return handlers.get(name)

    def _check(self, action, *args):
        if not check_rate(f"algo:{action}", rate=10, burst=20):
            return "Rate limited"
        try:
            if action == "generate":
                return self.generate(*args)
            if action == "optimize":
                return self.optimize(*args)
            if action == "benchmark":
                sizes = [int(s.strip()) for s in args[1].split(",") if s.strip()] if len(args) > 1 else [10, 100, 1000]
                return self.benchmark(args[0], sizes)
            if action == "analyze":
                return self.analyze_complexity(args[0])
        except Exception as e:
            return f"[Algorithm Error] {str(e)[:300]}"
        return f"[Algorithm Error] Unknown action: {action}"