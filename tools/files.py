import os
from pathlib import Path


ALLOWED_ROOTS = [
    os.path.realpath(os.path.expanduser("~")),
]


def _safe_resolve(path):
    path = os.path.expanduser(path)
    path = os.path.abspath(path)
    try:
        resolved = os.path.realpath(path)
    except OSError:
        resolved = path
    for root in ALLOWED_ROOTS:
        if resolved == root or os.path.commonpath([resolved, root]) == root:
            return resolved
    raise PermissionError("Access denied: path is outside allowed directories")


class FileTools:
    def __init__(self):
        self._fitz = None
        self._pillow = None
        self._pytesseract = None
        self._pandas = None
        self._docx = None

    @property
    def fitz(self):
        if self._fitz is None:
            import fitz
            self._fitz = fitz
        return self._fitz

    @property
    def pillow(self):
        if self._pillow is None:
            from PIL import Image
            self._pillow = Image
        return self._pillow

    @property
    def pytesseract(self):
        if self._pytesseract is None:
            import pytesseract
            self._pytesseract = pytesseract
        return self._pytesseract

    @property
    def pandas(self):
        if self._pandas is None:
            import pandas as pd
            self._pandas = pd
        return self._pandas

    @property
    def docx(self):
        if self._docx is None:
            import docx
            self._docx = docx
        return self._docx

    def read_file(self, path):
        try:
            path = _safe_resolve(path)
        except PermissionError as e:
            return str(e)
        if not os.path.exists(path):
            return f"File not found: {path}"
        ext = Path(path).suffix.lower()

        try:
            if ext == ".pdf":
                return self._read_pdf(path)
            elif ext in (".docx", ".doc"):
                return self._read_docx(path)
            elif ext in (".txt", ".md", ".py", ".js", ".ts", ".html", ".css", ".json", ".xml", ".yaml", ".yml", ".ini", ".cfg", ".log", ".csv"):
                with open(path, "r", encoding="utf-8", errors="replace") as f:
                    content = f.read(10000)
                return f"File {Path(path).name}:\n\n{content}"
            elif ext in (".png", ".jpg", ".jpeg", ".gif", ".bmp", ".tiff", ".webp"):
                return self.ocr_image(path)
            elif ext in (".xlsx", ".xls", ".ods"):
                return self.read_spreadsheet(path)
            else:
                return f"Unsupported file type: {ext}"
        except PermissionError:
            return "Access denied: permission error reading file"
        except Exception:
            return "Error reading file"

    def _read_pdf(self, path):
        doc = self.fitz.open(path)
        pages = []
        for i, page in enumerate(doc):
            text = page.get_text()
            if text.strip():
                pages.append(f"--- Page {i+1} ---\n{text}")
            if i >= 20:
                pages.append(f"... ({len(doc) - 20} more pages)")
                break
        doc.close()
        return "\n".join(pages)[:10000]

    def _read_docx(self, path):
        doc = self.docx.Document(path)
        paras = [p.text for p in doc.paragraphs if p.text.strip()]
        return "\n".join(paras)[:10000]

    def ocr_image(self, path):
        try:
            path = _safe_resolve(path)
            img = self.pillow.open(path)
            text = self.pytesseract.image_to_string(img)
            text = text.strip()
            if not text:
                return "No text detected in the image."
            return f"OCR from {Path(path).name}:\n\n{text[:5000]}"
        except PermissionError as e:
            return str(e)
        except Exception:
            return "OCR error"

    def read_spreadsheet(self, path):
        try:
            path = _safe_resolve(path)
            ext = Path(path).suffix.lower()
            if ext == ".csv":
                df = self.pandas.read_csv(path)
            else:
                df = self.pandas.read_excel(path)
            info = f"Shape: {df.shape[0]} rows x {df.shape[1]} columns\n"
            info += f"Columns: {', '.join(str(c) for c in df.columns)}\n\n"
            info += df.head(50).to_string()
            return info[:8000]
        except PermissionError as e:
            return str(e)
        except Exception:
            return "Spreadsheet error"

    def get_tool_definitions(self):
        return [
            {"type": "function", "function": {"name": "read_file", "description": "Read PDF/DOCX/TXT/code/image/spreadsheet", "parameters": {"type": "object", "properties": {"path": {"type": "string", "description": "Path"}}, "required": ["path"]}}},
            {"type": "function", "function": {"name": "ocr_image", "description": "OCR text from image", "parameters": {"type": "object", "properties": {"path": {"type": "string", "description": "Image path"}}, "required": ["path"]}}},
            {"type": "function", "function": {"name": "read_spreadsheet", "description": "Read CSV/Excel", "parameters": {"type": "object", "properties": {"path": {"type": "string", "description": "Path"}}, "required": ["path"]}}},
        ]

    def get_handler(self, name):
        handlers = {
            "read_file": self.read_file,
            "ocr_image": self.ocr_image,
            "read_spreadsheet": self.read_spreadsheet,
        }
        return handlers.get(name)