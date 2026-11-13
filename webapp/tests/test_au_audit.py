# © 2026 Omar Mokhtar. All rights reserved.
"""Phase AU: tools/audit_dependencies.py says what it found and exits with a code a release step can read."""
import importlib.util
import io
import subprocess
import unittest
from pathlib import Path

PATH = Path(__file__).resolve().parents[2] / "tools" / "audit_dependencies.py"
spec = importlib.util.spec_from_file_location("audit_dependencies", PATH)
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


def fake(code, stdout="", stderr=""):
    return lambda *a, **k: subprocess.CompletedProcess(a[0], code, stdout, stderr)


class TheAudit(unittest.TestCase):
    def run_it(self, run=None, which=lambda name: "/bin/pip-audit"):
        out = io.StringIO()
        return audit.main(run=run or fake(0, "No known vulnerabilities found"), which=which, out=out), out.getvalue()

    def test_clean(self):
        code, text = self.run_it()
        self.assertEqual(code, 0)
        self.assertIn("No known vulnerabilities", text)

    def test_a_vulnerability_is_exit_one(self):
        code, _ = self.run_it(fake(1, "Found 1 known vulnerability in 1 package"))
        self.assertEqual(code, 1)

    def test_no_network_or_no_tool_is_exit_two_not_a_pass(self):
        self.assertEqual(self.run_it(fake(1, "", "ConnectionError: could not reach pypi"))[0], 2)
        code, text = self.run_it(which=lambda name: None)
        self.assertEqual(code, 2)
        self.assertIn("pip install pip-audit", text)

    def test_the_requirements_file_is_the_sites_own(self):
        self.assertTrue(audit.REQUIREMENTS.is_file())


if __name__ == "__main__":
    unittest.main()
