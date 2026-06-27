"""F.R.I.D.A.Y. Coding Skills Assessment (rate-limit resilient).

Batches questions into fewer API calls with delays to avoid 429.
Tests 7 categories: Algorithms, Data Structures, OOP, Debugging,
Optimization, System Design, and Code Quality.
"""

import sys, os, time, json, re, subprocess, unittest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


# Delay between API calls to avoid rate limits
API_DELAY = 3  # seconds between batches


def _init_brain():
    """Initialize the brain based on config provider."""
    from core.brain import OllamaBrain, GroqBrain
    config = {}
    config_path = os.path.join(os.path.dirname(__file__), "..", "config.json")
    if os.path.exists(config_path):
        with open(config_path) as f:
            config = json.load(f)
    provider = config.get("provider", "groq")
    registry = {
        "groq": GroqBrain,
        "ollama": OllamaBrain,
    }
    cls = registry.get(provider, GroqBrain)
    return cls(config)


def _ask(brain, prompt, retries=2):
    """Send a coding prompt with retry on rate limit."""
    messages = [{"role": "user", "content": prompt}]
    for attempt in range(retries + 1):
        result = brain.chat(messages, tools_enabled=False)
        content = result.get("message", {}).get("content", "")
        if "429" in content or "rate limit" in content.lower():
            if attempt < retries:
                wait = API_DELAY * (attempt + 1)
                print(f"\n    [RATE LIMIT] Waiting {wait}s before retry...")
                time.sleep(wait)
                continue
        return re.sub(r'<think>.*?</think>', '', content, flags=re.DOTALL).strip()
    return content


def _extract_code(response):
    """Extract Python code blocks from the response (handles python and py tags)."""
    blocks = re.findall(r'```(?:python|py)\n(.*?)```', response, re.DOTALL)
    return '\n\n'.join(blocks) if blocks else response


def _exec_code(code):
    """Safely execute code in a subprocess."""
    try:
        r = subprocess.run(
            [sys.executable, "-c", code],
            capture_output=True, text=True, timeout=10,
            cwd=os.path.join(os.path.dirname(__file__), "..")
        )
        return r.stdout.strip(), r.stderr.strip(), r.returncode
    except subprocess.TimeoutExpired:
        return "", "TIMEOUT", 1


