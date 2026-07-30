import os
import html as _html
from pathlib import Path
from core.ratelimit import check_rate


class WebArtifactBuilder:
    def _check_rate(self, op):
        return check_rate(f"webart:{op}", rate=5, burst=10)

    def create_component(self, name="", description="", html_content="", css_content="", js_content=""):
        if not self._check_rate("create"):
            return "Rate limited"
        if not name:
            return "Component name required"
        if not html_content:
            return "HTML content required"

        safe_name = "".join(c if c.isalnum() or c in "-_" else "_" for c in name)
        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{_html.escape(name)}</title>
<style>
{css_content or "body { margin: 0; font-family: system-ui, sans-serif; background: #fff; color: #222; }"}
</style>
</head>
<body>
{html_content}
<script>
{js_content or ""}
</script>
</body>
</html>"""
        return html

    def create_interactive_artifact(self, title="", components=None, layout="grid"):
        if not self._check_rate("interactive"):
            return "Rate limited"
        if not title:
            title = "Interactive Artifact"
        comps = components or []

        sections_html = ""
        for i, comp in enumerate(comps):
            comp_name = _html.escape(comp.get("name", f"section-{i}"))
            comp_type = comp.get("type", "html")
            comp_content = comp.get("content", "")
            if comp_type == "chart":
                sections_html += f'<div class="section" id="{comp_name}"><canvas id="chart-{i}"></canvas></div>\n'
            elif comp_type == "form":
                sections_html += f'<div class="section" id="{comp_name}"><form id="form-{i}">{comp_content}</form><div id="output-{i}"></div></div>\n'
            elif comp_type == "data":
                sections_html += f'<div class="section" id="{comp_name}"><pre id="data-{i}">{_html.escape(comp_content)}</pre></div>\n'
            else:
                sections_html += f'<div class="section" id="{comp_name}">{comp_content}</div>\n'

        safe_title = _html.escape(title)
        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{safe_title}</title>
<style>
* {{ box-sizing: border-box; margin: 0; padding: 0; }}
body {{ font-family: system-ui, sans-serif; background: #f5f5f5; color: #222; padding: 20px; }}
h1 {{ font-size: 1.5rem; margin-bottom: 16px; color: #333; }}
.container {{ max-width: 1200px; margin: 0 auto; }}
.section {{ background: #fff; border-radius: 8px; padding: 16px; margin-bottom: 16px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }}
.grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 16px; }}
.grid .section {{ margin-bottom: 0; }}
canvas {{ width: 100% !important; height: auto !important; max-height: 400px; }}
pre {{ background: #f8f8f8; padding: 12px; border-radius: 4px; overflow-x: auto; font-size: 0.875rem; }}
input, textarea, select {{ width: 100%; padding: 8px; margin-bottom: 8px; border: 1px solid #ddd; border-radius: 4px; }}
button {{ padding: 8px 16px; background: #2563eb; color: #fff; border: none; border-radius: 4px; cursor: pointer; }}
button:hover {{ background: #1d4ed8; }}
.result {{ margin-top: 8px; padding: 8px; background: #f0fdf4; border-radius: 4px; }}
</style>
</head>
<body>
<div class="container">
<h1>{safe_title}</h1>
<div class="{layout}">
{sections_html}
</div>
</div>
<script>
document.querySelectorAll('form').forEach(form => {{
    form.addEventListener('submit', function(e) {{
        e.preventDefault();
        const data = new FormData(this);
        const output = this.parentElement.querySelector('[id^="output"]');
        if (output) {{
            output.innerHTML = '<div class=\\"result\\">Submitted: ' + JSON.stringify(Object.fromEntries(data)) + '</div>';
        }}
    }});
}});
</script>
</body>
</html>"""
        return html

    def create_dashboard(self, title="", widgets=None, refresh_interval=0):
        if not self._check_rate("dashboard"):
            return "Rate limited"
        if not title:
            title = "Dashboard"
        widgets = widgets or []

        cards = ""
        for w in widgets:
            w_type = w.get("type", "value")
            w_title = _html.escape(w.get("title", ""))
            w_data = w.get("data", "")
            w_color = _html.escape(w.get("color", "#2563eb"))
            if w_type == "value":
                cards += f"""
                <div class="card">
                    <div class="card-title">{w_title}</div>
                    <div class="card-value" style="color:{w_color}">{_html.escape(str(w_data))}</div>
                </div>"""
            elif w_type == "chart":
                cards += f"""
                <div class="card card-wide">
                    <div class="card-title">{w_title}</div>
                    <canvas id="chart-{widgets.index(w)}"></canvas>
                </div>"""
            elif w_type == "list":
                items = w_data if isinstance(w_data, list) else [w_data]
                list_html = "".join(f"<li>{_html.escape(str(i))}</li>" for i in items)
                cards += f"""
                <div class="card">
                    <div class="card-title">{w_title}</div>
                    <ul class="card-list">{list_html}</ul>
                </div>"""
            else:
                cards += f"""
                <div class="card">
                    <div class="card-title">{w_title}</div>
                    <div>{_html.escape(str(w_data))}</div>
                </div>"""

        auto_refresh = f"setInterval(function(){{ location.reload(); }}, {refresh_interval * 1000});" if refresh_interval > 0 else ""

        safe_title = _html.escape(title)
        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{safe_title}</title>
