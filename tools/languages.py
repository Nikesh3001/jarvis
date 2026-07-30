"""Multi-language IDE tools for FRIDAY.

Provides lint, format, project scaffolding, and package management
for all major programming languages.
"""
import os
import sys
import subprocess
import tempfile
import shutil
from pathlib import Path
from core.platform_utils import is_windows, is_macos, is_linux
from core.ratelimit import check_rate


# Language detection by file extension
EXTENSION_MAP = {
    ".py": "python", ".pyw": "python",
    ".js": "javascript", ".mjs": "javascript", ".cjs": "javascript",
    ".ts": "typescript", ".tsx": "typescript", ".jsx": "javascript",
    ".go": "go",
    ".rs": "rust",
    ".java": "java",
    ".c": "c", ".h": "c",
    ".cpp": "cpp", ".cxx": "cpp", ".cc": "cpp", ".hpp": "cpp",
    ".cs": "csharp",
    ".rb": "ruby",
    ".php": "php",
    ".swift": "swift",
    ".kt": "kotlin", ".kts": "kotlin",
    ".scala": "scala",
    ".r": "r", ".R": "r",
    ".dart": "dart",
    ".lua": "lua",
    ".hs": "haskell",
    ".ex": "elixir", ".exs": "elixir",
    ".sql": "sql",
    ".sh": "bash", ".bash": "bash", ".zsh": "zsh",
    ".ps1": "powershell",
    ".html": "html", ".htm": "html",
    ".css": "css", ".scss": "scss", ".less": "less",
    ".vue": "vue",
    ".svelte": "svelte",
    ".sol": "solidity",
    ".cob": "cobol", ".cbl": "cobol",
    ".f90": "fortran", ".f": "fortran",
    ".asm": "assembly", ".s": "assembly",
    ".m": "matlab",
    ".jl": "julia",
    ".nim": "nim",
    ".zig": "zig",
    ".v": "v",
    ".ml": "ocaml",
    ".clj": "clojure",
    ".erl": "erlang",
}

# Project root detection files
PROJECT_MARKERS = {
    "python": ["pyproject.toml", "setup.py", "setup.cfg", "requirements.txt", "Pipfile"],
    "javascript": ["package.json"],
    "typescript": ["tsconfig.json", "package.json"],
    "go": ["go.mod"],
    "rust": ["Cargo.toml"],
    "java": ["pom.xml", "build.gradle", "build.gradle.kts"],
    "csharp": ["*.csproj", "*.sln"],
    "ruby": ["Gemfile"],
    "php": ["composer.json"],
    "swift": ["Package.swift"],
    "kotlin": ["build.gradle.kts", "build.gradle"],
    "dart": ["pubspec.yaml"],
    "elixir": ["mix.exs"],
    "scala": ["build.sbt"],
    "r": ["DESCRIPTION"],
}

# Package managers per language
PACKAGE_MANAGERS = {
    "python": {"install": "pip install {pkg}", "uninstall": "pip uninstall {pkg}", "list": "pip list", "search": "pip index versions {pkg}"},
    "javascript": {"install": "npm install {pkg}", "uninstall": "npm uninstall {pkg}", "list": "npm list --depth=0", "search": "npm search {pkg}"},
    "typescript": {"install": "npm install {pkg}", "uninstall": "npm uninstall {pkg}", "list": "npm list --depth=0", "search": "npm search {pkg}"},
    "go": {"install": "go get {pkg}", "uninstall": "go mod tidy", "list": "go list -m all", "search": ""},
    "rust": {"install": "cargo add {pkg}", "uninstall": "cargo rm {pkg}", "list": "cargo tree --depth=1", "search": "cargo search {pkg}"},
    "java": {"install": "", "uninstall": "", "list": "", "search": ""},
    "ruby": {"install": "gem install {pkg}", "uninstall": "gem uninstall {pkg}", "list": "gem list", "search": "gem search {pkg}"},
    "php": {"install": "composer require {pkg}", "uninstall": "composer remove {pkg}", "list": "composer show", "search": "composer search {pkg}"},
    "dart": {"install": "dart pub add {pkg}", "uninstall": "dart pub remove {pkg}", "list": "dart pub deps", "search": ""},
    "swift": {"install": "", "uninstall": "", "list": "swift package show-dependencies", "search": ""},
    "kotlin": {"install": "", "uninstall": "", "list": "", "search": ""},
    "elixir": {"install": "mix deps.get", "uninstall": "", "list": "mix deps", "search": ""},
}

