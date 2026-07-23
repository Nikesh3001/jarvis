"""Comprehensive tests for SystemTools."""

import sys, os, tempfile, unittest
from unittest.mock import patch, MagicMock
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from tools.system import SystemTools


class TestSystemToolsInit(unittest.TestCase):
    def test_init_creates_instance(self):
        s = SystemTools()
        self.assertIsNone(s._psutil)

    def test_psutil_property_lazy_loads(self):
        s = SystemTools()
        p = s.psutil
        self.assertIsNotNone(p)
        self.assertIs(s.psutil, p)  # cached

    def test_get_all_tool_definitions_returns_list(self):
        s = SystemTools()
        defs = s.get_all_tool_definitions()
        self.assertIsInstance(defs, list)
        self.assertGreater(len(defs), 20)
        for d in defs:
            self.assertIn("function", d)
            self.assertIn("name", d["function"])
            self.assertIn("description", d["function"])
            self.assertIn("parameters", d["function"])

    def test_get_handler_returns_callable(self):
        s = SystemTools()
        handler = s.get_handler("get_cpu")
        self.assertTrue(callable(handler))

    def test_get_handler_unknown_returns_none(self):
        s = SystemTools()
        self.assertIsNone(s.get_handler("nonexistent_tool"))

    def test_all_tool_names_have_handlers(self):
        s = SystemTools()
        defs = s.get_all_tool_definitions()
        for d in defs:
            name = d["function"]["name"]
            handler = s.get_handler(name)
            self.assertIsNotNone(handler, f"No handler for tool: {name}")


class TestSystemInfo(unittest.TestCase):
    def setUp(self):
        self.s = SystemTools()

    def test_get_cpu_returns_string(self):
        result = self.s.get_cpu()
        self.assertIsInstance(result, str)
        self.assertIn("CPU", result)

    def test_get_cpu_contains_percent(self):
        result = self.s.get_cpu()
        self.assertIn("%", result)

    def test_get_memory_returns_string(self):
        result = self.s.get_memory()
        self.assertIsInstance(result, str)
        self.assertIn("RAM", result)

    def test_get_memory_contains_percent(self):
        result = self.s.get_memory()
        self.assertIn("%", result)

    def test_get_disk_returns_string(self):
        result = self.s.get_disk()
        self.assertIsInstance(result, str)
        self.assertIn("Disk", result)

    def test_get_battery_returns_string(self):
        result = self.s.get_battery()
        self.assertIsInstance(result, str)
        self.assertTrue(
            "Battery" in result or "No battery" in result or "desktop" in result
        )

    def test_get_network_returns_string(self):
        result = self.s.get_network()
        self.assertIsInstance(result, str)
        self.assertTrue("Network" in result or "Connections" in result or "failed" in result)

    def test_get_system_info_returns_string(self):
        result = self.s.get_system_info()
        self.assertIsInstance(result, str)
        self.assertIn("System", result)

    def test_get_system_uptime_returns_string(self):
        result = self.s.get_system_uptime()
        self.assertIsInstance(result, str)
        self.assertTrue("Uptime" in result or "failed" in result)

    def test_get_processes_returns_string(self):
        result = self.s.get_processes(top=5)
        self.assertIsInstance(result, str)
        self.assertIn("Top processes", result)

    def test_get_processes_custom_top(self):
        result = self.s.get_processes(top=3)
        self.assertIsInstance(result, str)

    def test_get_services_returns_string(self):
        result = self.s.get_services()
        self.assertIsInstance(result, str)
        self.assertTrue("Running services" in result or "failed" in result)

    def test_get_active_connections_returns_string(self):
        result = self.s.get_active_connections()
        self.assertIsInstance(result, str)
        self.assertTrue("Connections" in result or "failed" in result)

    def test_get_installed_software_returns_string(self):
        result = self.s.get_installed_software()
        self.assertIsInstance(result, str)
        self.assertTrue("Software" in result or "failed" in result or "unavailable" in result)

    def test_get_startup_programs_returns_string(self):
        result = self.s.get_startup_programs()
        self.assertIsInstance(result, str)
        self.assertTrue("Startup" in result or "failed" in result or "No startup" in result)

    def test_explore_drives_returns_string(self):
        result = self.s.explore_drives()
        self.assertIsInstance(result, str)
        self.assertTrue("Drives" in result or "failed" in result)

    def test_list_wifi_returns_string(self):
        result = self.s.list_wifi()
        self.assertIsInstance(result, str)
        self.assertTrue("WiFi" in result or "failed" in result or "unavailable" in result)

    def test_wifi_status_returns_string(self):
        result = self.s.wifi_status()
        self.assertIsInstance(result, str)
        self.assertIn("WiFi", result)

    def test_list_windows_returns_string(self):
        result = self.s.list_windows()
        self.assertIsInstance(result, str)
        self.assertTrue("Windows" in result or "failed" in result or "unavailable" in result)