<style>
* {{ box-sizing: border-box; margin: 0; padding: 0; }}
body {{ font-family: system-ui, sans-serif; background: #f0f2f5; padding: 20px; color: #333; }}
h1 {{ font-size: 1.5rem; margin-bottom: 20px; }}
.dashboard {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 16px; }}
.card {{ background: #fff; border-radius: 8px; padding: 20px; box-shadow: 0 1px 3px rgba(0,0,0,0.08); }}
.card-wide {{ grid-column: 1 / -1; }}
.card-title {{ font-size: 0.8rem; text-transform: uppercase; letter-spacing: 0.05em; color: #666; margin-bottom: 8px; }}
.card-value {{ font-size: 2rem; font-weight: 700; }}
.card-list {{ list-style: none; }}
.card-list li {{ padding: 4px 0; border-bottom: 1px solid #f0f0f0; }}
canvas {{ width: 100% !important; max-height: 300px; }}
</style>
</head>
<body>
<h1>{safe_title}</h1>
<div class="dashboard">{cards}</div>
<script>
{auto_refresh}
</script>
</body>
</html>"""
        return html

    def get_tool_definitions(self):
        return [
            {"type": "function", "function": {
                "name": "create_web_component",
                "description": "Create a single self-contained HTML/CSS/JS component. Returns the full HTML as a string.",
                "parameters": {"type": "object", "properties": {
                    "name": {"type": "string", "description": "Component name"},
                    "description": {"type": "string", "description": "What the component does"},
                    "html_content": {"type": "string", "description": "HTML body content"},
                    "css_content": {"type": "string", "description": "CSS styles (optional)"},
                    "js_content": {"type": "string", "description": "JavaScript code (optional)"},
                }, "required": ["name", "html_content"]}
            }},
            {"type": "function", "function": {
                "name": "create_interactive_artifact",
                "description": "Build a multi-section interactive HTML artifact with charts, forms, and data displays.",
                "parameters": {"type": "object", "properties": {
                    "title": {"type": "string", "description": "Page title"},
                    "components": {"type": "string",
                        "description": "JSON list of components: [{\"name\":\"...\",\"type\":\"html|chart|form|data\",\"content\":\"...\"}]"},
                    "layout": {"type": "string", "description": "Layout type: grid or stack", "default": "grid"},
                }, "required": ["title", "components"]}
            }},
            {"type": "function", "function": {
                "name": "create_dashboard",
                "description": "Build a dashboard HTML page with value cards, charts, and lists. Returns full HTML.",
                "parameters": {"type": "object", "properties": {
                    "title": {"type": "string", "description": "Dashboard title"},
                    "widgets": {"type": "string",
                        "description": "JSON list of widgets: [{\"type\":\"value|chart|list\",\"title\":\"...\",\"data\":\"...\",\"color\":\"#hex\"}]"},
                    "refresh_interval": {"type": "integer", "description": "Auto-refresh interval in seconds (0=no refresh)", "default": 0},
                }, "required": ["title", "widgets"]}
            }},
        ]

    def get_handler(self, name):
        handlers = {
            "create_web_component": self._handle_create_component,
            "create_interactive_artifact": self._handle_create_interactive,
            "create_dashboard": self._handle_create_dashboard,
        }
        return handlers.get(name)

    def _handle_create_component(self, name="", description="", html_content="", css_content="", js_content=""):
        return self.create_component(name, description, html_content, css_content, js_content)

    def _handle_create_interactive(self, title="", components="", layout="grid"):
        try:
            import json
            comps = json.loads(components) if components else []
        except (json.JSONDecodeError, TypeError):
            comps = []
        return self.create_interactive_artifact(title, comps, layout)

    def _handle_create_dashboard(self, title="", widgets="", refresh_interval=0):
        try:
            import json
            w = json.loads(widgets) if widgets else []
        except (json.JSONDecodeError, TypeError):
            w = []
        return self.create_dashboard(title, w, refresh_interval)
