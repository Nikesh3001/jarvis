"""Comprehensive tests for GitOps."""

import sys, os, tempfile, shutil, unittest
from unittest.mock import patch, MagicMock
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from tools.git_ops import GitOps, _sanitize_git_url


class TestGitURLSanitization(unittest.TestCase):
    def test_valid_https_url(self):
        url = "https://github.com/user/repo.git"
        self.assertEqual(_sanitize_git_url(url), url)

    def test_valid_http_url(self):
        url = "http://github.com/user/repo.git"
        self.assertEqual(_sanitize_git_url(url), url)

    def test_valid_ssh_url(self):
        url = "git@github.com:user/repo.git"
        self.assertEqual(_sanitize_git_url(url), url)

    def test_valid_git_protocol(self):
        url = "git://github.com/user/repo.git"
        self.assertEqual(_sanitize_git_url(url), url)

    def test_block_unsupported_protocol(self):
        with self.assertRaises(ValueError):
            _sanitize_git_url("ftp://example.com/repo.git")

    def test_block_ext_protocol(self):
        with self.assertRaises(ValueError):
            _sanitize_git_url("https://example.com/ext::command")

    def test_block_injection_semicolon(self):
        with self.assertRaises(ValueError):
            _sanitize_git_url("https://example.com;rm -rf /")

    def test_block_injection_pipe(self):
        with self.assertRaises(ValueError):
            _sanitize_git_url("https://example.com|cat /etc/passwd")

    def test_block_injection_backtick(self):
        with self.assertRaises(ValueError):
            _sanitize_git_url("https://example.com`whoami`")

    def test_block_injection_dollar(self):
        with self.assertRaises(ValueError):
            _sanitize_git_url("https://example.com$(whoami)")

    def test_block_multiple_at_signs(self):
        with self.assertRaises(ValueError):
            _sanitize_git_url("https://user@host@evil.com/repo.git")

    def test_block_injection_config_flag(self):
        with self.assertRaises(ValueError):
            _sanitize_git_url("https://example.com -c core.askpass=evil")

    def test_block_bare_path(self):
        with self.assertRaises(ValueError):
            _sanitize_git_url("/local/path/to/repo")


class TestGitOpsInit(unittest.TestCase):
    def test_init_creates_instance(self):
        g = GitOps()
        self.assertIsNotNone(g)

    def test_get_tool_definitions_returns_list(self):
        g = GitOps()
        defs = g.get_tool_definitions()
        self.assertIsInstance(defs, list)
        self.assertGreater(len(defs), 10)
        names = [d["function"]["name"] for d in defs]
        self.assertIn("git_status", names)
        self.assertIn("git_diff", names)
        self.assertIn("git_log", names)
        self.assertIn("git_commit", names)
        self.assertIn("git_add", names)
        self.assertIn("git_push", names)
        self.assertIn("git_pull", names)
        self.assertIn("git_clone", names)
        self.assertIn("git_branch", names)
        self.assertIn("git_checkout", names)
        self.assertIn("git_init", names)
        self.assertIn("git_remote", names)
        self.assertIn("git_reset", names)

    def test_all_tool_names_have_handlers(self):
        g = GitOps()
        defs = g.get_tool_definitions()
        for d in defs:
            name = d["function"]["name"]
            handler = g.get_handler(name)
            self.assertIsNotNone(handler, f"No handler for tool: {name}")

    def test_get_handler_unknown_returns_none(self):
        g = GitOps()
        self.assertIsNone(g.get_handler("nonexistent"))


class TestGitOperations(unittest.TestCase):
    def setUp(self):
        self.g = GitOps()
        self.tmpdir = tempfile.mkdtemp()
        self.orig_dir = os.getcwd()
        os.chdir(self.tmpdir)

    def tearDown(self):
        os.chdir(self.orig_dir)
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_git_init(self):
        result = self.g.git_init()
        self.assertTrue(os.path.isdir(os.path.join(self.tmpdir, ".git")))

    def test_git_status_after_init(self):
        self.g.git_init()
        result = self.g.git_status()
        self.assertTrue("On branch" in result or "nothing to commit" in result or "Output" in result)

    def test_git_add_and_commit(self):
        self.g.git_init()
        os.system("git config user.email 'test@test.com'")
        os.system("git config user.name 'Test'")
        with open(os.path.join(self.tmpdir, "test.txt"), "w") as f:
            f.write("hello")
        self.g.git_add(".")
        result = self.g.git_commit("test commit")
        self.assertTrue("Output" in result or "commit" in result.lower() or "HEAD" in result)

    def test_git_commit_empty_message(self):
        result = self.g.git_commit("")
        self.assertIn("Invalid", result)

    def test_git_commit_long_message(self):
        result = self.g.git_commit("x" * 300)
        self.assertIn("Invalid", result)

    def test_git_log(self):
        self.g.git_init()
        result = self.g.git_log()
        self.assertIsInstance(result, str)

    def test_git_diff_empty_repo(self):
        self.g.git_init()
        result = self.g.git_diff()
        self.assertIsInstance(result, str)

    def test_git_branch_empty_repo(self):
        self.g.git_init()
        result = self.g.git_branch()
        self.assertIsInstance(result, str)

    def test_git_remote_empty_repo(self):
        self.g.git_init()
        result = self.g.git_remote()
        self.assertIsInstance(result, str)

    def test_git_clone_invalid_url(self):
        result = self.g.git_clone("not-a-url")
        self.assertTrue("Unsupported" in result or "dangerous" in result.lower())

    def test_git_clone_injection(self):
        result = self.g.git_clone("https://example.com;rm -rf /")
        self.assertTrue("dangerous" in result.lower() or "characters" in result.lower())

    def test_git_commit_all(self):
        self.g.git_init()
        os.system("git config user.email 'test@test.com'")
        os.system("git config user.name 'Test'")
        with open(os.path.join(self.tmpdir, "test2.txt"), "w") as f:
            f.write("hello2")
        result = self.g.git_commit_all("commit all")
        self.assertIsInstance(result, str)

    def test_git_commit_all_empty_message(self):
        result = self.g.git_commit_all("")
        self.assertIn("Invalid", result)

    def test_git_reset(self):
        self.g.git_init()
        result = self.g.git_reset("HEAD")
        self.assertIsInstance(result, str)


if __name__ == "__main__":
    unittest.main()
