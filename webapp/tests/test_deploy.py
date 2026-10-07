# © 2026 Omar Mokhtar. All rights reserved.
"""Phase I task 4: the one-command installer for the Oracle server.

Pinned: the scripts are valid bash; the solver is pinned to the package's own
version; the website listens on localhost only and Caddy is the only thing
facing the internet (HTTPS on <ip>.sslip.io); the firewall opens 80 and 443
and nothing else; the first admin is created at a password prompt, never with
a default password. DRY_RUN=1 renders the service and Caddy files into a
scratch folder and prints the system commands instead of running them."""
import os
import re
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEPLOY = ROOT / "deploy"
INSTALL = DEPLOY / "install.sh"
UPDATE = DEPLOY / "update.sh"


def dry_run(**env):
    out = Path(tempfile.mkdtemp())
    full = dict(os.environ, DRY_RUN="1", DRY_ROOT=str(out), DOMAIN="129-151-1-2.sslip.io",
                ADMIN_USER="omar", ADMIN_NAME="Omar Mokhtar")
    full.update(env)
    proc = subprocess.run(["bash", str(INSTALL)], capture_output=True, text=True, env=full, timeout=120)
    return proc, out


class TheScripts(unittest.TestCase):
    def test_install_script_is_valid_bash(self):
        for script in (INSTALL, UPDATE):
            proc = subprocess.run(["bash", "-n", str(script)], capture_output=True, text=True)
            self.assertEqual(proc.returncode, 0, proc.stderr)

    def test_install_pins_the_solver(self):
        text = INSTALL.read_text(encoding="utf-8")
        self.assertIn("ortools==9.15.6755", text)
        # ... the same build the runner's runtime check demands.
        self.assertIn('"ortools": ("9.15.6755", True)',
                      (ROOT / "tools" / "runtime_environment_check.py").read_text(encoding="utf-8"))

    def test_service_runs_waitress_on_localhost_only(self):
        from webapp import serve
        self.assertEqual(serve.HOST, "127.0.0.1")
        service = (DEPLOY / "scheduler-web.service").read_text(encoding="utf-8")
        self.assertIn("-m webapp.serve", service)
        self.assertIn("User=scheduler", service)
        self.assertNotIn("0.0.0.0", service + Path(serve.__file__).read_text(encoding="utf-8"))

    def test_caddy_uses_sslip_domain_and_only_proxies_to_localhost(self):
        caddy = (DEPLOY / "Caddyfile.template").read_text(encoding="utf-8")
        self.assertIn("{{DOMAIN}}", caddy)
        self.assertEqual(re.findall(r"reverse_proxy\s+(\S+)", caddy), ["127.0.0.1:8080"])
        self.assertIn(".sslip.io", INSTALL.read_text(encoding="utf-8"))

    def test_firewall_opens_80_and_443_only(self):
        ports = set(re.findall(r"--dport\s+(\d+)", INSTALL.read_text(encoding="utf-8")))
        self.assertEqual(ports, {"80", "443"})

    def test_install_creates_admin_interactively_never_with_a_default_password(self):
        text = INSTALL.read_text(encoding="utf-8")
        self.assertIn("webapp.manage", text)
        self.assertIn("create-admin", text)
        self.assertNotRegex(text, r"(?i)--password|password=|PASSWORD=")
        from webapp import manage
        with self.assertRaises(SystemExit):  # there is no way to pass a password as an argument
            manage.main(["--data-dir", tempfile.mkdtemp(), "create-admin", "x", "--password", "y"])


class TheDryRun(unittest.TestCase):
    def test_dry_run_renders_service_and_caddy(self):
        proc, out = dry_run()
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        caddy = (out / "etc" / "caddy" / "Caddyfile").read_text(encoding="utf-8")
        self.assertIn("129-151-1-2.sslip.io {", caddy)
        service = (out / "etc" / "systemd" / "system" / "scheduler-web.service").read_text(encoding="utf-8")
        self.assertIn("SCHEDULER_DATA_DIR=/var/lib/scheduler", service)
        for command in ("apt-get install", "useradd", "iptables", "systemctl enable", "create-admin"):
            self.assertIn(command, proc.stdout)
        self.assertIn("https://129-151-1-2.sslip.io", proc.stdout)

    def test_refuses_without_root_when_not_a_dry_run(self):
        if os.geteuid() == 0:
            self.skipTest("running as root here")
        proc = subprocess.run(["bash", str(INSTALL)], capture_output=True, text=True, timeout=60)
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("sudo", proc.stdout + proc.stderr)


class TheServerEntry(unittest.TestCase):
    def test_config_from_environment(self):
        from webapp import serve
        config = serve.config_from_env({"SCHEDULER_DATA_DIR": "/var/lib/scheduler",
                                        "SCHEDULER_PACKAGE_ROOT": "/opt/scheduler/package"})
        self.assertEqual(config["DATA_DIR"], "/var/lib/scheduler")
        self.assertEqual(config["PACKAGE_ROOT"], "/opt/scheduler/package")
        self.assertTrue(config["HTTPS"])  # behind Caddy: cookies are Secure
        self.assertEqual(config["PARALLEL"], 1)
        with self.assertRaises(SystemExit):
            serve.config_from_env({})  # no data folder: refuse to start, say why


if __name__ == "__main__":
    unittest.main()
