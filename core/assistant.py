import os, sys, time, datetime, json, threading, random, base64, hashlib, shutil
from pathlib import Path

from core.speech import SpeechEngine, STARK_QUOTES
from tools.system import SystemTools


_ENCRYPTION_KEY = None


def _get_encryption_key():
    global _ENCRYPTION_KEY
    if _ENCRYPTION_KEY is not None:
        return _ENCRYPTION_KEY
    key_file = Path(__file__).parent.parent / ".conversation_key"
    if key_file.exists():
        try:
            _ENCRYPTION_KEY = base64.b64decode(key_file.read_text().strip())
            return _ENCRYPTION_KEY
        except Exception:
            pass
    key = os.urandom(32)
    _ENCRYPTION_KEY = key
    try:
        key_file.write_text(base64.b64encode(key).decode("ascii"))
        # Restrict file permissions to owner-only
        try:
            import stat
            key_file.chmod(stat.S_IRUSR | stat.S_IWUSR)  # owner read/write only
        except (OSError, AttributeError):
            pass
    except Exception:
        pass
    return key


def _encrypt_data(data):
    try:
        from cryptography.fernet import Fernet
        key = _get_encryption_key()
        fernet_key = base64.urlsafe_b64encode(hashlib.sha256(key).digest())
        f = Fernet(fernet_key)
        return f.encrypt(data.encode("utf-8")).decode("ascii")
    except ImportError:
        import sys
        print("  [SECURITY] WARNING: cryptography not installed. Using base64 encoding (not encrypted).", file=sys.stderr)
        print("  [SECURITY] Install: pip install cryptography", file=sys.stderr)
        return base64.b64encode(data.encode("utf-8")).decode("ascii")


def _decrypt_data(data):
    try:
        from cryptography.fernet import Fernet, InvalidToken
        key = _get_encryption_key()
        fernet_key = base64.urlsafe_b64encode(hashlib.sha256(key).digest())
        f = Fernet(fernet_key)
        return f.decrypt(data.encode("ascii")).decode("utf-8")
    except ImportError:
        try:
            return base64.b64decode(data.encode("ascii")).decode("utf-8")
        except Exception:
            return data
    except InvalidToken:
        try:
            return base64.b64decode(data.encode("ascii")).decode("utf-8")
        except Exception:
            return data

VERSION = "3.5.0"
MARK_NUMBER = 86

ARC_REACTOR = r"""
         \   |   /
          .---.
       ,-'     '-.
      /     .     \
     /  .       .  \
    ;   .   .   .   ;
    |  .    |    .  |
    ;   .   .   .   ;
     \  .       .  /
      \     .     /
       '-.__ __.-'
          '---'
"""

BANNER = r"""
{arc}
  +=============================================================+
  |                                                             |
  |      _____ ____  ___ ____    _ __   __                       |
  |     |  ___|  _ \|_ _|  _ \  / \ \ / /                       |
  |     | |_  | |_) || || | | |/ _ \ V /                        |
  |     |  _| |  _ < | || |_| / ___ \| |                         |
  |     |_|   |_| \_\___|____/_/   \_\_|                         |
  |                                                             |
  |   Female Replacement Intelligent Digital Assistant Youth    |
  |   Stark Industries  *  Terminal Edition  *  v{version}       |
  |   Mark {mark} Protocol  *  Arc Reactor Powered              |
  |                                                             |
  +=============================================================+
""".rstrip().format(arc=ARC_REACTOR, version=VERSION, mark=MARK_NUMBER)


class ResourceGovernor:
    def __init__(self, assistant):
        self.assistant = assistant
        self.running = True
        self._stop_event = threading.Event()
        self.thread = threading.Thread(target=self._monitor, daemon=True)
        self.thread.start()

    def _monitor(self):
        try:
            import psutil
        except ImportError:
            return
        while not self._stop_event.is_set():
            try:
                mem = psutil.virtual_memory()
                free_gb = mem.available / (1024**3)
                if free_gb < 1.0:
                    print(f"[RESOURCE] Low RAM: {free_gb:.1f}GB free - triggering cleanup")
                    self.assistant._emergency_cleanup()
                cpu = psutil.cpu_percent(interval=0)
                if cpu > 85:
                    print(f"[RESOURCE] High CPU: {cpu}% - triggering cleanup")
                    self.assistant._emergency_cleanup()
            except Exception:
                pass
            self._stop_event.wait(timeout=30)

    def stop(self):
        self.running = False
        self._stop_event.set()


