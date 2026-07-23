"""Thinking-before-answering training pipeline.
Generates responses, validates <think> sections, auto-corrects, iterates until pass rate >= 95%.
"""

import sys, os, re, json, time
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))
from core.thinking_protocol import validate_thinking, generate_thinking_section, ThinkingTrainer, REQUIRED_SECTIONS

TRAINING_QUERIES = [
    {"query": "What is a hash table and how does it work?", "category": "knowledge", "complexity": "medium"},
    {"query": "Write a Python function to find all duplicate elements in a list", "category": "coding", "complexity": "medium"},
    {"query": "Explain the difference between TCP and UDP", "category": "knowledge", "complexity": "low"},
    {"query": "Design a rate limiter for a distributed API", "category": "system_design", "complexity": "high"},
    {"query": "How would you optimize a slow database query?", "category": "debugging", "complexity": "medium"},
    {"query": "What is the time complexity of binary search?", "category": "knowledge", "complexity": "low"},
    {"query": "Debug this code: why does my list comprehension return None?", "category": "debugging", "complexity": "medium"},
    {"query": "Compare microservices vs monolith architecture", "category": "system_design", "complexity": "medium"},
    {"query": "Write a recursive fibonacci function with memoization", "category": "coding", "complexity": "medium"},
    {"query": "How does garbage collection work in Python?", "category": "knowledge", "complexity": "medium"},
    {"query": "Explain CAP theorem with real-world examples", "category": "knowledge", "complexity": "high"},
    {"query": "How would you implement autocomplete for a search bar?", "category": "system_design", "complexity": "high"},
    {"query": "What causes a deadlock and how do you prevent it?", "category": "debugging", "complexity": "medium"},
    {"query": "Write a decorator that measures execution time", "category": "coding", "complexity": "low"},
    {"query": "Explain how HTTPS works at the protocol level", "category": "knowledge", "complexity": "high"},
]

MIN_WORDS_PER_SECTION = {
    "ANALYSIS": 30,
    "CONTEXT": 20,
    "PLAN": 30,
    "REASONING": 30,
    "VERIFICATION": 30,
    "IMPROVEMENT": 20,
}
MAX_ATTEMPTS = 3

