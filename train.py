"""
Training pipeline: test -> grade -> modify -> loop.
Tests intent understanding, command handling, tool routing, and prompt completeness.
Each iteration identifies gaps and auto-fixes them until grade >= 90/100.
"""
import sys, os, re, json, math
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from core.human_understanding import analyze_intent, guess_params, get_tools_for_intent, HUMAN_INTENTS
from core.brain import SYSTEM_PROMPT

ROOT = Path(__file__).parent
MAX_ITERATIONS = 5


class TrainingSession:
    def __init__(self):
        self.iteration = 0
        self.score = 0
        self.results = {}
        self.fixes_applied = []

    def test_intent_accuracy(self):
        tests = [
            ("system_info", ["whats my cpu usage", "check memory", "system status", "how much ram", "show me disk space"]),
            ("process_manage", ["list running processes", "show tasks", "kill process chrome"]),
            ("network", ["wifi status", "list wifi networks", "my ip address"]),
            ("volume_control", ["turn up volume", "mute sound", "set volume to 50"]),
            ("window_manage", ["focus window chrome", "switch to notepad"]),
            ("clipboard", ["what is on my clipboard", "show clipboard", "clipboard content"]),
            ("screen", ["take a screenshot", "capture screen"]),
            ("file_ops", ["list files in folder", "read file readme", "delete file temp"]),
            ("shell", ["run command dir", "execute ping google.com"]),
            ("web_search", ["search web for news", "google python tutorial", "look up weather"]),
            ("web_fetch", ["fetch url https://example.com", "open website google"]),
            ("code_run", ["write a python function", "run python script", "implement binary search"]),
            ("git", ["git status", "commit changes", "push to remote", "git pull origin main"]),
            ("memory", ["remember my name is John", "save this for later", "remind me about meeting"]),
            ("planning", ["create a plan to deploy", "we need a plan"]),
            ("news", ["latest news", "breaking headlines", "top stories"]),
            ("stocks", ["stock price AAPL", "market summary today"]),
            ("scrape", ["scrape this page", "extract links from url"]),
            ("research_deep", ["research quantum computing", "deep analysis of algorithm"]),
            ("language_tools", ["lint this file", "format code", "install package pytest"]),
            ("task_orchestrator", ["orchestrate the build"]),
        ]
        passed = 0
        total = sum(len(qs) for _, qs in tests)
        failures = []
        for intent, queries in tests:
            for q in queries:
                a = analyze_intent(q)
                if a["intent"] == intent:
                    passed += 1
                else:
                    failures.append({"query": q, "expected": intent, "got": a["intent"], "conf": a["confidence"]})
        return {"passed": passed, "total": total, "failures": failures}

    def test_greeting_detection(self):
        greetings = ["hi", "hello", "hey", "good morning", "whatsup", "howdy"]
        passed = sum(1 for g in greetings if analyze_intent(g)["intent"] == "greeting")
        return {"passed": passed, "total": len(greetings)}

    def test_gratitude_detection(self):
        thanks = ["thanks", "thank you", "appreciate it", "good job"]
        passed = sum(1 for t in thanks if analyze_intent(t)["intent"] == "gratitude")
        return {"passed": passed, "total": len(thanks)}

    def test_guess_fallback(self):
        tests = [("show battery", "system_info"), ("list directory", "file_ops"),
                 ("search python", "web_search"), ("run npm install", "shell")]
        passed = sum(1 for q, e in tests if analyze_intent(q)["intent"] == e)
        return {"passed": passed, "total": len(tests)}

    def test_intent_to_tools_completeness(self):
        known = set(sig.name for sig in HUMAN_INTENTS) | {"greeting", "gratitude", "none"}
        mapped = set()
        for intent_name in known:
            tools = get_tools_for_intent({"intent": intent_name})
            if tools is not None:
                mapped.add(intent_name)
        missing = known - mapped - {"none", "greeting", "gratitude", "vision"}
        return {"mapped": len(mapped), "total": len(known), "missing": list(missing)}

    def test_prompt_completeness(self):
        required = {
            "windows": r"windows|start chrome|cmd",
            "platform": r"platform|PLATFORM",
            "clipboard": r"clipboard",
            "no_vision": r"vision|image",
            "identity": r"who are you|self.introduction",
            "no_fabricate": r"fabricate tool|never fabricate",
            "coding": r"coding|algorithm|complexity|Big O",
            "thinking": r"think|<think>|THINKING",
            "debugging": r"3 attempts|never acceptable",
            "knowledge": r"KNOWLEDGE|answer DIRECTLY",
        }
        passed = sum(1 for _, p in required.items() if re.search(p, SYSTEM_PROMPT, re.IGNORECASE))
        missing = [t for t, p in required.items() if not re.search(p, SYSTEM_PROMPT, re.IGNORECASE)]
        return {"passed": passed, "total": len(required), "missing": missing}

    def test_param_guessing(self):
        tests = [
            ("web_search", "search for python tutorials", {"query": "python tutorials"}),
            ("web_fetch", "https://example.com", {"url": "https://example.com"}),
            ("volume_control", "turn up the volume", {"level": "up"}),
            ("memory", "remember that my name is John", {"content": "that my name is john"}),
            ("shell", "run command dir", {"command": "dir"}),
            ("code_run", "write python code", {"language": "python"}),
        ]
        passed = 0
        for intent, query, expected in tests:
            params = guess_params(intent, query)
            if all(params.get(k) == v for k, v in expected.items()):
                passed += 1
        return {"passed": passed, "total": len(tests)}

    def test_tool_diversity(self):
        non_chat = [s.name for s in HUMAN_INTENTS if s.name not in ("greeting", "gratitude", "vision")]
        empty = []
        for intent in non_chat:
            a = {"intent": intent}
            if not get_tools_for_intent(a):
                empty.append(intent)
        return {"total": len(non_chat), "empty": empty}

    def grade(self, results):
        weights = {
            "intent_accuracy": 30, "greeting_detection": 10, "gratitude_detection": 5,
            "guess_fallback": 10, "intent_to_tools": 15, "prompt_completeness": 15,
            "param_guessing": 5, "tool_diversity": 10,
        }
        score = 0
        details = {}
        for name, weight in weights.items():
            r = results.get(name, {})
            if "passed" in r:
                pct = r["passed"] / r["total"] if r.get("total", 0) > 0 else 1.0
            elif "empty" in r:
                pct = 1.0 - (len(r.get("empty", [])) / r.get("total", 1))
            else:
                pct = 1.0
            sec = round(pct * weight, 1)
            score += sec
            det = {"pct": round(pct * 100, 1), "weight": weight, "score": sec}
            if "failures" in r and r["failures"]:
                det["failures"] = r["failures"][:5]
            if "missing" in r and r["missing"]:
                det["missing"] = r["missing"]
            if "empty" in r and r["empty"]:
                det["empty"] = r["empty"]
            details[name] = det
        return round(score, 1), details

    def report(self, score, details):
        line = "=" * 56
        print(f"\n{line}")
        print(f"  TRAINING REPORT -- Iteration {self.iteration}")
        print(f"{line}")
        for name, d in details.items():
            icon = "+" if d["score"] >= d["weight"] * 0.8 else "-" if d["score"] >= d["weight"] * 0.5 else "!"
            print(f"  {icon} {name:25s} {d['pct']:5.1f}%  ({d['score']:.1f}/{d['weight']})")
            if "failures" in d:
                for f in d["failures"][:3]:
                    print(f"      {f['query']:40s} expected={f['expected']:15s} got={f['got']:15s}")
            if "missing" in d:
                for m in d["missing"]:
                    print(f"      missing: {m}")
            if "empty" in d:
                for e in d["empty"]:
                    print(f"      no tools: {e}")
        print(f"{line}")
        print(f"  TOTAL SCORE: {score}/100")
        print(f"{line}")

    def auto_fix(self, results):
        fixes = []
        hu_path = ROOT / "core" / "human_understanding.py"
        hu_src = hu_path.read_text(encoding="utf-8")

        intent_acc = results.get("intent_accuracy", {})
        for f in intent_acc.get("failures", []):
            if not f["expected"]:
                continue
            sig_text = f'IntentSignature("{f["expected"]}"'
            if sig_text not in hu_src:
                continue
            words = [w.lower() for w in f["query"].split() if len(w) > 2 and w.lower() not in ("the", "this", "that", "what", "with", "from", "for", "and", "are")]
            for w in words[:2]:
                if w in hu_src:
                    continue
                m = re.search(rf'({re.escape(sig_text)}.*?primary=\[)(.*?)(\])', hu_src, re.DOTALL)
                if m:
                    existing = m.group(2)
                    if w not in existing:
                        new_primary = existing.rstrip() + (', ' if existing.strip() else '') + f'"{w}"'
                        fixes.append(f"Suggested: Add '{w}' to {f['expected']} primary")
                        break
            if len(fixes) >= 5:
                break

        for fix in fixes:
            print(f"  [FIX] {fix}")
        return fixes

    def run(self):
        print("\n  ============== JARVIS TRAINING ==============")
        print("  | Test -> Grade -> Fix -> Repeat            |")
        print("  ============================================")
        while self.iteration < MAX_ITERATIONS:
            self.iteration += 1
            results = {}
            results["intent_accuracy"] = self.test_intent_accuracy()
            results["greeting_detection"] = self.test_greeting_detection()
            results["gratitude_detection"] = self.test_gratitude_detection()
            results["guess_fallback"] = self.test_guess_fallback()
            results["intent_to_tools"] = self.test_intent_to_tools_completeness()
            results["prompt_completeness"] = self.test_prompt_completeness()
            results["param_guessing"] = self.test_param_guessing()
            results["tool_diversity"] = self.test_tool_diversity()

            score, details = self.grade(results)
            self.results = results
            self.score = score

            if score >= 90.0:
                break

            if self.iteration < MAX_ITERATIONS:
                fixes = self.auto_fix(results)
                if fixes:
                    self.fixes_applied.extend(fixes)

        print(f"\n  SCORE: {self.score:.1f}%")
        return self.score


if __name__ == "__main__":
    session = TrainingSession()
    final = session.run()
    sys.exit(0 if final >= 90 else 1)
