#!/usr/bin/env python3
"""Guards for the two release-evidence tools under tools/.

Both tools produce evidence a release decision is made on, so a silent wrong
answer from either is worse than a crash.  Each test here fails against the
pre-fix code.

Run:  python tests/test_rc9_2_1_tooling_integrity.py
"""
from __future__ import annotations

import csv
import importlib.util
import os
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "engine" / "_tools"))
sys.path.insert(0, str(ROOT / "tools"))

import l632_universal_scheduler as E  # noqa: E402


def load(name, relative):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


BASE_METRICS = {
    "active_intervals": 252, "before_target": 100, "before_floor": 200,
    "before_80": 150, "before_90": 120, "before_100": 90,
    "before_floor_deficit_sum": 12.5, "before_floor_deficit_max": 3.25,
    "before_max_consecutive_floor_gaps": 7, "before_severe_floor_gap_count": 5,
}


def parsed_for(target, floor):
    return SimpleNamespace(target_ratio=target, floor_ratio=floor, active=[[True] * 252])


class DeficitTermIndexIsDerivedNotHardcoded(unittest.TestCase):
    """The replay tool reconstructed the pre-fix ranking at tuple slots 9 and 10.

    Those slots hold the quantized deficit terms only when
    `_protected_tier_counts` yields exactly one tier, which is true of the
    90%/75% contract the tool was first used on and false of others.  Under
    100%/75% slot 9 is `-max_consecutive_floor_gaps`; overwriting it with a raw
    deficit float destroys a real safety term and the reported verdict is not
    the pre-fix verdict at all.
    """

    def setUp(self):
        self.replay = load("replay_candidate_ranking", "tools/replay_candidate_ranking.py")

    def test_index_tracks_the_protected_tier_count(self):
        for target, floor, expected in ((0.90, 0.75, 9), (1.00, 0.75, 10),
                                        (0.80, 0.75, 8), (1.00, 0.80, 9)):
            with self.subTest(target=target, floor=floor):
                parsed = parsed_for(target, floor)
                self.assertEqual(
                    self.replay.deficit_term_index(parsed, BASE_METRICS, "before"), expected)

    def test_hardcoded_nine_is_wrong_for_a_100_percent_contract(self):
        """Pins the concrete damage, so the guard cannot pass vacuously."""
        parsed = parsed_for(1.00, 0.75)
        tup = E._candidate_quality_tuple(parsed, BASE_METRICS, "before")
        want = -E._deficit_bucket(BASE_METRICS["before_floor_deficit_sum"])
        self.assertNotEqual(tup[9], want, "slot 9 is not the deficit term here")
        self.assertEqual(tup[10], want, "slot 10 is")
        self.assertEqual(tup[9], -BASE_METRICS["before_max_consecutive_floor_gaps"],
                         "slot 9 carries the consecutive-floor-gap safety term")

    def test_masking_touches_only_the_deficit_terms(self):
        for target, floor in ((0.90, 0.75), (1.00, 0.75), (0.80, 0.75)):
            with self.subTest(target=target, floor=floor):
                parsed = parsed_for(target, floor)
                index = self.replay.deficit_term_index(parsed, BASE_METRICS, "before")
                fixed = self.replay.prefix_ranking(parsed, BASE_METRICS, "before", False, index)
                masked = self.replay.prefix_ranking(parsed, BASE_METRICS, "before", True, index)
                differing = [i for i, (a, b) in enumerate(zip(fixed, masked)) if a != b]
                self.assertEqual(differing, [index, index + 1])

    def test_a_changed_tuple_shape_fails_loudly(self):
        """A future edit to the quality tuple must stop the tool, not skew it.

        Patching `_protected_tier_counts` alone proves nothing: the derivation
        reads the same helper, so both move together and the index stays right.
        The failure mode that matters is the tuple's LAYOUT changing under a
        derivation that still looks correct, so that is what is simulated here.
        """
        parsed = parsed_for(0.90, 0.75)
        original = E._candidate_quality_tuple
        try:
            E._candidate_quality_tuple = lambda *a, **k: tuple(original(*a, **k)[2:])
            with self.assertRaises(SystemExit):
                self.replay.deficit_term_index(parsed, BASE_METRICS, "before")
        finally:
            E._candidate_quality_tuple = original

    def test_a_truncated_tuple_does_not_raise_indexerror(self):
        parsed = parsed_for(0.90, 0.75)
        original = E._candidate_quality_tuple
        try:
            E._candidate_quality_tuple = lambda *a, **k: (1, 2, 3)
            with self.assertRaises(SystemExit):
                self.replay.deficit_term_index(parsed, BASE_METRICS, "before")
        finally:
            E._candidate_quality_tuple = original


