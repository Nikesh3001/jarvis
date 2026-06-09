import re
from urllib.parse import urlparse, urljoin

from core.ssrf import validate_url, safe_httpx_get


class WebScraper:
    def __init__(self):
        self._httpx = None
        self._client = None

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

    def _fetch(self, url, **kwargs):
        url = validate_url(url)
        client = self._get_client()
        kwargs.pop("follow_redirects", None)
        return safe_httpx_get(url, client, **kwargs)

    def scrape_url(self, url, max_chars=8000):
        try:
            url = validate_url(url)
            client = self._get_client()
            response = safe_httpx_get(url, client, timeout=30)
            response.raise_for_status()
            html = response.text
            title_m = re.search(r'<title[^>]*>(.*?)</title>', html, re.IGNORECASE | re.DOTALL)
            title = title_m.group(1).strip() if title_m else url
            text = self._extract_readable(html)
            if len(text) < 50:
                text = self._extract_fallback(html)
            text = text[:max_chars]
            return f"Source: {url}\nTitle: {title}\n\n{text}"
        except ValueError as e:
            return f"Scrape error: {e}"
        except Exception:
            return "Scrape error"

    def _extract_readable(self, html):
        try:
            from readability import Document
            doc = Document(html)
            content = doc.summary()
            from html.parser import HTMLParser
            class Stripper(HTMLParser):
                def __init__(self):
                    super().__init__()
                    self.text = []
                def handle_data(self, d):
                    self.text.append(d)
            s = Stripper()
            s.feed(content)
            text = "".join(s.text)
            text = re.sub(r'\s+', ' ', text).strip()
            return text
        except ImportError:
            return self._extract_fallback(html)
        except Exception:
            return self._extract_fallback(html)

    def _extract_fallback(self, html):
        for tag in ['script', 'style', 'nav', 'footer', 'header', 'noscript']:
            html = re.sub(f'<{tag}[^>]*>.*?</{tag}>', '', html, flags=re.IGNORECASE | re.DOTALL)
        text = re.sub(r'<[^>]+>', ' ', html)
        text = re.sub(r'&[a-z]+;', ' ', text)
        text = re.sub(r'\s+', ' ', text).strip()
        lines = []
        for line in text.split('. '):
            line = line.strip()
            if len(line) > 40:
                lines.append(line)
        return ". ".join(lines[:50])

    def extract_links(self, url, max_links=20):
        try:
            url = validate_url(url)
            client = self._get_client()
            response = safe_httpx_get(url, client, timeout=20)
            response.raise_for_status()
            html = response.text
            links = re.findall(r'href="(https?://[^"]+)"', html)
            seen = set()
            unique = []
            for link in links:
                if link not in seen:
                    seen.add(link)
                    unique.append(link)
            parsed = urlparse(url)
            internal = [l for l in unique if parsed.netloc in l]
            external = [l for l in unique if parsed.netloc not in l]
            result = f"Links from {url}:\n"
            result += f"\nInternal ({len(internal)} found):\n"
            for l in internal[:max_links // 2]:
                result += f"  {l[:150]}\n"
            result += f"\nExternal ({len(external)} found):\n"
            for l in external[:max_links // 2]:
                result += f"  {l[:150]}\n"
            return result.strip()
        except ValueError as e:
            return f"Link extraction error: {e}"
        except Exception:
            return "Link extraction error"

    def check_site_status(self, url):
        try:
            url = validate_url(url)
            client = self._get_client()
            response = safe_httpx_get(url, client, timeout=15)
            return f"{url} — Status: {response.status_code}, Size: {len(response.content)} bytes, Redirects: {len(response.history)}"
        except ValueError as e:
            return f"Status check error: {e}"
        except Exception:
            return "Status check error"

    def get_tool_definitions(self):
        return [
            {"type": "function", "function": {"name": "scrape_url", "description": "Readable text from any URL", "parameters": {"type": "object", "properties": {"url": {"type": "string", "description": "URL"}, "max_chars": {"type": "integer", "description": "Max chars", "default": 8000}}, "required": ["url"]}}},
            {"type": "function", "function": {"name": "extract_links", "description": "Links from a webpage", "parameters": {"type": "object", "properties": {"url": {"type": "string", "description": "URL"}, "max_links": {"type": "integer", "description": "Max", "default": 20}}, "required": ["url"]}}},
            {"type": "function", "function": {"name": "check_site_status", "description": "HTTP status + redirects", "parameters": {"type": "object", "properties": {"url": {"type": "string", "description": "URL"}}, "required": ["url"]}}},
        ]

    def get_handler(self, name):
        handlers = {
            "scrape_url": self.scrape_url,
            "extract_links": self.extract_links,
            "check_site_status": self.check_site_status,
        }
        return handlers.get(name)
