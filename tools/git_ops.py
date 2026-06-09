import re
import subprocess


_GIT_CLONE_INJECTION_PATTERNS = re.compile(
    r'[;&|`$(){}[\]!#~<>]|'
    r'\s+-(c|config|depth|branch|origin|recurse|shallow|single-branch|no-checkout|'
    r'bundle|filter|reference|replicate|upload-pack|http|proxy|git|ssh|ssl|core\.)',
    re.IGNORECASE
)


def _sanitize_git_url(url):
    if not url.startswith(("http://", "https://", "git@", "ssh://", "git://")):
        raise ValueError(f"Unsupported git protocol in URL: {url[:50]}")
    if "ext::" in url.lower():
        raise ValueError(f"Remote execution protocol (ext::) is not allowed: {url[:50]}")
    if "://" in url and not url.startswith(("http://", "https://", "ssh://", "git://")):
        raise ValueError(f"Unsupported git protocol in URL: {url[:50]}")
    if _GIT_CLONE_INJECTION_PATTERNS.search(url):
        raise ValueError(f"URL contains potentially dangerous characters: {url[:50]}")
    if url.count("@") > 1:
        raise ValueError(f"Invalid URL format: {url[:50]}")
    return url


class GitOps:
    def _run(self, *args):
        try:
            r = subprocess.run(["git"] + list(args), capture_output=True, text=True, timeout=60)
            out = r.stdout.strip()[:3000] if r.stdout.strip() else ""
            err = r.stderr.strip()[:1000] if r.stderr.strip() else ""
            result = ""
            if out:
                result += f"Output:\n{out}\n"
            if err:
                result += f"Error:\n{err}\n"
            return result.strip() or "Git command completed (no output)"
        except subprocess.TimeoutExpired:
            return "Git command timed out"
        except FileNotFoundError:
            return "Git is not installed or not in PATH"
        except Exception:
            return "Git command failed"

    def git_status(self):
        return self._run("status")

    def git_diff(self):
        return self._run("diff")

    def git_log(self, count=10):
        return self._run("log", f"--oneline", f"-{count}")

    def git_commit(self, message):
        if not message or len(message) > 200:
            return "Invalid commit message"
        return self._run("commit", "-m", message)

    def git_add(self, paths="."):
        return self._run("add", paths)

    def git_push(self):
        return self._run("push")

    def git_pull(self):
        return self._run("pull")

    def git_clone(self, url, directory=None):
        try:
            url = _sanitize_git_url(url)
        except ValueError as e:
            return str(e)
        args = ["clone", url]
        if directory:
            args.append(directory)
        return self._run(*args)

    def git_branch(self):
        return self._run("branch", "-a")

    def git_checkout(self, branch):
        return self._run("checkout", branch)

    def git_init(self):
        return self._run("init")

    def git_remote(self):
        return self._run("remote", "-v")

    def git_remote_add(self, name, url):
        try:
            url = _sanitize_git_url(url)
        except ValueError as e:
            return str(e)
        return self._run("remote", "add", name, url)

    def git_commit_all(self, message):
        if not message or len(message) > 200:
            return "Invalid commit message"
        r1 = self._run("add", "-A")
        r2 = self._run("commit", "-m", message)
        return f"{r1}\n{r2}"

    def git_push_upstream(self, remote="origin", branch="main"):
        return self._run("push", "-u", remote, branch)

    def git_pull_rebase(self, remote="origin", branch="main"):
        return self._run("pull", "--rebase", remote, branch)

    def git_branch_rename(self, new_name="main"):
        return self._run("branch", "-M", new_name)

    def git_reset(self, target="HEAD"):
        return self._run("reset", target)

    def get_tool_definitions(self):
        return [
            {"type": "function", "function": {"name": "git_status", "description": "Working tree status", "parameters": {"type": "object", "properties": {}}}},
            {"type": "function", "function": {"name": "git_diff", "description": "Unstaged changes", "parameters": {"type": "object", "properties": {}}}},
            {"type": "function", "function": {"name": "git_log", "description": "Commit history", "parameters": {"type": "object", "properties": {"count": {"type": "integer", "description": "Count", "default": 10}}}}},
            {"type": "function", "function": {"name": "git_commit", "description": "Commit staged changes", "parameters": {"type": "object", "properties": {"message": {"type": "string", "description": "Commit message"}}, "required": ["message"]}}},
            {"type": "function", "function": {"name": "git_add", "description": "Stage files for commit", "parameters": {"type": "object", "properties": {"paths": {"type": "string", "description": "File paths or '.' for all", "default": "."}}, "required": []}}},
            {"type": "function", "function": {"name": "git_commit_all", "description": "Stage ALL changes and commit in one step", "parameters": {"type": "object", "properties": {"message": {"type": "string", "description": "Commit message"}}, "required": ["message"]}}},
            {"type": "function", "function": {"name": "git_push", "description": "Push to remote", "parameters": {"type": "object", "properties": {}}}},
            {"type": "function", "function": {"name": "git_push_upstream", "description": "First push to set upstream and push", "parameters": {"type": "object", "properties": {"remote": {"type": "string", "description": "Remote name", "default": "origin"}, "branch": {"type": "string", "description": "Branch name", "default": "main"}}}}},
            {"type": "function", "function": {"name": "git_pull", "description": "Pull from remote", "parameters": {"type": "object", "properties": {}}}},
            {"type": "function", "function": {"name": "git_pull_rebase", "description": "Pull with rebase to avoid merge commits", "parameters": {"type": "object", "properties": {"remote": {"type": "string", "description": "Remote", "default": "origin"}, "branch": {"type": "string", "description": "Branch", "default": "main"}}}}},
            {"type": "function", "function": {"name": "git_clone", "description": "Clone a repo (URL sanitized for security)", "parameters": {"type": "object", "properties": {"url": {"type": "string", "description": "URL"}, "directory": {"type": "string", "description": "Target dir"}}, "required": ["url"]}}},
            {"type": "function", "function": {"name": "git_branch", "description": "List branches", "parameters": {"type": "object", "properties": {}}}},
            {"type": "function", "function": {"name": "git_branch_rename", "description": "Rename current branch", "parameters": {"type": "object", "properties": {"new_name": {"type": "string", "description": "New name", "default": "main"}}}}},
            {"type": "function", "function": {"name": "git_checkout", "description": "Switch branch", "parameters": {"type": "object", "properties": {"branch": {"type": "string", "description": "Branch"}}, "required": ["branch"]}}},
            {"type": "function", "function": {"name": "git_init", "description": "Initialize new git repository", "parameters": {"type": "object", "properties": {}}}},
            {"type": "function", "function": {"name": "git_remote", "description": "List remotes", "parameters": {"type": "object", "properties": {}}}},
            {"type": "function", "function": {"name": "git_remote_add", "description": "Add a remote URL (URL sanitized for security)", "parameters": {"type": "object", "properties": {"name": {"type": "string", "description": "Remote name (e.g. origin)"}, "url": {"type": "string", "description": "Remote URL"}}, "required": ["name", "url"]}}},
            {"type": "function", "function": {"name": "git_reset", "description": "Reset to target commit", "parameters": {"type": "object", "properties": {"target": {"type": "string", "description": "Target", "default": "HEAD"}}}}},
        ]

    def get_handler(self, name):
        handlers = {
            "git_status": self.git_status, "git_diff": self.git_diff, "git_log": self.git_log,
            "git_commit": self.git_commit, "git_add": self.git_add, "git_commit_all": self.git_commit_all,
            "git_push": self.git_push, "git_push_upstream": self.git_push_upstream,
            "git_pull": self.git_pull, "git_pull_rebase": self.git_pull_rebase,
            "git_clone": self.git_clone, "git_branch": self.git_branch,
            "git_branch_rename": self.git_branch_rename,
            "git_checkout": self.git_checkout, "git_init": self.git_init,
            "git_remote": self.git_remote, "git_remote_add": self.git_remote_add,
            "git_reset": self.git_reset,
        }
        return handlers.get(name)
