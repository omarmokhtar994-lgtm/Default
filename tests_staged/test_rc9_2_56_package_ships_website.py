# © 2026 Omar Mokhtar. All rights reserved.
"""Phase I finish: the production package carries the team website.

Owner, 2026-10-07: a private website on the Oracle server instead of Colab,
"add copy rights by my name". The package builder ships webapp/ (the site)
and deploy/ (installer, updater, Oracle guide) so the server is set up from
the same ZIP whose gate result is in MANIFEST.json; and every website and
deploy source file carries the owner's copyright line near its top.
This suite reads files only: run_tests.sh's Python needs no Flask.
"""
import importlib.util
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
COPYRIGHT = "© 2026 Omar Mokhtar. All rights reserved."
SOURCE_SUFFIXES = {".py", ".sh", ".html", ".css", ".js", ".svg", ".service", ".template", ".md", ".txt"}


def load_builder():
    spec = importlib.util.spec_from_file_location("build_production_package_i5",
                                                  REPO / "tools" / "build_production_package.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class ThePackage(unittest.TestCase):
    def test_builder_ships_the_website_and_its_installer(self):
        trees = dict(load_builder().TREES)
        self.assertEqual(trees.get("webapp"), "webapp")
        self.assertEqual(trees.get("deploy"), "deploy")

    def test_installer_is_where_the_guide_says(self):
        for name in ("install.sh", "update.sh", "scheduler-web.service", "Caddyfile.template",
                     "requirements.txt", "ORACLE_SETUP_GUIDE.md"):
            self.assertTrue((REPO / "deploy" / name).is_file(), name)


class TheCopyright(unittest.TestCase):
    def test_every_website_and_deploy_source_file_carries_it(self):
        missing = []
        files = [p for folder in ("webapp", "deploy") for p in (REPO / folder).rglob("*")
                 if p.is_file() and (p.suffix in SOURCE_SUFFIXES or p.name in ("NOTICE", "Caddyfile.template"))
                 and "__pycache__" not in p.parts]
        self.assertGreater(len(files), 20)
        for path in files:
            head = "\n".join(path.read_text(encoding="utf-8").splitlines()[:4])
            if COPYRIGHT not in head:
                missing.append(str(path.relative_to(REPO)))
        self.assertEqual(missing, [])


if __name__ == "__main__":
    unittest.main()
