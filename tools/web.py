import json
import re
import socket
import ipaddress
from urllib.parse import urlparse

_PRIVATE_NETWORKS = [
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("169.254.0.0/16"),
    ipaddress.ip_network("0.0.0.0/32"),
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fc00::/7"),
    ipaddress.ip_network("fe80::/10"),
]

_CLOUD_METADATA = {"169.254.169.254", "169.254.169.253", "100.100.100.200"}


def _is_ssrf_blocked(hostname):
    if not hostname:
        return True
    try:
        addr = ipaddress.ip_address(hostname)
        if str(addr) in _CLOUD_METADATA:
            return True
        if any(addr in net for net in _PRIVATE_NETWORKS):
            return True
        return False
    except ValueError:
        pass
    old_timeout = socket.getdefaulttimeout()
    socket.setdefaulttimeout(5)
    try:
        for _, _, _, _, sockaddr in socket.getaddrinfo(hostname, 80):
            ip = sockaddr[0]
            addr = ipaddress.ip_address(ip)
            if str(addr) in _CLOUD_METADATA:
                return True
            if any(addr in net for net in _PRIVATE_NETWORKS):
                return True
        return False
    except OSError:
        return True
    finally:
        socket.setdefaulttimeout(old_timeout)


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

    def _validate_url(self, url):
        if not url.startswith(("http://", "https://")):
            if "." not in url:
                raise ValueError("Invalid URL")
            url = "https://" + url
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https"):
            raise ValueError("Only HTTP/HTTPS URLs are allowed")
        if _is_ssrf_blocked(parsed.hostname):
            raise ValueError("Access to internal or private network addresses is not allowed")
        return url

    def fetch(self, url):
        try:
            url = self._validate_url(url)
            r = self.httpx.get(url, timeout=30, follow_redirects=True,
                               headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"})
            final_url = str(r.url)
            if final_url != url:
                self._validate_url(final_url)
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
        except ValueError as e:
            return f"Blocked: {e}"
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
