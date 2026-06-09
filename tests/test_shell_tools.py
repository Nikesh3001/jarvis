"""Comprehensive tests for ShellCommander."""

import sys, os, unittest
from unittest.mock import patch, MagicMock
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from tools.shell import ShellCommander, _check_dangerous, _DANGEROUS_COMMANDS


class TestShellInit(unittest.TestCase):
    def test_init_creates_instance(self):
        s = ShellCommander()
        self.assertIsNotNone(s)

    def test_get_tool_definitions_returns_list(self):
        s = ShellCommander()
        defs = s.get_tool_definitions()
        self.assertIsInstance(defs, list)
        self.assertGreaterEqual(len(defs), 3)
        names = [d["function"]["name"] for d in defs]
        self.assertIn("run_command", names)
        self.assertIn("run_script", names)
        self.assertIn("run_shell", names)

    def test_get_handler_run_command(self):
        s = ShellCommander()
        self.assertTrue(callable(s.get_handler("run_command")))

    def test_get_handler_run_script(self):
        s = ShellCommander()
        self.assertTrue(callable(s.get_handler("run_script")))

    def test_get_handler_run_shell(self):
        s = ShellCommander()
        self.assertTrue(callable(s.get_handler("run_shell")))

    def test_get_handler_unknown_returns_none(self):
        s = ShellCommander()
        self.assertIsNone(s.get_handler("nonexistent"))


class TestDangerousCommandBlocking(unittest.TestCase):
    def test_block_rm_rf_root(self):
        with self.assertRaises(PermissionError):
            _check_dangerous("rm -rf /")

    def test_block_format_disk(self):
        with self.assertRaises(PermissionError):
            _check_dangerous("format C:")

    def test_block_shutdown(self):
        with self.assertRaises(PermissionError):
            _check_dangerous("shutdown -s")

    def test_block_reboot(self):
        with self.assertRaises(PermissionError):
            _check_dangerous("reboot")

    def test_block_python_exec(self):
        with self.assertRaises(PermissionError):
            _check_dangerous("python -c 'import os'")

    def test_block_powershell_invoke(self):
        with self.assertRaises(PermissionError):
            _check_dangerous("Invoke-Expression Get-Process")

    def test_block_encoded_command(self):
        with self.assertRaises(PermissionError):
            _check_dangerous("powershell -EncodedCommand AAAA")

    def test_block_diskpart(self):
        with self.assertRaises(PermissionError):
            _check_dangerous("diskpart /s script.txt")

    def test_block_reg_delete(self):
        with self.assertRaises(PermissionError):
            _check_dangerous("reg delete HKLM\\SOFTWARE")

    def test_block_net_user(self):
        with self.assertRaises(PermissionError):
            _check_dangerous("net user admin /add")

    def test_safe_command_allowed(self):
        try:
            _check_dangerous("echo hello world")
        except PermissionError:
            self.fail("Safe command should not be blocked")

    def test_safe_ls_allowed(self):
        try:
            _check_dangerous("ls -la")
        except PermissionError:
            self.fail("ls command should not be blocked")

    def test_safe_python_script_allowed(self):
        try:
            _check_dangerous("python script.py")
        except PermissionError:
            self.fail("python script.py should not be blocked")


class TestRunCommand(unittest.TestCase):
    def setUp(self):
        self.s = ShellCommander()

    @patch("tools.shell.check_rate", return_value=True)
    def test_run_echo(self, mock_rate):
        result = self.s.run_command("echo hello")
        self.assertIn("Exit code", result)
        self.assertIn("hello", result)

    @patch("tools.shell.check_rate", return_value=True)
    def test_run_dangerous_blocked(self, mock_rate):
        result = self.s.run_command("rm -rf /")
        self.assertIn("blocked", result.lower())

    @patch("tools.shell.check_rate", return_value=False)
    def test_rate_limited(self, mock_rate):
        result = self.s.run_command("echo hello")
        self.assertIn("Rate limit", result)

    @patch("tools.shell.check_rate", return_value=True)
    def test_run_command_returns_exit_code(self, mock_rate):
        result = self.s.run_command("echo test_exit_code")
        self.assertIn("Exit code", result)


class TestRunScript(unittest.TestCase):
    def setUp(self):
        self.s = ShellCommander()

    def test_run_python_script(self):
        result = self.s.run_script("print('hello from script')", "python")
        self.assertIn("hello from script", result)

    def test_run_python_script_with_error(self):
        result = self.s.run_script("print(1/0)", "python")
        self.assertTrue("Error" in result or "error" in result)

    def test_run_python_sandbox_blocks_os(self):
        result = self.s.run_script("import os; os.system('ls')", "python")
        self.assertTrue("blocked" in result.lower() or "forbidden" in result.lower() or "not allowed" in result.lower(), f"Expected blocking message, got: {result}")

    def test_run_python_sandbox_blocks_subprocess(self):
        result = self.s.run_script("import subprocess; subprocess.run(['ls'])", "python")
        self.assertTrue("blocked" in result.lower() or "forbidden" in result.lower() or "not allowed" in result.lower(), f"Expected blocking message, got: {result}")

    def test_run_python_sandbox_blocks_open(self):
        result = self.s.run_script("open('/etc/passwd')", "python")
        self.assertTrue("blocked" in result.lower() or "forbidden" in result.lower() or "not allowed" in result.lower(), f"Expected blocking message, got: {result}")

    def test_run_python_sandbox_blocks_exec(self):
        result = self.s.run_script("exec('print(1)')", "python")
        self.assertTrue("blocked" in result.lower() or "forbidden" in result.lower() or "not allowed" in result.lower(), f"Expected blocking message, got: {result}")

    def test_run_python_sandbox_blocks_eval(self):
        result = self.s.run_script("eval('1+1')", "python")
        self.assertTrue("blocked" in result.lower() or "forbidden" in result.lower() or "not allowed" in result.lower(), f"Expected blocking message, got: {result}")

    def test_run_python_syntax_error(self):
        result = self.s.run_script("def (broken", "python")
        self.assertTrue("blocked" in result.lower() or "syntax" in result.lower() or "error" in result.lower(), f"Expected blocking/error message, got: {result}")

    def test_run_unsupported_language_on_windows(self):
        from core.platform_utils import is_windows
        if not is_windows():
            result = self.s.run_script("echo hi", "powershell")
            self.assertIn("only supported", result.lower())

    def test_run_dangerous_script_blocked(self):
        result = self.s.run_script("rm -rf /", "python")
        self.assertIn("blocked", result.lower())

    def test_run_script_returns_output(self):
        result = self.s.run_script("print(2 + 2)", "python")
        self.assertIn("4", result)


class TestRunShell(unittest.TestCase):
    def setUp(self):
        self.s = ShellCommander()

    @patch("tools.shell.check_rate", return_value=True)
    def test_run_shell_returns_string(self, mock_rate):
        result = self.s.run_shell("echo test123")
        self.assertIsInstance(result, str)
        self.assertTrue("test123" in result or "failed" in result or "Exit code" in result)


if __name__ == "__main__":
    unittest.main()
