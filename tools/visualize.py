import os, json, hashlib
from pathlib import Path
from core.ratelimit import check_rate


OUTPUT_DIR = Path(__file__).resolve().parent.parent / "visuals"

COLORS = ["#1a56db", "#0e9f6e", "#d03801", "#7239ea", "#d4449a", "#16bdca", "#e38400", "#8b5cf6"]
SHADE = "#1a56db"


class VisualizeTools:
    def __init__(self):
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    def _check_rate(self, op):
        return check_rate(f"viz:{op}", rate=5, burst=10)

    def _save_and_return(self, fig, name):
        safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in name)
        path = OUTPUT_DIR / f"{safe}_{hashlib.md5(safe.encode()).hexdigest()[:8]}.png"
        fig.savefig(path, dpi=150, bbox_inches="tight", facecolor="white")
        import matplotlib.pyplot as _plt
        _plt.close(fig)
        return f"Chart saved: {path}"

    def create_chart(self, chart_type="bar", title="Chart", data="", labels="", xlabel="", ylabel=""):
        if not self._check_rate("chart"):
            return "Rate limited"
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        try:
            data_list = json.loads(data) if isinstance(data, str) else data
        except Exception:
            return "Invalid data JSON"
        try:
            label_list = json.loads(labels) if isinstance(labels, str) else labels
        except Exception:
            label_list = []

        fig, ax = plt.subplots(figsize=(8, 5))
        fig.patch.set_facecolor("#111827")
        ax.set_facecolor("#1f2937")
        ax.set_title(title, fontsize=14, fontweight="bold", color="#f3f4f6", pad=16)
        ax.set_xlabel(xlabel, color="#9ca3af")
        ax.set_ylabel(ylabel, color="#9ca3af")
        ax.tick_params(colors="#9ca3af")
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        ax.spines["bottom"].set_color("#374151")
        ax.spines["left"].set_color("#374151")

        if chart_type == "bar":
            bars = ax.bar(label_list or range(len(data_list)), data_list, color=COLORS[:len(data_list)] if len(data_list) <= len(COLORS) else [COLORS[i % len(COLORS)] for i in range(len(data_list))], edgecolor="none", width=0.65)
        elif chart_type == "line":
            ax.plot(label_list or range(len(data_list)), data_list, marker="o", color=COLORS[0], linewidth=2.5, markersize=6, markerfacecolor=COLORS[0], markeredgecolor="#111827", markeredgewidth=1.5)
            ax.fill_between(label_list or range(len(data_list)), data_list, alpha=0.1, color=COLORS[0])
        elif chart_type == "pie":
            wedges, texts, autotexts = ax.pie(data_list, labels=label_list or None, autopct="%1.1f%%", colors=COLORS[:len(data_list)], startangle=140, textprops={"color": "#f3f4f6", "fontsize": 11})
            for t in autotexts:
                t.set_color("#111827")
                t.set_fontweight("bold")
        elif chart_type == "scatter":
            ax.scatter(label_list or range(len(data_list)), data_list, color=[COLORS[i % len(COLORS)] for i in range(len(data_list))], s=80, edgecolors="#111827", linewidth=1.5)
        elif chart_type == "histogram":
            ax.hist(data_list, bins=min(len(data_list) // 2 or 5, 20), color=COLORS[0], edgecolor="#111827", linewidth=1.2)
        else:
            return f"Unknown chart type: {chart_type}"

        return self._save_and_return(fig, title)

    def create_diagram(self, diagram_type="flowchart", title="Diagram", definition=""):
        if not self._check_rate("diagram"):
            return "Rate limited"

        if diagram_type == "mermaid":
            return f"Mermaid diagram:\n\n```mermaid\n{definition}\n```\n\nRender at https://mermaid.live or use a Mermaid plugin."

        if diagram_type == "tree":
            lines = definition.strip().split("\n")
            mermaid_lines = ["graph TD"]
            stack = []
            for line in lines:
                stripped = line.lstrip()
                indent = len(line) - len(stripped)
                label = stripped.strip("\"'")
                node_id = f"N{len(mermaid_lines)}"
                mermaid_lines.append(f"    {node_id}[\"{label}\"]")
                while stack and stack[-1][1] >= indent:
                    stack.pop()
                if stack:
                    mermaid_lines.append(f"    {stack[-1][0]} --> {node_id}")
                stack.append((node_id, indent))
            code = "\n".join(mermaid_lines)
            return f"Tree diagram:\n\n```mermaid\n{code}\n```\n\nRender at https://mermaid.live"

        if diagram_type == "flowchart":
            code = f"graph LR\n{definition}"
            return f"Flowchart:\n\n```mermaid\n{code}\n```\n\nRender at https://mermaid.live"

        if diagram_type == "mindmap":
            code = f"mindmap\n{definition}"
            return f"Mind map:\n\n```mermaid\n{code}\n```\n\nRender at https://mermaid.live"

        if diagram_type == "sequence":
            code = f"sequenceDiagram\n{definition}"
            return f"Sequence diagram:\n\n```mermaid\n{code}\n```\n\nRender at https://mermaid.live"

        return f"Unknown diagram type: {diagram_type}"

    def get_tool_definitions(self):
        return [
            {"type": "function", "function": {
                "name": "create_chart",
                "description": "Generate a chart image (bar, line, pie, scatter, histogram) from data. Saves as PNG and returns the file path.",
                "parameters": {"type": "object", "properties": {
                    "chart_type": {"type": "string", "description": "Type of chart: bar, line, pie, scatter, histogram", "enum": ["bar", "line", "pie", "scatter", "histogram"]},
                    "title": {"type": "string", "description": "Chart title"},
                    "data": {"type": "string", "description": "JSON array of numeric values, e.g. [10, 20, 30]"},
                    "labels": {"type": "string", "description": "JSON array of string labels for each data point, e.g. [\"A\", \"B\", \"C\"]"},
                    "xlabel": {"type": "string", "description": "X-axis label"},
                    "ylabel": {"type": "string", "description": "Y-axis label"},
                }, "required": ["chart_type", "title", "data"]}
            }},
            {"type": "function", "function": {
                "name": "create_diagram",
                "description": "Generate a diagram: flowchart, tree, mind map, sequence diagram, or raw Mermaid. Returns Mermaid code that can be rendered at mermaid.live.",
                "parameters": {"type": "object", "properties": {
                    "diagram_type": {"type": "string", "description": "Type: mermaid, tree, flowchart, mindmap, sequence", "enum": ["mermaid", "tree", "flowchart", "mindmap", "sequence"]},
                    "title": {"type": "string", "description": "Diagram title"},
                    "definition": {"type": "string", "description": "For mermaid: raw Mermaid syntax. For tree: one node per line, indentation shows hierarchy (e.g. \nCEO\n CTO\n  Dev\n  QA\n CFO). For flowchart/mindmap/sequence: Mermaid body content (indented)."},
                }, "required": ["diagram_type", "title", "definition"]}
            }},
        ]

    def get_handler(self, name):
        handlers = {
            "create_chart": self.create_chart,
            "create_diagram": self.create_diagram,
        }
        return handlers.get(name)
