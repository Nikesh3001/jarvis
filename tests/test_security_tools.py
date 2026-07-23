"""Comprehensive tests for SecurityTool."""

import sys, os, unittest
from unittest.mock import patch, MagicMock
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from tools.security import SecurityTool


class TestSecurityInit(unittest.TestCase):
    def test_init_creates_instance(self):
        s = SecurityTool()
        self.assertIsNone(s._psutil)

    def test_psutil_property_lazy_loads(self):
        s = SecurityTool()
        p = s.psutil
        self.assertIsNotNone(p)
        self.assertIs(s.psutil, p)

    def test_get_tool_definitions_returns_list(self):
        s = SecurityTool()
        defs = s.get_tool_definitions()
        self.assertIsInstance(defs, list)
        self.assertEqual(len(defs), 29)
        names = [d["function"]["name"] for d in defs]
        self.assertIn("check_firewall", names)
        self.assertIn("check_open_ports", names)
        self.assertIn("check_listeners", names)
        self.assertIn("check_security_updates", names)
        self.assertIn("security_best_practices", names)

    def test_all_tool_names_have_handlers(self):
        s = SecurityTool()
        defs = s.get_tool_definitions()
        for d in defs:
            name = d["function"]["name"]
            handler = s.get_handler(name)
            self.assertIsNotNone(handler, f"No handler for tool: {name}")

    def test_get_handler_unknown_returns_none(self):
        s = SecurityTool()
        self.assertIsNone(s.get_handler("nonexistent"))


class TestFirewall(unittest.TestCase):
    def setUp(self):
        self.s = SecurityTool()

    def test_check_firewall_returns_string(self):
        result = self.s.check_firewall()
        self.assertIsInstance(result, str)
        self.assertTrue(
            "Firewall" in result or "unavailable" in result or "failed" in result
        )


class TestOpenPorts(unittest.TestCase):
    def setUp(self):
        self.s = SecurityTool()

    @patch("tools.security.check_rate", return_value=True)
    def test_check_open_ports_returns_string(self, mock_rate):
        result = self.s.check_open_ports()
        self.assertIsInstance(result, str)
        self.assertTrue(
            "Open ports" in result or "No common" in result or "error" in result.lower()
        )

    @patch("tools.security.check_rate", return_value=False)
    def test_check_open_ports_rate_limited(self, mock_rate):
        result = self.s.check_open_ports()
        self.assertIn("Rate limit", result)

    @patch("tools.security.check_rate", return_value=True)
    def test_check_open_ports_full_scan_disabled(self, mock_rate):
        result = self.s.check_open_ports(common_only=False)
        self.assertIn("disabled", result.lower())


class TestListeners(unittest.TestCase):
    def setUp(self):
        self.s = SecurityTool()

    def test_check_listeners_returns_string(self):
        result = self.s.check_listeners()
        self.assertIsInstance(result, str)
        self.assertTrue(
            "Listening" in result or "No listening" in result or "failed" in result
        )


class TestSecurityUpdates(unittest.TestCase):
    def setUp(self):
        self.s = SecurityTool()

    def test_check_security_updates_returns_string(self):
        result = self.s.check_security_updates()
        self.assertIsInstance(result, str)
        self.assertTrue(
            "update" in result.lower()
            or "up to date" in result.lower()
            or "unavailable" in result.lower()
            or "failed" in result.lower()
        )


class TestSecurityBestPractices(unittest.TestCase):
    def setUp(self):
        self.s = SecurityTool()

    def test_security_best_practices_returns_string(self):
        result = self.s.security_best_practices()
        self.assertIsInstance(result, str)
        self.assertIn("Security Best Practices", result)

    def test_security_best_practices_mentions_firewall(self):
        result = self.s.security_best_practices()
        self.assertTrue("firewall" in result.lower() or "Firewall" in result)

    def test_security_best_practices_mentions_memory(self):
        result = self.s.security_best_practices()
        self.assertTrue("memory" in result.lower() or "Memory" in result)

    def test_security_best_practices_mentions_passwords(self):
        result = self.s.security_best_practices()
        self.assertIn("password", result.lower())

    def test_security_best_practices_mentions_disk_encryption(self):
        result = self.s.security_best_practices()
        self.assertTrue(
            "BitLocker" in result
            or "FileVault" in result
            or "LUKS" in result
            or "dm-crypt" in result
        )


class TestRunningServices(unittest.TestCase):
    def setUp(self):
        self.s = SecurityTool()

    def test_check_running_services_returns_string(self):
        result = self.s.check_running_services()
        self.assertIsInstance(result, str)
        self.assertTrue(
            "Running services" in result
            or "LaunchAgents" in result
            or "failed" in result
        )


if __name__ == "__main__":
    unittest.main()
