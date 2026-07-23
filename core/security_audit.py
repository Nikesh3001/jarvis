import os
import re
import json
from pathlib import Path
from typing import Dict, List, Optional


class SecurityAuditor:
    def __init__(self, project_root: str = None):
        self.root = Path(project_root or os.getcwd()).resolve()
        self.findings = []
        self.severity_counts = {"CRITICAL": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0, "INFO": 0}

    def audit_all(self) -> Dict:
        self._check_config_files()
        self._check_env_files()
        self._check_api_key_exposure()
        self._check_command_injection_risks()
        self._check_path_traversal()
        self._check_sql_injection_patterns()
        self._check_sensitive_data_in_logs()
        self._check_import_safety()
        self._check_permission_issues()
        self._check_code_execution_patterns()
        return self._generate_report()

    def _add_finding(self, severity: str, title: str, description: str, filepath: str = "", line: int = 0, recommendation: str = ""):
        self.findings.append({
            "severity": severity,
            "title": title,
            "description": description,
            "file": str(filepath),
            "line": line,
            "recommendation": recommendation,
        })
        self.severity_counts[severity] = self.severity_counts.get(severity, 0) + 1

    def _check_config_files(self):
        config_paths = list(self.root.rglob("config.json")) + list(self.root.rglob("*.yaml")) + list(self.root.rglob("*.yml"))
        for path in config_paths:
            try:
                content = path.read_text(encoding="utf-8", errors="ignore")
                if "api_key" in content.lower() and "secret" not in path.name.lower():
                    self._add_finding(
                        "HIGH", "API key in config file",
                        f"Config file {path.name} may contain API keys",
                        path, 1,
                        "Move API keys to environment variables or secure keyring"
                    )
                if "password" in content.lower():
                    self._add_finding(
                        "HIGH", "Password in config file",
                        f"Config file {path.name} contains password field",
                        path, 1,
                        "Remove passwords from config files"
                    )
            except Exception:
                pass

    def _check_env_files(self):
        env_paths = list(self.root.rglob(".env"))
        for path in env_paths:
            content = path.read_text(encoding="utf-8", errors="ignore")
            for line in content.split("\n"):
                if "=" in line and not line.strip().startswith("#"):
                    key, val = line.split("=", 1)
                    if val.strip().strip("'\""):
                        self._add_finding(
                            "CRITICAL", "Secret in .env file",
                            f"Secret {key.strip()} stored in plaintext .env file",
                            path, content.split("\n").index(line) + 1,
                            "Use OS keyring or encrypted vault instead"
                        )
                        break

    def _check_api_key_exposure(self):
        api_key_patterns = [
            (r'(["\'`])sk-[a-zA-Z0-9_\-]{20,}\1', "OpenAI/Groq API key"),
            (r'(["\'`])gsk_[a-zA-Z0-9_\-]{20,}\1', "Groq API key"),
            (r'(["\'`])nvapi-[a-zA-Z0-9_\-]{40,}\1', "NVIDIA API key"),
            (r'(["\'`])AIza[0-9A-Za-z_\-]{35}\1', "Google API key"),
            (r'(["\'`])ghp_[a-zA-Z0-9_\-]{36,}\1', "GitHub token"),
        ]
        for pattern, name in api_key_patterns:
            for f in self.root.rglob("*.py"):
                try:
                    content = f.read_text(encoding="utf-8", errors="ignore")
                    for i, line in enumerate(content.split("\n"), 1):
                        if re.search(pattern, line):
                            self._add_finding(
                                "CRITICAL", f"Hardcoded {name}",
                                f"API key pattern found in source code",
                                f, i,
                                "Use environment variables or secure keyring"
                            )
                except Exception:
                    pass

    def _check_command_injection_risks(self):
        patterns = [
            (r'os\.system\(', "os.system usage"),
            (r'subprocess\.call\(', "subprocess.call usage"),
            (r'subprocess\.Popen\(', "subprocess.Popen usage"),
            (r'eval\(', "eval() usage"),
            (r'exec\(', "exec() usage"),
            (r'__import__\(', "__import__ usage"),
            (r'pickle\.load', "Unsafe pickle loading"),
        ]
        for f in self.root.rglob("*.py"):
            try:
                content = f.read_text(encoding="utf-8", errors="ignore")
                for pattern, name in patterns:
                    for i, line in enumerate(content.split("\n"), 1):
                        if re.search(pattern, line):
                            self._add_finding(
                                "HIGH", f"Dangerous function: {name}",
                                f"Use of {name} can lead to code injection if inputs are not sanitized",
                                f, i,
                                "Validate and sanitize all inputs, prefer safe alternatives"
                            )
            except Exception:
                pass

    def _check_path_traversal(self):
        pattern = r'open\(.*\.\.\./|\.\.\/.*path|\.\.\\'
        for f in self.root.rglob("*.py"):
            try:
                content = f.read_text(encoding="utf-8", errors="ignore")
                for i, line in enumerate(content.split("\n"), 1):
                    if re.search(r'["\'][^"\']*\.\.[\\/"][^"\']*["\']', line):
                        self._add_finding(
                            "MEDIUM", "Potential path traversal",
                            f"Hardcoded path traversal pattern detected",
                            f, i,
                            "Use os.path.realpath() to resolve and validate paths"
                        )
            except Exception:
                pass

    def _check_sql_injection_patterns(self):
        patterns = [
            (r'f["\'].*SELECT.*WHERE.*\{', "f-string SQL query"),
            (r'\+.*\+.*SELECT', "String concatenation SQL"),
            (r'execute\(\s*["\']\s*SELECT', "Raw SQL execution"),
        ]
        for f in self.root.rglob("*.py"):
            try:
                content = f.read_text(encoding="utf-8", errors="ignore")
                for pattern, name in patterns:
                    for i, line in enumerate(content.split("\n"), 1):
                        if re.search(pattern, line, re.IGNORECASE):
                            self._add_finding(
                                "HIGH", f"SQL injection risk: {name}",
                                f"Using string formatting/concatenation in SQL queries",
                                f, i,
                                "Use parameterized queries or ORM"
                            )
            except Exception:
                pass

    def _check_sensitive_data_in_logs(self):
        for f in self.root.rglob("*.py"):
            try:
                content = f.read_text(encoding="utf-8", errors="ignore")
                for i, line in enumerate(content.split("\n"), 1):
                    if "password" in line.lower() and ("print" in line.lower() or "log" in line.lower()):
                        self._add_finding(
                            "MEDIUM", "Password may be logged",
                            f"Password variable printed/logged",
                            f, i,
                            "Sanitize sensitive data before logging"
                        )
            except Exception:
                pass

    def _check_import_safety(self):
        dangerous_imports = ["pickle", "shelve", "marshal", "telnetlib", "ftplib", "smtplib"]
        for f in self.root.rglob("*.py"):
            try:
                content = f.read_text(encoding="utf-8", errors="ignore")
                for i, line in enumerate(content.split("\n"), 1):
                    for d_import in dangerous_imports:
                        if re.search(rf'import\s+{d_import}|from\s+{d_import}\s+import', line):
                            self._add_finding(
                                "LOW", f"Unsafe import: {d_import}",
                                f"Module {d_import} can be unsafe with untrusted data",
                                f, i,
                                f"Consider alternatives to {d_import} if processing untrusted data"
                            )
            except Exception:
                pass

    def _check_permission_issues(self):
        for f in self.root.rglob("*.py"):
            try:
                content = f.read_text(encoding="utf-8", errors="ignore")
                if "chmod(" in content or "os.chmod" in content:
                    for i, line in enumerate(content.split("\n"), 1):
                        if "777" in line:
                            self._add_finding(
                                "MEDIUM", "Overly permissive file mode 777",
                                f"Setting file permissions to 777 allows anyone to modify",
                                f, i,
                                "Use more restrictive permissions like 600 or 644"
                            )
            except Exception:
                pass

    def _check_code_execution_patterns(self):
        patterns = [
            (r'\bcompile\(', "compile()"),
            (r'tempfile\.', "Temporary file usage"),
            (r'mktemp', "Temporary file without cleanup"),
        ]
        for f in self.root.rglob("*.py"):
            try:
                content = f.read_text(encoding="utf-8", errors="ignore")
                for pattern, name in patterns:
                    for i, line in enumerate(content.split("\n"), 1):
                        if re.search(pattern, line):
                            self._add_finding(
                                "LOW", f"Code execution pattern: {name}",
                                f"Dynamic code execution detected",
                                f, i,
                                "Ensure inputs are validated and trusted"
                            )
            except Exception:
                pass

    def _generate_report(self) -> Dict:
        total = sum(self.severity_counts.values())
        return {
            "project": str(self.root),
            "summary": {
                "total_findings": total,
                **self.severity_counts,
                "risk_score": min(
                    (self.severity_counts["CRITICAL"] * 10 +
                     self.severity_counts["HIGH"] * 5 +
                     self.severity_counts["MEDIUM"] * 2 +
                     self.severity_counts["LOW"]) / max(total, 1) * 10, 100
                ),
            },
            "findings": sorted(self.findings, key=lambda x: ["CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO"].index(x["severity"])),
            "recommendations": [
                "Move all secrets to environment variables or secure keyring",
                "Sanitize all user inputs before processing",
                "Validate and resolve all file paths to prevent traversal",
                "Use parameterized queries for any database operations",
                "Remove hardcoded credentials from source code",
                "Implement proper logging without sensitive data",
            ],
        }

    def print_report(self):
        report = self._generate_report()
        s = report["summary"]
        line = "=" * 60
        print(f"\n{line}")
        print(f"  SECURITY AUDIT REPORT")
        print(f"  {report['project']}")
        print(f"{line}")
        print(f"  Risk Score: {s['risk_score']:.1f}/100")
        print(f"  Total Findings: {s['total_findings']}")
        print(f"    CRITICAL: {s['CRITICAL']}")
        print(f"    HIGH:     {s['HIGH']}")
        print(f"    MEDIUM:   {s['MEDIUM']}")
        print(f"    LOW:      {s['LOW']}")
        print(f"{line}")
        for f in report["findings"][:20]:
            severity = f["severity"].ljust(8)
            print(f"  [{severity}] {f['title']}")
            print(f"           {f['file']}:{f['line']}")
        if len(report["findings"]) > 20:
            print(f"  ... and {len(report['findings']) - 20} more findings")
        print(f"\n  Top Recommendations:")
        for i, rec in enumerate(report["recommendations"][:3], 1):
            print(f"  {i}. {rec}")
        print(f"{line}\n")
        return report
