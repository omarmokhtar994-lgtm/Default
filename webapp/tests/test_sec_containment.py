# © 2026 Omar Mokhtar. All rights reserved.
"""Security hardening (2026-11-11): the installed code is read-only for the website's account. What the service file allows it to write, what the install,
update, patch and rollback scripts do to the code's ownership, where compiled copies and caches go, and that a compile of the engine's own files
works when the code folder cannot be written (the failure the earlier server test hit: ``py_compile`` writes beside its source unless told where)."""
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
DEPLOY = REPO / "deploy"
SERVICE = (DEPLOY / "scheduler-web.service").read_text(encoding="utf-8")


def directives(text, name):
    return [line.split("=", 1)[1].strip() for line in text.splitlines() if line.startswith(name + "=")]


class TheServiceFile(unittest.TestCase):
    def test_the_only_place_it_may_write_is_the_data_folder(self):
        self.assertEqual(directives(SERVICE, "ReadWritePaths"), ["{{DATA_DIR}}"])
        self.assertEqual(directives(SERVICE, "ProtectSystem"), ["strict"])

    def test_the_code_and_the_python_environment_are_named_read_only(self):
        self.assertEqual(directives(SERVICE, "ReadOnlyPaths"), ["{{APP_DIR}}/package {{APP_DIR}}/venv"])

    def test_nothing_is_compiled_into_the_code_and_the_caches_have_a_home(self):
        env = directives(SERVICE, "Environment")
        self.assertIn("PYTHONDONTWRITEBYTECODE=1", env)
        self.assertIn("PYTHONPYCACHEPREFIX=/tmp/scheduler-pycache", env)               # inside PrivateTmp: emptied when the service stops
        self.assertIn("RUFF_CACHE_DIR={{DATA_DIR}}/cache/ruff", env)
        self.assertIn("XDG_CACHE_HOME={{DATA_DIR}}/cache", env)
        self.assertEqual(directives(SERVICE, "PrivateTmp"), ["yes"])
        self.assertEqual(directives(SERVICE, "NoNewPrivileges"), ["yes"])

    def test_the_rendered_file_names_real_paths(self):
        rendered = SERVICE.replace("{{APP_DIR}}", "/opt/scheduler").replace("{{DATA_DIR}}", "/var/lib/scheduler")
        self.assertNotIn("{{", rendered)
        self.assertEqual(directives(rendered, "ReadWritePaths"), ["/var/lib/scheduler"])
        self.assertNotIn("/opt/scheduler/package", " ".join(directives(rendered, "ReadWritePaths")))


class TheScripts(unittest.TestCase):
    def text(self, name):
        return (DEPLOY / name).read_text(encoding="utf-8")

    def test_no_script_gives_the_package_back_to_the_website_account(self):
        for name in ("install.sh", "update.sh", "apply_patch.sh", "rollback.sh", "seal_package.sh"):
            self.assertIsNone(re.search(r"chown\s+(-\w+\s+)*scheduler(:scheduler)?\s+\S*package", self.text(name)), name)

    def test_install_update_and_patch_seal_the_code_after_they_put_it_in_place(self):
        for name in ("install.sh", "update.sh", "apply_patch.sh"):
            self.assertIn("seal_package.sh", self.text(name), name)
        update = self.text("update.sh")
        call = 'bash "$APP_DIR/package/deploy/seal_package.sh" "$APP_DIR/package"'
        self.assertEqual(update.count(call), 1)
        self.assertLess(update.index('cp -a "$NEW" "$APP_DIR/package"'), update.index(call))          # after the code is in place
        self.assertLess(update.index(call), update.index('"$VENV/bin/pip" install'))                 # before anything of the new code runs

    def test_what_the_scripts_run_as_the_website_account_cannot_compile_into_the_code(self):
        for name in ("install.sh", "update.sh"):
            text = self.text(name)
            self.assertIn("PYTHONDONTWRITEBYTECODE=1", text, name)
            self.assertIn('PYTHONPYCACHEPREFIX="$DATA_DIR/cache/pycache"', text, name)

    def test_a_failed_seal_in_an_update_puts_the_previous_version_back(self):
        update = self.text("update.sh")
        block = update[update.index('if ! bash "$APP_DIR/package/deploy/seal_package.sh"'):update.index('"$VENV/bin/pip" install')]
        self.assertIn('mv "$APP_DIR/package.previous" "$APP_DIR/package"', block)
        self.assertIn("systemctl start scheduler-web", block)

    def test_the_update_checks_what_the_service_may_really_write(self):
        self.assertIn("--property=ReadWritePaths", self.text("update.sh"))

    def test_rollback_restores_the_previous_code_and_its_own_service_file_and_keeps_what_it_left(self):
        text = self.text("rollback.sh")
        for piece in ('mv "$APP_DIR/package" "$APP_DIR/package.rolled-back"', 'mv "$APP_DIR/package.previous" "$APP_DIR/package"',
                      'deploy/scheduler-web.service', "systemctl daemon-reload"):
            self.assertIn(piece, text)
        self.assertNotIn("rm -rf \"$APP_DIR/package.previous\"", text)       # the only copy of the old version is moved, never deleted first

    def test_every_script_parses_and_has_the_copyright_line(self):
        for name in ("install.sh", "update.sh", "apply_patch.sh", "rollback.sh", "seal_package.sh"):
            self.assertEqual(subprocess.run(["bash", "-n", str(DEPLOY / name)]).returncode, 0, name)
            self.assertIn("© 2026 Omar Mokhtar. All rights reserved.", "\n".join(self.text(name).splitlines()[:4]), name)


@unittest.skipUnless(os.geteuid() == 0, "needs root to make a folder read-only for another account")
class TheCompileOfTheEnginesFiles(unittest.TestCase):
    """The earlier server run failed because ``python -m py_compile`` writes its output next to the source, which the sealed folder refuses. With a
    cache prefix (the service file sets one) the same compile works and writes nothing into the code folder."""

    def setUp(self):
        self.root = Path(tempfile.mkdtemp())
        os.chmod(self.root, 0o755)
        self.addCleanup(subprocess.run, ["rm", "-rf", str(self.root)])
        self.code = self.root / "engine"
        self.code.mkdir()
        (self.code / "one.py").write_text("x = 1\n")
        subprocess.run(["chown", "-R", "root:root", str(self.code)], check=True)
        subprocess.run(["chmod", "-R", "go-w,a+rX", str(self.code)], check=True)

    def compile(self, **env):
        cmd = ["setpriv", "--reuid=65534", "--regid=65534", "--clear-groups", "env", "-i", "PATH=/usr/bin:/bin", *[f"{k}={v}" for k, v in env.items()],
               sys.executable, "-m", "py_compile", str(self.code / "one.py")]
        return subprocess.run(cmd, capture_output=True, text=True)

    def test_without_a_cache_prefix_the_compile_fails_in_a_read_only_folder(self):
        got = self.compile()
        self.assertNotEqual(got.returncode, 0)
        self.assertRegex(got.stderr, r"Permission|Read-only|PermissionError")

    def test_with_the_prefix_it_works_and_leaves_the_folder_untouched(self):
        prefix = self.root / "pyc"
        prefix.mkdir()
        os.chmod(prefix, 0o777)
        got = self.compile(PYTHONPYCACHEPREFIX=prefix)
        self.assertEqual(got.returncode, 0, got.stderr)
        self.assertFalse((self.code / "__pycache__").exists())
        self.assertTrue(list(prefix.rglob("*.pyc")))


if __name__ == "__main__":
    unittest.main()