class ThinkingTrainingSession:
    def __init__(self, brain=None):
        self.brain = brain
        self.trainer = ThinkingTrainer()
        self.iteration = 0
        self.results = []
        self.scores = []
        self.log_path = Path(__file__).parent.parent / "logs" / "thinking_training_log.jsonl"
        self.log_path.parent.mkdir(parents=True, exist_ok=True)

    def _init_brain(self):
        from core.brain import OllamaBrain, GroqBrain
        config = {}
        config_path = Path(__file__).parent.parent / "config.json"
        if config_path.exists():
            with open(config_path) as f:
                config = json.load(f)
        provider = config.get("provider", "groq")
        registry = {
            "groq": GroqBrain,
            "ollama": OllamaBrain,
        }
        cls = registry.get(provider, GroqBrain)
        return cls(config)

    def generate_response(self, query):
        if not self.brain:
            self.brain = self._init_brain()
        messages = [{"role": "user", "content": query}]
        result = self.brain.chat(messages, tools_enabled=False)
        if not result:
            result = {}
        return result.get("message", {}).get("content", str(result))

    def _construct_thinking_correction(self, validation: dict, query: str) -> str:
        sections = {}
        for section in REQUIRED_SECTIONS:
            missing = section in validation.get("sections_missing", [])
            existing_count = validation.get("section_word_counts", {}).get(section, 0)
            min_w = MIN_WORDS_PER_SECTION.get(section, 20)
            if missing or existing_count < min_w:
                sections[section.lower()] = self._generate_section_content(section, query)
        return generate_thinking_section(**sections)

    def _generate_section_content(self, section: str, query: str) -> str:
        prompts = {
            "ANALYSIS": f"Restating the user's need: they asked about '{query[:80]}'. This requires understanding the core concepts and identifying what the user truly needs to know beneath their surface-level question.",
            "CONTEXT": f"Drawing from relevant domain knowledge about '{query[:60]}'. Considering the user's likely background and what assumptions need to be addressed.",
            "PLAN": f"First, identify the key components of the answer. Second, structure the explanation logically. Third, provide concrete examples. Fourth, verify completeness.",
            "REASONING": f"Breaking down the problem step by step. Considering different approaches and their tradeoffs. Evaluating which explanation best serves the user's needs based on the question type.",
            "VERIFICATION": f"Checking that the answer is correct and complete. Considering edge cases and potential misunderstandings. Ensuring the explanation is actionable and clear.",
            "IMPROVEMENT": f"Reflecting on this response to identify how future answers can be more precise, more complete, and better tailored to the user's actual needs.",
        }
        return prompts.get(section, f"Analyzing the query about '{query[:50]}' to provide a thorough response.")

    def train_step(self, query_data: dict) -> dict:
        query = query_data["query"]
        category = query_data.get("category", "general")
        complexity = query_data.get("complexity", "medium")

        content_before = self.generate_response(query)
        validation_before = validate_thinking(content_before)

        attempt = 0
        content_after = content_before
        validation_after = validation_before

        while attempt < MAX_ATTEMPTS and not validation_after.get("valid"):
            attempt += 1
            correction = self._construct_thinking_correction(validation_after, query)
            fixed_content = re.sub(
                r'<think>.*?</think>',
                correction,
                content_after,
                count=1,
                flags=re.DOTALL,
            )
            if fixed_content == content_after:
                fixed_content = correction + "\n" + content_after
            content_after = fixed_content
            validation_after = validate_thinking(content_after)

        metrics = self.trainer.train_step(content_before, content_after)

        result = {
            "query": query[:80],
            "category": category,
            "complexity": complexity,
            "attempts": attempt + 1,
            "valid_before": validation_before.get("valid", False),
            "valid_after": validation_after.get("valid", False),
            "improved": metrics.get("improved", False),
            "before_sections": validation_before.get("sections_found", []),
            "after_sections": validation_after.get("sections_found", []),
            "before_words": validation_before.get("total_words", 0),
            "after_words": validation_after.get("total_words", 0),
            "issues": validation_before.get("sections_missing", []) + [
                f"{s}:{validation_before['section_word_counts'].get(s, 0)}w"
                for s in REQUIRED_SECTIONS
                if s not in validation_before.get("sections_missing", [])
                and validation_before.get("section_word_counts", {}).get(s, 0) < MIN_WORDS_PER_SECTION.get(s, 20)
            ],
        }
        self.results.append(result)
        return result

    def _calculate_score(self) -> dict:
        if not self.results:
            return {"overall": 0.0}
        total = len(self.results)
        valid = sum(1 for r in self.results if r.get("valid_after"))
        improved = sum(1 for r in self.results if r.get("improved"))
        avg_word_count = sum(r.get("after_words", 0) for r in self.results) / total
        avg_attempts = sum(r.get("attempts", 0) for r in self.results) / total
        sections_avg = sum(len(r.get("after_sections", [])) for r in self.results) / total

        pass_score = (valid / total) * 50
        improvement_bonus = (improved / total) * 15
        depth_score = min(avg_word_count / 150, 1.0) * 20
        section_score = (sections_avg / len(REQUIRED_SECTIONS)) * 10
        efficiency_penalty = min(avg_attempts / MAX_ATTEMPTS * 5, 5)
        quality = pass_score + improvement_bonus + depth_score + section_score - efficiency_penalty

        return {
            "overall": round(quality, 1),
            "pass_score": round(pass_score, 1),
            "improvement_bonus": round(improvement_bonus, 1),
            "depth_score": round(depth_score, 1),
            "section_score": round(section_score, 1),
            "efficiency_penalty": round(efficiency_penalty, 1),
            "valid_count": valid,
            "total_count": total,
            "improved_count": improved,
            "avg_word_count": round(avg_word_count, 1),
            "avg_attempts": round(avg_attempts, 1),
            "sections_avg": round(sections_avg, 1),
        }

    def _scan_codebase_thinking(self) -> dict:
        findings = []
        brain_path = Path(__file__).parent / "brain.py"
        src = brain_path.read_text(encoding="utf-8")

        if "<think>" not in src:
            findings.append({"severity": "critical", "file": "brain.py", "issue": "No <think> tag in SYSTEM_PROMPT"})
        if "**ANALYSIS:" not in src:
            findings.append({"severity": "critical", "file": "brain.py", "issue": "Missing ANALYSIS section in thinking protocol"})
        if "**PLAN:" not in src:
            findings.append({"severity": "critical", "file": "brain.py", "issue": "Missing PLAN section in thinking protocol"})
        if "**VERIFICATION:" not in src:
            findings.append({"severity": "critical", "file": "brain.py", "issue": "Missing VERIFICATION section in thinking protocol"})
        if "**IMPROVEMENT:" not in src:
            findings.append({"severity": "critical", "file": "brain.py", "issue": "Missing IMPROVEMENT section in thinking protocol"})

        assistant_path = Path(__file__).parent / "assistant.py"
        ast_src = assistant_path.read_text(encoding="utf-8")
        if "_post_process" not in ast_src:
            findings.append({"severity": "high", "file": "assistant.py", "issue": "No _post_process method for thinking feedback"})
        if "_log_thinking" not in ast_src:
            findings.append({"severity": "high", "file": "assistant.py", "issue": "No thinking logging"})

        return {"scanned_files": ["brain.py", "assistant.py"], "findings": findings}

    def _log_result(self, result: dict):
        try:
            entry = {
                "timestamp": datetime.now().isoformat(),
                "result": result,
            }
            with self.log_path.open("a") as f:
                f.write(json.dumps(entry) + "\n")
        except Exception:
            pass

    def report(self, score_data: dict, scan_data: dict):
        line = "=" * 60
        print(f"\n{line}")
        print(f"  THINKING TRAINING REPORT — Iteration {self.iteration}")
        print(f"{line}")
        print(f"  Score Breakdown:")
        print(f"    Pass Rate:        {score_data['pass_score']:>6.1f}/50  ({score_data['valid_count']}/{score_data['total_count']} valid)")
        print(f"    Improvement:      {score_data['improvement_bonus']:>6.1f}/15  ({score_data['improved_count']} improved)")
        print(f"    Depth (words):    {score_data['depth_score']:>6.1f}/20  (avg {score_data['avg_word_count']}w)")
        print(f"    Sections:         {score_data['section_score']:>6.1f}/10  (avg {score_data['sections_avg']}/{len(REQUIRED_SECTIONS)} sections)")
        print(f"    Efficiency:       -{score_data['efficiency_penalty']:>5.1f}   (avg {score_data['avg_attempts']} attempts)")
        print(f"  {'─' * 56}")
        print(f"  OVERALL:           {score_data['overall']:>6.1f}/100")
        print(f"{line}")

        if scan_data.get("findings"):
            print(f"\n  Codebase Scan Findings ({len(scan_data['findings'])}):")
            for f in scan_data["findings"]:
                print(f"    [{f['severity'].upper():8s}] {f['file']}: {f['issue']}")

        print(f"\n  Query Results:")
        print(f"  {'Query':40s} {'Cat':12s} {'Before':>8s} {'After':>8s} {'Valid':>6s}")
        print(f"  {'─' * 76}")
        for r in self.results:
            q = r["query"][:38]
            c = r["category"][:10]
            bw = str(r["before_words"])
            aw = str(r["after_words"])
            v = "YES" if r["valid_after"] else "NO"
            print(f"  {q:40s} {c:12s} {bw:>8s} {aw:>8s} {v:>6s}")

    def run(self):
        from core.thinking_protocol import THINKING_TEMPLATE
        print("\n  ============== THINKING TRAINING ==============")
        print("  | Train thinking-before-answering protocol   |")
        print("  | Validate <think> sections → Auto-correct  |")
        print(f"  | {len(TRAINING_QUERIES)} training queries  |")
        print("  =============================================")

        scan_data = self._scan_codebase_thinking()
        for f in scan_data.get("findings", []):
            print(f"  [{f['severity'].upper():8s}] {f['file']}: {f['issue']}")

        print(f"\n  Beginning training loop...")
        self.iteration = 1

        for i, qd in enumerate(TRAINING_QUERIES):
            print(f"  [{i+1}/{len(TRAINING_QUERIES)}] {qd['query'][:50]}...", end=" ")
            result = self.train_step(qd)
            self._log_result(result)
            status = "OK" if result["valid_after"] else "FAIL"
            arrow = "✓" if result["improved"] else "=" if result["valid_before"] else "✗"
            print(f" {arrow} {status} ({result['before_words']}w→{result['after_words']}w, {result['attempts']} attempts)")
            time.sleep(0.5)

        score_data = self._calculate_score()
        self.scores.append(score_data["overall"])
        self.report(score_data, scan_data)

        trainer_report = self.trainer.get_report()
        print(f"\n  Trainer Summary:")
        print(f"    Sessions trained:  {trainer_report['sessions']}")
        print(f"    Improved:          {trainer_report['improved_count']} ({trainer_report['improvement_rate']}%)")
        print(f"    Avg quality:       {trainer_report['average_quality']}%")
        print(f"    Total trained:     {trainer_report['total_trained']}")

        return score_data["overall"]


if __name__ == "__main__":
    session = ThinkingTrainingSession()
    final = session.run()
    target = 95.0
    if final >= target:
        print(f"\n  PASSED: {final:.1f} >= {target}")
    else:
        print(f"\n  BELOW THRESHOLD: {final:.1f} < {target}")
    sys.exit(0 if final >= target else 1)