# Linters per language
LINTERS = {
    "python": {"cmd": "python -m py_compile {file}", "name": "py_compile"},
    "javascript": {"cmd": "node --check {file}", "name": "node --check"},
    "typescript": {"cmd": "npx tsc --noEmit {file}", "name": "tsc"},
    "go": {"cmd": "go vet ./...", "name": "go vet"},
    "rust": {"cmd": "cargo clippy -- -D warnings", "name": "clippy"},
    "java": {"cmd": "javac -Xlint:all {file}", "name": "javac lint"},
    "ruby": {"cmd": "ruby -c {file}", "name": "ruby -c"},
    "php": {"cmd": "php -l {file}", "name": "php lint"},
    "swift": {"cmd": "swiftc -syntax-only {file}", "name": "swiftc syntax"},
    "kotlin": {"cmd": "kotlinc -script {file}", "name": "kotlinc"},
    "bash": {"cmd": "bash -n {file}", "name": "bash -n"},
    "powershell": {"cmd": "powershell -NoProfile -Command \"Get-Command {file} -ErrorAction Stop\"", "name": "PS syntax"},
    "dart": {"cmd": "dart analyze {file}", "name": "dart analyze"},
    "lua": {"cmd": "luac -p {file}", "name": "luac"},
    "r": {"cmd": "Rscript -e 'parse(file=\"{file}\")'", "name": "R parse"},
}

# Formatters per language
FORMATTERS = {
    "python": {"cmd": "python -m black --quiet {file}", "name": "black"},
    "javascript": {"cmd": "npx prettier --write {file}", "name": "prettier"},
    "typescript": {"cmd": "npx prettier --write {file}", "name": "prettier"},
    "go": {"cmd": "gofmt -w {file}", "name": "gofmt"},
    "rust": {"cmd": "cargo fmt -- {file}", "name": "rustfmt"},
    "ruby": {"cmd": "rubocop -A {file}", "name": "rubocop"},
    "php": {"cmd": "php-cs-fixer fix {file}", "name": "php-cs-fixer"},
    "swift": {"cmd": "swiftformat {file}", "name": "swiftformat"},
    "kotlin": {"cmd": "ktlint --format {file}", "name": "ktlint"},
    "dart": {"cmd": "dart format {file}", "name": "dart format"},
    "css": {"cmd": "npx prettier --write {file}", "name": "prettier"},
    "html": {"cmd": "npx prettier --write {file}", "name": "prettier"},
    "sql": {"cmd": "", "name": "none"},
}