class GateReportDoesNotReadAPassOutOfMissingEvidence(unittest.TestCase):

    def setUp(self):
        self.gate = load("release_gate_report", "tools/release_gate_report.py")

    def _case(self, tmp, **fields):
        root = Path(tmp) / "CASE"
        root.mkdir(parents=True, exist_ok=True)
        row = {"status": "PASS", "active_intervals": 252, "before_target": 200,
               "after_target": 198, "before_floor": 240, "after_floor": 239,
               "target_losses_from_breaks": 2, "floor_losses_from_breaks": 1,
               "quality_benchmark_status": "PASS",
               "protected_benchmark_status": "NOT_CONFIGURED"}
        row.update(fields)
        path = root / "case.l6_3_2_3_summary.csv"
        with path.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=list(row))
            writer.writeheader()
            writer.writerow(row)
        return root

    def test_unconfigured_protected_benchmark_is_not_reported_as_a_plain_pass(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = self.gate.evaluate(self._case(tmp))
        self.assertEqual(result["gate4_quality_retention"], "PASS_PROTECTED_NOT_EVALUATED")
        self.assertIn("never checked", result["gate4_detail"])

    def test_a_blank_protected_status_is_treated_the_same_way(self):
        """Artifacts produced before the engine fix leave the field empty."""
        with tempfile.TemporaryDirectory() as tmp:
            result = self.gate.evaluate(self._case(tmp, protected_benchmark_status=""))
        self.assertEqual(result["gate4_quality_retention"], "PASS_PROTECTED_NOT_EVALUATED")

    def test_an_actually_evaluated_protected_benchmark_still_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = self.gate.evaluate(self._case(tmp, protected_benchmark_status="PASS"))
        self.assertEqual(result["gate4_quality_retention"], "PASS")

    def test_a_failed_protected_benchmark_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = self.gate.evaluate(self._case(tmp, protected_benchmark_status="FAIL"))
        self.assertEqual(result["gate4_quality_retention"], "FAIL")

    def test_skeleton_only_detection_is_exact_not_a_substring(self):
        """SKELETONS_AND_BREAK_DIAGNOSTICS_READY reached the break stage.

        The old substring test excused gates 4 and 5 as NOT_APPLICABLE on it,
        so a real break regression on such a run was never gated.
        """
        with tempfile.TemporaryDirectory() as tmp:
            root = self._case(tmp, status="SKELETONS_AND_BREAK_DIAGNOSTICS_READY",
                              target_losses_from_breaks=200)
            result = self.gate.evaluate(root)
        self.assertNotEqual(result["gate5_break_regression"], "NOT_APPLICABLE")
        self.assertEqual(result["gate5_break_regression"], "FAIL")

    def test_the_genuine_skeleton_only_status_is_still_excused(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = self.gate.evaluate(self._case(tmp, status="SKELETON_ONLY_COMPLETE"))
        self.assertEqual(result["gate5_break_regression"], "NOT_APPLICABLE")
        self.assertEqual(result["gate4_quality_retention"], "NOT_APPLICABLE")

    def test_every_excused_status_is_one_the_engine_can_emit(self):
        """The exact-match set must not drift from the engine's vocabulary.

        Asserts on a bool, not with assertIn against the whole engine, so a
        failure prints one line instead of 19,000.
        """
        source = (ROOT / "engine" / "_tools" / "l632_universal_scheduler.py").read_text(
            encoding="utf-8")
        for status in self.gate.SKELETON_ONLY_STATUSES:
            with self.subTest(status=status):
                self.assertTrue(
                    f'"{status}"' in source or f"'{status}'" in source,
                    f"{status} is excused from gates 4 and 5 but the engine "
                    f"never emits it; an excuse for a status that cannot occur "
                    f"is dead, and one for a status that can is a hole")

    def test_the_engine_skeleton_only_status_is_in_the_set(self):
        self.assertIn("SKELETON_ONLY_COMPLETE", self.gate.SKELETON_ONLY_STATUSES)


class RC9_1ComparisonRefusesMismatchedInputs(unittest.TestCase):
    """Gates 2 and 9 mean "not materially worse than RC9.1".

    The RC9.2.1 NMG EN runs used a REPAIRED fixture - two associates added on
    the 23:00-08:00 shift to cover early Sunday - while the RC9.1 baseline came
    from the unrepaired historical workbook. Comparing 227 against 214 across
    those rosters reads as a large RC9.2.1 win and means nothing: extra
    headcount trivially buys coverage. A comparator that will compare anything
    is worse than no comparator.
    """

    NMGEN_HISTORICAL = "230179d964674219" + "0" * 48
    REPAIRED_FIXTURE = "ed90d630ebae2ca8" + "0" * 48

    def setUp(self):
        self.gate = load("release_gate_report", "tools/release_gate_report.py")
        self.baseline = self.gate.load_rc9_1_baseline()

    def _case(self, tmp, input_sha, **fields):
        import json
        root = Path(tmp) / "CASE"
        root.mkdir(parents=True, exist_ok=True)
        (root / "UNIVERSAL_RUN_IDENTITY.json").write_text(
            json.dumps({"input_sha256": input_sha}), encoding="utf-8")
        # target_ratio matters: without it the comparator holds the comparison
        # back rather than assuming the tiers line up. NMG EN is a 90% contract.
        row = {"status": "PASS", "active_intervals": 252, "target_ratio": 0.9,
               "before_target": 214, "before_floor": 218}
        row.update(fields)
        if fields.get("target_ratio") == "":
            del row["target_ratio"]
        path = root / "case.l6_3_2_3_summary.csv"
        with path.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=list(row))
            writer.writeheader()
            writer.writerow(row)
        return root

    def _gate2(self, tmp, sha, **fields):
        return self.gate.evaluate(self._case(tmp, sha, **fields), self.baseline)

    def test_the_baseline_is_present_and_declares_its_evidence_class(self):
        self.assertTrue(self.baseline, "evidence/RC9_1_BASELINE.json must ship")
        self.assertIn("CONSOLIDATED", self.baseline["evidence_class"])
        self.assertIn("NMG EN", self.baseline["scenarios"])

    def test_a_different_input_is_refused_not_compared(self):
        """The trap: this would otherwise report a flattering +13 target win."""
        with tempfile.TemporaryDirectory() as tmp:
            result = self._gate2(tmp, self.REPAIRED_FIXTURE,
                                 before_target=227, before_floor=232)
        self.assertEqual(result["gate2_vs_rc9_1"], "NOT_COMPARABLE_INPUT_NOT_IN_BASELINE")
        self.assertIn("refusing to compare", result["gate2_detail"])

    def test_a_different_contract_width_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = self._gate2(tmp, self.NMGEN_HISTORICAL, active_intervals=264)
        self.assertEqual(result["gate2_vs_rc9_1"], "NOT_COMPARABLE_DIFFERENT_CONTRACT")

    def test_a_material_regression_on_the_same_input_fails(self):
        """-14, the size of the real Cricut Voice gap, is well beyond the noise."""
        with tempfile.TemporaryDirectory() as tmp:
            result = self._gate2(tmp, self.NMGEN_HISTORICAL, before_target=200)
        self.assertEqual(result["gate2_vs_rc9_1"], "FAIL")
        self.assertIn("-14", result["gate2_detail"])

    def test_one_interval_of_noise_is_not_a_regression(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = self._gate2(tmp, self.NMGEN_HISTORICAL, before_target=213)
        self.assertTrue(result["gate2_vs_rc9_1"].startswith("PASS"))

    def test_a_pass_is_never_reported_as_a_bare_pass(self):
        """The comparator is consolidated metrics, not raw RC9.1 artifacts."""
        with tempfile.TemporaryDirectory() as tmp:
            result = self._gate2(tmp, self.NMGEN_HISTORICAL)
        self.assertEqual(result["gate2_vs_rc9_1"], "PASS_AGAINST_CONSOLIDATED_BASELINE")
        self.assertNotEqual(result["gate2_vs_rc9_1"], "PASS")

    def test_a_different_target_ratio_is_refused(self):
        """before_target names a different tier under a different contract.

        Cricut Voice and Cricut Chat carry a 100% RC9.1 target while NMG EN and
        NMG SP carry 90%. Comparing a 90% run's before_target against a 100%
        baseline silently compares before_90 against before_100. The ratios
        happened to agree on every real case, which is luck, not a check.
        """
        with tempfile.TemporaryDirectory() as tmp:
            result = self._gate2(tmp, self.NMGEN_HISTORICAL, target_ratio=1.0)
        self.assertEqual(result["gate2_vs_rc9_1"], "NOT_COMPARABLE_DIFFERENT_TARGET")
        self.assertIn("different tier", result["gate2_detail"])

    def test_a_matching_target_ratio_compares(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = self._gate2(tmp, self.NMGEN_HISTORICAL, target_ratio=0.9)
        self.assertTrue(result["gate2_vs_rc9_1"].startswith("PASS"))

    def test_an_unreported_target_ratio_is_held_back_not_assumed(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = self._gate2(tmp, self.NMGEN_HISTORICAL, target_ratio="")
        self.assertEqual(result["gate2_vs_rc9_1"], "NOT_COMPARABLE_TARGET_UNKNOWN")

    def test_every_baseline_scenario_declares_its_target_ratio(self):
        for name, row in self.baseline["scenarios"].items():
            with self.subTest(scenario=name):
                self.assertIn("target_ratio", row,
                              "a baseline row without a target ratio cannot be compared safely")

    def test_a_truncated_search_is_not_compared(self):
        """Cricut Voice explored 1 of 15 skeleton profiles at a 900s budget.

        DEEP's design budget is 14400s. Reading that run's -14 target as an
        RC9.2.1 quality regression would blame the engine for a budget that
        never let it search.
        """
        with tempfile.TemporaryDirectory() as tmp:
            result = self._gate2(
                tmp, self.NMGEN_HISTORICAL, before_target=180,
                stage1_profiles_requested=15, stage1_profiles_attempted=1,
                stage1_profile_coverage_status="TRUNCATED_INSUFFICIENT_STAGE1_BUDGET")
        self.assertEqual(result["gate2_vs_rc9_1"], "NOT_COMPARABLE_SEARCH_TRUNCATED")
        self.assertIn("1 of 15", result["gate2_detail"])

    def test_a_complete_search_is_compared(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = self._gate2(
                tmp, self.NMGEN_HISTORICAL,
                stage1_profiles_requested=15, stage1_profiles_attempted=15,
                stage1_profile_coverage_status="COMPLETE")
        self.assertTrue(result["gate2_vs_rc9_1"].startswith("PASS"))

    def test_a_partial_count_alone_is_enough_to_hold_back(self):
        """Older artifacts carry no coverage status, only the counts."""
        with tempfile.TemporaryDirectory() as tmp:
            result = self._gate2(tmp, self.NMGEN_HISTORICAL,
                                 stage1_profiles_requested=15,
                                 stage1_profiles_attempted=3)
        self.assertEqual(result["gate2_vs_rc9_1"], "NOT_COMPARABLE_SEARCH_TRUNCATED")

    def test_a_shortfall_inside_the_run_noise_is_inconclusive_not_a_fail(self):
        """Coverage is not reproducible run to run at a fixed seed.

        OR-Tools searching in parallel under a wall-clock limit is
        non-deterministic: the seed fixes the RNG, not which worker reaches a
        bound first. Measured on Cricut Voice at a fixed seed and 300s budget,
        same host: before_target 248, 242, 243 - a spread of 6. A tolerance of 2
        sits below that, so a single pair of runs can differ by more than the
        gate's own threshold, and calling that a regression is not supportable.
        """
        with tempfile.TemporaryDirectory() as tmp:
            result = self._gate2(tmp, self.NMGEN_HISTORICAL, before_target=211)
        self.assertEqual(result["gate2_vs_rc9_1"], "INCONCLUSIVE_WITHIN_RUN_NOISE")
        self.assertIn("repeat the run", result["gate2_detail"])

    def test_a_shortfall_beyond_the_noise_band_still_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = self._gate2(tmp, self.NMGEN_HISTORICAL, before_target=200)
        self.assertEqual(result["gate2_vs_rc9_1"], "FAIL")

    def test_the_noise_band_is_wider_than_the_tolerance(self):
        """Otherwise the inconclusive branch is unreachable."""
        self.assertGreater(self.gate.COMPARATOR_RUN_NOISE_BAND,
                           self.gate.COMPARATOR_TARGET_TOLERANCE)

    def test_gate9_tracks_gate2(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = self._gate2(tmp, self.NMGEN_HISTORICAL)
        self.assertEqual(result["gate9_vs_rc9_1"], result["gate2_vs_rc9_1"])

    def test_without_a_baseline_both_gates_say_so(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = self.gate.evaluate(self._case(tmp, self.NMGEN_HISTORICAL), {})
        self.assertEqual(result["gate2_vs_rc9_1"], "REQUIRES_RC9_1_BASELINE")


class Gate5CannotBeSatisfiedByShippingAWorseSkeleton(unittest.TestCase):
    """Gate 5 measured only a delta, and a delta is gameable by starting lower.

    Two AE AR B2B runs shipped the IDENTICAL schedule - after_target 156 of 168
    active - and the gate disagreed with itself:

        before 166 -> after 156   loss 10/168 = 6.0%   FAIL
        before 162 -> after 156   loss  6/168 = 3.6%   PASS

    Nothing about the delivered schedule changed. Stage 1 simply produced a
    worse skeleton the second time, which shrank the loss and flipped the gate.
    """

    def setUp(self):
        self.gate = load("release_gate_report", "tools/release_gate_report.py")
        self.baseline = self.gate.load_rc9_1_baseline()
        self._saved = os.environ.pop(self.gate.MINIMUM_AFTER_TARGET_RATIO_ENV, None)

    def tearDown(self):
        os.environ.pop(self.gate.MINIMUM_AFTER_TARGET_RATIO_ENV, None)
        if self._saved is not None:
            os.environ[self.gate.MINIMUM_AFTER_TARGET_RATIO_ENV] = self._saved

    def _case(self, tmp, **fields):
        import json
        root = Path(tmp) / "CASE"
        root.mkdir(parents=True, exist_ok=True)
        (root / "UNIVERSAL_RUN_IDENTITY.json").write_text(
            json.dumps({"input_sha256": "0" * 64}), encoding="utf-8")
        row = {"status": "PASS_WITH_QUALITY_WARNINGS", "active_intervals": 168,
               "target_ratio": 1.0, "before_target": 166, "after_target": 156,
               "before_floor": 168, "after_floor": 166,
               "minimum_exception_proven": "true"}
        row.update(fields)
        path = root / "case.l6_3_2_3_summary.csv"
        with path.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=list(row))
            writer.writeheader()
            writer.writerow(row)
        return self.gate.evaluate(root, self.baseline)

    def test_the_absolute_result_is_always_reported(self):
        """156/168 must travel with 'target -10'. Reading the delta alone is
        what let a worse skeleton look like a better break stage."""
        for before in (166, 162):
            with tempfile.TemporaryDirectory() as tmp:
                result = self._case(tmp, before_target=before)
            with self.subTest(before_target=before):
                self.assertIn("156/168", result["gate5_detail"])
                self.assertIn("92.9%", result["gate5_detail"])

    def test_the_absolute_ratio_is_a_column_not_only_prose(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = self._case(tmp)
        self.assertEqual(result["after_target_ratio"], "0.9286")

    def test_a_delta_only_pass_says_so_instead_of_reporting_pass(self):
        """The two runs above must not both read as an unqualified PASS."""
        with tempfile.TemporaryDirectory() as tmp:
            result = self._case(tmp, before_target=162)
        self.assertEqual(result["gate5_break_regression"],
                         "PASS_DELTA_ONLY_NO_ABSOLUTE_STANDARD")
        self.assertNotEqual(result["gate5_break_regression"], "PASS")
        self.assertIn("no absolute after-break minimum is configured",
                      result["gate5_detail"])

    def test_an_absolute_standard_catches_what_the_delta_missed(self):
        """The identical schedule that passed on delta fails on substance."""
        os.environ[self.gate.MINIMUM_AFTER_TARGET_RATIO_ENV] = "0.95"
        with tempfile.TemporaryDirectory() as tmp:
            result = self._case(tmp, before_target=162)
        self.assertEqual(result["gate5_break_regression"], "FAIL")
        self.assertIn("95.0%", result["gate5_detail"])

    def test_the_standard_comes_from_the_schedule_not_a_global(self):
        """Per schedule, from the workbook - different schedules differ.

        An environment variable applies one number to every scenario scored in
        the same report. Coverage owed after breaks is a per-contract
        commitment, so it travels with the schedule the way target_ratio does.
        """
        with tempfile.TemporaryDirectory() as tmp:
            result = self._case(tmp, before_target=162,
                                minimum_after_break_target_ratio=0.95)
        self.assertEqual(result["gate5_break_regression"], "FAIL")
        self.assertIn("workbook", result["gate5_detail"])

    def test_a_schedule_that_states_its_own_standard_ignores_the_environment(self):
        """A global must never override a contract that speaks for itself."""
        os.environ[self.gate.MINIMUM_AFTER_TARGET_RATIO_ENV] = "0.99"
        with tempfile.TemporaryDirectory() as tmp:
            result = self._case(tmp, before_target=162,
                                minimum_after_break_target_ratio=0.90)
        self.assertEqual(result["gate5_break_regression"], "PASS")
        self.assertIn("workbook", result["gate5_detail"])

    def test_two_schedules_can_hold_different_standards(self):
        """92.9% passes a 0.90 contract and fails a 0.95 one."""
        verdicts = {}
        for ratio in (0.90, 0.95):
            with tempfile.TemporaryDirectory() as tmp:
                verdicts[ratio] = self._case(
                    tmp, before_target=162,
                    minimum_after_break_target_ratio=ratio,
                )["gate5_break_regression"]
        self.assertEqual(verdicts[0.90], "PASS")
        self.assertEqual(verdicts[0.95], "FAIL")

    def test_a_percentage_in_the_workbook_is_accepted(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = self._case(tmp, before_target=162,
                                minimum_after_break_target_ratio=95)
        self.assertEqual(result["gate5_break_regression"], "FAIL")

    def test_the_environment_still_scores_artifacts_that_predate_the_row(self):
        os.environ[self.gate.MINIMUM_AFTER_TARGET_RATIO_ENV] = "0.95"
        with tempfile.TemporaryDirectory() as tmp:
            result = self._case(tmp, before_target=162)
        self.assertEqual(result["gate5_break_regression"], "FAIL")
        self.assertIn("environment", result["gate5_detail"])

    def test_a_configured_standard_that_is_met_is_a_real_pass(self):
        os.environ[self.gate.MINIMUM_AFTER_TARGET_RATIO_ENV] = "0.90"
        with tempfile.TemporaryDirectory() as tmp:
            result = self._case(tmp, before_target=162)
        self.assertEqual(result["gate5_break_regression"], "PASS")

    def test_a_percentage_is_accepted_as_well_as_a_ratio(self):
        os.environ[self.gate.MINIMUM_AFTER_TARGET_RATIO_ENV] = "95"
        with tempfile.TemporaryDirectory() as tmp:
            result = self._case(tmp, before_target=162)
        self.assertEqual(result["gate5_break_regression"], "FAIL")

    def test_an_unparseable_standard_is_not_silently_a_pass(self):
        """A typo must not read as 'configured and satisfied'."""
        os.environ[self.gate.MINIMUM_AFTER_TARGET_RATIO_ENV] = "not-a-number"
        with tempfile.TemporaryDirectory() as tmp:
            result = self._case(tmp, before_target=162)
        self.assertEqual(result["gate5_break_regression"],
                         "PASS_DELTA_ONLY_NO_ABSOLUTE_STANDARD")

    def test_a_real_delta_regression_still_fails(self):
        """The original question - did breaks wreck the schedule - still holds."""
        with tempfile.TemporaryDirectory() as tmp:
            result = self._case(tmp, before_target=166, after_target=120,
                                target_losses_from_breaks=46)
        self.assertEqual(result["gate5_break_regression"], "FAIL")
        self.assertIn("target loss", result["gate5_detail"])

    def test_an_absent_loss_column_is_not_zero_loss(self):
        """Found by this suite: a summary without the column scored as flawless.

        Same shape as A12 and A27 - a missing field read as a satisfied one.
        An older artifact that predates the column would have passed gate 5
        with a 46-interval regression sitting in its own before/after pair.
        """
        with tempfile.TemporaryDirectory() as tmp:
            result = self._case(tmp, before_target=166, after_target=120)
        self.assertEqual(result["gate5_break_regression"], "FAIL",
                         "loss must be derived from before/after when absent")
        self.assertIn("46", result["gate5_detail"])

    def test_a_summary_that_contradicts_itself_is_refused_not_scored(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = self._case(tmp, before_target=166, after_target=120,
                                target_losses_from_breaks=2)
        self.assertEqual(result["gate5_break_regression"], "FAIL")
        self.assertIn("inconsistent summary", result["gate5_detail"])

    def test_a_consistent_summary_is_not_flagged(self):
        """Both real AE AR B2B runs agree; they must stay clean."""
        for before, after, loss in ((166, 156, 10), (162, 156, 6)):
            with tempfile.TemporaryDirectory() as tmp:
                result = self._case(tmp, before_target=before, after_target=after,
                                    target_losses_from_breaks=loss)
            with self.subTest(before=before):
                self.assertNotIn("inconsistent", result["gate5_detail"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
