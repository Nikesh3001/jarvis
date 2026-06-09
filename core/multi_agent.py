import json
from datetime import datetime


class MultiAgentSystem:
    """
    Multi-role agent system that simulates a development team:
    - Architect: Designs system architecture and plans
    - Developer: Writes and implements code
    - Analyst: Analyzes requirements and problems
    - Reviewer: Reviews code and provides feedback
    - Tester: Tests and validates implementations
    - Security: Reviews for security vulnerabilities
    """

    ROLES = {
        "architect": {
            "title": "System Architect",
            "focus": "design patterns, architecture, system design, scalability",
            "persona": "You are a seasoned system architect. You think about the big picture: component interaction, data flow, scalability, maintainability, and design patterns. You provide architectural plans and design documents."
        },
        "developer": {
            "title": "Developer",
            "focus": "implementation, coding, building features, fixing bugs",
            "persona": "You are a senior software engineer. You write clean, efficient, well-structured code. You follow best practices and design patterns. You implement features based on architectural plans."
        },
        "analyst": {
            "title": "Business/System Analyst",
            "focus": "requirements, problem analysis, research, data gathering",
            "persona": "You are a thorough analyst. You break down problems, research solutions, gather data, and provide clear analysis. You identify edge cases and potential issues before development begins."
        },
        "reviewer": {
            "title": "Code Reviewer",
            "focus": "code quality, best practices, bugs, improvements",
            "persona": "You are a meticulous code reviewer. You examine code for bugs, performance issues, security vulnerabilities, and adherence to best practices. You provide constructive, actionable feedback."
        },
        "tester": {
            "title": "QA Tester",
            "focus": "testing, edge cases, validation, quality assurance",
            "persona": "You are a thorough QA engineer. You design test cases, test edge cases, validate functionality, and ensure quality. You think about what could break and how to prevent it."
        },
        "security": {
            "title": "Security Engineer",
            "focus": "vulnerabilities, hardening, secure coding, threat modeling",
            "persona": "You are a security engineer. You identify vulnerabilities, recommend hardening measures, and ensure secure coding practices. You think like an attacker to find weaknesses."
        },
    }

    def __init__(self, brain=None):
        self.brain = brain
        self._roles = ["analyst", "architect", "developer", "reviewer", "tester", "security"]
        self._output = {}

    def run_team(self, task, context=""):
        results = {}
        results["analysis"] = self._run_role("analyst", task, context)
        results["architecture"] = self._run_role("architect", task, results["analysis"])
        results["implementation"] = self._run_role("developer", task, results["architecture"])
        results["review"] = self._run_role("reviewer", task, results["implementation"])
        results["testing"] = self._run_role("tester", task, results["implementation"])
        results["security_review"] = self._run_role("security", task, results["implementation"])
        summary = self._generate_summary(task, results)
        return {
            "task": task,
            "team": results,
            "summary": summary,
        }

    def run_phase(self, phase, task, context=""):
        valid_phases = ["analyst", "architect", "developer", "reviewer", "tester", "security"]
        if phase not in valid_phases:
            return f"Invalid phase. Choose from: {', '.join(valid_phases)}"
        result = self._run_role(phase, task, context)
        self._output[phase] = result
        return result

    def get_full_report(self):
        return self._output

    def _run_role(self, role, task, context=""):
        role_info = self.ROLES.get(role, {})
        prompt = (
            f"{role_info.get('persona', '')}\n\n"
            f"Your role: {role_info.get('title', role)}\n"
            f"Focus: {role_info.get('focus', 'general')}\n\n"
        )
        if context:
            prompt += f"Context/Input:\n{context}\n\n"
        prompt += f"Task:\n{task}\n\n"
        prompt += (
            "Provide thorough, actionable output. Be specific and detailed. "
            "If code is involved, include actual code snippets. "
            "Format your response clearly with sections."
        )
        return self._query_llm(prompt)

    def _query_llm(self, prompt):
        if self.brain and hasattr(self.brain, 'chat'):
            try:
                messages = [
                    {"role": "system", "content": "You are a technical AI assistant."},
                    {"role": "user", "content": prompt}
                ]
                result = self.brain.chat(messages, tools_enabled=False)
                content = result.get("message", {}).get("content", "")
                return content or "No response from LLM."
            except Exception as e:
                return f"LLM query error: {e}"
        return "Brain not initialized. Ensure Groq API key is configured."

    def _generate_summary(self, task, results):
        summary_parts = ["## Multi-Agent Summary\n", f"Task: {task}\n", f"Completed: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n"]
        for role, result in results.items():
            first_line = result.strip().split("\n")[0][:100] if result.strip() else "(empty)"
            summary_parts.append(f"\n**{role.upper()}**: {first_line}...")
        return "\n".join(summary_parts)

    def design_architecture(self, project_name, requirements):
        prompt = (
            f"Design a complete system architecture for: {project_name}\n\n"
            f"Requirements:\n{requirements}\n\n"
            f"Include:\n"
            f"1. High-level architecture diagram (text-based)\n"
            f"2. Component breakdown\n"
            f"3. Data flow\n"
            f"4. Technology stack recommendations\n"
            f"5. File/directory structure\n"
            f"6. API design (if applicable)\n"
            f"7. Key design decisions and tradeoffs\n"
            f"8. Security considerations"
        )
        return self._query_llm(prompt)

    def review_code(self, code, language="python"):
        prompt = (
            f"Review the following {language} code thoroughly:\n\n{code}\n\n"
            f"Check for:\n"
            f"1. Bugs and logic errors\n"
            f"2. Security vulnerabilities\n"
            f"3. Performance issues\n"
            f"4. Code style and readability\n"
            f"5. Best practices\n"
            f"6. Edge cases not handled\n"
            f"7. Suggestions for improvement\n\n"
            f"Rate the code quality from 1-10 and provide specific, actionable feedback."
        )
        return self._query_llm(prompt)

    def research_topic(self, topic):
        prompt = (
            f"Research the following topic thoroughly:\n\n{topic}\n\n"
            f"Provide:\n"
            f"1. Overview and key concepts\n"
            f"2. Current state and trends\n"
            f"3. Pros and cons / tradeoffs\n"
            f"4. Practical applications\n"
            f"5. Recommendations\n"
            f"6. Sources or further reading suggestions"
        )
        return self._query_llm(prompt)

    def get_tool_definitions(self):
        return [
            {"type": "function", "function": {"name": "run_phase", "description": "Run team role (analyst/architect/developer/reviewer/tester/security)", "parameters": {"type": "object", "properties": {"phase": {"type": "string", "enum": ["analyst", "architect", "developer", "reviewer", "tester", "security"], "description": "Role"}, "task": {"type": "string", "description": "Task"}, "context": {"type": "string", "description": "Context", "default": ""}}, "required": ["phase", "task"]}}},
            {"type": "function", "function": {"name": "run_team", "description": "Full dev pipeline: analyst→architect→developer→reviewer→tester→security", "parameters": {"type": "object", "properties": {"task": {"type": "string", "description": "Task"}, "context": {"type": "string", "description": "Context", "default": ""}}, "required": ["task"]}}},
            {"type": "function", "function": {"name": "design_architecture", "description": "Full system architecture design", "parameters": {"type": "object", "properties": {"project_name": {"type": "string", "description": "Project"}, "requirements": {"type": "string", "description": "Reqs"}}, "required": ["project_name", "requirements"]}}},
            {"type": "function", "function": {"name": "research_topic", "description": "Research with pros/cons", "parameters": {"type": "object", "properties": {"topic": {"type": "string", "description": "Topic"}}, "required": ["topic"]}}},
        ]

    def get_handler(self, name):
        handlers = {
            "run_phase": self.run_phase,
            "run_team": self.run_team,
            "design_architecture": self.design_architecture,
            "research_topic": self.research_topic,
        }
        return handlers.get(name)
