import re
from typing import Dict, List, Tuple, Optional


class IntentSignature:
    __slots__ = ('name', 'primary', 'secondary', 'anti_patterns', 'phrase_patterns',
                 'strong_indicators', 'default_params', 'category')

    def __init__(self, name: str, category: str,
                 primary: List[str],
                 secondary: Optional[List[str]] = None,
                 anti_patterns: Optional[List[str]] = None,
                 phrase_patterns: Optional[List[str]] = None,
                 strong_indicators: Optional[List[str]] = None,
                 default_params: Optional[Dict] = None):
        self.name = name
        self.category = category
        self.primary = [w.lower() for w in primary]
        self.secondary = [w.lower() for w in (secondary or [])]
        self.anti_patterns = [w.lower() for w in (anti_patterns or [])]
        self.phrase_patterns = [p.lower() for p in (phrase_patterns or [])]
        self.strong_indicators = [w.lower() for w in (strong_indicators or [])]
        self.default_params = default_params or {}

    def score(self, text: str) -> Tuple[float, Dict]:
        lower = text.lower()
        tokens = set(lower.split())
        n = len(tokens) if tokens else 1

        def _in_text(w):
            if " " in w:
                return w in lower
            return w in tokens

        matched_primary = [w for w in self.primary if _in_text(w)]
        matched_secondary = [w for w in self.secondary if _in_text(w)]
        matched_anti = [w for w in self.anti_patterns if _in_text(w)]
        matched_phrases = [p for p in self.phrase_patterns if p in lower]
        matched_strong = [w for w in self.strong_indicators if _in_text(w)]

        raw = 0.0
        raw += len(matched_primary) * 3.0
        raw += len(matched_strong) * 4.0
        raw += len(matched_secondary) * 1.0
        raw += len(matched_phrases) * 5.0
        raw -= len(matched_anti) * 4.0
        raw = max(raw, 0.0)

        proximity_bonus = 0.0
        if len(matched_primary) >= 2:
            words = lower.split()
            positions = [i for i, w in enumerate(words) if w in self.primary]
            if len(positions) >= 2:
                spans = [positions[i+1] - positions[i] for i in range(len(positions)-1)]
                avg_gap = sum(spans) / len(spans)
                proximity_bonus = max(0, 2.0 - avg_gap * 0.3)

        presence = raw / min(n, 15)
        confidence = min(presence + proximity_bonus, raw)
        info = {
            'primary': matched_primary,
            'secondary': matched_secondary,
            'phrases': matched_phrases,
            'strong': matched_strong,
            'raw_score': raw,
            'proximity': proximity_bonus,
        }
        return (confidence, info)


