#!/usr/bin/env python3
"""Published-artifact identity guards.

The exact-engine-identity release gate is only as good as what the published
artifact actually asserts.  `production_output_polisher.py` writes the release
name and engine hash into the production workbook's Production Summary sheet,
into PRODUCTION_ARTIFACT_MANIFEST.json, and into the production ZIP filename -
and it took all of them from module literals that had drifted:

  RELEASE = 'L6.3.2.3-RC9.1-...'   while publishing an RC9.2.1 run
  ENGINE  = '4b5f58e5df...'        matching no engine in the project - not
                                   RC9.1's da21c3ba, not RC9.2.1's 56ec2eef,
                                   not the current build

So every published workbook asserted a fabricated engine identity.  Identity is
now derived from the run that produced the case.

Run:  python tests/test_rc9_2_1_production_identity.py
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
POLISHER_PATH = ROOT / "engine" / "production" / "production_output_polisher.py"
ENGINE_PATH = ROOT / "engine" / "_tools" / "l632_universal_scheduler.py"


def load_polisher():
    spec = importlib.util.spec_from_file_location("production_output_polisher", POLISHER_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def case_root(tmp, universal=None, engine_identity=None):
    root = Path(tmp)
    if universal is not None:
        (root / "UNIVERSAL_RUN_IDENTITY.json").write_text(json.dumps(universal), encoding="utf-8")
    if engine_identity is not None:
        (root / "debug").mkdir(parents=True, exist_ok=True)
        (root / "debug" / "RUN_IDENTITY.json").write_text(
            json.dumps(engine_identity), encoding="utf-8")
    return root


REAL_RELEASE = "L6.3.2.5-RC9.2.1-PROTECTED-TIER-RESIDUAL-BALANCE-RC1"


class PublishedIdentityIsDerivedNotHardcoded(unittest.TestCase):

    def setUp(self):
        self.pol = load_polisher()

    def test_release_and_engine_come_from_the_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = case_root(tmp, universal={
                "release": REAL_RELEASE, "engine_sha256": "abc123", "input_sha256": "in123"})
            ident = self.pol.run_identity(root)
        self.assertEqual(ident["release"], REAL_RELEASE)
        self.assertEqual(ident["engine_sha256"], "abc123")
        self.assertNotEqual(ident["engine_sha256"], self.pol.ENGINE,
                            "must not publish the stale literal when a run identity exists")

    def test_contract_hash_is_recovered_from_the_engine_identity(self):
        """Cases produced before the wrapper merged identity keep it only in debug/.

        Stopping at the first identity file would publish those with the
        contract hash still missing.
        """
        with tempfile.TemporaryDirectory() as tmp:
            root = case_root(
                tmp,
                universal={"release": REAL_RELEASE, "engine_sha256": "abc123"},
                engine_identity={"contract_sha256": "con456", "run_id": "rid789",
                                 "engine_sha256": "abc123"})
            ident = self.pol.run_identity(root)
        self.assertEqual(ident["contract_sha256"], "con456")
        self.assertEqual(ident["run_id"], "rid789")
        self.assertIn("+", ident["identity_source"], "both sources must be recorded")

    def test_engine_identity_alone_is_sufficient(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = case_root(tmp, engine_identity={
                "version": REAL_RELEASE, "engine_sha256": "abc123",
                "contract_sha256": "con456", "run_id": "rid789"})
            ident = self.pol.run_identity(root)
        self.assertEqual(ident["release"], REAL_RELEASE)
        self.assertEqual(ident["contract_sha256"], "con456")
        self.assertEqual(ident["identity_source"], "debug/RUN_IDENTITY.json")

    def test_fallback_is_marked_not_silent(self):
        with tempfile.TemporaryDirectory() as tmp:
            ident = self.pol.run_identity(Path(tmp))
        self.assertEqual(ident["identity_source"], "FALLBACK_LITERALS",
                         "a case with no identity must say so, not quietly publish literals")
        self.assertEqual(ident["release"], self.pol.RELEASE)

    def test_corrupt_identity_file_does_not_crash_publishing(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "UNIVERSAL_RUN_IDENTITY.json").write_text("{not json", encoding="utf-8")
            ident = self.pol.run_identity(Path(tmp))
        self.assertEqual(ident["identity_source"], "FALLBACK_LITERALS")

    def test_empty_identity_file_falls_back(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = case_root(tmp, universal={})
            ident = self.pol.run_identity(root)
        self.assertEqual(ident["release"], self.pol.RELEASE)

    def test_published_fields_reference_the_derived_identity(self):
        # Compare with whitespace stripped from BOTH sides, and assert on a bool
        # so a failure prints one line rather than the entire polisher source.
        compact = POLISHER_PATH.read_text(encoding="utf-8").replace(" ", "")
        for field in ("'Production Release':ident['release']",
                      "'Engine SHA256':ident['engine_sha256']",
                      "'Solver Version':ident['solver']",
                      "'Contract SHA256':ident['contract_sha256']"):
            with self.subTest(field=field):
                self.assertTrue(
                    field.replace(" ", "") in compact,
                    f"published workbook field {field} must use the derived identity")

    def test_manifest_and_zip_name_use_the_derived_release(self):
        compact = POLISHER_PATH.read_text(encoding="utf-8").replace(" ", "")
        self.assertTrue("manifest={'release':ident['release']" in compact,
                        "release manifest must use the derived release")
        self.assertFalse("zp=prod/f'{cid}_{RELEASE}_PRODUCTION_ONLY.zip'" in compact,
                         "ZIP filename must not carry the stale literal release")
        self.assertTrue("'engine_sha256':ident['engine_sha256']" in compact,
                        "manifest solver block must use the derived engine hash")

    def test_stale_literal_engine_hash_matches_no_real_engine(self):
        """Pins why this mattered: the literal was never any engine's hash."""
        actual = hashlib.sha256(ENGINE_PATH.read_bytes()).hexdigest()
        self.assertNotEqual(self.pol.ENGINE, actual)
        for known in ("da21c3bacf577e5a806dae0c75fbc70411d0747b2ef599d391ad9f276074e415",
                      "56ec2eefe64b56e85d6d5b3d492d052778cf9b4b3a8a57293bf106139fbc441a"):
            self.assertNotEqual(self.pol.ENGINE, known)


class SelfcheckCannotPassVacuously(unittest.TestCase):
    """The polisher selfcheck used a bare `assert`.

    Under `python -O` assertions are stripped, so the selfcheck printed PASS
    having verified nothing - a selfcheck that cannot fail.
    """

    def test_selfcheck_does_not_rely_on_assert(self):
        source = POLISHER_PATH.read_text(encoding="utf-8")
        selfcheck = source[source.index("if a.selfcheck:"):]
        self.assertNotIn("assert ", selfcheck,
                         "`python -O` strips assert; the selfcheck must branch and return 1")
        self.assertIn("return 1", selfcheck, "the selfcheck must have a failing path")

    def test_selfcheck_passes_under_optimised_mode(self):
        import subprocess
        result = subprocess.run(
            [sys.executable, "-O", str(POLISHER_PATH), "--selfcheck"],
            capture_output=True, text=True, timeout=120)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("PASS", result.stdout)


if __name__ == "__main__":
    unittest.main(verbosity=2)
