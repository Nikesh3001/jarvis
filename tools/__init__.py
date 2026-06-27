# Lazy imports to avoid circular dependency with core.assistant
# Each tool module is imported on first access

__all__ = ["SystemTools", "WebTools", "FileTools", "CodeInterpreter",
           "FileEditor", "ShellCommander", "GitOps", "Automator", "Planner",
           "NewsTool", "StockTool", "WebScraper", "SecurityTool", "LanguageTools",
           "InternetTools"]


def __getattr__(name):
    if name == "SystemTools":
        from tools.system import SystemTools
        return SystemTools
    if name == "WebTools":
        from tools.web import WebTools
        return WebTools
    if name == "FileTools":
        from tools.files import FileTools
        return FileTools
    if name == "CodeInterpreter":
        from tools.code_interpreter import CodeInterpreter
        return CodeInterpreter
    if name == "FileEditor":
        from tools.file_editor import FileEditor
        return FileEditor
    if name == "ShellCommander":
        from tools.shell import ShellCommander
        return ShellCommander
    if name == "GitOps":
        from tools.git_ops import GitOps
        return GitOps
    if name == "Automator":
        from tools.automator import Automator
        return Automator
    if name == "Planner":
        from tools.planner import Planner
        return Planner
    if name == "NewsTool":
        from tools.news import NewsTool
        return NewsTool
    if name == "StockTool":
        from tools.stocks import StockTool
        return StockTool
    if name == "WebScraper":
        from tools.scraper import WebScraper
        return WebScraper
    if name == "SecurityTool":
        from tools.security import SecurityTool
        return SecurityTool
    if name == "LanguageTools":
        from tools.languages import LanguageTools
        return LanguageTools
    if name == "InternetTools":
        from tools.internet import InternetTools
        return InternetTools
    raise AttributeError(f"module 'tools' has no attribute {name!r}")
