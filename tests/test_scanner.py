import contextlib
import io
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from repoguard.cli import main
from repoguard.scanner import render, scan, scan_bytes


class ScannerTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.git("init")
        self.git("config", "user.name", "Test")
        self.git("config", "user.email", "test@tests.invalid")
        for name in ["README.md", "LICENSE", ".gitignore"]:
            (self.root / name).write_text("Repository metadata\n")
        self.git("add", ".")
        self.git("commit", "-m", "Initial")

    def tearDown(self):
        self.temporary.cleanup()

    def git(self, *args):
        result = subprocess.run(["git", "-C", str(self.root), *args], capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr.decode())
        return result.stdout

    def test_staged_blob_is_scanned_instead_of_working_copy(self):
        token = "ghp_" + "A" * 36
        path = self.root / "settings.txt"
        path.write_text(token)
        self.git("add", "settings.txt")
        path.write_text("clean now")
        report = scan(self.root)
        self.assertTrue(any(item["rule"] == "github-token" for item in report["issues"]))
        self.assertNotIn(token, render(report))
        self.assertNotIn(token, render(report, True))

    def test_unstaged_files_are_not_scanned(self):
        (self.root / "private.txt").write_text("ghp_" + "A" * 36)
        self.assertEqual(scan(self.root)["scanned"], 0)

    def test_environment_file_is_reported(self):
        (self.root / ".env").write_text("APP_NAME=local")
        self.git("add", ".env")
        self.assertIn("environment-file", [issue["rule"] for issue in scan(self.root)["issues"]])

    def test_binary_files_do_not_produce_text_matches(self):
        content = b"\x00" + b"ghp_" + b"A" * 36
        self.assertEqual(scan_bytes(content, "binary.bin"), [])

    def test_private_key_rule_reports_line_without_content(self):
        result = scan_bytes(b"header\n-----BEGIN PRIVATE KEY-----\nsecret", "key.pem")
        self.assertEqual(result[0]["line"], 2)
        self.assertEqual(result[0]["rule"], "private-key")
        self.assertNotIn("BEGIN PRIVATE", json.dumps(result))

    def test_large_file_is_rejected_before_content_scan(self):
        (self.root / "large.bin").write_bytes(b"x" * (6 * 1024**2))
        self.git("add", "large.bin")
        self.assertEqual(scan(self.root)["issues"][0]["rule"], "large-file")

    def test_configured_ignore_is_explicit_and_counted(self):
        (self.root / ".repoguard.toml").write_text('ignore=["fixtures/*"]\nmax_file_mb=5\n')
        (self.root / "fixtures").mkdir()
        (self.root / "fixtures" / "key.txt").write_text("ghp_" + "A" * 36)
        self.git("add", "fixtures")
        report = scan(self.root)
        self.assertEqual(report["ignored"], 1)
        self.assertEqual(report["issues"], [])

    def test_all_scope_includes_existing_index_files(self):
        self.assertEqual(scan(self.root, True)["scanned"], 3)

    def test_cli_returns_failure_without_printing_token(self):
        token = "ghp_" + "B" * 36
        (self.root / "secret.txt").write_text(token)
        self.git("add", "secret.txt")
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            code = main(["--path", str(self.root), "scan", "--json"])
        self.assertEqual(code, 1)
        self.assertNotIn(token, output.getvalue())
        json.loads(output.getvalue())

    def test_existing_hook_is_never_overwritten(self):
        hook = self.root / ".git" / "hooks" / "pre-commit"
        hook.write_text("preserve-me")
        with contextlib.redirect_stderr(io.StringIO()):
            code = main(["--path", str(self.root), "hook", "--install"])
        self.assertEqual(code, 2)
        self.assertEqual(hook.read_text(), "preserve-me")
