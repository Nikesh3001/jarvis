import json
import time
from pathlib import Path


PLANS_DIR = Path(__file__).parent.parent / "plans"


class Planner:
    def __init__(self):
        self.current_plan = None
        self.current_step = 0
        PLANS_DIR.mkdir(exist_ok=True)

    def create_plan(self, objective, steps, context=None):
        plan = {
            "objective": objective,
            "steps": [{"id": i + 1, "description": s, "status": "pending", "result": None} for i, s in enumerate(steps)],
            "context": context or "",
            "created": time.time(),
            "current_step": 0,
            "completed": False,
        }
        self.current_plan = plan
        self.current_step = 0
        safe_name = "".join(c if c.isalnum() or c in " -_" else "_" for c in objective)[:50]
        path = PLANS_DIR / f"plan_{safe_name}.json"
        path.write_text(json.dumps(plan, indent=2), encoding="utf-8")
        return f"Plan created: {objective}\n{len(steps)} steps defined.\n" + "\n".join(f"  Step {i+1}: {s}" for i, s in enumerate(steps))

    def execute_step(self, step_id):
        if not self.current_plan:
            return "No active plan. Create one first with create_plan."
        step = next((s for s in self.current_plan["steps"] if s["id"] == step_id), None)
        if not step:
            return f"Step {step_id} not found in plan."
        step["status"] = "in_progress"
        self.current_plan["current_step"] = step_id
        self.current_step = step_id
        self._save()
        return f"Executing step {step_id}: {step['description']}"

    def complete_step(self, step_id, result=None):
        if not self.current_plan:
            return "No active plan."
        step = next((s for s in self.current_plan["steps"] if s["id"] == step_id), None)
        if not step:
            return f"Step {step_id} not found."
        step["status"] = "completed"
        if result:
            step["result"] = str(result)[:500]
        self._save()
        return f"Step {step_id} completed."

    def fail_step(self, step_id, reason=None):
        if not self.current_plan:
            return "No active plan."
        step = next((s for s in self.current_plan["steps"] if s["id"] == step_id), None)
        if not step:
            return f"Step {step_id} not found."
        step["status"] = "failed"
        if reason:
            step["result"] = f"FAILED: {reason}"
        self._save()
        return f"Step {step_id} marked as failed."

    def get_progress(self):
        if not self.current_plan:
            return "No active plan."
        steps = self.current_plan["steps"]
        total = len(steps)
        done = sum(1 for s in steps if s["status"] == "completed")
        failed = sum(1 for s in steps if s["status"] == "failed")
        lines = [
            f"Objective: {self.current_plan['objective']}",
            f"Progress: {done}/{total} complete ({failed} failed)",
            f"Current step: {self.current_plan['current_step']}",
        ]
        for s in steps:
            icon = {"pending": "⏳", "in_progress": "▶️", "completed": "✅", "failed": "❌"}.get(s["status"], "⏳")
            lines.append(f"  {icon} Step {s['id']}: {s['description']} [{s['status']}]")
        return "\n".join(lines)

    def update_plan(self, objective=None, add_steps=None, modify_steps=None):
        if not self.current_plan:
            return "No active plan."
        if objective:
            self.current_plan["objective"] = objective
        if add_steps:
            base = len(self.current_plan["steps"])
            for i, s in enumerate(add_steps):
                self.current_plan["steps"].append({"id": base + i + 1, "description": s, "status": "pending", "result": None})
        if modify_steps:
            for mod in modify_steps:
                step = next((s for s in self.current_plan["steps"] if s["id"] == mod.get("id")), None)
                if step:
                    step.update(mod)
        self._save()
        return "Plan updated."

    def list_plans(self):
        files = sorted(PLANS_DIR.glob("plan_*.json"), reverse=True)[:20]
        if not files:
            return "No saved plans."
        lines = []
        for f in files:
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
                done = sum(1 for s in data["steps"] if s["status"] == "completed")
                total = len(data["steps"])
                lines.append(f"  {f.name}: {data['objective'][:60]} ({done}/{total})")
            except Exception:
                lines.append(f"  {f.name}: (corrupted)")
        return "Saved plans:\n" + "\n".join(lines)

    def load_plan(self, filename):
        path = PLANS_DIR / filename
        if not path.exists():
            return f"Plan not found: {filename}"
        try:
            self.current_plan = json.loads(path.read_text(encoding="utf-8"))
            self.current_step = self.current_plan.get("current_step", 0)
            return f"Loaded plan: {self.current_plan['objective']}"
        except Exception as e:
            return f"Load error: {e}"

    def _save(self):
        if self.current_plan:
            safe_name = "".join(c if c.isalnum() or c in " -_" else "_" for c in self.current_plan["objective"])[:50]
            path = PLANS_DIR / f"plan_{safe_name}.json"
            path.write_text(json.dumps(self.current_plan, indent=2), encoding="utf-8")

    def get_tool_definitions(self):
        return [
            {"type": "function", "function": {"name": "create_plan", "description": "Create multi-step plan", "parameters": {"type": "object", "properties": {"objective": {"type": "string", "description": "Goal"}, "steps": {"type": "array", "items": {"type": "string"}, "description": "Steps"}, "context": {"type": "string", "description": "Context"}}, "required": ["objective", "steps"]}}},
            {"type": "function", "function": {"name": "execute_step", "description": "Exec a plan step", "parameters": {"type": "object", "properties": {"step_id": {"type": "integer", "description": "ID"}}, "required": ["step_id"]}}},
            {"type": "function", "function": {"name": "complete_step", "description": "Complete step w/result", "parameters": {"type": "object", "properties": {"step_id": {"type": "integer", "description": "ID"}, "result": {"type": "string", "description": "Result"}}, "required": ["step_id"]}}},
            {"type": "function", "function": {"name": "fail_step", "description": "Mark step failed", "parameters": {"type": "object", "properties": {"step_id": {"type": "integer", "description": "ID"}, "reason": {"type": "string", "description": "Reason"}}, "required": ["step_id"]}}},
            {"type": "function", "function": {"name": "get_progress", "description": "Plan progress", "parameters": {"type": "object", "properties": {}}}},
            {"type": "function", "function": {"name": "update_plan", "description": "Modify current plan", "parameters": {"type": "object", "properties": {"objective": {"type": "string", "description": "Goal"}, "add_steps": {"type": "array", "items": {"type": "string"}, "description": "New steps"}, "modify_steps": {"type": "array", "items": {"type": "object"}, "description": "Changes"}}}}},
            {"type": "function", "function": {"name": "list_plans", "description": "All saved plans", "parameters": {"type": "object", "properties": {}}}},
            {"type": "function", "function": {"name": "load_plan", "description": "Load plan file", "parameters": {"type": "object", "properties": {"filename": {"type": "string", "description": "Name"}}, "required": ["filename"]}}},
        ]

    def get_handler(self, name):
        handlers = {
            "create_plan": self.create_plan, "execute_step": self.execute_step,
            "complete_step": self.complete_step, "fail_step": self.fail_step,
            "get_progress": self.get_progress, "update_plan": self.update_plan,
            "list_plans": self.list_plans, "load_plan": self.load_plan,
        }
        return handlers.get(name)
