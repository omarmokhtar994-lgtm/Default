"""Input vocabulary fails closed without rejecting ordinary values (F-02, C-2).

F-02: the Preference/Fixed vocabulary rejected ordinary spellings ("Public
Holiday", "Casual Leave", "OFF (approved)", "N/A", "-") as hard contract
failures, so a workbook that ran under RC5 produced no schedule at all.
C-2: a yes/no instruction holding anything else ("Enable", "Yes.") read as No,
which could switch Leave or Hard OFF off for the whole roster.

Contract smoke over all 42 repository workbooks: 0 contract results and 0
canonical contract hashes changed (evidence/independent_audit_2026_09_28).
"""
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
ROOT = Path(os.environ.get("CANDIDATE_ENGINE", REPO)).resolve()
sys.path.insert(0, str(ROOT / "engine" / "_tools"))
import l632_universal_scheduler as E  # noqa: E402

INPUTS = next(p for p in (ROOT / "inputs", REPO / "packages" / "rc9_2_2_production" / "inputs") if p.exists())
BOOK = INPUTS / "NMG_SP_RC9_1_READY_FIXED.xlsx"


class PreferenceVocabulary(unittest.TestCase):
    def test_ordinary_leave_and_off_spellings_are_recognised(self):
        cases = {
            "leave": ["Public Holiday", "Bank Holiday", "PH", "Casual Leave", "CL", "Medical Leave",
                      "Maternity Leave", "Vacation Leave", "annual-leave", "Leave (approved)", "Unpaid", "LOA"],
            "off": ["Comp Off", "OFF (approved)", "Requested Off", "Off Request", "R/D", "D/O"],
            "blank": ["N/A", "-", "TBD"],
        }
        for kind, values in cases.items():
            for value in values:
                with self.subTest(value=value):
                    self.assertEqual(E.preference_kind(value), kind)

    def test_ambiguous_values_still_fail_closed(self):
        for value in ("Training", "WFH", "Half Day", "9-6", "Morning", "Sick Off", "Off Duty"):
            with self.subTest(value=value):
                self.assertEqual(E.preference_kind(value), "other")

    def test_values_recognised_before_keep_their_meaning(self):
        for value in sorted(E.OFF_WORDS):
            self.assertEqual(E.preference_kind(value), "off", value)
        for value in sorted(E.LEAVE_WORDS):
            self.assertEqual(E.preference_kind(value), "leave", value)
        for value in ("09:00-18:00", "07:00 - 16:00", "22:00-07:00"):
            self.assertEqual(E.preference_kind(value), "shift", value)


def _edit(book: Path, edits):
    from openpyxl import load_workbook
    wb = load_workbook(book)
    for edit in edits:
        edit(wb)
    wb.save(book)


def _set_instruction(key: str, value):
    def edit(wb):
        for ws in wb.worksheets:
            for row in ws.iter_rows():
                for cell in row:
                    if isinstance(cell.value, str) and E.norm(cell.value) == E.norm(key):
                        ws.cell(cell.row, cell.column + 1, value)
                        return
        raise AssertionError(f"instruction {key!r} not found")
    return edit


def _set_first_preference(value):
    def edit(wb):
        ws = next(wb[n] for n in wb.sheetnames if E.norm(n) in {"preference", "prefrence", "preferences"})
        header = E._find_header_row(ws, ["name"], prefer_day_columns=True)
        headers = {E.norm(ws.cell(header, c).value): c for c in range(1, ws.max_column + 1)}
        name_col = next((c for h, c in headers.items() if "name" in h), 1)
        day_cols = E._day_columns(ws, header)
        first_associate = E.parse_input(BOOK).associates[0].name
        row = header + 1
        ws.cell(row, name_col, first_associate)
        ws.cell(row, day_cols[0], value)
    return edit


def _add_mapping(rows):
    def edit(wb):
        ws = wb.create_sheet("Preference Code Mapping")
        ws.append(["Value", "Meaning"])
        for row in rows:
            ws.append(list(row))
    return edit


