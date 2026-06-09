"""Comprehensive tests for FileTools."""

import sys, os, tempfile, csv, unittest
from unittest.mock import patch, MagicMock
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from tools.files import FileTools, _safe_resolve


class TestSafeResolve(unittest.TestCase):
    def test_resolve_home_relative(self):
        result = _safe_resolve("~/test.txt")
        self.assertTrue(result.startswith(os.path.expanduser("~")))

    def test_resolve_absolute_in_home(self):
        home = os.path.expanduser("~")
        test_path = os.path.join(home, "test_resolve.txt")
        result = _safe_resolve(test_path)
        self.assertEqual(result, os.path.realpath(test_path))


class TestFileToolsInit(unittest.TestCase):
    def test_init_creates_instance(self):
        f = FileTools()
        self.assertIsNone(f._fitz)
        self.assertIsNone(f._pillow)
        self.assertIsNone(f._pytesseract)
        self.assertIsNone(f._pandas)
        self.assertIsNone(f._docx)

    def test_get_tool_definitions_returns_list(self):
        f = FileTools()
        defs = f.get_tool_definitions()
        self.assertIsInstance(defs, list)
        self.assertEqual(len(defs), 3)
        names = [d["function"]["name"] for d in defs]
        self.assertIn("read_file", names)
        self.assertIn("ocr_image", names)
        self.assertIn("read_spreadsheet", names)

    def test_get_handler_read_file(self):
        f = FileTools()
        handler = f.get_handler("read_file")
        self.assertTrue(callable(handler))

    def test_get_handler_ocr_image(self):
        f = FileTools()
        handler = f.get_handler("ocr_image")
        self.assertTrue(callable(handler))

    def test_get_handler_spreadsheet(self):
        f = FileTools()
        handler = f.get_handler("read_spreadsheet")
        self.assertTrue(callable(handler))

    def test_get_handler_unknown_returns_none(self):
        f = FileTools()
        self.assertIsNone(f.get_handler("nonexistent"))


class TestReadTextFile(unittest.TestCase):
    def setUp(self):
        self.f = FileTools()
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_read_txt_file(self):
        path = os.path.join(self.tmpdir, "test.txt")
        with open(path, "w") as fh:
            fh.write("Hello, World!")
        result = self.f.read_file(path)
        self.assertIn("Hello, World!", result)
        self.assertIn("test.txt", result)

    def test_read_python_file(self):
        path = os.path.join(self.tmpdir, "test.py")
        with open(path, "w") as fh:
            fh.write("def hello():\n    return 'world'\n")
        result = self.f.read_file(path)
        self.assertIn("def hello", result)

    def test_read_json_file(self):
        path = os.path.join(self.tmpdir, "test.json")
        with open(path, "w") as fh:
            fh.write('{"key": "value"}')
        result = self.f.read_file(path)
        self.assertIn("key", result)
        self.assertIn("value", result)

    def test_read_csv_file(self):
        path = os.path.join(self.tmpdir, "test.csv")
        with open(path, "w", newline="") as fh:
            writer = csv.writer(fh)
            writer.writerow(["name", "age"])
            writer.writerow(["Alice", 30])
        result = self.f.read_file(path)
        self.assertIn("name", result)
        self.assertIn("Alice", result)

    def test_read_md_file(self):
        path = os.path.join(self.tmpdir, "test.md")
        with open(path, "w") as fh:
            fh.write("# Title\n\nSome content here.")
        result = self.f.read_file(path)
        self.assertIn("Title", result)
        self.assertIn("content", result)

    def test_read_nonexistent_file(self):
        home = os.path.expanduser("~")
        path = os.path.join(home, "_nonexistent_test_file_12345.txt")
        result = self.f.read_file(path)
        self.assertIn("File not found", result)

    def test_read_unsupported_extension(self):
        path = os.path.join(self.tmpdir, "test.xyz")
        with open(path, "w") as fh:
            fh.write("data")
        result = self.f.read_file(path)
        self.assertIn("Unsupported", result)

    def test_read_file_truncates_long_content(self):
        path = os.path.join(self.tmpdir, "long.txt")
        with open(path, "w") as fh:
            fh.write("x" * 20000)
        result = self.f.read_file(path)
        self.assertLessEqual(len(result), 15000)


class TestCSVSpreadsheet(unittest.TestCase):
    def setUp(self):
        self.f = FileTools()
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_read_csv_spreadsheet(self):
        path = os.path.join(self.tmpdir, "data.csv")
        with open(path, "w", newline="") as fh:
            writer = csv.writer(fh)
            writer.writerow(["Name", "Score"])
            writer.writerow(["Alice", 95])
            writer.writerow(["Bob", 87])
        result = self.f.read_spreadsheet(path)
        self.assertIn("2 rows", result)
        self.assertIn("Name", result)
        self.assertIn("Score", result)


if __name__ == "__main__":
    unittest.main()
