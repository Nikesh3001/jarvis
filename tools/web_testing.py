import os
import json
import re
from pathlib import Path
from urllib.parse import urlparse

from core.ratelimit import check_rate
from core.ssrf import is_ssrf_blocked
import core.guardian as guardian


class WebTestingTools:
    def _check_rate(self, op):
        return check_rate(f"webtest:{op}", rate=3, burst=5)

    def _has_playwright(self):
        try:
            import playwright
            return True
        except ImportError:
            return False

    def run_browser_test(self, url, actions, headless=True):
        if not self._check_rate("browser_test"):
            return "Rate limited"
        if not self._has_playwright():
            return "Playwright not installed. Install with: pip install playwright && playwright install chromium"
        parsed = urlparse(url)
        if parsed.scheme == "file":
            return "file:// URLs are not allowed in browser tests"
        host = parsed.hostname or parsed.netloc
        if host:
            blocked = is_ssrf_blocked(host)
            if blocked:
                return f"URL blocked by SSRF guard: {blocked}"
        try:
            from playwright.sync_api import sync_playwright
            results = []
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=headless)
                page = browser.new_page()
                page.goto(url, timeout=30000)
                results.append(f"Loaded: {url} (title: {page.title()})")
                for action in actions:
                    action_type = action.get("type", "")
                    selector = action.get("selector", "")
                    value = action.get("value", "")
                    if action_type == "click" and selector:
                        page.click(selector)
                        results.append(f"Clicked: {selector}")
                    elif action_type == "type" and selector:
                        page.fill(selector, value)
                        results.append(f"Typed '{value}' into {selector}")
                    elif action_type == "screenshot":
                        path = action.get("path", "screenshot.png")
                        page.screenshot(path=path)
                        results.append(f"Screenshot saved: {path}")
                    elif action_type == "evaluate":
                        result = page.evaluate(value)
                        results.append(f"JS eval: {result}")
                    elif action_type == "wait":
                        page.wait_for_timeout(int(value) if value else 1000)
                        results.append(f"Waited {value}ms")
                    elif action_type == "assert_text" and selector:
                        element = page.wait_for_selector(selector, timeout=5000)
                        text = element.text_content()
                        results.append(f"Text in {selector}: {text[:200]}")
                browser.close()
            return "\n".join(results)
        except Exception as e:
            return f"Browser test failed: {e}"

    def generate_test_script(self, url, test_cases):
        if not self._check_rate("generate_test"):
            return "Rate limited"
        try:
            safe_url = url.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
            safe_name = re.sub(r'[^a-zA-Z0-9_]', '_', url)
            script = '"""Auto-generated Playwright test."""\n'
            script += "from playwright.sync_api import sync_playwright\n\n\n"
            script += f'def test_{safe_name}():\n'
            script += f'    """Test: {safe_url}"""\n'
            script += "    with sync_playwright() as p:\n"
            script += "        browser = p.chromium.launch()\n"
            script += "        page = browser.new_page()\n"
            script += f'        page.goto("{safe_url}")\n\n'
            for i, tc in enumerate(test_cases):
                if isinstance(tc, str):
                    script += f"        # Test case {i+1}: {tc}\n"
                elif isinstance(tc, dict):
                    desc = tc.get("description", f"Step {i+1}")
                    script += f"        # {desc}\n"
                    action = tc.get("action", "")
                    selector = tc.get("selector", "")
                    value = tc.get("value", "")
                    if action == "click":
                        script += f'        page.click("{selector}")\n'
                    elif action == "type":
                        script += f'        page.fill("{selector}", "{value}")\n'
                    elif action == "assert":
                        script += f'        assert page.wait_for_selector("{selector}", timeout=5000) is not None\n'
                script += "\n"
            script += '        print("All tests passed!")\n'
            script += "        browser.close()\n\n\n"
            script += 'if __name__ == "__main__":\n'
            script += f'    test_{url.replace("://", "_").replace(".", "_").replace("/", "_")}()\n'
            return script
        except Exception as e:
            return f"Script generation failed: {e}"

    def get_tool_definitions(self):
        return [
            {"type": "function", "function": {"name": "run_browser_test", "description": "Run a browser test on a URL with specified actions (click, type, screenshot, evaluate, wait, assert_text)", "parameters": {"type": "object", "properties": {"url": {"type": "string", "description": "URL to test"}, "actions": {"type": "array", "items": {"type": "object"}, "description": "List of actions: {type, selector, value, path}"}, "headless": {"type": "boolean", "description": "Run headless", "default": True}}, "required": ["url", "actions"]}}},
            {"type": "function", "function": {"name": "generate_test_script", "description": "Generate a Playwright test script for a URL", "parameters": {"type": "object", "properties": {"url": {"type": "string", "description": "URL to test"}, "test_cases": {"type": "array", "description": "Test case descriptions or action objects"}}, "required": ["url", "test_cases"]}}},
        ]

    def get_handler(self, name):
        handlers = {
            "run_browser_test": self.run_browser_test,
            "generate_test_script": self.generate_test_script,
        }
        return handlers.get(name)