class ContractBehaviour(unittest.TestCase):
    def contract(self, *edits):
        with tempfile.TemporaryDirectory() as tmp:
            book = Path(tmp) / BOOK.name
            shutil.copy(BOOK, book)
            _edit(book, edits)
            parsed = E.parse_input(book)
            codes = {f.get("code") for f in E.validate_input_contract(parsed).get("failures", [])}
            return parsed, codes

    def test_the_unedited_workbook_passes(self):
        _, codes = self.contract()
        self.assertFalse(codes)

    def test_an_unknown_switch_value_fails_the_contract(self):
        _, codes = self.contract(_set_instruction("Leave Enabled", "Enable"))
        self.assertIn("HARD_INVALID_INSTRUCTION_BOOLEAN", codes)

    def test_yes_and_no_still_pass(self):
        for value in ("Yes", "No"):
            _, codes = self.contract(_set_instruction("Leave Enabled", value))
            self.assertNotIn("HARD_INVALID_INSTRUCTION_BOOLEAN", codes, value)

    def test_an_ordinary_leave_spelling_no_longer_blocks_the_run(self):
        parsed, codes = self.contract(_set_first_preference("Public Holiday"))
        self.assertNotIn("UNRECOGNISED_PREFERENCE_VALUE", codes)

    def test_an_unknown_code_still_blocks_the_run(self):
        _, codes = self.contract(_set_first_preference("TRN"))
        self.assertIn("UNRECOGNISED_PREFERENCE_VALUE", codes)

    def test_a_mapping_sheet_turns_a_site_code_into_leave(self):
        parsed, codes = self.contract(_set_first_preference("TRN"), _add_mapping([("TRN", "Leave")]))
        self.assertNotIn("UNRECOGNISED_PREFERENCE_VALUE", codes)
        self.assertTrue(any("Leave" in a.preferences for a in parsed.associates))
        self.assertTrue(any(w.startswith("PREFERENCE_MAPPING_APPLIED") for w in parsed.parser_warnings))

    def test_a_mapping_with_an_unknown_meaning_fails(self):
        _, codes = self.contract(_add_mapping([("TRN", "Training")]))
        self.assertIn("HARD_INVALID_PREFERENCE_MAPPING", codes)


class BaselineWorkbookDepartedOverride(unittest.TestCase):
    """AE_AR_B2B is baseline-protected; its manifest names 5 departed associates (F-21)."""

    def test_the_manifest_names_clear_exactly_the_unknown_previous_week_rows(self):
        import json
        manifest = next(p for p in (ROOT / "SCENARIOS.json",
                                    REPO / "packages" / "rc9_2_2_production" / "SCENARIOS.json") if p.exists())
        row = next(r for r in json.loads(manifest.read_text())["scenarios"] if r["scenario_id"] == "AE_AR_B2B")
        book = INPUTS / row["input"]
        codes = lambda parsed: {f.get("code") for f in E.validate_input_contract(parsed).get("failures", [])}
        self.assertIn("HARD_PREVIOUS_SATURDAY_UNKNOWN_ASSOCIATE", codes(E.parse_input(book)))
        parsed = E.parse_input(book, acknowledged_departed_override=row["acknowledged_departed"])
        self.assertFalse(codes(parsed))
        self.assertEqual(sum(w.startswith("DEPARTED_ASSOCIATE_ROW_IGNORED") for w in parsed.parser_warnings),
                         len(row["acknowledged_departed"]))
        # acknowledging one person must not silence another
        partial = E.parse_input(book, acknowledged_departed_override=row["acknowledged_departed"][:-1])
        self.assertIn("HARD_PREVIOUS_SATURDAY_UNKNOWN_ASSOCIATE", codes(partial))


class OnlyTheRowTheEngineReadsIsChecked(unittest.TestCase):
    def test_a_later_alias_with_prose_is_ignored(self):
        warnings = []
        im = {E.norm("Use Preferences"): "No", E.norm("Preferences"): "Separate OFF From Preference Only"}
        E._validate_boolean_instructions(im, warnings)
        self.assertEqual(warnings, [])
        E._validate_boolean_instructions({E.norm("Preferences"): "Separate OFF"}, warnings)
        self.assertEqual(len(warnings), 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
