import json
import re

from core.ssrf import validate_url, safe_httpx_get


class WebTools:
    def __init__(self):
        self._ddgs = None
        self._httpx = None
        self._client = None

    @property
    def ddgs(self):
        if self._ddgs is None:
            try:
                from ddgs import DDGS
            except ImportError:
                from duckduckgo_search import DDGS
            self._ddgs = DDGS
        return self._ddgs

    @property
    def httpx(self):
        if self._httpx is None:
            import httpx
            self._httpx = httpx
        return self._httpx

    def _get_client(self):
        if self._client is None:
            self._client = self.httpx.Client(
                follow_redirects=False,
                timeout=30,
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"},
            )
        return self._client

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
                snippet = (body[:150] + "...") if len(body) > 150 else body
                lines.append(f"{i+1}. {title}\n   {href}\n   {snippet}")
            return "Search results:\n" + "\n\n".join(lines)
        except Exception as e:
            return "Search failed"

    def fetch(self, url):
        try:
            url = validate_url(url)
            client = self._get_client()
            response = safe_httpx_get(url, client)
            response.raise_for_status()
            html = response.text

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
        except ValueError as e:
            return f"Blocked: {e}"
        except Exception as e:
            return "Fetch failed"

    def get_tool_definitions(self):
        return [
            {"type": "function", "function": {"name": "web_search", "description": "Search the internet using DuckDuckGo for current information, news, facts, or answers to questions. Use this for any query that needs up-to-date, real-time, or web-based information.", "parameters": {"type": "object", "properties": {"query": {"type": "string", "description": "The search query or question to look up on the web"}, "max_results": {"type": "integer", "description": "Number of search results to return (1-10)", "default": 5}}, "required": ["query"]}}},
            {"type": "function", "function": {"name": "web_fetch", "description": "Fetch and extract readable text content from a URL. Returns the page title and main article text stripped of HTML markup. Use this to read articles, documentation, or any web page content.", "parameters": {"type": "object", "properties": {"url": {"type": "string", "description": "The full URL (including https://) of the web page to fetch"}}, "required": ["url"]}}},
        ]

    def get_handler(self, name):
        handlers = {
            "web_search": self.search,
            "web_fetch": self.fetch,
        }
        return handlers.get(name)