# Scaffolding templates
SCAFFOLD_TEMPLATES = {
    "python": {
        "name": "Python Project",
        "files": {
            "pyproject.toml": '[build-system]\nrequires = ["setuptools>=68.0"]\nbuild-backend = "setuptools.backends._legacy:_Backend"\n\n[project]\nname = "{name}"\nversion = "0.1.0"\ndescription = "{description}"\nrequires-python = ">=3.10"\n\n[tool.pytest.ini_options]\ntestpaths = ["tests"]\n',
            "src/__init__.py": "",
            "src/main.py": 'def main():\n    print("Hello from {name}!")\n\nif __name__ == "__main__":\n    main()\n',
            "tests/__init__.py": "",
            "tests/test_main.py": 'from src.main import main\n\ndef test_main(capsys):\n    main()\n    captured = capsys.readouterr()\n    assert "Hello" in captured.out\n',
            ".gitignore": "__pycache__/\n*.pyc\nvenv/\n.venv/\n*.egg-info/\ndist/\nbuild/\n.env\n",
        }
    },
    "javascript": {
        "name": "Node.js Project",
        "files": {
            "package.json": '{{"name": "{name}", "version": "1.0.0", "description": "{description}", "main": "src/index.js", "scripts": {{"start": "node src/index.js", "test": "jest", "lint": "eslint src/"}}}}\n',
            "src/index.js": 'console.log("Hello from {name}!");\n\nmodule.exports = {{}};\n',
            "src/index.test.js": "describe('{name}', () => {\n  test('should work', () => {\n    expect(true).toBe(true);\n  });\n});\n",
            ".gitignore": "node_modules/\n.env\ndist/\ncoverage/\n",
            ".eslintrc.json": '{{"env": {{"node": true, "es2024": true}}, "extends": "eslint:recommended", "parserOptions": {{"ecmaVersion": 2024}}}}\n',
        }
    },
    "go": {
        "name": "Go Project",
        "files": {
            "go.mod": "module {name}\n\ngo 1.22\n",
            "main.go": 'package main\n\nimport "fmt"\n\nfunc main() {\n\tfmt.Println("Hello from {name}!")\n}\n',
            "main_test.go": 'package main\n\nimport "testing"\n\nfunc TestMain(t *testing.T) {\n\tt.Log("Test passed")\n}\n',
            ".gitignore": "*.exe\n*.test\n*.out\nvendor/\n",
        }
    },
    "rust": {
        "name": "Rust Project",
        "files": {
            "Cargo.toml": '[package]\nname = "{name}"\nversion = "0.1.0"\nedition = "2021"\ndescription = "{description}"\n\n[dependencies]\n',
            "src/main.rs": 'fn main() {\n    println!("Hello from {name}!");\n}\n',
            "src/lib.rs": 'pub fn hello() -> String {\n    "Hello from {name}!".to_string()\n}\n\n#[cfg(test)]\nmod tests {\n    use super::*;\n\n    #[test]\n    fn test_hello() {\n        assert!(hello().contains("Hello"));\n    }\n}\n',
            ".gitignore": "target/\nCargo.lock\n",
        }
    },
    "java": {
        "name": "Java Project",
        "files": {
            "pom.xml": '<?xml version="1.0" encoding="UTF-8"?>\n<project xmlns="http://maven.apache.org/POM/4.0.0"\n         xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"\n         xsi:schemaLocation="http://maven.apache.org/POM/4.0.0 http://maven.apache.org/xsd/maven-4.0.0.xsd">\n    <modelVersion>4.0.0</modelVersion>\n    <groupId>com.example</groupId>\n    <artifactId>{name}</artifactId>\n    <version>1.0-SNAPSHOT</version>\n    <properties>\n        <maven.compiler.source>21</maven.compiler.source>\n        <maven.compiler.target>21</maven.compiler.target>\n    </properties>\n</project>\n',
            "src/main/java/com/example/App.java": 'package com.example;\n\npublic class App {\n    public static void main(String[] args) {\n        System.out.println("Hello from {name}!");\n    }\n}\n',
            ".gitignore": "target/\n*.class\n*.jar\n.idea/\n*.iml\n",
        }
    },
    "csharp": {
        "name": "C# Project",
        "files": {
            "{name}.csproj": '<Project Sdk="Microsoft.NET.Sdk">\n  <PropertyGroup>\n    <OutputType>Exe</OutputType>\n    <TargetFramework>net8.0</TargetFramework>\n    <RootNamespace>{name}</RootNamespace>\n  </PropertyGroup>\n</Project>\n',
            "Program.cs": 'Console.WriteLine("Hello from {name}!");\n',
            ".gitignore": "bin/\nobj/\n*.user\n.vs/\n",
        }
    },
    "ruby": {
        "name": "Ruby Project",
        "files": {
            "Gemfile": 'source "https://rubygems.org"\n\ngem "rake"\ngem "rspec"\n',
            "lib/{name}.rb": 'module {name}\n  def self.hello\n    "Hello from {name}!"\n  end\nend\n',
            "spec/{name}_spec.rb": "require_relative '../lib/{name}'\n\nRSpec.describe {name} do\n  it 'says hello' do\n    expect({name}.hello).to include('Hello')\n  end\nend\n",
            ".gitignore": "*.gem\nvendor/\nbundle/\n",
        }
    },
    "php": {
        "name": "PHP Project",
        "files": {
            "composer.json": '{{"name": "example/{name}", "description": "{description}", "require": {{"php": ">=8.1"}}, "autoload": {{"psr-4": {{"App\\\\": "src/"}}}}}}\n',
            "src/App.php": '<?php\n\nnamespace App;\n\nclass App {\n    public function hello(): string {\n        return "Hello from {name}!";\n    }\n}\n',
            ".gitignore": "vendor/\ncomposer.lock\n",
        }
    },
    "typescript": {
        "name": "TypeScript Project",
        "files": {
            "package.json": '{{"name": "{name}", "version": "1.0.0", "main": "dist/index.js", "scripts": {{"build": "tsc", "start": "node dist/index.js", "test": "jest"}}}}\n',
            "tsconfig.json": '{{"compilerOptions": {{"target": "ES2024", "module": "commonjs", "strict": true, "outDir": "dist", "rootDir": "src"}}, "include": ["src"]}}\n',
            "src/index.ts": 'console.log("Hello from {name}!");\n',
            ".gitignore": "node_modules/\ndist/\n.env\n",
        }
    },
    "dart": {
        "name": "Dart/Flutter Project",
        "files": {
            "pubspec.yaml": 'name: {name}\ndescription: {description}\nversion: 1.0.0\n\nenvironment:\n  sdk: ">=3.0.0 <4.0.0"\n\ndependencies:\n  \n',
            "bin/main.dart": 'void main() {\n  print("Hello from {name}!");\n}\n',
            "test/main_test.dart": "import 'package:test/test.dart';\n\nvoid main() {\n  test('hello', () {\n    expect(true, isTrue);\n  });\n}\n",
            ".gitignore": ".dart_tool/\n.packages\nbuild/\n",
        }
    },
    "swift": {
        "name": "Swift Project",
        "files": {
            "Package.swift": '// swift-tools-version: 5.9\nimport PackageDescription\n\nlet package = Package(\n    name: "{name}",\n    targets: [\n        .executableTarget(name: "{name}"),\n        .testTarget(name: "{name}Tests", dependencies: ["{name}"]),\n    ]\n)\n',
            "Sources/main.swift": 'print("Hello from {name}!")\n',
            "Tests/{name}Tests/{name}Tests.swift": 'import XCTest\n@testable import {name}\n\nfinal class {name}Tests: XCTestCase {\n    func testExample() {\n        XCTAssert(true)\n    }\n}\n',
            ".gitignore": ".build/\n.swiftpm/\nPackages/\n",
        }
    },
    "kotlin": {
        "name": "Kotlin Project",
        "files": {
            "build.gradle.kts": 'plugins {\n    kotlin("jvm") version "1.9.22"\n    application\n}\n\nrepositories {\n    mavenCentral()\n}\n\napplication {\n    mainClass.set("MainKt")\n}\n',
            "src/main/kotlin/Main.kt": 'fun main() {\n    println("Hello from {name}!")\n}\n',
            ".gitignore": "build/\n.gradle/\n.idea/\n*.iml\n",
        }
    },
    "scala": {
        "name": "Scala Project",
        "files": {
            "build.sbt": 'name := "{name}"\nversion := "0.1.0"\nscalaVersion := "3.3.1"\n',
            "src/main/scala/Main.scala": '@main def main(): Unit =\n  println("Hello from {name}!")\n',
            ".gitignore": "target/\n.bsp/\n.idea/\n",
        }
    },
    "elixir": {
        "name": "Elixir Project",
        "files": {
            "mix.exs": 'defmodule {name}.MixProject do\n  use Mix.Project\n\n  def project do\n    [\n      app: :{name},\n      version: "0.1.0",\n      elixir: "~> 1.16",\n      start_permanent: Mix.env() == :prod,\n    ]\n  end\n\n  def application do\n    [extra_applications: [:logger]]\n  end\nend\n',
            "lib/{name}.ex": 'defmodule {name} do\n  def hello do\n    "Hello from {name}!"\n  end\nend\n',
            "test/{name}_test.exs": 'defmodule {name}Test do\n  use ExUnit.Case\n  doctest {name}\n\n  test "hello" do\n    assert {name}.hello() |> String.contains?("Hello")\n  end\nend\n',
            ".gitignore": "_build/\ndeps/\n*.ez\n",
        }
    },
    "lua": {
        "name": "Lua Project",
        "files": {
            "main.lua": 'print("Hello from {name}!")\n',
            ".gitignore": "*.luac\n",
        }
    },
    "haskell": {
        "name": "Haskell Project",
        "files": {
            "{name}.cabal": 'cabal-version: 2.4\nname: {name}\nversion: 0.1.0.0\n\nexecutable {name}\n  main-is: Main.hs\n  build-depends: base >=4.17\n  default-language: Haskell2010\n',
            "Main.hs": 'module Main where\n\nmain :: IO ()\nmain = putStrLn "Hello from {name}!"\n',
            ".gitignore": "dist-newstyle/\n.stack-work/\n",
        }
    },
}