class TestVolumeControls(unittest.TestCase):
    def setUp(self):
        self.s = SystemTools()

    def test_get_volume_returns_string(self):
        result = self.s.get_volume()
        self.assertIsInstance(result, str)
        self.assertIn("Volume", result)

    def test_get_volume_no_extra_newlines(self):
        result = self.s.get_volume()
        self.assertNotIn("\n", result, "Volume output should not contain newlines")

    def test_set_volume_clamps_low(self):
        result = self.s.set_volume(-10)
        self.assertIn("0%", result)

    def test_set_volume_clamps_high(self):
        result = self.s.set_volume(200)
        self.assertIn("100%", result)

    def test_set_volume_returns_string(self):
        result = self.s.set_volume(50)
        self.assertIsInstance(result, str)
        self.assertIn("Volume set", result)

    def test_mute_volume_returns_string(self):
        result = self.s.mute_volume()
        self.assertIsInstance(result, str)
        self.assertTrue("muted" in result.lower() or "toggle" in result.lower() or "failed" in result)

    def test_media_play_pause_returns_string(self):
        result = self.s.media_play_pause()
        self.assertIsInstance(result, str)
        self.assertTrue("Play" in result or "toggled" in result or "failed" in result)

    def test_media_next_returns_string(self):
        result = self.s.media_next()
        self.assertIsInstance(result, str)
        self.assertTrue("Next" in result or "failed" in result)

    def test_media_prev_returns_string(self):
        result = self.s.media_prev()
        self.assertIsInstance(result, str)
        self.assertTrue("Prev" in result or "failed" in result)


class TestClipboard(unittest.TestCase):
    def setUp(self):
        self.s = SystemTools()

    def test_set_clipboard_returns_string(self):
        result = self.s.set_clipboard("test text")
        self.assertIsInstance(result, str)
        self.assertTrue("set" in result.lower() or "failed" in result or "blocked" in result.lower())

    def test_get_clipboard_returns_string(self):
        result = self.s.get_clipboard()
        self.assertIsInstance(result, str)
        self.assertTrue("Clipboard" in result or "failed" in result or "empty" in result)


class TestProcessManagement(unittest.TestCase):
    def setUp(self):
        self.s = SystemTools()

    def test_kill_nonexistent_process(self):
        result = self.s.kill_process("zzz_nonexistent_process_12345")
        self.assertIn("No process matching", result)

    def test_find_installed_app_returns_string(self):
        result = self.s.find_installed_app("python")
        self.assertIsInstance(result, str)
        self.assertTrue("Found" in result or "No app" in result or "failed" in result)


class TestScreenshot(unittest.TestCase):
    def setUp(self):
        self.s = SystemTools()

    def test_take_screenshot_returns_string(self):
        result = self.s.take_screenshot()
        self.assertIsInstance(result, str)
        self.assertTrue("Screenshot" in result or "failed" in result)


if __name__ == "__main__":
    unittest.main()