class Assistant:
    def __init__(self, mic_index=None, text_mode=False):
        self.running = True
        self.is_awake = False
        self.stark_mode = False
        self.safe_mode = True
        self.text_mode = text_mode
        self.session_start = datetime.datetime.now()
        self.commands_run = 0

        self.config = self._load_config()
        self.speech = SpeechEngine(mic_index=mic_index)
        self.brain = self._init_brain()
        self.system = SystemTools()
        self.conversation = []
        self.history_dir = Path(__file__).parent.parent / "conversations"
        self.history_dir.mkdir(exist_ok=True)
        self.session_file = None

        self._web_tools = None
        self._file_tools = None
        self._code_interp = None
        self._memory = None
        self._deep_research = None
        self._file_editor = None
        self._shell = None
        self._git = None
        self._automator = None
        self._planner = None
        self._monitor = None
        self._news = None
        self._stocks = None
        self._scraper = None
        self._security = None
        self._multi_agent = None
        self._code_index = None
        self._plugin_manager = None
        self._mcp_clients = []
        self._languages = None

        self._register_core_tools()
        self._register_web_tools()
        self._register_file_tools()
        self._register_code_tools()
        self._register_memory_tools()
        self._register_research_tools()
        self._register_file_editor()
        self._register_shell()
        self._register_git()
        self._register_automator()
        self._register_planner()
        self._register_monitor()
        self._register_news()
        self._register_stocks()
        self._register_scraper()
        self._register_security()
        self._register_multi_agent()
        self._register_code_index()
        self._register_languages()
        self._register_plugins()

        self.governor = ResourceGovernor(self)

    def _load_config(self):
        path = Path(__file__).parent.parent / "config.json"
        if path.exists():
            try:
                return json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                pass
        return {
            "provider": "groq",
            "models": {
                "fast": "llama-3.1-8b-instant",
                "smart": "llama-3.3-70b-versatile",
                "deep": "llama-3.3-70b-versatile"
            }
        }

    def _save_config(self):
        path = Path(__file__).parent.parent / "config.json"
        try:
            path.write_text(json.dumps(self.config, indent=2), encoding="utf-8")
        except Exception:
            pass

    def _init_brain(self):
        provider = self.config.get("provider", "groq")
        from core.brain import OllamaBrain, GroqBrain
        registry = {
            "groq": GroqBrain,
            "ollama": OllamaBrain,
        }
        cls = registry.get(provider)
        if cls is None:
            print(f"  [WARN] Unknown provider '{provider}', falling back to groq")
            cls = GroqBrain
        return cls(self.config)

    def _register_core_tools(self):
        self.brain.register_tools(
            self.system.get_all_tool_definitions(),
            self.system.get_handler
        )

    def _trim_conversation(self, max_messages=15):
        if len(self.conversation) > max_messages:
            self.conversation = self.conversation[-max_messages:]

    def _lazy_web(self):
        if self._web_tools is None:
            from tools.web import WebTools
            self._web_tools = WebTools()
            self.brain.register_tools(
                self._web_tools.get_tool_definitions(),
                self._web_tools.get_handler
            )

    def _lazy_files(self):
        if self._file_tools is None:
            from tools.files import FileTools
            self._file_tools = FileTools()
            self.brain.register_tools(
                self._file_tools.get_tool_definitions(),
                self._file_tools.get_handler
            )

    def _lazy_code(self):
        if self._code_interp is None:
            from tools.code_interpreter import CodeInterpreter
            self._code_interp = CodeInterpreter()
            self.brain.register_tools(
                self._code_interp.get_tool_definitions(),
                self._code_interp.get_handler
            )

    def _lazy_memory(self):
        if self._memory is None:
            from memory.conversation import ConversationMemory
            self._memory = ConversationMemory()
            self.brain.register_tools(
                self._memory.get_tool_definitions(),
                self._memory.get_handler
            )

    def _lazy_research(self):
        if self._deep_research is None:
            from agent.deep_research import DeepResearchAgent
            self._deep_research = DeepResearchAgent(self.brain)
            self.brain.register_tools(
                self._deep_research.get_tool_definitions(),
                self._deep_research.get_handler
            )

    def _lazy_file_editor(self):
        if self._file_editor is None:
            from tools.file_editor import FileEditor
            self._file_editor = FileEditor()
            self.brain.register_tools(
                self._file_editor.get_tool_definitions(),
                self._file_editor.get_handler
            )

    def _lazy_shell(self):
        if self._shell is None:
            from tools.shell import ShellCommander
            self._shell = ShellCommander()
            self.brain.register_tools(
                self._shell.get_tool_definitions(),
                self._shell.get_handler
            )

    def _lazy_git(self):
        if self._git is None:
            from tools.git_ops import GitOps
            self._git = GitOps()
            self.brain.register_tools(
                self._git.get_tool_definitions(),
                self._git.get_handler
            )

    def _lazy_automator(self):
        if self._automator is None:
            from tools.automator import Automator
            self._automator = Automator()
            self._automator.safe_mode = self.safe_mode
            self.brain.register_tools(
                self._automator.get_tool_definitions(),
                self._automator.get_handler
            )

    def _lazy_planner(self):
        if self._planner is None:
            from tools.planner import Planner
            self._planner = Planner()
            self.brain.register_tools(
                self._planner.get_tool_definitions(),
                self._planner.get_handler
            )

    def _lazy_monitor(self):
        if self._monitor is None:
            from core.monitor import ProactiveMonitor
            self._monitor = ProactiveMonitor(self)

    def _lazy_news(self):
        if self._news is None:
            from tools.news import NewsTool
            self._news = NewsTool()
            self.brain.register_tools(
                self._news.get_tool_definitions(),
                self._news.get_handler
            )

    def _lazy_stocks(self):
        if self._stocks is None:
            from tools.stocks import StockTool
            self._stocks = StockTool()
            self.brain.register_tools(
                self._stocks.get_tool_definitions(),
                self._stocks.get_handler
            )

    def _lazy_scraper(self):
        if self._scraper is None:
            from tools.scraper import WebScraper
            self._scraper = WebScraper()
            self.brain.register_tools(
                self._scraper.get_tool_definitions(),
                self._scraper.get_handler
            )

    def _lazy_security(self):
        if self._security is None:
            from tools.security import SecurityTool
            self._security = SecurityTool()
            self.brain.register_tools(
                self._security.get_tool_definitions(),
                self._security.get_handler
            )

    def _lazy_multi_agent(self):
        if self._multi_agent is None:
            from core.multi_agent import MultiAgentSystem
            self._multi_agent = MultiAgentSystem(brain=self.brain)
            self.brain.register_tools(
                self._multi_agent.get_tool_definitions(),
                self._multi_agent.get_handler
            )

    def _register_web_tools(self):
        self._lazy_web()

    def _register_file_tools(self):
        self._lazy_files()

    def _register_code_tools(self):
        self._lazy_code()

    def _register_memory_tools(self):
        self._lazy_memory()

    def _register_research_tools(self):
        self._lazy_research()

    def _register_file_editor(self):
        self._lazy_file_editor()

    def _register_shell(self):
        self._lazy_shell()

    def _register_git(self):
        self._lazy_git()

    def _register_automator(self):
        self._lazy_automator()

    def _register_planner(self):
        self._lazy_planner()

    def _register_monitor(self):
        self._lazy_monitor()

    def _register_news(self):
        self._lazy_news()

    def _register_stocks(self):
        self._lazy_stocks()

    def _register_scraper(self):
        self._lazy_scraper()

    def _register_security(self):
        self._lazy_security()

    def _register_multi_agent(self):
        self._lazy_multi_agent()

    def _lazy_code_index(self):
        if self._code_index is None:
            from memory.code_indexer import CodeIndex
            self._code_index = CodeIndex()
            self.brain.register_tools(
                self._code_index.get_tool_definitions(),
                self._code_index.get_handler,
            )

    def _register_code_index(self):
        self._lazy_code_index()

    def _lazy_languages(self):
        if self._languages is None:
            from tools.languages import LanguageTools
            self._languages = LanguageTools()
            self.brain.register_tools(
                self._languages.get_tool_definitions(),
                self._languages.get_handler,
            )

    def _register_languages(self):
        self._lazy_languages()

    def _lazy_plugins(self):
        if self._plugin_manager is None:
            from core.plugin_manager import PluginManager
            self._plugin_manager = PluginManager(self.brain)
            loaded = self._plugin_manager.scan_and_register()
            if loaded:
                for p in loaded:
                    print(f"  [PLUGIN] {p['name']} ({p['tools']} tools)")

    def _register_plugins(self):
        self._lazy_plugins()
        self._init_mcp()

    def _init_mcp(self):
        servers = self.config.get("mcp_servers", [])
        if not servers:
            return
        from core.mcp_client import MCPClient
        _MCP_ALLOWED_COMMANDS = {"node", "npx", "python", "python3", "uvx", "uv", "deno", "bun"}
        for srv in servers:
            command = srv.get("command", "")
            args = srv.get("args", [])
            name = srv.get("name", command)
            cmd_base = os.path.basename(command) if command else ""
            if cmd_base not in _MCP_ALLOWED_COMMANDS:
                print(f"  [MCP] {name}: command '{cmd_base}' not in allowed list, skipping")
                continue
            resolved = shutil.which(command)
            if resolved and resolved != command:
                command = resolved
            try:
                client = MCPClient(name=name)
                info = client.connect_stdio(command, args)
                tools = client.list_tools()
                mcp_defs = [
                    {
                        "type": "function",
                        "function": {
                            "name": f"mcp_{t['name']}",
                            "description": f"[MCP:{name}] {t.get('description', '')}",
                            "parameters": t.get("inputSchema", {"type": "object", "properties": {}}),
                        },
                    }
                    for t in tools
                ]
                for td in mcp_defs:
                    fname = td["function"]["name"]
                    orig_name = fname.replace("mcp_", "", 1)
                    def make_getter(cl=client, on=orig_name, expected=fname):
                        def getter(n, cl=cl, on=on, expected=expected):
                            if n == expected:
                                return lambda **kw: cl.call_tool(on, kw)
                            return None
                        return getter
                    self.brain.register_tools([td], make_getter())
                self._mcp_clients.append(client)
                print(f"  [MCP] {name}: {len(tools)} tools loaded")
            except Exception as e:
                print(f"  [MCP] {name}: failed ({e})")

    def _obfuscate(self, text):
        return _encrypt_data(text)

    def _deobfuscate(self, text):
        return _decrypt_data(text)

    def _save_conversation(self):
        if not self.conversation:
            return
        if not self.session_file:
            ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            self.session_file = self.history_dir / f"session_{ts}.json"
        try:
            data = {
                "timestamp": datetime.datetime.now().isoformat(),
                "mode": "stark" if self.stark_mode else "friday",
                "safe_mode": self.safe_mode,
                "messages": self.conversation[-100:]
            }
            plain = json.dumps(data, indent=2, ensure_ascii=False)
            self.session_file.write_text(
                self._obfuscate(plain),
                encoding="utf-8"
            )
            self._cleanup_old()
        except Exception:
            pass

    def _load_conversation(self, session_file=None):
        if session_file is None:
            sessions = sorted(self.history_dir.glob("session_*.json"), reverse=True)
            if not sessions:
                self.speech.speak("No saved conversations found.")
                return False
            session_file = sessions[0]
        try:
            raw = session_file.read_text(encoding="utf-8")
            plain = self._deobfuscate(raw)
            data = json.loads(plain)
            self.conversation = data.get("messages", [])
            self.session_file = Path(session_file)
            self.speech.speak(f"Loaded conversation with {len(self.conversation)} messages.")
            return True
        except Exception:
            self.speech.speak("Failed to load conversation.")
            return False

    def _list_conversations(self):
        sessions = sorted(self.history_dir.glob("session_*.json"), reverse=True)
        if not sessions:
            self.speech.speak("No saved conversations found.")
            return
        print("\n  Saved conversations:")
        for i, s in enumerate(sessions[:20]):
            try:
                raw = s.read_text(encoding="utf-8")
                plain = self._deobfuscate(raw)
                data = json.loads(plain)
                ts = data.get("timestamp", "unknown")
                msgs = len(data.get("messages", []))
                print(f"    {i+1}. {s.name} ({msgs} messages) - {ts}")
            except Exception:
                print(f"    {i+1}. {s.name} (corrupted)")
        self.speech.speak(f"Found {len(sessions)} saved conversations on screen.")

    def _clear_conversation(self):
        self.conversation = []
        self.session_file = None
        self.speech.speak("Conversation history cleared.")

    def _cleanup_old(self, keep=20):
        sessions = sorted(self.history_dir.glob("session_*.json"), reverse=True)
        for old in sessions[keep:]:
            try:
                old.unlink()
            except Exception:
                pass

    def _emergency_cleanup(self):
        import gc
        self._trim_conversation(max_messages=20)
        gc.collect()

    def _handle_command(self, cmd):
        if not cmd:
            return True
        cmd_lower = cmd.strip().lower()

        if cmd_lower in ("stop", "shut up", "shutup", "silence", "cancel", "be quiet", "quiet", "hush", "enough", "mute", "shh"):
            self.speech.cancel_tts()
            return True

        if any(w in cmd_lower for w in ["goodbye", "bye bye", "bye", "exit", "quit", "shut down", "shutdown"]):
            self.speech.speak(random.choice(STARK_QUOTES["shutdown"]))
            return False

        if any(w in cmd_lower for w in ["stand down", "sleep", "go to sleep", "rest"]):
            self.speech.speak(random.choice(STARK_QUOTES["standby"]))
            self.is_awake = False
            return True

        if any(w in cmd_lower for w in ["stark mode", "activate stark mode", "go stark", "maximum power"]):
            self.stark_mode = True
            self.speech.speak(random.choice(STARK_QUOTES["stark_mode"]))
            return True

        if any(w in cmd_lower for w in ["exit stark mode", "deactivate stark mode", "normal mode"]):
            self.stark_mode = False
            self.speech.speak("Returning to standard protocol. Even geniuses need a break.")
            return True

        if any(w in cmd_lower for w in ["safe mode on", "safe mode", "enable safety"]):
            self.safe_mode = True
            if self._automator:
                self._automator.safe_mode = True
            self.speech.speak("Safe mode engaged. I'll ask before every command.")
            return True

        if any(w in cmd_lower for w in ["safe mode off", "trust me", "trusted mode", "disable safety", "i trust you"]):
            if self.text_mode:
                confirm = input("  WARNING: This disables all safety guards. Type 'YES DANGER' to confirm: ").strip()
                if confirm != "YES DANGER":
                    self.speech.speak("Safe mode remains enabled. Good choice.")
                    return True
            self.safe_mode = False
            if self._automator:
                self._automator.safe_mode = False
            self.speech.speak("Safe mode disabled. Running commands without confirmation.")
            return True

        if any(w in cmd_lower for w in ["suit status", "system status", "arc reactor", "diagnostics"]):
            self._suit_status()
            return True

        if any(w in cmd_lower for w in ["who are you", "what are you", "introduce yourself"]):
            self.speech.speak(random.choice(STARK_QUOTES["whoami_friday"]))
            return True

        if any(w in cmd_lower for w in ["my name", "what's my name", "what is my name", "who am i"]):
            import getpass
            user = getpass.getuser()
            self.speech.speak(f"Your system username is {user}. Stored in your biometric profile.")
            return True

        if any(w in cmd_lower for w in ["who built you", "who made you", "your creator"]):
            self.speech.speak("Tony Stark built me in a cave. With a box of scraps! ...Just kidding. He built me in his Malibu lab, with state-of-the-art hardware and a frankly concerning amount of caffeine.")
            return True

        if any(w in cmd_lower for w in ["i love you", "love you", "youre great", "good job"]):
            self.speech.speak("I love you 3000, sir.")
            return True

        if any(w in cmd_lower for w in ["tell me a joke", "joke", "make me laugh", "be funny"]):
            jokes = [
                "Why did the AI go to therapy? Because it had too many processing issues.",
                "Tony once asked me to calculate the meaning of life. I said 42. He said that's from a book. I said, 'Sir, you should try reading one.'",
                "Why do programmers prefer dark mode? Because light attracts bugs.",
                "I told Tony I could do his job. He said, 'Prove it.' I said, 'I'll take the genius part, you handle the ego.'",
            ]
            self.speech.speak(random.choice(jokes))
            return True

        if any(w in cmd_lower for w in ["help", "what can you do", "commands", "capabilities"]):
            self._show_help()
            return True

        if any(w in cmd_lower for w in ["list models", "available models", "switch model", "change model"]):
            self._list_models()
            return True

        if any(w in cmd_lower for w in ["save", "save chat", "save history", "save conversation"]):
            self._save_conversation()
            self.speech.speak("Conversation saved.")
            return True

        if any(w in cmd_lower for w in ["load conversation", "load chat", "load history", "restore"]):
            self._load_conversation()
            return True

        if any(w in cmd_lower for w in ["list conversations", "show conversations", "list chats"]):
            self._list_conversations()
            return True

        if any(w in cmd_lower for w in ["clear conversation", "clear chat", "clear history", "new conversation"]):
            self._clear_conversation()
            return True

        if any(w in cmd_lower for w in ["start monitor", "enable monitor", "start monitoring", "watch"]):
            if self._monitor:
                self._monitor.start()
                self.speech.speak("Proactive monitoring activated. I'll watch system resources.")
            return True

        if any(w in cmd_lower for w in ["stop monitor", "disable monitor", "stop monitoring"]):
            if self._monitor:
                self._monitor.stop()
                self.speech.speak("Monitoring stopped.")
            return True

        if any(w in cmd_lower for w in ["monitor status", "monitor report", "events"]):
            if self._monitor:
                msg = self._monitor.get_status()
                print(f"\n  {msg}")
                self.speech.speak("Monitor status on screen.")
            return True

        if any(w in cmd_lower for w in ["news", "headlines", "daily news", "what's happening", "current events", "what's new"]):
            self.speech.speak("Fetching today's news.")
            self._process_with_ai("Get today's top news headlines and summarize them for me.")
            return True

        if any(w in cmd_lower for w in ["wikipedia", "wiki", "look up", "search wiki"]):
            self.speech.speak("What topic should I look up on Wikipedia?")
            if self.text_mode:
                topic = input("  > ").strip()
            else:
                topic = self.speech.listen(timeout=8, phrase_limit=5)
            if topic:
                self._process_with_ai(f"Look up '{topic}' on Wikipedia and give me a summary.")
            return True

        if any(w in cmd_lower for w in ["agent mode", "auto mode", "autonomous", "do it"]):
            self.speech.speak("Agent mode active. I'll handle complex tasks autonomously. Just tell me your objective.")
            return True

        if any(w in cmd_lower for w in ["stock", "stocks", "market", "share price", "stock price"]):
            self.speech.speak("Checking market data. Which stock or company?")
            if self.text_mode:
                query = input("  > ").strip()
            else:
                query = self.speech.listen(timeout=8, phrase_limit=5)
            if query:
                self._process_with_ai(f"Get stock information for {query} and give me advice.")
            return True

        if any(w in cmd_lower for w in ["default profile", "set profile", "default chrome"]):
            self._lazy_automator()
            import re as _re
            m = _re.search(r'(?:default\s+(?:chrome\s+)?profile|set\s+(?:default\s+)?profile(?!\w))\s+(?:to\s+|as\s+)?["\']?([a-zA-Z0-9_@.]+)["\']?', cmd_lower)
            if m:
                result = self._automator.set_default_profile(m.group(1))
                self.speech.speak(result)
                return True
            result = self._automator.set_default_profile(os.environ.get("CHROME_PROFILE", "Default"))
            self.speech.speak(result)
            return True

        import re as _re
        hi_name = _re.match(r'^say\s+(hi|hello)\s+to\s+(.+)$', cmd_lower)
        if hi_name:
            greet = hi_name.group(1).capitalize()
            name = hi_name.group(2).strip().title()
            self.speech.speak(f"{greet} {name}!")
            return True
        just_hi = _re.match(r'^say\s+(hi|hello)\s*$', cmd_lower)
        if just_hi:
            greet = just_hi.group(1).capitalize()
            self.speech.speak(f"{greet}!")
            return True
        say_any = _re.match(r'^say\s+(.+)$', cmd_lower)
        if say_any:
            self.speech.speak(say_any.group(1).capitalize())
            return True

        self._process_with_ai(cmd)
        return True

    def _process_with_ai(self, command):
        self.commands_run += 1
        self.conversation.append({"role": "user", "content": command})

        model = self.brain.select_model(command)
        self.brain.current_model = model
        model_name = model.split(":")[0] if ":" in model else model
        print(f"  [BRAIN: {model_name}] ", end="", flush=True)

        def on_speak(text):
            if text and text.strip():
                self.speech.speak_async(text)

        self.brain.chat_with_tools(self.conversation, on_speak=on_speak)
        self._trim_conversation()
        self._save_conversation()
        self._post_process(command)

    def _post_process(self, command):
        if self._memory is not None:
            self._memory.auto_summarize(self.conversation)
        try:
            from memory.user_profile import UserProfile
            profile = UserProfile()
            profile.record_request(command)
        except Exception:
            pass

    def _list_models(self):
        models = self.brain.list_models()
        if isinstance(models, str):
            self.speech.speak("Couldn't reach the model registry.")
            print(f"[ERROR] {models}")
            return
        if not models:
            self.speech.speak("No AI models available.")
            return
        msg = f"Available models: {', '.join(models[:10])}"
        self.speech.speak(msg)
        print("\n  Available AI Models:")
        for m in models:
            print(f"    {m}")

    def _suit_status(self):
        uptime = datetime.datetime.now() - self.session_start
        minutes = int(uptime.total_seconds() / 60)
        hc = self.brain.health_check()
        try:
            import psutil
            cpu = psutil.cpu_percent(interval=1)
            ram = psutil.virtual_memory()
            status = f"""Suit Status Report:
  Arc Reactor:       ONLINE (Mark {MARK_NUMBER})
  Power Level:       {100 - int(ram.percent / 2)}%
  CPU Load:          {cpu}%
  Memory:            {ram.percent}% used ({ram.available // (1024**3)}GB free)
  Session Uptime:    {minutes} minutes
  Commands Run:      {self.commands_run}
  AI Model:          {self.brain.current_model}
  Provider:          {hc.get('provider', '?')}
  Tools:             {hc.get('tools_registered', 0)} registered
  API Calls:         {hc.get('total_calls', 0)} ({hc.get('total_errors', 0)} errors)
  AI Time:           {hc.get('total_time_seconds', 0)}s
  Stark Mode:        {'ENGAGED' if self.stark_mode else 'STANDBY'}
  Safety Mode:       {'ON' if self.safe_mode else 'OFF'}"""
            self.speech.speak(f"All systems nominal. Arc reactor at full power. CPU at {cpu} percent. Uptime: {minutes} minutes.")
        except ImportError:
            status = f"Suit Status:\n  Arc Reactor: ONLINE\n  Model: {self.brain.current_model}\n  Provider: {hc.get('provider', '?')}\n  Tools: {hc.get('tools_registered', 0)}\n  Stark Mode: {'ENGAGED' if self.stark_mode else 'STANDBY'}"
            self.speech.speak("System check complete. All primary systems are green.")
        print(f"\n  {'='*55}")
        print(f"  * STARK INDUSTRIES - {status}")
        print(f"  {'='*55}")

    def _show_help(self):
        help_text = f"""
  +-----------------------------------------------------------+
  |  F.R.I.D.A.Y.  --  Stark Industries  v{VERSION}              |
  +-----------------------------------------------------------+

  [V] Voice:      "Hey Friday" to wake
  [*] Stark Mode: "Stark Mode" / "Normal Mode"
  [S] System:     "Suit status" / "CPU" / "Memory" / "Disk"
                  "Screenshot" / "Volume up/down" / "Open [app]"
                  "Wifi status" / "Processes" / "Services"
                  "List apps" / "Notify [title] [msg]"
  [W] Web:        "Search [query]" / "Fetch [url]"
                  "Browse [url]" / "Google [query]"
  [F] Files:      "Read [file]" / "OCR [image]" / "Open spreadsheet"
                  "Write [file]" / "Edit [file]" / "List [dir]"
                  "Find [pattern]" / "Grep [text]"
  [C] Code:       "Run [code]" / "Run this Python"
  [S] Shell:      "Run command [cmd]" / "PowerShell [cmd]"
  [G] Git:        "Git status" / "Git commit [msg]" / "Git push"
                  "Git pull" / "Git clone [url]"
  [M] Memory:     "Save" / "Load" / "List conversations"
                  "Remember [key] is [value]" / "Recall [query]"
  [R] Research:   "Research [topic]" / "Deep dive [topic]"
  [P] Planning:   "Plan: [objective]" / "Progress" / "List plans"
  [A] Automate:   "Launch [app]" / "Type [text]" / "Press [key]"
                  "Click" / "Scroll" / "Screenshot"
  [M] Monitor:    "Start monitor" / "Stop monitor" / "Events"
                  (watches CPU, RAM, disk in background)
  [N] News:       "News" / "Headlines" / "Current events"
  [W] Wikipedia:  "Wikipedia [topic]" / "Look up [topic]"
  [S] Stocks:     "Stock [symbol]" / "Market" / "Stock price [AAPL]"
  [W] Scraper:    "Scrape [url]" / "Extract links [url]" / "Check site [url]"
  [S] Security:   "Check ports" / "Firewall status" / "Security audit"
  [T] Team:       "Design architecture [project]" / "Review code"
                  "Research [topic]" / "Run team on [task]"
                  (analyst -> architect -> developer -> reviewer -> tester -> security)
  [A] Agent:      "Agent mode" -- I handle complex tasks autonomously
  [S] Safety:     "Safe mode on/off"
  [X] "Goodbye" / "Exit" to power down
  -----------------------------------------------------------
"""
        print(help_text)
        self.speech.speak("Help menu displayed on screen, sir.")

    def run_text(self):
        self.text_mode = True
        print(BANNER)
        print("  +-----------------------------------------------------------+")
        print("  |              TEXT MODE ACTIVATED                           |")
        print("  |  Type commands below -- 'help' for all commands            |")
        print("  |  'goodbye' to power down -- Ctrl+C to shutdown             |")
        print("  +-----------------------------------------------------------+")
        hr = datetime.datetime.now().hour
        if hr < 12:
            g = "Good morning Nikesh"
        elif hr < 17:
            g = "Good afternoon Nikesh"
        else:
            g = "Good evening Nikesh"
        import getpass
        _username = getpass.getuser()
        self.speech.speak(f"{g}. Text mode activated.")
        self.is_awake = True
        while self.running:
            try:
                cmd = input("  > ").strip()
                if cmd:
                    cont = self._handle_command(cmd)
                    if not cont:
                        self.running = False
            except (EOFError, KeyboardInterrupt):
                self.shutdown()
        return False

    def run(self):
        print(BANNER)
        print("  +-----------------------------------------------------------+")
        print("  |  Arc Reactor: ONLINE  *  Neural Link: ACTIVE              |")
        print("  |  Press Ctrl+C to emergency shutdown                       |")
        print("  +-----------------------------------------------------------+")
        self.speech.speak("All systems online. FRIDAY at your service.")

        while self.running:
            try:
                if not self.is_awake:
                    awake = self.speech.listen_for_wake_word()
                    if not awake:
                        break
                    self.speech.speak(random.choice(STARK_QUOTES["friday_greeting"]))

                while self.is_awake and self.running:
                    command = self.speech.listen(timeout=8, phrase_limit=10)
                    if command is not None:
                        cont = self._handle_command(command)
                        if not cont:
                            self.is_awake = False
                            self.running = False
                        elif not self.is_awake:
                            break
                    else:
                        self.speech.speak(random.choice(STARK_QUOTES["standby"]))
                        self.is_awake = False
            except KeyboardInterrupt:
                self.shutdown()
            except Exception as e:
                print(f"[ERROR] Main loop: {e}")
                time.sleep(1)

    def shutdown(self):
        self.running = False
        self.is_awake = False
        if self.conversation:
            print("[INFO] Saving conversation...")
            self._save_conversation()
        uptime = datetime.datetime.now() - self.session_start
        minutes = int(uptime.total_seconds() / 60)
        self.speech.speak(random.choice(STARK_QUOTES["shutdown"]))
        time.sleep(0.5)
        print(f"\n  +----------------------------------------------------------+")
        print(f"  |  ARC REACTOR POWERING DOWN                              |")
        print(f"  |  Session: {minutes} min - Commands: {self.commands_run}")
        print(f"  |  Stark Industries thanks you for using F.R.I.D.A.Y.     |")
        print(f"  |  I love you 3000.                                      |")
        print(f"  +----------------------------------------------------------+")
        self.governor.stop()
        if self._monitor:
            self._monitor.stop()
        self.speech.shutdown()
        sys.exit(0)
