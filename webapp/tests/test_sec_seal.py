# © 2026 Omar Mokhtar. All rights reserved.
"""Security hardening (2026-11-11): deploy/seal_package.sh makes the installed code root-owned and read-only for the website's account, deletes compiled
copies, and its --check finds what is wrong. Run on made-up package folders. Needs root (it changes ownership) and skips with that reason without it."""
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

SEAL = Path(__file__).resolve().parents[2] / "deploy" / "seal_package.sh"


def package(root: Path) -> Path:
    pkg = root / "package"
    for rel in ("webapp/app.py", "runners/rc922_runner.py", "tools/check.py", "MANIFEST.json"):
        (pkg / rel).parent.mkdir(parents=True, exist_ok=True)
        (pkg / rel).write_text("x = 1\n")
    return pkg


def run(*args):
    return subprocess.run(["bash", str(SEAL), *map(str, args)], capture_output=True, text=True)


@unittest.skipUnless(os.geteuid() == 0, "sealing changes ownership, so it needs root")
class TheSeal(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp())
        os.chmod(self.root, 0o755)                      # like /opt/scheduler: the account must be able to walk down to the code
        self.addCleanup(shutil.rmtree, self.root, True)
        self.pkg = package(self.root)

    def test_a_package_the_website_account_owns_is_not_sealed_and_says_where(self):
        os.chown(self.pkg / "webapp" / "app.py", 65534, 65534)
        got = run("--check", self.pkg)
        self.assertEqual(got.returncode, 1)
        self.assertIn("not owned by root:root", got.stdout)
        self.assertIn("webapp/app.py", got.stdout)

    def test_sealing_makes_it_root_owned_readable_and_not_writable_and_check_agrees(self):
        (self.pkg / "webapp" / "__pycache__").mkdir()
        (self.pkg / "webapp" / "__pycache__" / "app.cpython-312.pyc").write_bytes(b"\0")
        os.chmod(self.pkg / "tools" / "check.py", 0o666)
        (self.pkg / "tools" / "run.sh").write_text("#!/bin/sh\n")
        os.chmod(self.pkg / "tools" / "run.sh", 0o775)
        got = run(self.pkg)
        self.assertEqual(got.returncode, 0, got.stdout + got.stderr)
        self.assertIn("SEALED", got.stdout)
        self.assertFalse((self.pkg / "webapp" / "__pycache__").exists())          # only the source is run
        for path in self.pkg.rglob("*"):
            st = path.lstat()
            self.assertEqual((st.st_uid, st.st_gid), (0, 0), str(path))
            self.assertFalse(st.st_mode & 0o022, f"{path} {oct(st.st_mode)}")
            self.assertTrue(st.st_mode & 0o004, f"{path} is not world-readable")
        self.assertTrue((self.pkg / "tools" / "run.sh").stat().st_mode & 0o001, "what could be run still can")
        self.assertEqual(run("--check", self.pkg).returncode, 0)

    def test_the_account_really_cannot_change_a_sealed_file_but_can_read_it(self):
        run(self.pkg)
        for rel in ("webapp/app.py", "webapp"):
            self.assertEqual(subprocess.run(["setpriv", "--reuid=65534", "--regid=65534", "--clear-groups", "test", "-w", str(self.pkg / rel)]).returncode, 1, rel)
        self.assertEqual(subprocess.run(["setpriv", "--reuid=65534", "--regid=65534", "--clear-groups", "test", "-r", str(self.pkg / "webapp" / "app.py")]).returncode, 0)
        write = subprocess.run(["setpriv", "--reuid=65534", "--regid=65534", "--clear-groups", "sh", "-c", f"echo evil >> {self.pkg}/webapp/app.py"], capture_output=True)
        self.assertNotEqual(write.returncode, 0)
        self.assertEqual((self.pkg / "webapp" / "app.py").read_text(), "x = 1\n")

    def test_a_link_out_of_the_package_is_found_and_sealing_does_not_follow_it(self):
        outside = self.root / "data"
        outside.mkdir()
        (outside / "file.txt").write_text("data")
        os.chown(outside / "file.txt", 65534, 65534)
        (self.pkg / "webapp" / "data_link").symlink_to(outside / "file.txt")
        got = run(self.pkg)
        self.assertEqual(got.returncode, 1)
        self.assertIn("link leaves the package", got.stdout)
        self.assertEqual((outside / "file.txt").stat().st_uid, 65534, "the file the link points to was not touched")

    def test_a_file_with_two_names_is_found(self):
        os.link(self.pkg / "webapp" / "app.py", self.root / "other_name.py")
        got = run(self.pkg)
        self.assertEqual(got.returncode, 1)
        self.assertIn("more than one name", got.stdout)

    def test_it_refuses_what_is_not_a_package_and_the_data_folder(self):
        for target in (self.root, "/", "/var/lib/scheduler", "/opt"):
            got = run(target)
            self.assertNotEqual(got.returncode, 0, str(target))
        self.assertEqual(run().returncode, 2)


if __name__ == "__main__":
    unittest.main()