HUMAN_INTENTS = [
    IntentSignature("system_info", "system",
        primary=["cpu", "memory", "ram", "disk", "battery", "system"],
        secondary=["usage", "status", "info", "performance", "hardware", "uptime", "processor", "storage", "load"],
        strong_indicators=["whats my", "how much", "show me", "check my"],
        phrase_patterns=["system status", "suit status", "systems check", "how is my computer", "system info"]),
    IntentSignature("process_manage", "system",
        primary=["process", "task", "tasks", "running", "service"],
        secondary=["kill", "stop", "start", "list", "manage", "cpu", "memory"],
        strong_indicators=["running processes", "list processes", "kill process"],
        phrase_patterns=["whats running", "show processes", "running programs", "show tasks"]),
    IntentSignature("network", "system",
        primary=["wifi", "network", "internet", "connection", "ip"],
        secondary=["status", "signal", "strength", "connect", "disconnect", "list", "available", "speed"],
        strong_indicators=["wifi status", "network status", "my ip", "internet speed"],
        phrase_patterns=["list wifi", "wifi networks", "network connections", "am i connected"]),
    IntentSignature("volume_control", "system",
        primary=["volume", "sound", "audio", "speaker", "mute"],
        secondary=["up", "down", "loud", "quiet", "max", "min", "set", "change", "adjust", "increase", "decrease"],
        strong_indicators=["turn up", "turn down", "volume up", "volume down", "mute"],
        phrase_patterns=["set volume", "change volume", "increase volume", "decrease volume"]),
    IntentSignature("window_manage", "system",
        primary=["window", "app", "application", "focus"],
        secondary=["switch", "open", "close", "launch", "start", "bring", "front", "minimize", "maximize"],
        strong_indicators=["focus window", "switch to", "bring to front", "open app"],
        phrase_patterns=["switch window", "focus on", "launch application"]),
    IntentSignature("clipboard", "system",
        primary=["clipboard", "copy", "paste"],
        secondary=["get", "set", "show", "whats", "content"],
        strong_indicators=["clipboard content", "clipboard text"],
        phrase_patterns=["whats on my clipboard", "what is on my clipboard", "what's on my clipboard", "show clipboard", "copy to clipboard"]),
    IntentSignature("screen", "system",
        primary=["screenshot", "screen", "display", "monitor"],
        secondary=["take", "capture", "show", "whats on", "snapshot"],
        strong_indicators=["screenshot", "take a screenshot", "capture screen"],
        phrase_patterns=["whats on my screen", "take screenshot", "capture display"]),
    IntentSignature("file_ops", "files",
        primary=["file", "folder", "directory", "read", "write", "edit", "delete", "move", "copy", "list"],
        secondary=["create", "rename", "find", "search", "open", "save", "content", "path", "text"],
        anti_patterns=["code", "python", "script", "program"],
        strong_indicators=["read file", "write file", "list files", "find file", "create file", "edit file"],
        phrase_patterns=["show me the file", "list directory", "create folder", "delete file", "copy file"]),
    IntentSignature("shell", "shell",
        primary=["shell", "terminal", "command", "powershell", "cmd", "run", "execute", "script"],
        secondary=["prompt", "console", "dos", "batch", "command line"],
        anti_patterns=["code", "python", "analyze", "write a"],
        strong_indicators=["run command", "execute command", "open terminal", "run in terminal", "ping"],
        phrase_patterns=["run a command", "execute this", "in terminal", "in powershell", "execute ping"]),
    IntentSignature("web_search", "web",
        primary=["search", "web", "google", "look up", "find", "tell me about"],
        secondary=["online", "internet", "browser", "website", "information", "wikipedia", "news about"],
        anti_patterns=["file", "local", "my computer", "desktop", "folder", "clipboard", "volume", "cpu", "memory", "system", "binary search", "ping", ".com"],
        strong_indicators=["search for", "google", "look up", "search web", "find online"],
        phrase_patterns=["search the web", "look this up", "whats the latest", "tell me about"]),
    IntentSignature("web_fetch", "web",
        primary=["fetch", "url", "http", "https", "page", "website", "open url"],
        secondary=["load", "visit", "go to", "content", "read", "extract"],
        strong_indicators=["fetch url", "open website", "go to url", "load page"],
        phrase_patterns=["fetch this url", "open this page", "go to website", "open website"]),
    IntentSignature("code_run", "code",
        primary=["code", "python", "script", "run", "program", "compile", "execute", "write", "function", "class", "implement"],
        secondary=["test", "debug", "review", "fix", "refactor", "analyze code", "check syntax", "create", "build", "define"],
        anti_patterns=["terminal", "shell", "command", "powershell", "cmd"],
        strong_indicators=["run python", "run code", "execute script", "run this code", "compile", "debug this", "write a", "write code"],
        phrase_patterns=["run this code", "execute this script", "compile this", "debug this program", "write a python", "write a function", "implement a"]),
    IntentSignature("git", "git",
        primary=["git", "commit", "push", "pull", "clone", "branch", "repo", "repository"],
        secondary=["status", "diff", "log", "merge", "rebase", "stash", "checkout", "add", "origin", "remote"],
        strong_indicators=["git status", "git commit", "git push", "git pull", "git clone"],
        phrase_patterns=["git status", "commit changes", "push to remote", "pull from repo", "create branch"]),
    IntentSignature("memory", "memory",
        primary=["remember", "forget", "recall", "memory", "remind"],
        secondary=["store", "save", "keep", "note", "save this", "dont forget", "learn"],
        strong_indicators=["remember this", "remember that", "dont forget", "save this for later"],
        phrase_patterns=["remember this", "save this", "store this", "remind me"]),
    IntentSignature("planning", "planning",
        primary=["plan", "task", "step", "goal", "objective"],
        secondary=["create", "make", "build", "execute", "track", "progress", "milestone", "list"],
        strong_indicators=["create a plan", "make a plan", "plan this", "task list"],
        phrase_patterns=["create a plan", "make a task list", "orchestrate this", "break this down into steps"]),
    IntentSignature("news", "news",
        primary=["news", "headline", "current events", "whats happening"],
        secondary=["today", "latest", "breaking", "update", "world", "tech news", "top stories"],
        strong_indicators=["latest news", "breaking news", "headlines", "whats happening"],
        phrase_patterns=["latest news", "breaking news", "whats happening in the world", "todays headlines"]),
    IntentSignature("stocks", "stocks",
        primary=["stock", "market", "price", "share", "trade", "invest"],
        secondary=["ticker", "symbol", "nifty", "sensex", "nasdaq", "s&p", "dow jones", "crypto", "bitcoin"],
        strong_indicators=["stock price", "market today", "stock market", "share price"],
        phrase_patterns=["stock price", "market summary", "how is the market"]),
    IntentSignature("scrape", "scrape",
        primary=["scrape", "extract", "crawl", "scraper"],
        secondary=["data", "content", "links", "all", "from page", "collect"],
        strong_indicators=["scrape this", "extract data", "scrape website"],
        phrase_patterns=["scrape this page", "extract links from", "crawl this website"]),
    IntentSignature("research_deep", "research",
        primary=["research", "deep", "analyze", "analyze this", "study", "comprehensive"],
        secondary=["report", "detailed", "thorough", "investigate", "explore", "literature"],
        anti_patterns=["quick", "simple", "brief", "short"],
        strong_indicators=["deep research", "research this", "analyze this", "in depth"],
        phrase_patterns=["deep research", "research topic", "analyze this", "comprehensive report"]),
    IntentSignature("ocr", "ocr",
        primary=["ocr", "image text", "read text", "extract text"],
        secondary=["image", "picture", "photo", "scan", "recognize", "screenshot text"],
        strong_indicators=["read text from", "ocr this", "extract text from image"],
        phrase_patterns=["read text from image", "extract text from picture", "ocr this image"]),
    IntentSignature("language_tools", "languages",
        primary=["lint", "format", "scaffold", "package", "install", "detect", "language"],
        secondary=["project", "dependencies", "module", "library", "setup", "init"],
        strong_indicators=["lint this", "format code", "scaffold project", "install package"],
        phrase_patterns=["lint this file", "format this code", "scaffold a project", "install a package", "detect project type"]),
    IntentSignature("vision", "vision",
        primary=["vision", "image", "photo", "picture", "see", "look at"],
        secondary=["what", "analyze", "describe", "tell me", "content", "object", "scene"],
        strong_indicators=["whats in this image", "analyze this image", "describe this picture", "what do you see"],
        phrase_patterns=["whats in this image", "analyze this image", "describe this picture", "what do you see"]),
    IntentSignature("task_orchestrator", "planning",
        primary=["orchestrate", "deploy", "pipeline", "workflow", "multi step", "automate"],
        secondary=["build", "setup", "configure", "deploy app", "ci/cd", "integration"],
        strong_indicators=["orchestrate", "automate this", "set up pipeline"],
        phrase_patterns=["orchestrate deploying", "automate this workflow", "set up a pipeline"]),
]

