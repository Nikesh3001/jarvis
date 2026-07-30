"""Multi-modal vision engine for screenshot analysis and image understanding."""

import os
import base64
import io
import subprocess
import tempfile
import time
import json
from pathlib import Path
from typing import Optional
from core.guardian import PathValidator
from core.platform_utils import is_windows, is_macos, is_linux


class VisionEngine:
    """Image analysis via multiple backends: OCR, multimodal LLM, or local."""

    def __init__(self):
        self._last_screenshot = None

    def capture_and_analyze(self, prompt: str = "Describe what you see in this screenshot in detail.") -> str:
        path = self._capture_screenshot()
        if not path:
            return "Screenshot capture failed"
        return self.analyze_image(path, prompt)

    def analyze_image(self, image_path: str, prompt: str = "Describe this image in detail.") -> str:
        try:
            image_path = PathValidator.safe_resolve(image_path)
        except PermissionError:
            return f"Access denied: {image_path}"
        if not os.path.exists(image_path):
            return f"Image not found: {image_path}"
        ext = Path(image_path).suffix.lower()
        if ext not in (".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp"):
            return f"Unsupported image format: {ext}"

        result = self._try_multimodal(image_path, prompt)
        if result:
            return result
        result = self._try_ocr(image_path)
        if result:
            return f"[OCR Analysis]\n{result}"
        return "No analysis method available"

    def _try_multimodal(self, image_path: str, prompt: str) -> Optional[str]:
        try:
            mime = "image/png" if image_path.endswith(".png") else "image/jpeg"
            with open(image_path, "rb") as f:
                b64 = base64.b64encode(f.read()).decode()

            from core.brain import _get_secret
            key = _get_secret("OPENAI_API_KEY")
            if key:
                from openai import OpenAI
                client = OpenAI(api_key=key)
                resp = client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[{
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}", "detail": "high"}}
                        ]
                    }],
                    max_tokens=1024
                )
                return resp.choices[0].message.content

            key = _get_secret("ANTHROPIC_API_KEY")
            if key:
                import anthropic
                client = anthropic.Anthropic(api_key=key)
                resp = client.messages.create(
                    model="claude-3-5-haiku-latest",
                    max_tokens=1024,
                    messages=[{
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {"type": "image", "source": {"type": "base64", "media_type": mime, "data": b64}}
                        ]
                    }]
                )
                return resp.content[0].text

            key = _get_secret("GEMINI_API_KEY")
            if key:
                import google.generativeai as genai
                genai.configure(api_key=key)
                import PIL.Image
                img = PIL.Image.open(image_path)
                model = genai.GenerativeModel("gemini-2.0-flash")
                resp = model.generate_content([prompt, img])
                return resp.text
        except Exception as e:
            return None
        return None

    def _try_ocr(self, image_path: str) -> Optional[str]:
        try:
            from tools.files import FileTools
            ft = FileTools()
            return ft.ocr_image(image_path)
        except Exception:
            return None

    def _capture_screenshot(self) -> Optional[str]:
        path = os.path.join(tempfile.gettempdir(), f"vision_{int(time.time())}.png")
        try:
            import pyautogui
            pyautogui.screenshot(path)
            self._last_screenshot = path
            return path
        except ImportError:
            pass
        try:
            import mss
            with mss.mss() as sct:
                sct.shot(output=path)
            self._last_screenshot = path
            return path
        except ImportError:
            pass
        try:
            if is_windows():
                r = subprocess.run(["powershell", "-NoProfile", "-Command",
                    f"Add-Type -AssemblyName System.Windows.Forms; $s = [Windows.Forms.Screen]::PrimaryScreen.Bounds; $b = New-Object Drawing.Bitmap $s.Width,$s.Height; $g = [Drawing.Graphics]::FromImage($b); $g.CopyFromScreen(0,0,0,0,$s.Size); $b.Save('{path}'); $g.Dispose(); $b.Dispose()"],
                    capture_output=True, text=True, timeout=30)
                if r.returncode == 0:
                    self._last_screenshot = path
                    return path
            elif is_macos():
                subprocess.run(["screencapture", path], timeout=30)
                self._last_screenshot = path
                return path
            else:
                subprocess.run(["gnome-screenshot", "-f", path], timeout=30)
                self._last_screenshot = path
                return path
        except Exception:
            return None

    def get_screen_text(self) -> str:
        """Capture screenshot and extract all visible text."""
        path = self._capture_screenshot()
        if not path:
            return "Screenshot capture failed"
        text = self._try_ocr(path)
        try:
            os.unlink(path)
        except Exception:
            pass
        return text or "No text detected on screen"

    def analyze_screen(self, context: str = "") -> str:
        """High-level screen analysis - describes what's on screen."""
        path = self._capture_screenshot()
        if not path:
            return "Screenshot capture failed"
        prompt = f"Analyze this screenshot{' in context: ' + context if context else ''}. Describe: 1) What application is visible 2) What content is shown 3) Key UI elements 4) Any important information on screen."
        result = self.analyze_image(path, prompt)
        try:
            os.unlink(path)
        except Exception:
            pass
        return result or "Screen analysis failed"

    def get_tool_definitions(self):
        return [
            {"type": "function", "function": {"name": "analyze_screenshot", "description": "Capture and analyze the current screen with AI vision - describes all visible content, UI elements, and information", "parameters": {"type": "object", "properties": {"context": {"type": "string", "description": "Optional context for what to look for"}}}}},
            {"type": "function", "function": {"name": "analyze_image", "description": "Analyze any image file with AI vision - OCR text, describe contents, identify objects", "parameters": {"type": "object", "properties": {"image_path": {"type": "string", "description": "Path to image file"}, "prompt": {"type": "string", "description": "What to look for/analyze", "default": "Describe this image in detail."}}}}},
            {"type": "function", "function": {"name": "get_screen_text", "description": "Capture screenshot and extract all visible text via OCR", "parameters": {"type": "object", "properties": {}}}},
        ]

    def get_handler(self, name):
        handlers = {
            "analyze_screenshot": lambda context="": self.analyze_screen(context),
            "analyze_image": lambda image_path, prompt="Describe this image in detail.": self.analyze_image(image_path, prompt),
            "get_screen_text": lambda: self.get_screen_text(),
        }
        return handlers.get(name)
