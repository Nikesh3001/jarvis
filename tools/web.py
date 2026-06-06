import json
import re
import socket
from urllib.parse import urlparse


class WebTools:
    def __init__(self):
        self._ddgs = None
        self._httpx = None
        self._readability = None

    @property
    def ddgs(self):
        if self._ddgs is None:
            from duckduckgo_search import DDGS
            self._ddgs = DDGS
        return self._ddgs

    @property
    def httpx(self):
        if self._httpx is None:
            import httpx
            self._httpx = httpx
        return self._httpx

    def search(self, query, max_results=5):
        try:
            results = list(self.ddgs().text(query, max_results=max_results))
            if not results:
                return "No search results found."
            lines = []
            for i, r in enumerate(results):
                href = r.get("href", "")
                title = r.get("title", "")
                body = r.get("body", "")
                lines.append(f"{i+1}. {title} - {href}")
            return "Search results:\n" + "\n".join(lines)
        except Exception as e:
            return "Search failed"

    def _is_private_url(self, url):
        host = urlparse(url).hostname
        if not host:
            return True
        try:
            ip = socket.gethostbyname(host)
            private_ranges = ['127.', '10.', '172.16.', '172.17.', '172.18.', '172.19.',
                              '172.20.', '172.21.', '172.22.', '172.23.', '172.24.',
                              '172.25.', '172.26.', '172.27.', '172.28.', '172.29.',
                              '172.30.', '172.31.', '192.168.', '169.254.']
            for prefix in private_ranges:
                if ip.startswith(prefix):
                    return True
            if ip == '0.0.0.0' or ip == '::1':
                return True
        except Exception:
            pass
        if host in ('localhost', '127.0.0.1', '::1', '0.0.0.0'):
            return True
        return False

    def fetch(self, url):
        try:
            if not url.startswith(('http://', 'https://')):
                url = 'https://' + url
            if self._is_private_url(url):
                return f"Blocked: cannot fetch internal/private URL ({url})"
            r = self.httpx.get(url, timeout=30, follow_redirects=True)
            r.raise_for_status()
            html = r.text

            try:
                from readability import Document
                doc = Document(html)
                text = doc.summary()
                from html.parser import HTMLParser
                class MLStripper(HTMLParser):
                    def __init__(self):
                        super().__init__()
                        self.reset()
                        self.strict = False
                        self.convert_charrefs = True
                        self.text = []
                    def handle_data(self, d):
                        self.text.append(d)
                s = MLStripper()
                s.feed(text)
                clean = ''.join(s.text).strip()
            except ImportError:
                clean = re.sub(r'<[^>]+>', '', html)
                clean = re.sub(r'\s+', ' ', clean).strip()

            clean = clean[:8000]
            return f"Content from {url}:\n\n{clean}"
        except Exception as e:
            return "Fetch failed"

    def get_tool_definitions(self):
        return [
            {"type": "function", "function": {"name": "web_search", "description": "Search web for query", "parameters": {"type": "object", "properties": {"query": {"type": "string", "description": "Search"}, "max_results": {"type": "integer", "description": "Count", "default": 5}}, "required": ["query"]}}},
            {"type": "function", "function": {"name": "web_fetch", "description": "Fetch URL content", "parameters": {"type": "object", "properties": {"url": {"type": "string", "description": "URL"}}, "required": ["url"]}}},
        ]

    def get_handler(self, name):
        handlers = {
            "web_search": self.search,
            "web_fetch": self.fetch,
        }
        return handlers.get(name)