_GREETING_PATTERNS = [
    r'^(hi|hello|hey|yo|sup|howdy|greetings|welcome)(\s|$|,|!)',
    r'(good morning|good afternoon|good evening)',
    r'(whatsup|wassup|how are you|how are things|whats up)',
    r'^(who are you|who is this|what are you)\??$',
]

_GRATITUDE_PATTERNS = [
    r'(thank|thanks|thx|\bty\b|appreciate)',
    r'(good job|nice work|well done|great)',
]

_ACTION_VERBS = {
    "show": "system_info", "get": "system_info", "check": "system_info",
    "list": "file_ops", "find": "file_ops", "search": "web_search",
    "create": "file_ops", "make": "file_ops", "delete": "file_ops",
    "run": "shell", "execute": "shell", "open": "shell",
    "read": "file_ops", "write": "file_ops", "edit": "file_ops",
    "tell": "web_search", "what": "web_search", "who": "web_search",
    "explain": "web_search", "how": "web_search",
}


def _is_greeting(text: str) -> bool:
    lower = text.lower().strip()
    for p in _GREETING_PATTERNS:
        if re.search(p, lower):
            return True
    return False


def _is_gratitude(text: str) -> bool:
    lower = text.lower().strip()
    for p in _GRATITUDE_PATTERNS:
        if re.search(p, lower):
            return True
    return False


