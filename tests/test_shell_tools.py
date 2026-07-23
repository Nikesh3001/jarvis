import sys, os, unittest
from unittest.mock import patch, MagicMock
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from tools.shell import ShellCommander, _check_command_safety, _get_allowed


class TestShellInit(unittest.TestCase):
    def test_init_creates_instance(self):
        s = ShellCommander()
        self.assertIsNotNone(s)

    def test_get_tool_definitions_returns_list(self):
        s = ShellCommander()
        defs = s.get_tool_definitions()
        self.assertIsInstance(defs, list)
        self.assertGreaterEqual(len(defs), 2)
        names = [d["function"]["name"] for d in defs]
        self.assertIn("run_command", names)
        self.assertIn("run_shell", names)

    def test_get_handler_run_command(self):
        s = ShellCommander()
        self.assertTrue(callable(s.get_handler("run_command")))

    def test_get_handler_run_shell(self):
        s = ShellCommander()
        self.assertTrue(callable(s.get_handler("run_shell")))

    def test_get_handler_unknown_returns_none(self):
        s = ShellCommander()
        self.assertIsNone(s.get_handler("nonexistent"))


class TestDangerousCommandBlocking(unittest.TestCase):
    def test_block_chaining(self):
        with self.assertRaises(PermissionError):
            _check_command_safety("echo hello & del /F *")

    def test_block_sudo(self):
        with self.assertRaises(PermissionError):
            _check_command_safety("sudo rm -rf /")

    def test_block_runas(self):
        with self.assertRaises(PermissionError):
            _check_command_safety("runas /user:admin cmd")

    def test_block_pipe(self):
        with self.assertRaises(PermissionError):
            _check_command_safety("echo hello | del /F *")

    def test_block_backtick(self):
        with self.assertRaises(PermissionError):
            _check_command_safety("echo `whoami`")

    def test_safe_command_allowed(self):
        try:
            _check_command_safety("echo hello world")
        except PermissionError:
            self.fail("Safe command should not be blocked")

    def test_safe_dir_allowed(self):
        try:
            _check_command_safety("dir C:")
        except PermissionError:
            self.fail("dir command should not be blocked")

    def test_block_unknown_command(self):
        with self.assertRaises(PermissionError):
            _check_command_safety("malicious_tool --attack")


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
        result = self.s.run_command("del /F *")
        self.assertTrue("blocked" in result.lower() or "not in the allowed" in result.lower())

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
        self.assertTrue("Error" in result or "error" in result.lower())

    def test_run_python_sandbox_blocks_os(self):
        result = self.s.run_script("import os; os.system('ls')", "python")
        self.assertTrue("blocked" in result.lower() or "forbidden" in result.lower() or "not allowed" in result.lower() or "not in safe list" in result.lower())

    def test_run_python_sandbox_blocks_open(self):
        result = self.s.run_script("open('/etc/passwd')", "python")
        self.assertTrue("blocked" in result.lower() or "forbidden" in result.lower() or "not allowed" in result.lower())

    def test_run_python_sandbox_blocks_exec(self):
        result = self.s.run_script("exec('print(1)')", "python")
        self.assertTrue("blocked" in result.lower() or "forbidden" in result.lower() or "not allowed" in result.lower())

    def test_run_unsupported_language(self):
        result = self.s.run_script("echo hi", "powershell")
        self.assertIn("only python", result.lower())

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
