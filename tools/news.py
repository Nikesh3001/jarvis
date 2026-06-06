import json
import re
from datetime import datetime


class NewsTool:
    def __init__(self):
        self._httpx = None

    @property
    def httpx(self):
        if self._httpx is None:
            import httpx
            self._httpx = httpx
        return self._httpx

    def wikipedia_summary(self, topic, sentences=3):
        try:
            url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{__import__('urllib').parse.quote(topic)}"
            r = self.httpx.get(url, timeout=15)
            r.raise_for_status()
            data = r.json()
            title = data.get("title", topic)
            extract = data.get("extract", "No summary available.")
            short = ". ".join(extract.split(". ")[:sentences]) + "." if extract else "No content."
            return f"Wikipedia - {title}:\n{short}"
        except Exception:
            return "Wikipedia lookup failed"

    def wikipedia_search(self, query):
        try:
            url = f"https://en.wikipedia.org/w/api.php?action=opensearch&search={__import__('urllib').parse.quote(query)}&limit=5&format=json"
            r = self.httpx.get(url, timeout=15)
            r.raise_for_status()
            data = r.json()
            if len(data) < 2 or not data[1]:
                return f"No Wikipedia results for '{query}'."
            results = []
            for i, title in enumerate(data[1]):
                desc = data[2][i] if len(data) > 2 and i < len(data[2]) else ""
                url_result = data[3][i] if len(data) > 3 and i < len(data[3]) else ""
                results.append(f"{i+1}. {title} — {desc[:200]} ({url_result})")
            return "Wikipedia results:\n" + "\n".join(results)
        except Exception:
            return "Wikipedia search failed"

    def get_daily_news(self, category="top", region="US"):
        regions = {
            "IN": {"gl": "IN", "hl": "en-IN", "ceid": "IN:en"},
            "US": {"gl": "US", "hl": "en-US", "ceid": "US:en"},
            "GB": {"gl": "GB", "hl": "en-GB", "ceid": "GB:en"},
            "CA": {"gl": "CA", "hl": "en-CA", "ceid": "CA:en"},
            "AU": {"gl": "AU", "hl": "en-AU", "ceid": "AU:en"},
        }
        rcfg = regions.get(region.upper(), regions["US"])
        try:
            categories = {
                "top": f"https://news.google.com/rss?hl={rcfg['hl']}&gl={rcfg['gl']}&ceid={rcfg['ceid']}",
                "world": f"https://news.google.com/rss/topics/CAAqJggKIiBDQkFTRWdvSUwyMHZNRGx1YlY4U0FtVnVHZ0pWVXlnQVAB?hl={rcfg['hl']}&gl={rcfg['gl']}&ceid={rcfg['ceid']}",
                "tech": f"https://news.google.com/rss/topics/CAAqJggKIiBDQkFTRWdvSUwyMHZNRFp1ZEdvU0FtVnVHZ0pWVXlnQVAB?hl={rcfg['hl']}&gl={rcfg['gl']}&ceid={rcfg['ceid']}",
                "science": f"https://news.google.com/rss/topics/CAAqJggKIiBDQkFTRWdvSUwyMHZNRFp0Y1RjU0FtVnVHZ0pWVXlnQVAB?hl={rcfg['hl']}&gl={rcfg['gl']}&ceid={rcfg['ceid']}",
            }
            url = categories.get(category, categories["top"])
            r = self.httpx.get(url, timeout=20)
            r.raise_for_status()
            items = re.findall(r'<item>(.*?)</item>', r.text, re.DOTALL)
            if not items:
                return "No news items found."
            headlines = []
            for item in items[:8]:
                title_match = re.search(r'<title>(.*?)</title>', item)
                title = title_match.group(1) if title_match else "Untitled"
                title = re.sub(r'<!\[CDATA\[(.*?)\]\]>', r'\1', title)
                headlines.append(f"  {len(headlines)+1}. {title}")
            date_str = datetime.now().strftime("%B %d, %Y")
            return f"Daily News — {date_str} ({category}):\n" + "\n".join(headlines)
        except Exception as e:
            try:
                rcfg = regions.get(region.upper(), regions["US"])
                alt = self.httpx.get(f"https://news.google.com/rss?hl={rcfg['hl']}&gl={rcfg['gl']}&ceid={rcfg['ceid']}", timeout=15)
                alt.raise_for_status()
                items = re.findall(r'<item>(.*?)</item>', alt.text, re.DOTALL)
                headlines = []
                for item in items[:6]:
                    title_match = re.search(r'<title>(.*?)</title>', item)
                    title = title_match.group(1) if title_match else "Untitled"
                    title = re.sub(r'<!\[CDATA\[(.*?)\]\]>', r'\1', title)
                    headlines.append(f"  {len(headlines)+1}. {title}")
                return "Today's headlines:\n" + "\n".join(headlines)
            except Exception:
                return "News unavailable"

    def get_current_events(self):
        try:
            r = self.httpx.get("https://en.wikipedia.org/api/rest_v1/feed/onthisday/events/" + datetime.now().strftime("%m/%d"), timeout=15)
            r.raise_for_status()
            data = r.json()
            events = data.get("events", [])[:5]
            if not events:
                return "No events found for today."
            lines = []
            for ev in events:
                year = ev.get("year", "?")
                text = ev.get("text", "")
                lines.append(f"  {year}: {text[:200]}")
            return "On this day in history:\n" + "\n".join(lines)
        except Exception:
            try:
                r = self.httpx.get("https://en.wikipedia.org/api/rest_v1/page/summary/Portal:Current_events", timeout=15)
                r.raise_for_status()
                data = r.json()
                extract = data.get("extract", "")
                if extract:
                    paras = extract.split("\n")
                    relevant = [p for p in paras if len(p) > 50][:5]
                    return "Current events:\n" + "\n".join(f"  {p[:300]}" for p in relevant)
                return "Current events info unavailable."
            except Exception:
                return "Current events unavailable"

    def get_tool_definitions(self):
        return [
            {"type": "function", "function": {"name": "wikipedia_summary", "description": "Wikipedia summary of topic", "parameters": {"type": "object", "properties": {"topic": {"type": "string", "description": "Topic"}, "sentences": {"type": "integer", "description": "Count", "default": 3}}, "required": ["topic"]}}},
            {"type": "function", "function": {"name": "wikipedia_search", "description": "Search Wikipedia", "parameters": {"type": "object", "properties": {"query": {"type": "string", "description": "Query"}}, "required": ["query"]}}},
            {"type": "function", "function": {"name": "get_daily_news", "description": "Daily news headlines by category and region (top/world/tech/science, region: IN/US/GB/CA/AU)", "parameters": {"type": "object", "properties": {"category": {"type": "string", "description": "top/world/tech/science", "default": "top"}, "region": {"type": "string", "description": "Country code: IN/US/GB/CA/AU", "default": "US"}}}}},
            {"type": "function", "function": {"name": "get_current_events", "description": "On this day in history", "parameters": {"type": "object", "properties": {}}}},
        ]

    def get_handler(self, name):
        handlers = {
            "wikipedia_summary": self.wikipedia_summary,
            "wikipedia_search": self.wikipedia_search,
            "get_daily_news": self.get_daily_news,
            "get_current_events": self.get_current_events,
        }
        return handlers.get(name)
