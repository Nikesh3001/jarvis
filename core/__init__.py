# Lazy imports to avoid circular dependency with tools/__init__.py
# Each core module is imported on first access

__all__ = ["Assistant", "OllamaBrain", "SpeechEngine", "ProactiveMonitor"]


def __getattr__(name):
    if name == "Assistant":
        from core.assistant import Assistant
        return Assistant
    if name == "OllamaBrain":
        from core.brain import OllamaBrain
        return OllamaBrain
    if name == "SpeechEngine":
        from core.speech import SpeechEngine
        return SpeechEngine
    if name == "ProactiveMonitor":
        from core.monitor import ProactiveMonitor
        return ProactiveMonitor
    raise AttributeError(f"module 'core' has no attribute {name!r}")
