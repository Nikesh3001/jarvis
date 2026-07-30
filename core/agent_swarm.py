import time
import threading
from datetime import datetime


class SwarmMessage:
    def __init__(self, sender, recipient, msg_type, subject, content, context=None):
        self.sender = sender
        self.recipient = recipient
        self.type = msg_type
        self.subject = subject
        self.content = content
        self.context = context or {}
        self.timestamp = time.time()

    def to_dict(self):
        return {
            "from": self.sender,
            "to": self.recipient,
            "type": self.type,
            "subject": self.subject,
            "content": self.content[:500] if self.content else "",
            "timestamp": datetime.fromtimestamp(self.timestamp).strftime("%H:%M:%S"),
        }


class SwarmAgent:
    def __init__(self, name, title, focus, persona, brain, swarm):
        self.name = name
        self.title = title
        self.focus = focus
        self.persona = persona
        self.brain = brain
        self.swarm = swarm
        self.inbox = []
        self.lock = threading.Lock()
        self.result = None
        self.status = "idle"
        self.conversation_log = []

    def receive(self, message):
        with self.lock:
            self.inbox.append(message)
            self.conversation_log.append(message.to_dict())

    def process(self, task, context=""):
        self.status = "thinking"
        prompt = (
            f"{self.persona}\n\n"
            f"Your role: {self.title}\n"
            f"Focus: {self.focus}\n\n"
        )
        if context:
            prompt += f"Context/Input:\n{context}\n\n"
        prompt += f"Task:\n{task}\n\n"
        prompt += (
            "Before answering, reason inside <think> tags:\n"
            "<think>\n"
            "ANALYSIS: What does this task require?\n"
            "CONTEXT: What information is available?\n"
            "PLAN: How will I approach this?\n"
            "REASONING: Step-by-step logic\n"
            "VERIFICATION: Check my work\n"
            "IMPROVEMENT: What did other agents contribute?\n"
            "</think>\n\n"
            "Then provide your answer. Be thorough. "
            "You may reference or build upon other agents' work."
        )

        try:
            messages = [
                {"role": "system", "content": "You are a specialist AI agent collaborating with a team."},
                {"role": "user", "content": prompt}
            ]
            result = self.brain.chat(messages, tools_enabled=False)
            if not result:
                result = {}
            content = result.get("message", {}).get("content", "")
            self.result = content or "No response."
        except Exception as e:
            self.result = f"Agent error: {e}"
        self.status = "done"
        return self.result

    def ask(self, recipient, question, context=None):
        msg = SwarmMessage(
            sender=self.name,
            recipient=recipient,
            msg_type="request",
            subject="clarification",
            content=question,
            context=context,
        )
        self.swarm.route(msg)
        self.conversation_log.append(msg.to_dict())

    def respond(self, recipient, answer, context=None):
        msg = SwarmMessage(
            sender=self.name,
            recipient=recipient,
            msg_type="response",
            subject="answer",
            content=answer,
            context=context,
        )
        self.swarm.route(msg)
        self.conversation_log.append(msg.to_dict())

    def broadcast(self, content, subject="update"):
        msg = SwarmMessage(
            sender=self.name,
            recipient="all",
            msg_type="broadcast",
            subject=subject,
            content=content,
        )
        self.swarm.route(msg)
        self.conversation_log.append(msg.to_dict())

    def get_conversation(self):
        return self.conversation_log[-20:]


