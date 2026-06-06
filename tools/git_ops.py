import subprocess


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
        except Exception as e:
            return f"Git error: {e}"

    def git_status(self):
        return self._run("status")

    def git_diff(self):
        return self._run("diff")

    def git_log(self, count=10):
        return self._run("log", f"--oneline", f"-{count}")

    def git_commit(self, message):
        return self._run("commit", "-m", message)

    def git_add(self, paths="."):
        return self._run("add", paths)

    def git_push(self):
        return self._run("push")

    def git_pull(self):
        return self._run("pull")

    def git_clone(self, url, directory=None):
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

    def git_reset(self, target="HEAD"):
        return self._run("reset", target)

    def get_tool_definitions(self):
        return [
            {"type": "function", "function": {"name": "git_status", "description": "Working tree status", "parameters": {"type": "object", "properties": {}}}},
            {"type": "function", "function": {"name": "git_diff", "description": "Unstaged changes", "parameters": {"type": "object", "properties": {}}}},
            {"type": "function", "function": {"name": "git_log", "description": "Commit history", "parameters": {"type": "object", "properties": {"count": {"type": "integer", "description": "Count", "default": 10}}}}},
            {"type": "function", "function": {"name": "git_commit", "description": "Commit with message", "parameters": {"type": "object", "properties": {"message": {"type": "string", "description": "Msg"}}, "required": ["message"]}}},
            {"type": "function", "function": {"name": "git_add", "description": "Stage files", "parameters": {"type": "object", "properties": {"paths": {"type": "string", "description": "Paths", "default": "."}}, "required": []}}},
            {"type": "function", "function": {"name": "git_push", "description": "Push to remote", "parameters": {"type": "object", "properties": {}}}},
            {"type": "function", "function": {"name": "git_pull", "description": "Pull from remote", "parameters": {"type": "object", "properties": {}}}},
            {"type": "function", "function": {"name": "git_clone", "description": "Clone a repo", "parameters": {"type": "object", "properties": {"url": {"type": "string", "description": "URL"}, "directory": {"type": "string", "description": "Target dir"}}, "required": ["url"]}}},
            {"type": "function", "function": {"name": "git_branch", "description": "List branches", "parameters": {"type": "object", "properties": {}}}},
            {"type": "function", "function": {"name": "git_checkout", "description": "Switch branch", "parameters": {"type": "object", "properties": {"branch": {"type": "string", "description": "Branch"}}, "required": ["branch"]}}},
            {"type": "function", "function": {"name": "git_init", "description": "Init repository", "parameters": {"type": "object", "properties": {}}}},
            {"type": "function", "function": {"name": "git_remote", "description": "Show remotes", "parameters": {"type": "object", "properties": {}}}},
            {"type": "function", "function": {"name": "git_reset", "description": "Reset to target", "parameters": {"type": "object", "properties": {"target": {"type": "string", "description": "Target", "default": "HEAD"}}}}},
        ]

    def get_handler(self, name):
        handlers = {
            "git_status": self.git_status, "git_diff": self.git_diff, "git_log": self.git_log,
            "git_commit": self.git_commit, "git_add": self.git_add, "git_push": self.git_push,
            "git_pull": self.git_pull, "git_clone": self.git_clone, "git_branch": self.git_branch,
            "git_checkout": self.git_checkout, "git_init": self.git_init, "git_remote": self.git_remote,
            "git_reset": self.git_reset,
        }
        return handlers.get(name)
