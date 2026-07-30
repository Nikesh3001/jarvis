"""Comprehensive tests for WebTools."""

import sys, os, unittest
from unittest.mock import patch, MagicMock
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from tools.web import WebTools


class TestWebToolsInit(unittest.TestCase):
    def test_init_creates_instance(self):
        w = WebTools()
        self.assertIsNone(w._ddgs)
        self.assertIsNone(w._httpx)
        self.assertIsNone(w._client)

    def test_get_tool_definitions_returns_list(self):
        w = WebTools()
        defs = w.get_tool_definitions()
        self.assertIsInstance(defs, list)
        self.assertEqual(len(defs), 3)
        names = [d["function"]["name"] for d in defs]
        self.assertIn("web_search", names)
        self.assertIn("web_fetch", names)
        self.assertIn("web_osint_search", names)

    def test_get_handler_search(self):
        w = WebTools()
        handler = w.get_handler("web_search")
        self.assertTrue(callable(handler))

    def test_get_handler_fetch(self):
        w = WebTools()
        handler = w.get_handler("web_fetch")
        self.assertTrue(callable(handler))

    def test_get_handler_unknown_returns_none(self):
        w = WebTools()
        self.assertIsNone(w.get_handler("nonexistent"))


class TestWebSearch(unittest.TestCase):
    def setUp(self):
        self.w = WebTools()

    @patch("tools.web.WebTools.ddgs")
    def test_search_returns_string(self, mock_ddgs_cls):
        mock_instance = MagicMock()
        mock_instance.text.return_value = [
            {"title": "Test", "href": "https://example.com", "body": "desc"}
        ]
        mock_ddgs_cls.return_value = mock_instance
        result = self.w.search("test query")
        self.assertIsInstance(result, str)
        self.assertIn("Search results", result)

    @patch("tools.web.WebTools.ddgs")
    def test_search_empty_results(self, mock_ddgs_cls):
        mock_instance = MagicMock()
        mock_instance.text.return_value = []
        mock_ddgs_cls.return_value = mock_instance
        result = self.w.search("xyznonexistent123")
        self.assertIn("No search results", result)

    @patch("tools.web.WebTools.ddgs")
    def test_search_multiple_results(self, mock_ddgs_cls):
        mock_instance = MagicMock()
        mock_instance.text.return_value = [
            {"title": "A", "href": "https://a.com", "body": "a"},
            {"title": "B", "href": "https://b.com", "body": "b"},
            {"title": "C", "href": "https://c.com", "body": "c"},
        ]
        mock_ddgs_cls.return_value = mock_instance
        result = self.w.search("test", max_results=3)
        self.assertIn("1.", result)
        self.assertIn("2.", result)
        self.assertIn("3.", result)

    @patch("tools.web.WebTools.ddgs")
    def test_search_exception_returns_fail(self, mock_ddgs_cls):
        mock_instance = MagicMock()
        mock_instance.text.side_effect = Exception("network error")
        mock_ddgs_cls.return_value = mock_instance
        result = self.w.search("test")
        self.assertEqual(result, "Search failed")


class TestWebFetch(unittest.TestCase):
    def setUp(self):
        self.w = WebTools()

    @patch("tools.web.safe_httpx_get")
    @patch("tools.web.validate_url", side_effect=lambda u: u)
    def test_fetch_returns_content(self, mock_validate, mock_get):
        mock_response = MagicMock()
        mock_response.text = "<html><body>Hello World</body></html>"
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response
        result = self.w.fetch("https://example.com")
        self.assertIn("Content from", result)
        self.assertIn("Hello World", result)

    @patch("tools.web.validate_url", side_effect=ValueError("blocked"))
    def test_fetch_blocked_returns_error(self, mock_validate):
        result = self.w.fetch("http://localhost")
        self.assertTrue("Blocked" in result or "failed" in result)

    @patch("tools.web.safe_httpx_get")
    @patch("tools.web.validate_url", side_effect=lambda u: u)
    def test_fetch_exception_returns_fail(self, mock_validate, mock_get):
        mock_get.side_effect = Exception("timeout")
        result = self.w.fetch("https://example.com")
        self.assertEqual(result, "Fetch failed")


if __name__ == "__main__":
    unittest.main()
