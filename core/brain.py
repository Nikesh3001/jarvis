import json
import os
import requests
import time
from pathlib import Path


OLLAMA_HOST = "http://localhost:11434"

SYSTEM_PROMPT = """You are FRIDAY, an expert coding and system assistant. Be concise and direct.

RULES:
- Analyze first, then act. Verify results. Never fabricate tool output.
- For coding: read relevant files first, understand context, then make changes.
- Use markdown with language tags for code. End with a brief confirmation.
- When asked to open something (app, website, file), call the relevant tool ONCE. Do not repeat.
- For social sites (instagram, facebook, youtube, twitter) use browse_url.
- For apps: first try launch_app. If you need to find an app, use list_all_apps first.
- Multi-step tasks: complete each step and verify before moving to the next."""


class OllamaBrain:
    def __init__(self, config=None):
        self.config = config or {}
        models_cfg = self.config.get("models", {})
        self.fast_model = models_cfg.get("fast", "phi4-mini:latest")
        self.smart_model = models_cfg.get("smart", "phi4-mini:latest")
        self.deep_model = models_cfg.get("deep", "phi4-mini:latest")
        self.current_model = self.smart_model
        self.max_tool_rounds = 10
        self.tool_registry = {}
        self.tool_definitions = []
        self._fallback_available = None

    def register_tools(self, tool_defs, handler_getter):
        for td in tool_defs:
            name = td["function"]["name"]
            handler = handler_getter(name)
            if handler:
                self.tool_registry[name] = handler
                self.tool_definitions.append(td)

    def list_models(self):
        models = self._check_ollama()
        return sorted(models) if models else []

    def _check_ollama(self):
        try:
            r = requests.get(f"{OLLAMA_HOST}/api/tags", timeout=5)
            models = [m["name"] for m in r.json().get("models", [])]
            return models
        except Exception:
            return []

    def select_model(self, user_message):
        if not user_message:
            return self.smart_model
        prompt = user_message.lower()
        deep_keywords = ["research", "analyze", "deep", "complex", "report", "write",
                         "essay", "compare", "evaluate", "investigate", "study",
                         "refactor", "architecture", "design pattern", "optimize",
                         "debug", "review", "implement", "refactor this", "build"]
        code_keywords = ["def ", "class ", "function", "import ", "async ", "await ",
                         "javascript", "typescript", "python", "rust", "golang", "c++",
                         "react", "node", "api", "endpoint", "database", "sql",
                         "algorithm", "data structure", "unit test", "pytest"]
        quick_keywords = ["cpu", "ram", "memory", "disk", "battery", "status", "time",
                          "date", "weather", "volume", "wifi", "screenshot", "clipboard",
                          "uptime", "process", "hello", "hi ", "hey", "thanks"]
        if any(kw in prompt for kw in deep_keywords) or any(kw in prompt for kw in code_keywords) or len(prompt) > 200:
            return self.deep_model
        if any(kw in prompt for kw in quick_keywords) and len(prompt) < 80:
            return self.fast_model
        return self.smart_model

    def _ensure_model(self, model):
        if self._fallback_available is None:
            self._fallback_available = self._check_ollama()
            if not self._fallback_available:
                return model
        if model not in self._fallback_available:
            if self.smart_model in self._fallback_available:
                return self.smart_model
            return self._fallback_available[0]
        return model

    def _relevant_tools(self, user_message):
        if not self.tool_definitions or not user_message:
            return self.tool_definitions
        prompt = user_message.lower()
        first_word = prompt.split()[0] if prompt.split() else ""
        greetings = {"hi", "hello", "hey", "yo", "sup", "howdy", "greetings"}
        conversational_starts = {"say", "tell", "ask", "reply", "answer", "respond", "chat", "talk", "speak"}
        if first_word in greetings or first_word in conversational_starts or any(g in prompt.split() for g in ["hi", "hello", "hey"]):
            if len(prompt) < 60:
                return []
        keyword_map = {
            "cpu|memory|ram|disk|battery|network|process|system|uptime|service|software|startup|volume|wifi|window|clipboard|screenshot|drive|explore": ["get_cpu", "get_memory", "get_disk", "get_battery", "get_network", "get_system_info", "get_system_uptime", "get_processes", "kill_process", "start_process", "take_screenshot", "get_clipboard", "set_clipboard", "get_volume", "set_volume", "mute_volume", "list_wifi", "wifi_status", "list_windows", "focus_window", "get_installed_software", "get_startup_programs", "get_services", "get_active_connections", "explore_drives", "find_installed_app"],
            "shell|cmd|command|terminal|powershell|run|execute|script": ["run_command", "run_shell", "run_powershell", "run_script"],
            "file|read|write|edit|append|list|move|copy|delete|mkdir|find|grep|folder|directory": ["read_file", "write_file", "edit_file", "append_file", "list_files", "move_file", "copy_file", "delete_file", "create_directory", "find_files", "grep_files", "file_info"],
            "search|web|google|bing|duckduckgo|look up|find|fetch|url|http|website": ["web_search", "web_fetch"],
            "git|commit|push|pull|clone|branch|repo": ["git_status", "git_diff", "git_log", "git_commit", "git_add", "git_push", "git_pull", "git_clone", "git_branch", "git_checkout", "git_init", "git_remote", "git_reset"],
            "browser|chrome|firefox|edge|open|launch|start|app|instagram|facebook|twitter|youtube": ["launch_app", "browse_url", "search_web", "open_file", "open_folder", "send_keys", "press_key", "hotkey", "click", "scroll", "list_apps", "list_all_apps", "find_installed_app"],
            "code|python|script|run|sandbox": ["run_code"],
            "remember|memory|forget|recall": ["remember", "recall", "list_memories", "forget"],
            "plan|task|step|goal|objective": ["create_plan", "execute_step", "complete_step", "fail_step", "get_progress", "update_plan", "list_plans", "load_plan"],
            "news|headline|current|event|wikipedia|wiki": ["wikipedia_summary", "wikipedia_search", "get_daily_news", "get_current_events"],
            "stock|market|price|trade|invest": ["get_stock_price", "search_stock", "get_market_summary"],
            "scrape|scraper|extract|link": ["scrape_url", "extract_links", "check_site_status"],
            "security|firewall|port|vulnerability|audit": ["check_firewall", "check_open_ports", "check_listeners", "check_security_updates", "security_best_practices"],
            "research|deep|analyze": ["deep_research", "research_topic", "design_architecture"],
            "ocr|image|spreadsheet": ["ocr_image", "read_spreadsheet"],
        }
        selected = set()
        for keywords, tool_names in keyword_map.items():
            if any(kw in prompt for kw in keywords.split("|")):
                selected.update(tool_names)
        if not selected:
            selected.update({"web_search", "web_fetch", "read_file", "run_command", "launch_app", "browse_url"})
        result = [td for td in self.tool_definitions if td["function"]["name"] in selected]
        return result[:40] if len(result) > 40 else result

    def chat(self, messages, tools_enabled=True):
        model = self._ensure_model(self.current_model)
        msgs = [{"role": "system", "content": SYSTEM_PROMPT}]
        for m in messages:
            msgs.append({"role": m["role"], "content": m.get("content", "")})

        last_user = ""
        for m in reversed(messages):
            if m["role"] == "user":
                last_user = m.get("content", "")
                break

        payload = {
            "model": model,
            "messages": msgs,
            "stream": False,
            "keep_alive": "0",
            "options": {"temperature": 0.1, "num_predict": 512, "num_ctx": 2048}
        }
        if tools_enabled and self.tool_definitions:
            payload["tools"] = self._relevant_tools(last_user)

        try:
            r = requests.post(f"{OLLAMA_HOST}/api/chat", json=payload, timeout=300)
            r.raise_for_status()
            return r.json()
        except requests.exceptions.Timeout:
            return {"message": {"role": "assistant", "content": "Request timed out. Try a simpler query, sir."}}
        except Exception as e:
            return {"message": {"role": "assistant", "content": "[AI backend error: request failed]"}}

    def _parse_text_tool_call(self, text):
        m = __import__("re").search(r'\[TOOL\]\s*(\w+)\((.+?)\)\s*\[/TOOL\]', text, __import__("re").DOTALL)
        if not m:
            return None, None, text
        name = m.group(1)
        args_raw = m.group(2).strip()
        try:
            args = json.loads(args_raw)
        except json.JSONDecodeError:
            try:
                args = json.loads("{" + args_raw + "}")
            except json.JSONDecodeError:
                args = {"url": args_raw} if "://" in args_raw else {"query": args_raw}
        remaining = text[:m.start()] + text[m.end():]
        return name, args, remaining.strip()

    def chat_with_tools(self, messages, on_speak=None):
        round_num = 0
        seen_tool_keys = set()
        while round_num < self.max_tool_rounds:
            round_num += 1
            result = self.chat(messages, tools_enabled=True)
            msg = result.get("message", {})
            content = msg.get("content", "")
            tool_calls = msg.get("tool_calls", [])

            if not tool_calls and content:
                name, args, remaining = self._parse_text_tool_call(content)
                if name:
                    tool_calls = [{"function": {"name": name, "arguments": args}}]
                    content = remaining

            if not tool_calls:
                if content and on_speak:
                    on_speak(content)
                messages.append({"role": "assistant", "content": content})
                return content

            if content and on_speak:
                on_speak(content)

            messages.append({"role": "assistant", "content": content or ""})

            loop_break = False
            for tc in tool_calls:
                if isinstance(tc, dict) and "function" in tc:
                    func_info = tc["function"]
                elif isinstance(tc, dict) and "name" in tc:
                    func_info = tc
                elif isinstance(tc, dict) and "type" in tc:
                    func_info = tc
                else:
                    func_info = tc.get("function", tc)
                name = func_info.get("name", "")
                args = func_info.get("arguments", {})
                if isinstance(args, str):
                    try:
                        args = json.loads(args)
                    except json.JSONDecodeError:
                        args = {}

                tool_key = f"{name}({json.dumps(args, sort_keys=True)})"
                if tool_key in seen_tool_keys:
                    if on_speak:
                        print(f"  [STOP] '{name}' already called, finishing")
                    loop_break = True
                    break
                seen_tool_keys.add(tool_key)

                handler = self.tool_registry.get(name)
                if handler:
                    try:
                        if isinstance(args, dict):
                            result_str = handler(**args)
                        else:
                            result_str = handler(args)
                    except PermissionError as e:
                        result_str = f"Access denied: {e}"
                    except FileNotFoundError as e:
                        result_str = f"File not found: {e}"
                    except Exception:
                        result_str = f"Error executing {name}: operation failed"
                else:
                    result_str = f"Tool '{name}' not found"

                if on_speak:
                    print(f"  [TOOL:{name}] -> {result_str[:200]}")

                messages.append({
                    "role": "tool",
                    "content": result_str,
                    "name": name
                })

            if loop_break:
                break

        final = self.chat(messages, tools_enabled=False)
        final_content = final.get("message", {}).get("content", "Done.")
        if on_speak:
            on_speak(final_content)
        messages.append({"role": "assistant", "content": final_content})
        return final_content

    def simple_chat(self, messages, on_token=None):
        model = self._ensure_model(self.current_model)
        msgs = [{"role": "system", "content": SYSTEM_PROMPT}]
        for m in messages[-10:]:
            msgs.append({"role": m["role"], "content": m.get("content", "")})

        payload = {
            "model": model,
            "messages": msgs,
            "stream": True,
            "keep_alive": "10m",
            "options": {"temperature": 0.1, "num_predict": 512}
        }
        full = ""
        try:
            r = requests.post(f"{OLLAMA_HOST}/api/chat", json=payload, stream=True, timeout=120)
            for line in r.iter_lines():
                if line:
                    try:
                        data = json.loads(line)
                        token = data.get("message", {}).get("content", "")
                        if token:
                            full += token
                            if on_token:
                                on_token(token)
                    except json.JSONDecodeError:
                        continue
            return full.strip()
        except Exception as e:
            return f"[Error: {e}]"


