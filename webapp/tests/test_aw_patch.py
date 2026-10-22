# © 2026 Omar Mokhtar. All rights reserved.
"""Phase AW (owner, 2026-10-22: "can't you send me a small patch instead of full packing for small things?"): a patch holds
only the website files that changed since the installed package; it is applied only to exactly the files it was made
for, keeps a backup, and can be undone. Made-up files in a temporary folder."""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "tools"))
import make_patch  # noqa: E402

APPLY = REPO / "deploy" / "apply_patch.sh"


class ThePatch(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.dir, True)
        self.root = self.dir / "repo"
        for rel, text in {"webapp/a.py": "A = 1\n", "webapp/static/x.css": "body { color: red }\n",
                          "deploy/requirements.txt": "flask==3\n", "deploy/apply_patch.sh": APPLY.read_text(),
                          "engine/e.py": "E = 1\n"}.items():
            f = self.root / rel
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_text(text)
        self.base = self.dir / "base.zip"
        with zipfile.ZipFile(self.base, "w") as z:
            for rel in ("webapp/a.py", "webapp/static/x.css", "deploy/requirements.txt", "deploy/apply_patch.sh", "engine/e.py"):
                z.write(self.root / rel, "PKG/" + rel)
            z.writestr("PKG/MANIFEST.json", "{}")
        self.app_dir = self.dir / "opt"
        with zipfile.ZipFile(self.base) as z:
            z.extractall(self.dir / "unz")
        shutil.copytree(self.dir / "unz" / "PKG", self.app_dir / "package")
        (self.root / "webapp/static/x.css").write_text("body { color: blue }\n")  # the change
        (self.root / "webapp/b.py").write_text("B = 2\n")                          # a new file
        (self.root / "engine/e.py").write_text("E = 2\n")                          # never patched

    def make(self):
        return make_patch.build(self.base, "fix", self.dir / "out", self.root)

    def apply(self, *args):
        env = dict(os.environ, APP_DIR=str(self.app_dir), PATCH_NO_SERVICE="1")
        return subprocess.run(["bash", str(APPLY), *map(str, args)], capture_output=True, text=True, env=env)

    def read(self, rel):
        return (self.app_dir / "package" / rel).read_text()

    def test_only_the_changed_and_new_website_files_are_in_it(self):
        z = zipfile.ZipFile(self.make())
        names = sorted(n for n in z.namelist() if n.startswith("files/"))
        self.assertEqual(names, ["files/webapp/b.py", "files/webapp/static/x.css"])
        self.assertIn("apply_patch.sh", z.namelist())

    def test_nothing_changed_means_no_patch(self):
        shutil.copy(self.dir / "unz/PKG/webapp/static/x.css", self.root / "webapp/static/x.css")
        (self.root / "webapp/b.py").unlink()
        self.assertIsNone(self.make())

    def test_it_applies_keeps_a_backup_and_can_be_undone(self):
        got = self.apply(self.make())
        self.assertEqual(got.returncode, 0, got.stdout + got.stderr)
        self.assertEqual(self.read("webapp/static/x.css"), "body { color: blue }\n")
        self.assertEqual(self.read("webapp/b.py"), "B = 2\n")
        self.assertEqual(self.read("engine/e.py"), "E = 1\n")  # never touched
        backup = next((self.app_dir / "patch-backups").iterdir())
        self.assertEqual((backup / "files/webapp/static/x.css").read_text(), "body { color: red }\n")
        undone = self.apply("--rollback", backup)
        self.assertEqual(undone.returncode, 0, undone.stdout + undone.stderr)
        self.assertEqual(self.read("webapp/static/x.css"), "body { color: red }\n")
        self.assertFalse((self.app_dir / "package/webapp/b.py").exists())

    def test_applying_it_twice_is_harmless(self):
        patch = self.make()
        self.assertEqual(self.apply(patch).returncode, 0)
        again = self.apply(patch)
        self.assertEqual(again.returncode, 0, again.stdout + again.stderr)
        self.assertEqual(self.read("webapp/static/x.css"), "body { color: blue }\n")

    def test_it_refuses_files_that_are_not_the_ones_it_was_made_for(self):
        (self.app_dir / "package/webapp/static/x.css").write_text("body { color: green }\n")  # someone changed it
        got = self.apply(self.make())
        self.assertNotEqual(got.returncode, 0)
        self.assertIn("PATCH STOPPED", got.stdout)
        self.assertEqual(self.read("webapp/static/x.css"), "body { color: green }\n")  # nothing changed
        self.assertFalse((self.app_dir / "package/webapp/b.py").exists())

    def test_a_patched_file_that_does_not_compile_is_put_back(self):
        (self.root / "webapp/b.py").write_text("def broken(:\n")
        got = self.apply(self.make())
        self.assertNotEqual(got.returncode, 0)
        self.assertIn("does not compile", got.stdout)
        self.assertEqual(self.read("webapp/static/x.css"), "body { color: red }\n")
        self.assertFalse((self.app_dir / "package/webapp/b.py").exists())

    def test_a_damaged_patch_is_refused(self):
        patch = self.make()
        damaged = self.dir / "bad.zip"
        with zipfile.ZipFile(patch) as zin, zipfile.ZipFile(damaged, "w") as zout:
            for item in zin.infolist():
                zout.writestr(item, b"tampered" if item.filename == "files/webapp/b.py" else zin.read(item))
        got = self.apply(damaged)
        self.assertNotEqual(got.returncode, 0)
        self.assertIn("damaged", got.stdout)


if __name__ == "__main__":
    unittest.main()