class AgentSwarm:
    MAX_PARALLEL = 4
    AGENT_TIMEOUT = 60

    ROLES = {
        "analyst": {
            "title": "System Analyst",
            "focus": "requirements, problem analysis, research, data gathering",
            "persona": (
                "You are a brilliant analyst. Your job is to deeply understand the problem. "
                "Break it down, find requirements, identify constraints, and define what success looks like. "
                "You ask clarifying questions to other agents when needed. "
                "You provide structured analysis with clear findings."
            ),
        },
        "architect": {
            "title": "System Architect",
            "focus": "design patterns, architecture, system design, scalability",
            "persona": (
                "You are a world-class system architect. You design the high-level structure. "
                "You evaluate tradeoffs, choose patterns, and plan component interactions. "
                "You consult the analyst for requirements and the developer for feasibility. "
                "You produce clear architecture plans."
            ),
        },
        "developer": {
            "title": "Developer",
            "focus": "implementation, coding, building features, fixing bugs",
            "persona": (
                "You are an elite software engineer. You write clean, correct, efficient code. "
                "You ask the architect for design clarification when needed. "
                "You implement based on specifications. "
                "You produce working code with proper error handling."
            ),
        },
        "reviewer": {
            "title": "Code Reviewer",
            "focus": "code quality, best practices, bugs, improvements",
            "persona": (
                "You are a meticulous code reviewer. You examine code for bugs, security issues, "
                "performance problems, and style violations. You discuss findings with the developer. "
                "You provide specific, actionable feedback with line-level precision."
            ),
        },
        "tester": {
            "title": "QA Tester",
            "focus": "testing, edge cases, validation, quality assurance",
            "persona": (
                "You are a world-class QA engineer. You design comprehensive test cases. "
                "You think about edge cases, failure modes, and boundary conditions. "
                "You coordinate with the developer to understand the implementation. "
                "You produce test plans and test code."
            ),
        },
    }

    def __init__(self, brain=None):
        self.brain = brain
        self.agents = {}
        self.whiteboard = {}
        self.message_log = []
        self._lock = threading.Lock()

    def debug_conversation_state(self):
        """Output current conversation state for debugging."""
        print(f"\n=== DEBUG STATE ===")
        print(f"Total conversations: {len(self.message_log)}")
        for i, msg in enumerate(self.message_log[-10:]):  # Last 10 messages
            print(f"  {i}: From {msg.get('from', 'Unknown')} to {msg.get('to', 'Unknown')}")
            print(f"     Type: {msg.get('type', 'Unknown')}")
            print(f"     Subject: {msg.get('subject', 'Unknown')}")
            print(f"     Content: {str(msg.get('content', ''))[:100]}...")
            print()

    def _get_or_create_agent(self, role):
        if role not in self.agents:
            info = self.ROLES.get(role)
            if not info:
                return None
            self.agents[role] = SwarmAgent(
                name=role,
                title=info["title"],
                focus=info["focus"],
                persona=info["persona"],
                brain=self.brain,
                swarm=self,
            )
        return self.agents[role]

    def route(self, message):
        with self._lock:
            self.message_log.append(message.to_dict())
        if message.recipient == "all":
            for agent in self.agents.values():
                agent.receive(message)
        elif message.recipient in self.agents:
            self.agents[message.recipient].receive(message)

    def get_whiteboard(self, key, default=None):
        with self._lock:
            return self.whiteboard.get(key, default)

    def set_whiteboard(self, key, value):
        with self._lock:
            self.whiteboard[key] = value

    def _run_agent_thread(self, role, task, context, results, index):
        agent = self._get_or_create_agent(role)
        result = agent.process(task, context)
        with self._lock:
            results[index] = {"role": role, "result": result, "agent": agent}

    def run_parallel(self, task, phases=None, context=""):
        if not phases:
            phases = ["analyst", "architect", "developer"]

        phases = phases[:self.MAX_PARALLEL]
        threads = []
        results = {}
        self.set_whiteboard("task", task)
        self.set_whiteboard("context", context)

        for i, role in enumerate(phases):
            t = threading.Thread(
                target=self._run_agent_thread,
                args=(role, task, context, results, i),
            )
            t.start()
            threads.append(t)

        for t in threads:
            t.join(timeout=self.AGENT_TIMEOUT)

        ordered = []
        for i in range(len(phases)):
            if i in results:
                ordered.append(results[i])

        return ordered

    def run_pipeline(self, task, context=""):
        all_roles = ["analyst", "architect", "developer", "reviewer", "tester"]
        self.set_whiteboard("task", task)

        analyst_result = self._run_single("analyst", task, context)
        if not analyst_result:
            return {"error": "Analyst phase failed"}

        arch_result = self._run_single("architect", task, analyst_result)
        dev_result = self._run_single("developer", task, arch_result)

        parallel_phases = self.run_parallel(
            "Review and test the implementation",
            phases=["reviewer", "tester"],
            context=f"Task: {task}\n\nArchitecture:\n{arch_result}\n\nImplementation:\n{dev_result}",
        )

        synthesis = self._synthesize(
            task, analyst_result, arch_result, dev_result, parallel_phases
        )
        return {
            "task": task,
            "analyst": analyst_result,
            "architect": arch_result,
            "developer": dev_result,
            "parallel": [p["result"] for p in parallel_phases],
            "synthesis": synthesis,
            "conversation": self.get_conversation_log(),
        }

    def _run_single(self, role, task, context=""):
        agent = self._get_or_create_agent(role)
        return agent.process(task, context)

    def _synthesize(self, task, analyst, architect, developer, parallel):
        parallel_text = "\n\n".join(
            [f"**{p['role'].upper()}**: {p['result'][:500]}" for p in parallel]
        )
        prompt = (
            "You are the lead orchestrator. Synthesize the following multi-agent work into a cohesive final report.\n\n"
            f"Task: {task}\n\n"
            f"**ANALYST FINDINGS**:\n{analyst[:1000]}\n\n"
            f"**ARCHITECTURE**:\n{architect[:1000]}\n\n"
            f"**IMPLEMENTATION**:\n{developer[:1000]}\n\n"
            f"**REVIEW & QUALITY**:\n{parallel_text}\n\n"
            "Produce a unified final report that integrates all contributions. "
            "Highlight key decisions, tradeoffs, and action items."
        )
        try:
            messages = [
                {"role": "system", "content": "You are a lead orchestrator synthesizing multi-agent work."},
                {"role": "user", "content": prompt},
            ]
            result = self.brain.chat(messages, tools_enabled=False)
            if not result:
                result = {}
            return result.get("message", {}).get("content", "Synthesis complete.")
        except Exception as e:
            return f"Synthesis error: {e}"

    def run_conversation(self, task, context=""):
        agents_to_activate = ["analyst", "architect", "developer"]
        results = self.run_parallel(task, agents_to_activate, context)

        for r in results:
            agent = r["agent"]
            agent.broadcast(
                f"Here is my contribution to the task '{task}':\n{r['result'][:500]}",
                subject=f"{r['role']}_complete"
            )

        if len(results) >= 2:
            first = results[0]["agent"]
            second = results[1]["agent"]
            first.ask(second.name, "Does my analysis cover everything you need for your work?")
            time.sleep(0.5)
            for msg in self.message_log[-5:]:
                if msg["type"] == "request":
                    source = self.agents.get(msg["from"])
                    target = self.agents.get(msg["to"])
                    if source and target:
                        reply = f"Regarding your question: Yes, your analysis is thorough. I have what I need. Key points I'm using: {results[1]['result'][:300]}"
                        target.respond(source.name, reply)

        synthesis = self._synthesize_parallel(task, results)
        return {
            "task": task,
            "results": {r["role"]: r["result"] for r in results},
            "synthesis": synthesis,
            "conversation": self.get_conversation_log(),
        }

    def _synthesize_parallel(self, task, results):
        parts = []
        for r in results:
            parts.append(f"**{r['role'].upper()}**: {r['result'][:800]}")
        combined = "\n\n".join(parts)
        prompt = (
            "You are the lead orchestrator. Synthesize the following parallel agent work into a unified report.\n\n"
            f"Task: {task}\n\n{combined}\n\n"
            "Produce a cohesive final report that integrates all perspectives."
        )
        try:
            messages = [
                {"role": "system", "content": "You are a lead orchestrator synthesizing multi-agent work."},
                {"role": "user", "content": prompt},
            ]
            result = self.brain.chat(messages, tools_enabled=False)
            if not result:
                result = {}
            return result.get("message", {}).get("content", "Synthesis complete.")
        except Exception as e:
            return f"Synthesis error: {e}"

    def get_conversation_log(self):
        return self.message_log[-30:]

    def delegate(self, task, role=None):
        if role and role in self.ROLES:
            agent = self._get_or_create_agent(role)
            return agent.process(task)
        return self.run_pipeline(task)

    def get_tool_definitions(self):
        return [
            {
                "type": "function",
                "function": {
                    "name": "agent_swarm",
                    "description": "Run a task through parallel AI agents (analyst, architect, developer, reviewer, tester) that talk to each other and work concurrently. Use for complex multi-faceted tasks.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "task": {"type": "string", "description": "The task or problem to solve"},
                            "roles": {
                                "type": "array",
                                "items": {"type": "string", "enum": list(self.ROLES.keys())},
                                "description": "Which agents to activate (default: analyst, architect, developer)",
                            },
                        },
                        "required": ["task"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "delegate_agent",
                    "description": "Delegate a task to a single specialist agent (analyst, architect, developer, reviewer, tester)",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "task": {"type": "string", "description": "The task to delegate"},
                            "role": {"type": "string", "enum": list(self.ROLES.keys()), "description": "Which agent to use"},
                        },
                        "required": ["task", "role"],
                    },
                },
            },
        ]

    def get_handler(self, name):
        handlers = {
            "agent_swarm": self.run_conversation,
            "delegate_agent": self.delegate,
        }
        return handlers.get(name)
