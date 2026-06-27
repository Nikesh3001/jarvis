"""
Internet access tools inspired by Agent-Reach.
Provides YouTube transcripts, GitHub info, RSS feeds, Jina Reader web reading,
and semantic search capabilities — all free, no API keys required.

Upstream tools (called via subprocess):
  - yt-dlp: YouTube subtitle extraction + video search
  - gh CLI: GitHub repo viewing, search, issues
  - feedparser: RSS/Atom feed parsing (Python library)
  - Jina Reader: Clean web page reading (free, no key)

Install prerequisites:
  pip install yt-dlp feedparser
  gh CLI: https://cli.github.com/
"""

import json
import os
import re
import shutil
import subprocess
import tempfile
from urllib.parse import quote, urlparse

from core.ssrf import validate_url, safe_httpx_get


class InternetTools:
    """Tools for deep internet access — YouTube, GitHub, RSS, Jina Reader, semantic search."""

    def __init__(self):
        self._httpx = None
        self._client = None
        self._feedparser = None
        self._yt_dlp_available = None
        self._gh_available = None

    # ── Lazy imports ──────────────────────────────────────────────────

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

    def __del__(self):
        """Close HTTP client on garbage collection."""
        try:
            if self._client is not None:
                self._client.close()
        except Exception:
            pass

    @property
    def feedparser(self):
        if self._feedparser is None:
            import feedparser
            self._feedparser = feedparser
        return self._feedparser

    def _check_yt_dlp(self):
        if self._yt_dlp_available is None:
            self._yt_dlp_available = shutil.which("yt-dlp") is not None
        return self._yt_dlp_available

    def _check_gh(self):
        if self._gh_available is None:
            self._gh_available = shutil.which("gh") is not None
        return self._gh_available

    def _run_cmd(self, cmd, timeout=30):
        """Run a shell command and return (stdout, stderr, returncode)."""
        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=timeout,
                shell=isinstance(cmd, str)
            )
            return result.stdout.strip(), result.stderr.strip(), result.returncode
        except FileNotFoundError:
            return "", "Command not found", 1
        except subprocess.TimeoutExpired:
            return "", "Command timed out", 1
        except Exception as e:
            return "", str(e), 1

    # ── YouTube ───────────────────────────────────────────────────────

    def youtube_transcript(self, url, lang="en"):
        """Extract subtitles/transcript from a YouTube video using yt-dlp."""
        if not self._check_yt_dlp():
            return "yt-dlp not installed. Install: pip install yt-dlp"

        try:
            url = validate_url(url)
        except ValueError as e:
            return f"Invalid URL: {e}"

        try:
            # First get video info
            stdout, stderr, rc = self._run_cmd(
                ["yt-dlp", "--dump-json", "--no-download", url],
                timeout=30
            )
            if rc != 0:
                return f"Failed to get video info: {stderr[:200]}"

            info = json.loads(stdout)
            title = info.get("title", "Unknown")
            channel = info.get("channel", info.get("uploader", "Unknown"))
            duration = info.get("duration", 0)
            description = info.get("description", "")[:500]
            view_count = info.get("view_count", 0)
            upload_date = info.get("upload_date", "Unknown")

            # Try to get subtitles
            subtitle_text = ""
            with tempfile.TemporaryDirectory() as tmpdir:
                sub_cmd = [
                    "yt-dlp",
                    "--write-sub", "--write-auto-sub",
                    "--sub-lang", lang,
                    "--sub-format", "vtt",
                    "--skip-download",
                    "-o", os.path.join(tmpdir, "sub"),
                    url
                ]
                _, _, sub_rc = self._run_cmd(sub_cmd, timeout=30)

                # Find subtitle file
                for f in os.listdir(tmpdir) if os.path.exists(tmpdir) else []:
                    if f.endswith(".vtt"):
                        vtt_path = os.path.join(tmpdir, f)
                        with open(vtt_path, "r", encoding="utf-8", errors="ignore") as vf:
                            raw = vf.read()
                        # Clean VTT timestamps
                        lines = []
                        for line in raw.split("\n"):
                            line = line.strip()
                            if not line:
                                continue
                            if re.match(r"^\d{2}:\d{2}", line):
                                continue
                            if line.startswith("WEBVTT"):
                                continue
                            if "-->" in line:
                                continue
                            if re.match(r"^\d+$", line):
                                continue
                            lines.append(line)
                        seen = set()
                        deduped = []
                        for l in lines:
                            if l not in seen:
                                seen.add(l)
                                deduped.append(l)
                        subtitle_text = " ".join(deduped)
                        break

            result_parts = [
                f"📺 YouTube Video: {title}",
                f"   Channel: {channel}",
                f"   Duration: {duration // 60}m {duration % 60}s",
                f"   Views: {view_count:,}",
                f"   Uploaded: {upload_date}",
                f"   URL: {url}",
                "",
                f"📝 Description:\n{description}",
            ]
            if subtitle_text:
                # Limit transcript length
                if len(subtitle_text) > 6000:
                    subtitle_text = subtitle_text[:6000] + "...[truncated]"
                result_parts.extend(["", f"📜 Transcript ({lang}):\n{subtitle_text}"])
            else:
                result_parts.extend(["", f"No subtitles found for language '{lang}'. Try: en, es, fr, zh, ja, ko"])

            return "\n".join(result_parts)
        except Exception as e:
            return f"YouTube transcript error: {e}"

    def youtube_search(self, query, max_results=5):
        """Search YouTube for videos using yt-dlp."""
        if not self._check_yt_dlp():
            return "yt-dlp not installed. Install: pip install yt-dlp"

        try:
            search_url = f"ytsearch{max_results}:{query}"
            stdout, stderr, rc = self._run_cmd(
                ["yt-dlp", "--dump-json", "--no-download", "--flat-playlist", search_url],
                timeout=30
            )
            if rc != 0:
                return f"YouTube search failed: {stderr[:200]}"

            results = []
            for line in stdout.split("\n"):
                if not line.strip():
                    continue
                try:
                    info = json.loads(line)
                    title = info.get("title", "Unknown")
                    vid = info.get("id", "")
                    channel = info.get("channel", info.get("uploader", "Unknown"))
                    duration = info.get("duration", 0)
                    dur_str = f"{duration // 60}m{duration % 60}s" if duration else "N/A"
                    results.append(f"  • {title}\n    Channel: {channel} | Duration: {dur_str}\n    https://youtube.com/watch?v={vid}")
                except json.JSONDecodeError:
                    continue

            if not results:
                return "No YouTube results found."
            return f"🔍 YouTube search: \"{query}\"\n\n" + "\n\n".join(results)
        except Exception as e:
            return f"YouTube search error: {e}"

    # ── GitHub ────────────────────────────────────────────────────────

    def github_repo_info(self, repo):
        """Get information about a GitHub repository using gh CLI."""
        if not self._check_gh():
            return "gh CLI not installed. Install: https://cli.github.com/"

        # Normalize repo format
        if repo.startswith("https://github.com/"):
            repo = repo.replace("https://github.com/", "").rstrip("/").rstrip(".git")
        elif repo.startswith("http://github.com/"):
            repo = repo.replace("http://github.com/", "").rstrip("/").rstrip(".git")
        elif repo.startswith("github.com/"):
            repo = repo.replace("github.com/", "").rstrip("/").rstrip(".git")

        stdout, stderr, rc = self._run_cmd(
            ["gh", "repo", "view", repo, "--json",
             "name,description,url,homepageUrl,stargazerCount,forkCount,licenseInfo,"
             "primaryLanguage,createdAt,updatedAt,pushedAt,defaultBranchRef,"
             "isArchived,isFork,repositoryTopics"],
            timeout=15
        )
        if rc != 0:
            return f"Failed to get repo info: {stderr[:200]}"

        try:
            data = json.loads(stdout)
        except json.JSONDecodeError:
            return f"Failed to parse repo data"

        parts = [
            f"📦 GitHub: {data.get('name', repo)}",
            f"   URL: {data.get('url', '')}",
            f"   Description: {data.get('description', 'N/A')}",
            f"   ⭐ Stars: {data.get('stargazerCount', 0):,}",
            f"   🍴 Forks: {data.get('forkCount', 0):,}",
        ]

        lang = data.get("primaryLanguage", {})
        if lang:
            parts.append(f"   Language: {lang.get('name', 'N/A')}")

        license_info = data.get("licenseInfo", {})
        if license_info:
            parts.append(f"   License: {license_info.get('name', 'N/A')}")

        topics = data.get("repositoryTopics", [])
        if topics:
            topic_names = [t.get("topic", {}).get("name", "") for t in topics]
            parts.append(f"   Topics: {', '.join(topic_names[:10])}")

        parts.append(f"   Created: {data.get('createdAt', 'N/A')[:10]}")
        parts.append(f"   Last push: {data.get('pushedAt', 'N/A')[:10]}")

        if data.get("isArchived"):
            parts.append("   ⚠️ This repo is ARCHIVED")
        if data.get("isFork"):
            parts.append("   🍴 This is a FORK")

        return "\n".join(parts)

    def github_search(self, query, max_results=5):
        """Search GitHub repositories using gh CLI."""
        if not self._check_gh():
            return "gh CLI not installed. Install: https://cli.github.com/"

        stdout, stderr, rc = self._run_cmd(
            ["gh", "search", "repos", query, "--limit", str(max_results),
             "--json", "nameWithOwner,description,stargazerCount,primaryLanguage,url"],
            timeout=15
        )
        if rc != 0:
            return f"GitHub search failed: {stderr[:200]}"

        try:
            repos = json.loads(stdout)
        except json.JSONDecodeError:
            return "Failed to parse search results"

        if not repos:
            return "No GitHub results found."

        lines = [f"🔍 GitHub search: \"{query}\"\n"]
        for r in repos:
            name = r.get("nameWithOwner", "")
            desc = (r.get("description") or "N/A")[:80]
            stars = r.get("stargazerCount", 0)
            lang = (r.get("primaryLanguage") or {}).get("name", "N/A")
            url = r.get("url", "")
            lines.append(f"  • {name} ⭐ {stars:,}")
            lines.append(f"    {desc}")
            lines.append(f"    Language: {lang} | {url}")
            lines.append("")

        return "\n".join(lines)

    def github_issues(self, repo, state="open", max_results=5):
        """List issues for a GitHub repository."""
        if not self._check_gh():
            return "gh CLI not installed. Install: https://cli.github.com/"

        if repo.startswith("https://github.com/"):
            repo = repo.replace("https://github.com/", "").rstrip("/").rstrip(".git")
        elif repo.startswith("github.com/"):
            repo = repo.replace("github.com/", "").rstrip("/").rstrip(".git")

        stdout, stderr, rc = self._run_cmd(
            ["gh", "issue", "list", "--repo", repo, "--state", state,
             "--limit", str(max_results), "--json", "number,title,state,createdAt,labels"],
            timeout=15
        )
        if rc != 0:
            return f"Failed to list issues: {stderr[:200]}"

        try:
            issues = json.loads(stdout)
        except json.JSONDecodeError:
            return "Failed to parse issues"

        if not issues:
            return f"No {state} issues found in {repo}."

        lines = [f"📋 Issues in {repo} ({state}):\n"]
        for issue in issues:
            num = issue.get("number", "?")
            title = issue.get("title", "N/A")
            labels = [l.get("name", "") for l in issue.get("labels", [])]
            label_str = f" [{', '.join(labels)}]" if labels else ""
            created = issue.get("createdAt", "")[:10]
            lines.append(f"  #{num} {title}{label_str}")
            lines.append(f"      Created: {created}")
            lines.append("")

        return "\n".join(lines)

    # ── RSS Feeds ─────────────────────────────────────────────────────

    def rss_read(self, url, max_entries=10):
        """Read and parse an RSS/Atom feed."""
        try:
            url = validate_url(url)
        except ValueError as e:
            return f"Invalid URL: {e}"

        try:
            client = self._get_client()
            response = safe_httpx_get(url, client, timeout=15)
            response.raise_for_status()
            feed = self.feedparser.parse(response.text)

            if feed.bozo and not feed.entries:
                return f"Failed to parse feed: {feed.bozo_exception}"

            feed_title = feed.feed.get("title", "Unknown Feed")
            feed_link = feed.feed.get("link", "")
            feed_desc = feed.feed.get("description", "")[:200]

            parts = [
                f"📡 RSS Feed: {feed_title}",
                f"   Link: {feed_link}",
            ]
            if feed_desc:
                parts.append(f"   Description: {feed_desc}")
            parts.append(f"   Entries: {len(feed.entries)}\n")

            for entry in feed.entries[:max_entries]:
                title = entry.get("title", "No title")
                link = entry.get("link", "")
                published = entry.get("published", entry.get("updated", ""))[:16]
                summary = entry.get("summary", "")[:200]
                # Strip HTML from summary
                summary = re.sub(r'<[^>]+>', '', summary).strip()
                parts.append(f"  • {title}")
                parts.append(f"    Published: {published}")
                parts.append(f"    Link: {link}")
                if summary:
                    parts.append(f"    {summary}")
                parts.append("")

            return "\n".join(parts)
        except Exception as e:
            return f"RSS read error: {e}"

    def rss_search_feeds(self, query):
        """Search for RSS feeds related to a topic using web search."""
        try:
            client = self._get_client()
            # Use DuckDuckGo lite for quick feed discovery
            search_url = f"https://lite.duckduckgo.com/lite?q={quote(query + ' RSS feed')}"
            response = safe_httpx_get(search_url, client, timeout=10)
            html = response.text
            # Extract URLs that look like RSS feeds
            feeds = re.findall(r'(https?://[^\s"<>]+(?:\.xml|/rss|/feed|/atom)[^\s"<>]*)', html, re.IGNORECASE)
            if not feeds:
                # Fallback: look for any feed-like URLs
                feeds = re.findall(r'(https?://[^\s"<>]+)', html)
                feeds = [f for f in feeds if any(x in f.lower() for x in ["rss", "feed", "atom", ".xml"])]

            if not feeds:
                return f"No RSS feeds found for \"{query}\". Try searching for a specific website's RSS feed URL."

            lines = [f"📡 RSS feeds for \"{query}\":\n"]
            for f in feeds[:5]:
                lines.append(f"  • {f}")
            lines.append("\nUse 'rss_read' to read any of these feeds.")
            return "\n".join(lines)
        except Exception as e:
            return f"Feed search error: {e}"

    # ── Jina Reader (enhanced web reading) ────────────────────────────

    def jina_read(self, url):
        """Read a web page using Jina Reader API — produces clean, readable markdown."""
        try:
            url = validate_url(url)
        except ValueError as e:
            return f"Invalid URL: {e}"

        try:
            jina_url = f"https://r.jina.ai/{url}"
            client = self._get_client()
            response = safe_httpx_get(
                jina_url, client, timeout=30,
                headers={
                    "Accept": "text/plain",
                    "User-Agent": "Mozilla/5.0",
                }
            )
            if response.status_code != 200:
                # Fallback to standard fetch
                return self._fallback_read(url)

            text = response.text.strip()
            if len(text) > 10000:
                text = text[:10000] + "\n\n...[truncated]"
            return f"📄 {url}\n\n{text}"
        except Exception as e:
            return self._fallback_read(url)

    def _fallback_read(self, url):
        """Fallback web reading using httpx + readability."""
        try:
            client = self._get_client()
            response = safe_httpx_get(url, client, timeout=20)
            response.raise_for_status()
            html = response.text
            try:
                from readability import Document
                doc = Document(html)
                text = doc.summary()
                from html.parser import HTMLParser
                class Stripper(HTMLParser):
                    def __init__(self):
                        super().__init__()
                        self.text = []
                    def handle_data(self, d):
                        self.text.append(d)
                s = Stripper()
                s.feed(text)
                clean = " ".join(s.text).strip()
            except ImportError:
                clean = re.sub(r'<[^>]+>', ' ', html)
                clean = re.sub(r'\s+', ' ', clean).strip()

            if len(clean) > 8000:
                clean = clean[:8000] + "\n\n...[truncated]"
            return f"📄 {url} (fallback read)\n\n{clean}"
        except Exception as e:
            return f"Failed to read {url}: {e}"

    # ── Semantic Web Search (Exa via Jina) ────────────────────────────

    def semantic_search(self, query, max_results=5):
        """Search the web semantically using Jina Search API (free, no key)."""
        try:
            search_url = f"https://s.jina.ai/{quote(query)}"
            client = self._get_client()
            response = safe_httpx_get(
                search_url, client, timeout=15,
                headers={
                    "Accept": "application/json",
                    "User-Agent": "Mozilla/5.0",
                }
            )
            if response.status_code == 200:
                try:
                    data = response.json()
                    results = data.get("data", [])
                    if results:
                        lines = [f"🔍 Semantic search: \"{query}\"\n"]
                        for i, r in enumerate(results[:max_results]):
                            title = r.get("title", "No title")
                            url = r.get("url", "")
                            snippet = r.get("content", "")[:150]
                            lines.append(f"  {i+1}. {title}")
                            lines.append(f"     {url}")
                            if snippet:
                                lines.append(f"     {snippet}")
                            lines.append("")
                        return "\n".join(lines)
                except (json.JSONDecodeError, KeyError):
                    pass
            # Fallback to DuckDuckGo
            return self._ddg_fallback(query, max_results)
        except Exception:
            return self._ddg_fallback(query, max_results)

    def _ddg_fallback(self, query, max_results=5, note=None):
        """Fallback search using DuckDuckGo."""
        try:
            try:
                from ddgs import DDGS
            except ImportError:
                from duckduckgo_search import DDGS
            results = list(DDGS().text(query, max_results=max_results))
            if not results:
                return "No results found."
            prefix = f" {note}" if note else ""
            lines = [f"🔍 Web search: \"{query}\"{prefix}\n"]
            for i, r in enumerate(results):
                title = r.get("title", "No title")
                href = r.get("href", "")
                body = r.get("body", "")[:150]
                lines.append(f"  {i+1}. {title}")
                lines.append(f"     {href}")
                if body:
                    lines.append(f"     {body}")
                lines.append("")
            return "\n".join(lines)
        except Exception as e:
            return f"Search failed: {e}"

    # ── Tool Definitions ──────────────────────────────────────────────

    def get_tool_definitions(self):
        return [
            {"type": "function", "function": {
                "name": "youtube_transcript",
                "description": "Extract subtitles/transcript from a YouTube video. Returns video info and transcript text.",
                "parameters": {"type": "object", "properties": {
                    "url": {"type": "string", "description": "YouTube video URL"},
                    "lang": {"type": "string", "description": "Subtitle language (en, es, fr, zh, ja, ko). Default: en", "default": "en"},
                }, "required": ["url"]}
            }},
            {"type": "function", "function": {
                "name": "youtube_search",
                "description": "Search YouTube for videos. Returns titles, channels, durations, and links.",
                "parameters": {"type": "object", "properties": {
                    "query": {"type": "string", "description": "Search query"},
                    "max_results": {"type": "integer", "description": "Number of results", "default": 5},
                }, "required": ["query"]}
            }},
            {"type": "function", "function": {
                "name": "github_repo_info",
                "description": "Get detailed info about a GitHub repository (stars, forks, language, topics, etc.).",
                "parameters": {"type": "object", "properties": {
                    "repo": {"type": "string", "description": "Repository (owner/repo or full URL)"},
                }, "required": ["repo"]}
            }},
            {"type": "function", "function": {
                "name": "github_search",
                "description": "Search GitHub repositories by keyword.",
                "parameters": {"type": "object", "properties": {
                    "query": {"type": "string", "description": "Search query"},
                    "max_results": {"type": "integer", "description": "Number of results", "default": 5},
                }, "required": ["query"]}
            }},
            {"type": "function", "function": {
                "name": "github_issues",
                "description": "List issues in a GitHub repository.",
                "parameters": {"type": "object", "properties": {
                    "repo": {"type": "string", "description": "Repository (owner/repo or full URL)"},
                    "state": {"type": "string", "description": "Issue state: open, closed, all", "default": "open"},
                    "max_results": {"type": "integer", "description": "Number of issues", "default": 5},
                }, "required": ["repo"]}
            }},
            {"type": "function", "function": {
                "name": "rss_read",
                "description": "Read and parse an RSS/Atom feed. Returns feed entries with titles, links, and summaries.",
                "parameters": {"type": "object", "properties": {
                    "url": {"type": "string", "description": "RSS/Atom feed URL"},
                    "max_entries": {"type": "integer", "description": "Max entries to return", "default": 10},
                }, "required": ["url"]}
            }},
            {"type": "function", "function": {
                "name": "rss_search_feeds",
                "description": "Search for RSS feeds related to a topic or website.",
                "parameters": {"type": "object", "properties": {
                    "query": {"type": "string", "description": "Topic or website to find feeds for"},
                }, "required": ["query"]}
            }},
            {"type": "function", "function": {
                "name": "jina_read",
                "description": "Read any web page as clean, readable text using Jina Reader. Much better than raw HTML scraping.",
                "parameters": {"type": "object", "properties": {
                    "url": {"type": "string", "description": "URL to read"},
                }, "required": ["url"]}
            }},
            {"type": "function", "function": {
                "name": "semantic_search",
                "description": "Semantic web search using AI-powered search. Better than keyword search for understanding intent.",
                "parameters": {"type": "object", "properties": {
                    "query": {"type": "string", "description": "Search query (natural language)"},
                    "max_results": {"type": "integer", "description": "Number of results", "default": 5},
                }, "required": ["query"]}
            }},
        ]

    def get_handler(self, name):
        handlers = {
            "youtube_transcript": self.youtube_transcript,
            "youtube_search": self.youtube_search,
            "github_repo_info": self.github_repo_info,
            "github_search": self.github_search,
            "github_issues": self.github_issues,
            "rss_read": self.rss_read,
            "rss_search_feeds": self.rss_search_feeds,
            "jina_read": self.jina_read,
            "semantic_search": self.semantic_search,
        }
        return handlers.get(name)
