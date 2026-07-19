import tempfile
import unittest
from pathlib import Path

from app import scan_project


class RecoveryManagerTests(unittest.TestCase):
    def test_missing_folder_is_now(self):
        report = scan_project({"name": "Missing", "path": "missing-folder"}, [])
        self.assertEqual(report.priority, "now")

    def test_secret_content_is_not_in_prompt(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "main.py").write_text("print('ok')", encoding="utf-8")
            (root / ".env").write_text("SECRET_VALUE_DO_NOT_SHOW", encoding="utf-8")
            report = scan_project({"name": "Demo", "path": str(root)}, [])
        self.assertNotIn("SECRET_VALUE_DO_NOT_SHOW", report.prompt)
        self.assertIn("Secret-like filename", report.prompt)


if __name__ == "__main__":
    unittest.main()
