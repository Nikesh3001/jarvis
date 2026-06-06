import re
import socket
import ipaddress
from urllib.parse import urlparse


_PRIVATE_IPS = {
    "10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16",
    "127.0.0.0/8", "169.254.0.0/16", "0.0.0.0/32",
    "::1/128", "fc00::/7", "fe80::/10",
}
_CLOUD_METADATA = {"169.254.169.254", "169.254.169.253", "100.100.100.200"}


def _is_ssrf_blocked(hostname):
    if not hostname:
        return True
    try:
        addr = ipaddress.ip_address(hostname)
        if str(addr) in _CLOUD_METADATA:
            return True
        if any(addr in ipaddress.ip_network(n) for n in _PRIVATE_IPS):
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
            if any(addr in ipaddress.ip_network(n) for n in _PRIVATE_IPS):
                return True
        return False
    except OSError:
        return True
    finally:
        socket.setdefaulttimeout(old_timeout)


def _validate_url(url):
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


class WebScraper:
    def __init__(self):
        self._httpx = None
        self._readability = None

    @property
    def httpx(self):
        if self._httpx is None:
            import httpx
            self._httpx = httpx
        return self._httpx

    def _fetch(self, url, **kwargs):
        url = _validate_url(url)
        r = self.httpx.get(url, **kwargs)
        final_url = str(r.url)
        if final_url != url:
            _validate_url(final_url)
        return r

    def scrape_url(self, url, max_chars=8000):
        try:
            url = _validate_url(url)
            r = self._fetch(url, timeout=30, follow_redirects=True,
                           headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"})
            r.raise_for_status()
            html = r.text
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
            url = _validate_url(url)
            r = self._fetch(url, timeout=20, follow_redirects=True,
                           headers={"User-Agent": "Mozilla/5.0"})
            r.raise_for_status()
            html = r.text
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
            url = _validate_url(url)
            r = self._fetch(url, timeout=15, follow_redirects=True)
            return f"{url} — Status: {r.status_code}, Size: {len(r.content)} bytes, Redirects: {len(r.history)}"
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