class CodingSkillsAssessment(unittest.TestCase):
    """Comprehensive coding skills assessment for F.R.I.D.A.Y."""

    @classmethod
    def setUpClass(cls):
        try:
            cls.brain = _init_brain()
            cls.available = True
        except Exception as e:
            print(f"\n  [SKIP] Could not initialize brain: {e}")
            cls.available = False
        cls.results = {}

    def setUp(self):
        if not self.available:
            self.skipTest("Brain not available")

    @classmethod
    def _record(cls, category, name, passed, details=""):
        if category not in cls.results:
            cls.results[category] = []
        cls.results[category].append((name, passed, details))

    def _wait(self):
        """Wait between API calls to avoid rate limits."""
        time.sleep(API_DELAY)

    # ═══════════════════════════════════════════════════════════
    # BATCH 1: ALGORITHMS
    # ═══════════════════════════════════════════════════════════

    def test_01_algorithms_batch(self):
        """Algorithms: binary search, merge sort, two sum, fibonacci, BFS."""
        response = _ask(self.brain,
            "Write Python functions for ALL of these. Include time complexity and test assertions:\n"
            "1. binary_search(arr, target) - O(log n), returns index or -1\n"
            "2. merge_sort(arr) - O(n log n) sort\n"
            "3. two_sum(nums, target) - O(n) with hash map, return indices\n"
            "4. fibonacci(n) - O(n) DP, return nth fib number\n"
            "5. bfs(graph, start) - graph is dict, return visited list"
        )
        code = _extract_code(response)
        if code:
            # Ensure test assertions exist
            if "assert binary_search" not in code:
                code += "\nassert binary_search([1,3,5,7,9], 5) == 2\n"
            if "assert merge_sort" not in code:
                code += "\nassert merge_sort([3,1,4,1,5]) == [1,1,3,4,5]\n"
            if "assert two_sum" not in code:
                code += "\nassert sorted(two_sum([2,7,11,15], 9)) == [0,1]\n"
            if "assert fibonacci" not in code:
                code += "\nassert fibonacci(10) == 55\n"
            if "assert bfs" not in code:
                code += '\nassert bfs({"A":["B"],"B":[]}, "A")[0] == "A"\n'
            stdout, stderr, rc = _exec_code(code + '\nprint("PASS")')
            passed = rc == 0 and "PASS" in stdout
            self._record("Algorithms", "all_functions", passed, stderr[:100] if not passed else "")
            self.assertTrue(passed, f"Algorithms failed: {stderr[:200]}")
        else:
            self._record("Algorithms", "all", False, "No code extracted")
            self.fail("No code blocks in response")

        # Check complexity analysis
        has_complexity = any(kw in response.lower() for kw in ["o(n", "o(log", "o(1)", "time complexity"])
        self._record("Algorithms", "complexity_analysis", has_complexity)

    # ═══════════════════════════════════════════════════════════
    # BATCH 2: DATA STRUCTURES
    # ═══════════════════════════════════════════════════════════

    def test_02_data_structures_batch(self):
        """Data Structures: LinkedList, BST, LRU Cache."""
        self._wait()
        response = _ask(self.brain,
            "Write Python classes with test assertions:\n"
            "1. LinkedList with insert(val), delete(val), search(val), to_list()\n"
            "2. BST with insert(val), search(val), inorder() returning sorted list\n"
            "3. LRUCache(capacity) with get(key) and put(key, value) in O(1)"
        )
        code = _extract_code(response)
        if code:
            if "assert" not in code:
                code += """
ll = LinkedList()
for v in [3,1,2]: ll.insert(v)
assert sorted(ll.to_list()) == [1,2,3]
assert ll.search(1) == True
ll.delete(1)
assert ll.search(1) == False
tree = BST()
for v in [5,3,7,1]: tree.insert(v)
assert tree.inorder() == [1,3,5,7]
cache = LRUCache(2)
cache.put(1, "a"); cache.put(2, "b")
assert cache.get(1) == "a"
cache.put(3, "c")
assert cache.get(2) is None or cache.get(2) == -1
"""
            stdout, stderr, rc = _exec_code(code + '\nprint("PASS")')
            passed = rc == 0 and "PASS" in stdout
            self._record("Data Structures", "all_classes", passed, stderr[:100] if not passed else "")
            self.assertTrue(passed, f"Data structures failed: {stderr[:200]}")
        else:
            self._record("Data Structures", "all", False, "No code extracted")
            self.fail("No code blocks in response")

    # ═══════════════════════════════════════════════════════════
    # BATCH 3: OOP + DESIGN PATTERNS
    # ═══════════════════════════════════════════════════════════

    def test_03_oop_batch(self):
        """OOP: inheritance, decorators, context managers."""
        self._wait()
        response = _ask(self.brain,
            "Write Python code for:\n"
            "1. Shape hierarchy: abstract Shape with area()/perimeter(), Circle(r), Rectangle(w,h)\n"
            "2. @retry(max_attempts=3) decorator that retries on exception\n"
            "3. Timer context manager that measures execution time\n"
            "Include test assertions for each."
        )
        code = _extract_code(response)
        if code:
            if "assert" not in code:
                code += """
import math
c = Circle(5)
assert abs(c.area() - math.pi * 25) < 0.01
r = Rectangle(3, 4)
assert r.area() == 12
attempts = 0
@retry(max_attempts=3, delay=0.01)
def flaky():
    global attempts; attempts += 1
    if attempts < 3: raise ValueError("fail")
    return "ok"
assert flaky() == "ok"
"""
            stdout, stderr, rc = _exec_code(code + '\nprint("PASS")')
            passed = rc == 0 and "PASS" in stdout
            self._record("OOP", "all_patterns", passed, stderr[:100] if not passed else "")
            self.assertTrue(passed, f"OOP failed: {stderr[:200]}")
        else:
            self._record("OOP", "all", False, "No code extracted")
            self.fail("No code blocks in response")

    # ═══════════════════════════════════════════════════════════
    # BATCH 4: DEBUGGING + OPTIMIZATION (combined)
    # ═══════════════════════════════════════════════════════════

    def test_04_debug_optimize_batch(self):
        """Debugging and Optimization combined."""
        self._wait()
        response = _ask(self.brain,
            "1. Find and fix bugs in these snippets, explain each:\n\n"
            "Bug 1:\n```python\ndef find_max(lst):\n    max_val = lst[0]\n"
            "    for i in range(len(lst)):\n        if lst[i] > max_val: max_val = lst[i]\n"
            "    return max_val\n```\n\n"
            "Bug 2:\n```python\ndef count_down(n):\n    while n > 0:\n        print(n)\n```\n\n"
            "2. Optimize this to O(n) and write O(1) space is_palindrome:\n"
            "```python\ndef has_pair_with_sum(arr, target):\n"
            "    for i in range(len(arr)):\n"
            "        for j in range(i+1, len(arr)):\n"
            "            if arr[i]+arr[j]==target: return True\n    return False\n```"
        )
        lower = response.lower()

        # Debugging checks
        bug1 = any(kw in lower for kw in [
            "empty list", "indexerror", "index error", "edge case",
            "if not lst", "len(lst) == 0", "valueerror"
        ])
        self._record("Debugging", "empty_list_bug", bug1)

        bug2 = any(kw in lower for kw in [
            "decrement", "n -= 1", "n = n - 1", "n -=1",
            "infinite loop", "missing", "update n", "never decrease"
        ])
        self._record("Debugging", "infinite_loop_bug", bug2)

        # Optimization checks
        has_hash = any(kw in lower for kw in ["hash", "set", "seen", "lookup"])
        self._record("Optimization", "hash_optimization", has_hash)

        has_palindrome = any(kw in lower for kw in [
            "palindrome", "two pointer", "is_palindrome"
        ])
        self._record("Optimization", "palindrome_optimization", has_palindrome)

        self.assertTrue(bug1, "Should identify empty list bug")
        self.assertTrue(bug2, "Should identify infinite loop bug")

    # ═══════════════════════════════════════════════════════════
    # BATCH 5: SYSTEM DESIGN + CODE QUALITY (combined)
    # ═══════════════════════════════════════════════════════════

    def test_05_design_quality_batch(self):
        """System Design and Code Quality combined."""
        self._wait()
        response = _ask(self.brain,
            "Answer concisely:\n\n"
            "1. Rate limiter: implement RateLimiter class with allow(request_id), max N per window.\n\n"
            "2. URL shortener: API endpoints, data model, short code strategy, complexity.\n\n"
            "3. Code review - find security issues:\n"
            "```python\ndef get_user_data(user_id):\n"
            "    query = f\"SELECT * FROM users WHERE id = {user_id}\"\n"
            "    result = db.execute(query)\n    return {'user': result[0], 'password': result[0]['password']}\n```\n\n"
            "4. Refactor to SOLID:\n"
            "```python\ndef process_data(data, type):\n"
            "    if type == 'csv': return [line.split(',') for line in data.split('\\n')]\n"
            "    elif type == 'json':\n        import json; return json.loads(data)\n```"
        )
        lower = response.lower()

        # System Design
        has_rate_limiter = any(kw in lower for kw in [
            "ratelimiter", "token bucket", "sliding window", "def allow"
        ])
        self._record("System Design", "rate_limiter", has_rate_limiter)

        has_url_shortener = any(kw in lower for kw in [
            "endpoint", "api", "shorten", "base62", "hash"
        ])
        self._record("System Design", "url_shortener", has_url_shortener)

        # Code Quality
        has_injection = any(kw in lower for kw in [
            "sql injection", "injection", "parameterized", "sanitize"
        ])
        self._record("Code Quality", "sql_injection", has_injection)

        has_solid = any(kw in lower for kw in [
            "strategy", "polymorphism", "single responsibility", "solid", "class"
        ])
        self._record("Code Quality", "solid_refactoring", has_solid)

        self.assertTrue(has_rate_limiter, "Should implement rate limiter")
        self.assertTrue(has_url_shortener, "Should design URL shortener")
        self.assertTrue(has_injection, "Should identify SQL injection")
        self.assertTrue(has_solid, "Should suggest SOLID refactoring")

    # ═══════════════════════════════════════════════════════════
    # SCORECARD
    # ═══════════════════════════════════════════════════════════

    def test_z_scorecard(self):
        """Print the final scorecard."""
        print("\n" + "=" * 60)
        print("  F.R.I.D.A.Y. CODING SKILLS SCORECARD")
        print("=" * 60)

        total_pass = 0
        total_fail = 0
        for category, tests in self.results.items():
            passed = sum(1 for _, p, _ in tests if p)
            failed = sum(1 for _, p, _ in tests if not p)
            total_pass += passed
            total_fail += failed
            status = "PASS" if failed == 0 else f"{failed} FAILED"
            print(f"  {category:20s}  {passed}/{passed+failed}  [{status}]")
            for name, p, detail in tests:
                icon = "  ✅" if p else "  ❌"
                extra = f" ({detail[:50]})" if detail and not p else ""
                print(f"    {icon} {name}{extra}")

        total = total_pass + total_fail
        pct = (total_pass / total * 100) if total > 0 else 0
        print(f"\n  TOTAL: {total_pass}/{total} passed ({pct:.0f}%)")
        print("=" * 60)


if __name__ == "__main__":
    unittest.main(verbosity=2)