def analyze_intent(text: str) -> Dict:
    if not text or not text.strip():
        return {"intent": "none", "category": "none", "confidence": 0.0,
                "matched": {}, "guess": False, "is_greeting": False, "is_gratitude": False}

    if _is_greeting(text):
        return {"intent": "greeting", "category": "chat", "confidence": 1.0,
                "matched": {}, "guess": False, "is_greeting": True, "is_gratitude": False}

    if _is_gratitude(text):
        return {"intent": "gratitude", "category": "chat", "confidence": 1.0,
                "matched": {}, "guess": False, "is_greeting": False, "is_gratitude": True}

    scored = []
    for sig in HUMAN_INTENTS:
        conf, info = sig.score(text)
        scored.append((conf, sig, info))

    scored.sort(key=lambda x: -x[0])
    top_conf, top_sig, top_info = scored[0]
    runner_conf = scored[1][0] if len(scored) > 1 else 0.0

    threshold = 1.5
    is_strong = top_conf >= threshold
    is_ambiguous = top_conf < threshold and runner_conf > 0.5

    result = {
        "intent": top_sig.name,
        "category": top_sig.category,
        "confidence": round(min(top_conf, 15.0) / 15.0, 3),
        "raw_score": top_info['raw_score'],
        "matched": {
            "primary": top_info['primary'],
            "secondary": top_info['secondary'],
            "phrases": top_info.get('phrases', []),
            "strong": top_info.get('strong', []),
        },
        "guess": not is_strong,
        "is_greeting": False,
        "is_gratitude": False,
        "runner_up": scored[1][0] if len(scored) > 1 else 0.0,
    }

    if not is_strong:
        lower = text.lower()
        tokens = lower.split()
        verb = tokens[0] if tokens else ""
        action_target = _ACTION_VERBS.get(verb)
        if action_target:
            result["intent"] = action_target
            for sig in HUMAN_INTENTS:
                if sig.name == action_target:
                    result["category"] = sig.category
                    break
            result["confidence"] = max(result["confidence"], 0.4)
            result["guess"] = True
            result["guess_method"] = "verb_first"

        if not result.get("guess_method") and is_ambiguous:
            result["guess"] = True
            result["guess_method"] = "ambiguous"

    return result