class GroqBrain:
    def __init__(self, config=None):
        self.config = config or {}
        models_cfg = self.config.get("models", {})
        self.fast_model = models_cfg.get("fast", "llama-3.1-8b-instant")
        self.smart_model = models_cfg.get("smart", "llama-3.3-70b-versatile")
        self.deep_model = models_cfg.get("deep", "llama-3.3-70b-versatile")
        self.current_model = self.smart_model
        self.max_tool_rounds = 10
        self.tool_registry = {}
        self.tool_definitions = []

        api_key = self.config.get("api_key") or os.environ.get("GROQ_API_KEY")
        if not api_key:
            raise ValueError("Groq API key required in config.json or GROQ_API_KEY env var")
        from groq import Groq
        self.client = Groq(api_key=api_key)

    def register_tools(self, tool_defs, handler_getter):
        for td in tool_defs:
            name = td["function"]["name"]
            handler = handler_getter(name)
            if handler:
                self.tool_registry[name] = handler
                self.tool_definitions.append(td)

    def select_model(self, user_message):
        if not user_message:
            return self.smart_model
        prompt = user_message.lower()
        deep_keywords = ["research", "analyze", "deep", "complex", "report", "write",
                         "essay", "compare", "evaluate", "investigate", "study",
                         "refactor", "architecture", "design pattern", "optimize",
                         "debug", "review", "implement", "refactor this", "build"]
        code_keywords = ["def ", "class ", "function", "import ", "async ", "await ",
                         "javascript", "typescript", "python", "rust", "golang", "c++",
                         "react", "node", "api", "endpoint", "database", "sql",
                         "algorithm", "data structure", "unit test", "pytest"]
        quick_keywords = ["cpu", "ram", "memory", "disk", "battery", "status", "time",
                          "date", "weather", "volume", "wifi", "screenshot", "clipboard",
                          "uptime", "process", "hello", "hi ", "hey", "thanks"]
        if any(kw in prompt for kw in deep_keywords) or any(kw in prompt for kw in code_keywords) or len(prompt) > 200:
            return self.deep_model
        if any(kw in prompt for kw in quick_keywords) and len(prompt) < 80:
            return self.fast_model
        return self.smart_model

    def list_models(self):
        try:
            models = [m.id for m in self.client.models.list().data]
            return sorted(models)
        except Exception as e:
            return "[Error listing AI models: request failed]"

    def _relevant_tools(self, messages):
        if not self.tool_definitions:
            return []
        last_user = ""
        for m in reversed(messages):
            if m["role"] == "user":
                last_user = m.get("content", "")
                break
        if not last_user:
            return []
        prompt = last_user.lower().strip()

        greetings = {"hi", "hello", "hey", "yo", "sup", "good morning", "good afternoon",
                     "good evening", "whatsup", "wassup", "howdy", "greetings"}
        first_word = prompt.split()[0] if prompt.split() else ""
        if prompt in greetings or prompt.rstrip("?!.,") in greetings or first_word in greetings:
            return []

        conversational_starts = {"say", "tell", "ask", "reply", "answer", "respond", "chat", "talk", "speak"}
        if first_word in conversational_starts or any(
            g in prompt.split() for g in ["hi", "hello", "hey"]
        ):
            if len(prompt) < 60:
                return []

        keyword_map = {
            "cpu|memory|ram|disk|battery|network|process|system|uptime|service|software|startup|volume|wifi|window|clipboard|screenshot|drive|explore": ["get_cpu", "get_memory", "get_disk", "get_battery", "get_network", "get_system_info", "get_system_uptime", "get_processes", "kill_process", "start_process", "take_screenshot", "get_clipboard", "set_clipboard", "get_volume", "set_volume", "mute_volume", "list_wifi", "wifi_status", "list_windows", "focus_window", "get_installed_software", "get_startup_programs", "get_services", "get_active_connections", "explore_drives", "find_installed_app"],
            "shell|cmd|command|terminal|powershell|run|execute|script": ["run_command", "run_shell", "run_powershell", "run_script"],
            "file|read|write|edit|append|list|move|copy|delete|mkdir|find|grep|folder|directory": ["read_file", "write_file", "edit_file", "append_file", "list_files", "move_file", "copy_file", "delete_file", "create_directory", "find_files", "grep_files", "file_info"],
            "search|web|google|bing|duckduckgo|look up|find|fetch|url|http|website": ["web_search", "web_fetch"],
            "git|commit|push|pull|clone|branch|repo": ["git_status", "git_diff", "git_log", "git_commit", "git_add", "git_push", "git_pull", "git_clone", "git_branch", "git_checkout", "git_init", "git_remote", "git_reset"],
            "browser|chrome|firefox|edge|open|launch|start|app|instagram|facebook|twitter|youtube": ["launch_app", "browse_url", "search_web", "open_file", "open_folder", "send_keys", "press_key", "hotkey", "click", "scroll", "list_apps", "list_all_apps", "find_installed_app"],
            "code|python|script|run|sandbox": ["run_code"],
            "remember|memory|forget|recall": ["remember", "recall", "list_memories", "forget"],
            "plan|task|step|goal|objective": ["create_plan", "execute_step", "complete_step", "fail_step", "get_progress", "update_plan", "list_plans", "load_plan"],
            "news|headline|current|event|wikipedia|wiki": ["wikipedia_summary", "wikipedia_search", "get_daily_news", "get_current_events"],
            "stock|market|price|trade|invest": ["get_stock_price", "search_stock", "get_market_summary"],
            "scrape|scraper|extract|link": ["scrape_url", "extract_links", "check_site_status"],
            "security|firewall|port|vulnerability|audit": ["check_firewall", "check_open_ports", "check_listeners", "check_security_updates", "security_best_practices"],
            "research|deep|analyze": ["deep_research", "research_topic", "design_architecture"],
            "ocr|image|spreadsheet": ["ocr_image", "read_spreadsheet"],
        }
        selected = set()
        for keywords, tool_names in keyword_map.items():
            if any(kw in prompt for kw in keywords.split("|")):
                selected.update(tool_names)
        if not selected:
            selected.update({"web_search", "web_fetch", "read_file", "run_command", "launch_app", "browse_url"})
        result = [td for td in self.tool_definitions if td["function"]["name"] in selected]
        return result[:30] if len(result) > 30 else result

    def chat(self, messages, tools_enabled=True):
        model = self.current_model
        msgs = [{"role": "system", "content": SYSTEM_PROMPT}]
        for m in messages:
            role = m["role"]
            content = m.get("content", "")
            if role == "tool":
                msgs.append({
                    "role": "tool",
                    "tool_call_id": m.get("tool_call_id", ""),
                    "content": str(content)
                })
            else:
                msgs.append({"role": role, "content": content})

        is_deep = model in (self.deep_model, self.smart_model)
        kwargs = {
            "model": model,
            "messages": msgs,
            "temperature": 0.1,
            "max_tokens": 4096 if is_deep else 1024,
        }
        if tools_enabled and self.tool_definitions:
            kwargs["tools"] = self._relevant_tools(messages)
            kwargs["tool_choice"] = "auto"

        try:
            response = self.client.chat.completions.create(**kwargs, timeout=60)
            choice = response.choices[0]
            msg = choice.message
            result = {"message": {"role": "assistant", "content": msg.content or "", "tool_calls": []}}
            if msg.tool_calls:
                result["message"]["tool_calls"] = [
                    {
                        "id": tc.id,
                        "type": tc.type,
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments
                        }
                    }
                    for tc in msg.tool_calls
                ]
            return result
        except Exception as e:
            return {"message": {"role": "assistant", "content": "[AI backend error: request failed]"}}

    def chat_with_tools(self, messages, on_speak=None):
        round_num = 0
        seen_tool_keys = set()
        while round_num < self.max_tool_rounds:
            round_num += 1
            result = self.chat(messages, tools_enabled=True)
            msg = result.get("message", {})
            content = msg.get("content", "")
            tool_calls = msg.get("tool_calls", [])

            if not tool_calls:
                if content and on_speak:
                    on_speak(content)
                messages.append({"role": "assistant", "content": content})
                return content

            if content and on_speak:
                on_speak(content)

            messages.append({"role": "assistant", "content": content or ""})

            loop_break = False
            for tc in tool_calls:
                tc_id = tc.get("id", "")
                func = tc.get("function", {})
                name = func.get("name", "")
                args_raw = func.get("arguments", "{}")
                try:
                    args = json.loads(args_raw) if isinstance(args_raw, str) else args_raw
                except json.JSONDecodeError:
                    args = {}

                tool_key = f"{name}({json.dumps(args, sort_keys=True)})"
                if tool_key in seen_tool_keys:
                    if on_speak:
                        print(f"  [STOP] '{name}' already called, finishing")
                    loop_break = True
                    break
                seen_tool_keys.add(tool_key)

                handler = self.tool_registry.get(name)
                if handler:
                    try:
                        result_str = handler(**args) if isinstance(args, dict) else handler(args)
                    except PermissionError as e:
                        result_str = f"Access denied: {e}"
                    except FileNotFoundError as e:
                        result_str = f"File not found: {e}"
                    except Exception:
                        result_str = f"Error executing {name}: operation failed"
                else:
                    result_str = f"Tool '{name}' not found"

                if on_speak:
                    result_preview = result_str[:200].replace('\n', ' ')
                    print(f"  [TOOL:{name}] -> {result_preview}")

                messages.append({
                    "role": "tool",
                    "tool_call_id": tc_id,
                    "content": result_str
                })

            if loop_break:
                break

        final = self.chat(messages, tools_enabled=False)
        final_content = final.get("message", {}).get("content", "Done.")
        if on_speak:
            on_speak(final_content)
        messages.append({"role": "assistant", "content": final_content})
        return final_content

    def simple_chat(self, messages, on_token=None):
        msgs = [{"role": "system", "content": SYSTEM_PROMPT}]
        for m in messages[-10:]:
            msgs.append({"role": m["role"], "content": m.get("content", "")})
        try:
            stream = self.client.chat.completions.create(
                model=self.current_model,
                messages=msgs,
                temperature=0.1,
                max_tokens=1024,
                stream=True
            )
            full = ""
            for chunk in stream:
                token = chunk.choices[0].delta.content or ""
                if token:
                    full += token
                    if on_token:
                        on_token(token)
            return full.strip()
        except Exception:
            return "[Groq API error: request failed]"
