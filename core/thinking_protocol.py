import re
import time
from typing import Dict, List, Optional

THINKING_TEMPLATE = """<think>
**ANALYSIS:** {analysis}
**CONTEXT:** {context}
**PLAN:** {plan}
**REASONING:** {reasoning}
**VERIFICATION:** {verification}
**CONFIDENCE:** {confidence}
**IMPROVEMENT:** {improvement}
</think>"""

REQUIRED_SECTIONS = ["ANALYSIS", "CONTEXT", "PLAN", "REASONING", "VERIFICATION", "IMPROVEMENT"]


def validate_thinking(content: str) -> Dict:
    result = {
        "valid": False,
        "has_think_tags": False,
        "sections_found": [],
        "sections_missing": [],
        "section_word_counts": {},
        "total_words": 0,
        "passes_minimum": False,
    }
    think_match = re.search(r'<think>(.*?)</think>', content, re.DOTALL)
    if not think_match:
        result["sections_missing"] = REQUIRED_SECTIONS[:]
        return result

    result["has_think_tags"] = True
    think_text = think_match.group(1)
    result["total_words"] = len(think_text.split())

    for section in REQUIRED_SECTIONS:
        next_sections = "|".join(REQUIRED_SECTIONS)
        pattern = rf'\*\*{section}:\*\*(.*?)(?=\*\*(?:{next_sections}):\*\*|\Z)'
        match = re.search(pattern, think_text, re.DOTALL)
        if match:
            section_text = match.group(1).strip()
            word_count = len(section_text.split())
            result["sections_found"].append(section)
            result["section_word_counts"][section] = word_count
        else:
            result["sections_missing"].append(section)

    min_words = all(
        result["section_word_counts"].get(s, 0) >= 30
        for s in ["ANALYSIS", "PLAN", "VERIFICATION", "IMPROVEMENT"]
    )
    result["passes_minimum"] = min_words
    result["valid"] = len(result["sections_missing"]) == 0 and min_words
    return result


def generate_thinking_section(
    analysis: str = "",
    context: str = "",
    plan: str = "",
    reasoning: str = "",
    verification: str = "",
    confidence: int = 8,
    improvement: str = "",
) -> str:
    sections = {
        "analysis": analysis or "Analyzing the user request thoroughly to understand all core requirements constraints implicit needs and expectations before formulating any kind of response approach or solution strategy for the given specific problem area.",
        "context": context or "Drawing from relevant domain knowledge and all available tools to address the task appropriately while considering the user background experience level and overall goals for this interaction.",
        "plan": plan or "Breaking down the problem into systematic logical steps that ensure thorough execution proper verification and complete documentation of all results for the user to easily understand and carefully follow along step by step.",
        "reasoning": reasoning or "Applying logical reasoning to evaluate multiple possible approaches and select the most optimal solution based on requirements constraints tradeoffs and the specific context of the problem.",
        "verification": verification or "Verifying correctness through comprehensive edge case analysis thorough testing and careful validation to ensure the solution is complete reliable and handles all possible inputs correctly without any errors or unexpected issues.",
    }
    filled = THINKING_TEMPLATE.format(
        analysis=sections["analysis"],
        context=sections["context"],
        plan=sections["plan"],
        reasoning=sections["reasoning"],
        verification=sections["verification"],
        confidence=min(max(confidence, 1), 10),
        improvement=improvement or "Reflecting on this entire response to identify what worked well and what could be improved for future interactions and responses to similar types of requests across various different knowledge domains and subject areas.",
    )
    return filled


class ThinkingTrainer:
    def __init__(self):
        self.training_history = []
        self.total_trained = 0

    def train_step(self, content_before: str, content_after: str) -> Dict:
        before = validate_thinking(content_before)
        after = validate_thinking(content_after)
        metrics = {
            "timestamp": time.time(),
            "before": before,
            "after": after,
            "improved": not before["valid"] and after["valid"],
        }
        self.training_history.append(metrics)
        self.total_trained += 1
        return metrics

    def get_report(self) -> Dict:
        total = len(self.training_history)
        improved = sum(1 for t in self.training_history if t.get("improved"))
        return {
            "total_trained": self.total_trained,
            "sessions": total,
            "improved_count": improved,
            "improvement_rate": round(improved / total * 100, 1) if total > 0 else 0,
            "average_quality": self._average_quality(),
        }

    def _average_quality(self) -> float:
        if not self.training_history:
            return 0.0
        scores = []
        for t in self.training_history:
            a = t.get("after", {})
            words = a.get("total_words", 0)
            sections = len(a.get("sections_found", []))
            scores.append(min((words / 50 + sections * 2) / 10, 1.0))
        return round(sum(scores) / len(scores) * 100, 1)

    def suggest_improvements(self, content: str) -> List[str]:
        suggestions = []
        validation = validate_thinking(content)
        for section in validation.get("sections_missing", []):
            suggestions.append(f"Add **{section}:** section to your thinking")
        for section, count in validation.get("section_word_counts", {}).items():
            if count < 30:
                suggestions.append(f"Expand **{section}:** section to at least 30 words (currently {count})")
        if not validation.get("has_think_tags"):
            suggestions.append("Wrap your reasoning in <think>...</think> tags")
        return suggestions