def guess_params(intent_name: str, text: str) -> Dict:
    lower = text.lower()
    params = {}

    if intent_name in ("web_search",):
        import re as _re
        for prefix in ["search for", "search", "look up", "find", "what is", "who is", "tell me about"]:
            m = _re.search(_re.escape(prefix) + r'\s+(.+)', lower)
            if m:
                params["query"] = m.group(1).strip().rstrip("?.!")
                break
        if "query" not in params:
            params["query"] = text.strip()[:100]

    elif intent_name in ("web_fetch",):
        url_m = re.search(r'(https?://[^\s]+)', text)
        if url_m:
            params["url"] = url_m.group(1)
        else:
            params["url"] = text.strip()

    elif intent_name == "volume_control":
        if any(w in lower for w in ["up", "increase", "raise", "louder", "max"]):
            params["level"] = "up"
        elif any(w in lower for w in ["down", "decrease", "lower", "quieter", "min", "mute"]):
            params["level"] = "down"
        else:
            params["level"] = "toggle"

    elif intent_name in ("file_ops",):
        action = "list"
        for a, kw in [("read", ["read", "open", "show", "display", "cat"]),
                       ("write", ["write", "save", "create"]),
                       ("edit", ["edit", "modify", "change", "update", "append"]),
                       ("delete", ["delete", "remove", "rm"]),
                       ("copy", ["copy", "duplicate"]),
                       ("move", ["move", "rename"]),
                       ("list", ["list", "show", "ls", "dir", "whats in"])]:
            if any(k in lower for k in kw):
                action = a
                break
        params["action"] = action

    elif intent_name in ("code_run",):
        if any(w in lower for w in ["python", "py"]):
            params["language"] = "python"
        elif any(w in lower for w in ["javascript", "js", "node"]):
            params["language"] = "javascript"
        elif any(w in lower for w in ["c++", "cpp", "c"]):
            params["language"] = "cpp"
        elif any(w in lower for w in ["rust"]):
            params["language"] = "rust"

    elif intent_name == "memory":
        for prefix in ["remember", "save", "store", "note"]:
            m = re.search(re.escape(prefix) + r'\s+(.+)', lower)
            if m:
                params["content"] = m.group(1).strip()
                break

    elif intent_name == "shell":
        for prefix in ["run command", "run", "execute"]:
            m = re.search(re.escape(prefix) + r'\s+(.+)', lower)
            if m:
                params["command"] = m.group(1).strip()
                break

    return params


def get_tools_for_intent(analysis: Dict) -> List[str]:
    INTENT_TO_TOOLS = {
        "system_info": ["get_cpu", "get_memory", "get_disk", "get_battery", "get_network", "get_system_info", "get_system_uptime"],
        "process_manage": ["get_processes", "kill_process"],
        "network": ["list_wifi", "wifi_status", "get_active_connections", "get_network"],
        "volume_control": ["get_volume", "set_volume", "mute_volume"],
        "window_manage": ["list_windows", "focus_window"],
        "clipboard": ["get_clipboard", "set_clipboard"],
        "screen": ["take_screenshot"],
        "file_ops": ["read_file", "write_file", "edit_file", "append_file", "list_files", "move_file", "copy_file", "delete_file", "create_directory", "find_files", "grep_files", "file_info"],
        "shell": ["run_command", "run_shell", "run_powershell", "run_script"],
        "web_search": ["web_search", "web_fetch", "web_search_and_fetch"],
        "web_fetch": ["web_fetch"],
        "code_run": ["run_code"],
        "git": ["git_status", "git_diff", "git_log", "git_commit", "git_add", "git_push", "git_pull", "git_clone", "git_branch", "git_checkout", "git_init", "git_remote", "git_reset"],
        "memory": ["remember", "recall", "list_memories", "forget"],
        "planning": ["create_plan", "execute_step", "complete_step", "fail_step", "get_progress", "update_plan", "list_plans", "load_plan"],
        "news": ["wikipedia_summary", "wikipedia_search", "get_daily_news", "get_current_events"],
        "stocks": ["get_stock_price", "search_stock", "get_market_summary"],
        "scrape": ["scrape_url", "extract_links", "check_site_status"],
        "research_deep": ["deep_research", "research_topic", "design_architecture"],
        "ocr": ["ocr_image", "read_spreadsheet"],
        "language_tools": ["detect_language", "detect_project", "lint_file", "format_file", "scaffold_project", "package_install", "package_list", "run_file"],
        "task_orchestrator": ["create_plan", "execute_step"],
        "vision": [],
        "language_tools": ["detect_language", "detect_project", "lint_file", "format_file", "scaffold_project", "package_install", "package_list", "run_file"],
        "greeting": [],
        "gratitude": [],
    }
    return INTENT_TO_TOOLS.get(analysis["intent"], [])