class LanguageTools:
    """Multi-language IDE tools for FRIDAY."""

    def detect_language(self, file_path):
        """Detect programming language from file extension."""
        ext = Path(file_path).suffix.lower()
        lang = EXTENSION_MAP.get(ext)
        if lang:
            return f"Detected language: {lang} (from {ext})"
        return f"Unknown language for extension: {ext}"

    def detect_project(self, path="."):
        """Detect project type from root markers."""
        root = Path(path).resolve()
        found = []
        for lang, markers in PROJECT_MARKERS.items():
            for marker in markers:
                if "*" in marker:
                    matches = list(root.glob(marker))
                    if matches:
                        found.append(f"{lang} ({marker})")
                elif (root / marker).exists():
                    found.append(f"{lang} ({marker})")
        if found:
            return f"Project types detected:\n" + "\n".join(f"  - {f}" for f in found)
        return "No known project type detected in this directory."

    @staticmethod
    def _validate_path(path_str):
        """Reject paths containing shell metacharacters."""
        bad = set(';&|`$(){}[]!#~<>\'"\n\r\x00')
        if any(c in path_str for c in bad):
            raise ValueError(f"Path contains invalid characters: {path_str}")

    @staticmethod
    def _validate_package_name(name):
        """Reject package names containing shell metacharacters."""
        import re as _re
        if not _re.match(r'^[a-zA-Z0-9._\-]+$', name):
            raise ValueError(f"Package name contains invalid characters: {name}")

    def lint(self, file_path, language=None):
        """Lint a file using the appropriate linter."""
        if not check_rate("language_lint", rate=2, burst=5):
            return "Rate limit exceeded. Please wait before linting more files."
        path = Path(file_path).resolve()
        if not path.exists():
            return f"File not found: {file_path}"
        if language is None:
            ext = path.suffix.lower()
            language = EXTENSION_MAP.get(ext)
        if language is None:
            return f"Cannot detect language for: {file_path}"
        linter = LINTERS.get(language)
        if not linter:
            return f"No linter configured for {language}. Available: {', '.join(sorted(LINTERS.keys()))}"
        try:
            self._validate_path(str(path))
        except ValueError as e:
            return f"Blocked: {e}"
        cmd = linter["cmd"].replace("{file}", str(path))
        try:
            import shlex as _shlex
            cmd_parts = _shlex.split(cmd)
            r = subprocess.run(
                cmd_parts, shell=False, capture_output=True, text=True, timeout=30,
                cwd=str(path.parent)
            )
            out = []
            if r.stdout.strip():
                out.append(f"Output:\n{r.stdout.strip()[:3000]}")
            if r.stderr.strip():
                out.append(f"Errors:\n{r.stderr.strip()[:2000]}")
            if r.returncode == 0:
                return f"Lint ({linter['name']}): No issues found for {path.name}"
            result = "\n".join(out) if out else "Lint completed with issues"
            return f"Lint ({linter['name']}) exit {r.returncode}:\n{result}"
        except FileNotFoundError:
            return f"Linter '{linter['name']}' not installed. Install it first."
        except subprocess.TimeoutExpired:
            return f"Lint timed out after 30s"
        except Exception as e:
            return f"Lint failed: {e}"

    def format_file(self, file_path, language=None):
        """Format a file using the appropriate formatter."""
        if not check_rate("language_format", rate=2, burst=5):
            return "Rate limit exceeded. Please wait before formatting more files."
        path = Path(file_path).resolve()
        if not path.exists():
            return f"File not found: {file_path}"
        if language is None:
            ext = path.suffix.lower()
            language = EXTENSION_MAP.get(ext)
        if language is None:
            return f"Cannot detect language for: {file_path}"
        formatter = FORMATTERS.get(language)
        if not formatter or not formatter["cmd"]:
            return f"No formatter configured for {language}"
        try:
            self._validate_path(str(path))
        except ValueError as e:
            return f"Blocked: {e}"
        cmd = formatter["cmd"].replace("{file}", str(path))
        try:
            import shlex as _shlex
            cmd_parts = _shlex.split(cmd)
            r = subprocess.run(
                cmd_parts, shell=False, capture_output=True, text=True, timeout=30,
                cwd=str(path.parent)
            )
            out = []
            if r.stdout.strip():
                out.append(r.stdout.strip()[:2000])
            if r.stderr.strip():
                out.append(r.stderr.strip()[:2000])
            if r.returncode == 0:
                return f"Formatted {path.name} with {formatter['name']}"
            return f"Format ({formatter['name']}) exit {r.returncode}:\n" + "\n".join(out)
        except FileNotFoundError:
            return f"Formatter '{formatter['name']}' not installed. Install it first."
        except subprocess.TimeoutExpired:
            return f"Format timed out after 30s"
        except Exception as e:
            return f"Format failed: {e}"

    def scaffold(self, language, name="my_project", description="A new project", path=None):
        """Create a new project scaffold for the given language."""
        template = SCAFFOLD_TEMPLATES.get(language)
        if not template:
            available = ", ".join(sorted(SCAFFOLD_TEMPLATES.keys()))
            return f"Language '{language}' not supported. Available: {available}"
        if not name or "/" in name or "\\" in name or ".." in name:
            return f"Invalid project name: {name}"
        if path is None:
            path = Path.cwd() / name
        else:
            path = Path(path) / name
        if path.exists():
            return f"Directory already exists: {path}"
        created = []
        for file_path, content in template["files"].items():
            file_path = file_path.replace("{name}", name)
            full_path = path / file_path
            full_path.parent.mkdir(parents=True, exist_ok=True)
            content = content.replace("{name}", name).replace("{description}", description)
            full_path.write_text(content, encoding="utf-8")
            created.append(str(full_path.relative_to(path)))
        return f"Scaffolded {language} project '{name}' at {path}\nFiles created:\n" + "\n".join(f"  {f}" for f in created)

    def package_install(self, package, language="python", path=None):
        """Install a package using the language's package manager."""
        if not check_rate("package_install", rate=0.5, burst=2):
            return "Rate limit exceeded. Please wait before installing more packages."
        pm = PACKAGE_MANAGERS.get(language)
        if not pm or not pm["install"]:
            return f"No package manager configured for {language}"
        try:
            self._validate_package_name(package)
        except ValueError as e:
            return f"Blocked: {e}"
        cmd = pm["install"].replace("{pkg}", package)
        cwd = str(path) if path else None
        try:
            import shlex as _shlex
            cmd_parts = _shlex.split(cmd)
            r = subprocess.run(
                cmd_parts, shell=False, capture_output=True, text=True, timeout=120, cwd=cwd
            )
            out = []
            if r.stdout.strip():
                out.append(r.stdout.strip()[:3000])
            if r.stderr.strip():
                out.append(r.stderr.strip()[:2000])
            if r.returncode == 0:
                return f"Installed {package} ({language})"
            return f"Install exit {r.returncode}:\n" + "\n".join(out)
        except FileNotFoundError:
            return f"Package manager for {language} not found. Install it first."
        except subprocess.TimeoutExpired:
            return f"Install timed out after 120s"
        except Exception as e:
            return f"Install failed: {e}"

    def package_list(self, language="python", path=None):
        """List installed packages."""
        pm = PACKAGE_MANAGERS.get(language)
        if not pm or not pm["list"]:
            return f"No package manager configured for {language}"
        cmd = pm["list"]
        cwd = str(path) if path else None
        try:
            r = subprocess.run(
                cmd, shell=True, capture_output=True, text=True, timeout=30, cwd=cwd
            )
            output = r.stdout.strip()[:5000] if r.stdout.strip() else "No packages found"
            return f"Installed packages ({language}):\n{output}"
        except Exception as e:
            return f"List failed: {e}"

    def run_file(self, file_path, timeout=30):
        """Run a source file using the appropriate interpreter/compiler."""
        if not check_rate("run_file", rate=1, burst=3):
            return "Rate limit exceeded."
        path = Path(file_path).resolve()
        if not path.exists():
            return f"File not found: {file_path}"
        ext = path.suffix.lower()
        language = EXTENSION_MAP.get(ext)
        if not language:
            return f"Cannot determine interpreter for: {ext}"

        runners = {
            "python": [sys.executable, str(path)],
            "javascript": ["node", str(path)],
            "typescript": ["npx", "tsx", str(path)],
            "go": ["go", "run", str(path)],
            "ruby": ["ruby", str(path)],
            "php": ["php", str(path)],
            "lua": ["lua", str(path)],
            "bash": ["bash", str(path)],
            "dart": ["dart", "run", str(path)],
            "swift": ["swift", str(path)],
        }

        cmd = runners.get(language)
        if not cmd:
            return f"No runner configured for {language}. Use run_script with the appropriate language."

        try:
            r = subprocess.run(
                cmd, capture_output=True, text=True, timeout=timeout
            )
            out = []
            if r.stdout.strip():
                out.append(f"Output:\n{r.stdout.strip()[:5000]}")
            if r.stderr.strip():
                out.append(f"Stderr:\n{r.stderr.strip()[:2000]}")
            if r.returncode == 0:
                return "\n".join(out) if out else "Program ran successfully (no output)"
            return f"Exit code {r.returncode}:\n" + "\n".join(out)
        except FileNotFoundError:
            return f"Interpreter for {language} not found. Install it first."
        except subprocess.TimeoutExpired:
            return f"Execution timed out after {timeout}s"
        except Exception as e:
            return f"Execution failed: {e}"

    def get_tool_definitions(self):
        return [
            {"type": "function", "function": {"name": "detect_language", "description": "Detect programming language from file extension", "parameters": {"type": "object", "properties": {"file_path": {"type": "string", "description": "Path to file"}}, "required": ["file_path"]}}},
            {"type": "function", "function": {"name": "detect_project", "description": "Detect project type from root directory markers", "parameters": {"type": "object", "properties": {"path": {"type": "string", "description": "Project root path", "default": "."}}}}},
            {"type": "function", "function": {"name": "lint_file", "description": "Lint a source file using language-appropriate linter", "parameters": {"type": "object", "properties": {"file_path": {"type": "string", "description": "Path to source file"}, "language": {"type": "string", "description": "Language override (auto-detected if omitted)"}}}}},
            {"type": "function", "function": {"name": "format_file", "description": "Format a source file using language-appropriate formatter", "parameters": {"type": "object", "properties": {"file_path": {"type": "string", "description": "Path to source file"}, "language": {"type": "string", "description": "Language override"}}}}},
            {"type": "function", "function": {"name": "scaffold_project", "description": "Create a new project scaffold with boilerplate files for any language", "parameters": {"type": "object", "properties": {"language": {"type": "string", "description": "Language: python/javascript/typescript/go/rust/java/csharp/ruby/php/swift/kotlin/dart/elixir/scala/lua/haskell"}, "name": {"type": "string", "description": "Project name", "default": "my_project"}, "description": {"type": "string", "description": "Project description", "default": "A new project"}}, "required": ["language"]}}},
            {"type": "function", "function": {"name": "package_install", "description": "Install a package using the language's package manager", "parameters": {"type": "object", "properties": {"package": {"type": "string", "description": "Package name"}, "language": {"type": "string", "description": "Language", "default": "python"}}, "required": ["package"]}}},
            {"type": "function", "function": {"name": "package_list", "description": "List installed packages for a language", "parameters": {"type": "object", "properties": {"language": {"type": "string", "description": "Language", "default": "python"}}}}},
            {"type": "function", "function": {"name": "run_file", "description": "Execute a source file using the appropriate interpreter/compiler", "parameters": {"type": "object", "properties": {"file_path": {"type": "string", "description": "Path to source file"}, "timeout": {"type": "integer", "description": "Timeout in seconds", "default": 30}}, "required": ["file_path"]}}},
        ]

    def get_handler(self, name):
        handlers = {
            "detect_language": self.detect_language,
            "detect_project": self.detect_project,
            "lint_file": self.lint,
            "format_file": self.format_file,
            "scaffold_project": self.scaffold,
            "package_install": self.package_install,
            "package_list": self.package_list,
            "run_file": self.run_file,
        }
        return handlers.get(name)
