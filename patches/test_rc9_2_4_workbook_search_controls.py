#!/usr/bin/env python3
"""B-7: the workbook had no route to ~40 behavioural engine parameters.

Search shape, reserve budgets, quality minimums and the solver seed could only
be set on the command line. Worse, the production runner passes its own value
for nearly every one of them, and on the command line a runner default is
indistinguishable from a typed argument - so even adding workbook rows would
have achieved nothing without teaching the runner to stand aside.

These tests are written from both ends. The route has to work, and a workbook
that states none of these rows has to behave exactly as it did before.
"""
from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parent.parent
ENGINE = ROOT / "engine" / "_tools" / "l632_universal_scheduler.py"
RUNNER = ROOT / "engine" / "RUN_UNIVERSAL_PRODUCTION.py"
sys.path.insert(0, str(ROOT / "engine" / "_tools"))

import l632_universal_scheduler as E  # noqa: E402


def load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def im(**rows):
    """An instruction map keyed the way the parser normalizes labels."""
    return {E.norm(k.replace("_", " ")): v for k, v in rows.items()}


class ParsingWhatTheWorkbookStates(unittest.TestCase):
    def test_a_workbook_that_states_nothing_yields_nothing(self):
        # This is the whole behaviour-preservation argument: absent means
        # absent, not "the default", so the engine keeps the value it had.
        self.assertEqual(E._parse_search_controls({}), {})

    def test_a_blank_cell_is_not_a_value(self):
        raw = {E.norm("Solver Random Seed"): "  ", E.norm("Joint Patterns Per Shift"): None}
        self.assertEqual(E._parse_search_controls(raw), {})

    def test_each_kind_parses(self):
        raw = {
            E.norm("Solver Random Seed"): 4242,
            E.norm("Minimum After90 Gain Per After80 Loss"): "1.5",
            E.norm("Safe Incumbent Enabled"): "no",
            E.norm("Joint Change Limits"): "8, 16 ,24",
            E.norm("Skeleton Profiles"): "target90_restore_champion; floor_protected",
        }
        controls = E._parse_search_controls(raw)
        self.assertEqual(controls["solver_random_seed"], 4242)
        self.assertEqual(controls["min_after90_gain_per_after80_loss"], 1.5)
        self.assertIs(controls["safe_incumbent"], False)
        self.assertEqual(controls["joint_change_limits"], [8, 16, 24])
        self.assertEqual(controls["skeleton_profile_names"],
                         ["target90_restore_champion", "floor_protected"])

    def test_an_enabled_row_reads_as_true(self):
        controls = E._parse_search_controls({E.norm("Joint Refinement Enabled"): "Yes"})
        self.assertIs(controls["joint_refinement"], True)

    def test_a_row_that_cannot_be_read_is_a_contract_failure_not_a_default(self):
        # A scheduler who typed a value into the business contract must not
        # have it silently discarded.
        for label, value, kind in (("Solver Random Seed", "abc", "int"),
                                   ("Solver Random Seed", "7.5", "int"),
                                   ("Safe Incumbent Enabled", "maybe", "bool"),
                                   ("Joint Change Limits", "8,x,24", "int list"),
                                   ("Minimum After90 Gain Per After80 Loss", "n/a", "float")):
            with self.subTest(label=label, value=value):
                warnings = []
                controls = E._parse_search_controls({E.norm(label): value}, warnings)
                self.assertEqual(controls, {})
                self.assertEqual(len(warnings), 1, warnings)
                self.assertTrue(warnings[0].startswith("HARD_INVALID_SEARCH_CONTROL"))
                self.assertIn(label, warnings[0])
                self.assertIn(kind, warnings[0])

    def test_the_hard_prefix_makes_it_fail_closed(self):
        # The HARD_ convention is what turns a parser warning into a blocked
        # run. Without the prefix a bad control row would only be noted.
        self.assertTrue(all(
            w.startswith("HARD_")
            for w in [E._parse_search_controls({E.norm("Solver Random Seed"): "abc"}, w0) or w0[0]
                      for w0 in ([],)]))


class TheTablesCannotDriftApart(unittest.TestCase):
    """Three lists describe the same parameters. Any two disagreeing is a bug."""

    def setUp(self):
        import inspect
        self.run_case_params = set(inspect.signature(E.run_case).parameters)
        self.parser = E.build_arg_parser()
        self.parser_dests = {a.dest for a in self.parser._actions}

    def test_every_workbook_control_names_a_real_engine_parameter(self):
        for name, _, _ in E.WORKBOOK_SEARCH_CONTROLS:
            with self.subTest(name=name):
                self.assertIn(name, self.run_case_params)

    def test_every_cli_route_names_a_real_argparse_destination(self):
        for dest, _, _ in E.CLI_SEARCH_CONTROL_DESTS:
            with self.subTest(dest=dest):
                self.assertIn(dest, self.parser_dests)

    def test_every_cli_route_has_a_workbook_row(self):
        workbook_names = {name for name, _, _ in E.WORKBOOK_SEARCH_CONTROLS}
        for _, name, _ in E.CLI_SEARCH_CONTROL_DESTS:
            with self.subTest(name=name):
                self.assertIn(name, workbook_names)

    def test_every_workbook_row_has_a_cli_route(self):
        cli_names = {name for _, name, _ in E.CLI_SEARCH_CONTROL_DESTS}
        for name, _, _ in E.WORKBOOK_SEARCH_CONTROLS:
            with self.subTest(name=name):
                self.assertIn(name, cli_names)

    def test_no_alias_is_claimed_by_two_parameters(self):
        seen = {}
        for name, aliases, _ in E.WORKBOOK_SEARCH_CONTROLS:
            for alias in aliases:
                key = E.norm(alias)
                self.assertNotIn(key, seen,
                                 f"{alias!r} is claimed by {seen.get(key)} and {name}")
                seen[key] = name

    def test_list_valued_controls_are_declared_as_lists_on_both_sides(self):
        kinds = {name: kind for name, _, kind in E.WORKBOOK_SEARCH_CONTROLS}
        for name in E._LIST_SEARCH_CONTROLS:
            with self.subTest(name=name):
                self.assertIn(kinds[name], {"int_list", "str_list"})


class TellingATypedFlagFromADefault(unittest.TestCase):
    def setUp(self):
        self.parser = E.build_arg_parser()

    def base(self):
        return ["--input", "x.xlsx", "--output", "y.xlsx"]

    def test_an_untyped_flag_is_not_reported_as_supplied(self):
        supplied = E.explicitly_supplied_options(self.parser, self.base())
        self.assertNotIn("solver_random_seed", supplied)
        self.assertNotIn("joint_patterns_per_shift", supplied)
        self.assertNotIn("disable_safe_incumbent", supplied)

    def test_a_typed_flag_is_reported_even_at_its_default_value(self):
        # This is the case a parsed namespace cannot distinguish, and the one
        # that decides whether the workbook gets to speak.
        default_seed = self.parser.get_default("solver_random_seed")
        supplied = E.explicitly_supplied_options(
            self.parser, self.base() + ["--solver-random-seed", str(default_seed)])
        self.assertIn("solver_random_seed", supplied)

    def test_a_typed_store_true_flag_is_reported(self):
        supplied = E.explicitly_supplied_options(
            self.parser, self.base() + ["--disable-safe-incumbent"])
        self.assertIn("disable_safe_incumbent", supplied)

    def test_detection_does_not_disturb_the_real_parse(self):
        argv = self.base() + ["--solver-random-seed", "77"]
        before = self.parser.parse_args(argv)
        E.explicitly_supplied_options(self.parser, argv)
        after = self.parser.parse_args(argv)
        self.assertEqual(vars(before), vars(after))


class TranslatingTypedFlagsToEngineValues(unittest.TestCase):
    def setUp(self):
        self.parser = E.build_arg_parser()

    def controls(self, extra):
        argv = ["--input", "x.xlsx", "--output", "y.xlsx"] + extra
        args = self.parser.parse_args(argv)
        return E.cli_search_controls(args, E.explicitly_supplied_options(self.parser, argv))

    def test_nothing_typed_yields_nothing(self):
        self.assertEqual(self.controls([]), {})

    def test_a_scalar_is_carried_through(self):
        self.assertEqual(self.controls(["--solver-random-seed", "77"]),
                         {"solver_random_seed": 77})

    def test_a_disable_flag_becomes_the_capability_turned_off(self):
        self.assertEqual(self.controls(["--disable-joint-refinement"]),
                         {"joint_refinement": False})
        self.assertEqual(self.controls(["--disable-bundled-fallbacks"]),
                         {"include_bundled_fallbacks": False})

    def test_a_list_flag_is_split_the_way_the_engine_expects(self):
        self.assertEqual(self.controls(["--joint-change-limits", "4,8,12"]),
                         {"joint_change_limits": [4, 8, 12]})
        self.assertEqual(self.controls(["--skeleton-profiles", "a,b"]),
                         {"skeleton_profile_names": ["a", "b"]})

    def test_an_empty_list_flag_is_not_a_choice(self):
        # "" is how the runner spells "I have no opinion" for these two.
        self.assertEqual(self.controls(["--skeleton-profiles", ""]), {})


class PrecedenceInsideRunCase(unittest.TestCase):
    """The resolution order, read from the source that performs it."""

    def setUp(self):
        self.source = ENGINE.read_text(encoding="utf-8")
        start = self.source.index("_typed = dict(cli_search_controls or {})")
        self.block = self.source[start:start + 6000]

    def test_the_command_line_is_applied_after_the_workbook(self):
        typed_at = self.block.index("_resolved.update(_typed)")
        workbook_at = self.block.index("dict(parsed.search_controls)")
        self.assertLess(workbook_at, typed_at,
                        "the command line must overwrite the workbook, not the reverse")

    def test_every_control_falls_back_to_the_value_run_case_was_called_with(self):
        # `_resolved.get(name, <current value>)` is what keeps a parameter that
        # neither side sets at exactly the default it always had.
        compact = " ".join(self.block.split())
        for name, _, _ in E.WORKBOOK_SEARCH_CONTROLS:
            with self.subTest(name=name):
                self.assertIn(f'_resolved.get( "{name}", {name})'.replace("( ", "("),
                              compact.replace("( ", "("))

    def test_the_run_records_which_side_won(self):
        self.assertIn('"source": "command_line" if name in _typed else "workbook"',
                      self.block)
        self.assertIn('"search_control_decisions": search_control_decisions', self.source)

    def test_pattern_widths_are_normalized_after_the_workbook_is_read(self):
        # They used to be normalized before parse_input, where no workbook
        # value could exist yet, so a workbook-stated list would have skipped
        # the guard that a command-line one gets.
        normalize_at = self.source.index(
            "pattern_widths = sorted({max(1, int(x)) for x in pattern_widths})")
        parse_at = self.source.index("parsed = parse_input(")
        self.assertLess(parse_at, normalize_at)


class TheRunnerStandsAsideForTheWorkbook(unittest.TestCase):
    def setUp(self):
        self.runner = load("rc924_runner_controls", RUNNER)
        self.args = SimpleNamespace(
            num_workers=2, pattern_widths="24,44,60,115",
            repair_change_limits="2,4,6,8,12", skeleton_profiles="a,b",
            break_objective_modes="m1,m2", solver_random_seed=9000)
        self.mode_defaults = {"adaptive": 18, "post": 180, "target": 180, "final": 120,
                              "safe": 180, "joint": 900, "joint_attempts": 16,
                              "joint_no_improve": 6}

    def flags(self, workbook_controls, argv=None):
        parser = self.runner.build_parser()
        saved = sys.argv
        sys.argv = ["RUN_UNIVERSAL_PRODUCTION.py"] + (argv or [])
        try:
            return self.runner.engine_flags_for_run(
                self.args, self.mode_defaults, parser, workbook_controls)
        finally:
            sys.argv = saved

    def pairs(self, flags):
        return {flags[i]: flags[i + 1] for i in range(0, len(flags), 2)}

    def test_a_silent_workbook_leaves_every_flag_exactly_as_it_was(self):
        pairs = self.pairs(self.flags(set()))
        self.assertEqual(len(pairs), 24)
        self.assertEqual(pairs["--solver-random-seed"], "9000")
        self.assertEqual(pairs["--adaptive-no-improvement-attempts"], "18")
        self.assertEqual(pairs["--joint-change-limits"], "8,16,24,36,54")
        self.assertEqual(pairs["--coordinated-repair-cycles"], "1")

    def test_a_stated_control_makes_the_runner_drop_its_own_value(self):
        pairs = self.pairs(self.flags({"solver_random_seed", "joint_patterns_per_shift"}))
        self.assertNotIn("--solver-random-seed", pairs)
        self.assertNotIn("--joint-patterns-per-shift", pairs)
        self.assertEqual(len(pairs), 22)

    def test_an_operator_who_typed_the_flag_still_outranks_the_workbook(self):
        pairs = self.pairs(
            self.flags({"solver_random_seed"}, ["--solver-random-seed", "9000"]))
        self.assertEqual(pairs["--solver-random-seed"], "9000")

    def test_the_runners_own_depth_arithmetic_always_yields_to_the_workbook(self):
        # These have no option on the runner, so there is nothing an operator
        # could have typed and the workbook is always the more specific voice.
        pairs = self.pairs(self.flags({"joint_refinement_reserve_sec"},
                                      ["--joint-refinement-reserve-sec", "5"]))
        self.assertNotIn("--joint-refinement-reserve-sec", pairs)

    def test_every_runner_flag_maps_to_a_known_engine_parameter(self):
        workbook_names = {name for name, _, _ in E.WORKBOOK_SEARCH_CONTROLS}
        for _, _, parameter in self.runner._RUNNER_SEARCH_FLAGS:
            with self.subTest(parameter=parameter):
                self.assertIn(parameter, workbook_names)

    def test_the_runner_reports_what_the_workbook_took_over(self):
        source = RUNNER.read_text(encoding="utf-8")
        self.assertIn("workbook states", source)
        self.assertIn("_contract_run_settings(input_path)", source)


class PackagedWorkbooksAreUnaffected(unittest.TestCase):
    """Nothing ships with these rows, so nothing ships with a behaviour change."""

    def workbooks(self):
        return sorted((ROOT / "inputs").glob("*.xlsx"))

    def test_no_packaged_workbook_states_a_search_control(self):
        books = self.workbooks()
        if not books:
            self.skipTest("packaged inputs not present")
        for book in books:
            with self.subTest(book=book.name):
                parsed = E.parse_input(book)
                self.assertEqual(parsed.search_controls, {})

    def test_no_packaged_workbook_raises_a_search_control_warning(self):
        books = self.workbooks()
        if not books:
            self.skipTest("packaged inputs not present")
        for book in books:
            with self.subTest(book=book.name):
                parsed = E.parse_input(book)
                offending = [w for w in parsed.parser_warnings
                             if "SEARCH_CONTROL" in str(w)]
                self.assertEqual(offending, [])

    def test_search_controls_are_not_part_of_the_coverage_contract(self):
        # A deliberate decision, pinned so it stays one. The canonical contract
        # answers "what must this schedule satisfy"; how hard to search for it
        # is not part of that question, so two workbooks that differ only in
        # search shape are the same contract. The run's own choices are
        # recorded in the audit under search_control_decisions instead.
        books = self.workbooks()
        if not books:
            self.skipTest("packaged inputs not present")
        parsed = E.parse_input(books[0])
        baseline = E.canonical_hash(E.canonical_contract_snapshot(parsed))
        object.__setattr__(parsed, "search_controls", {"solver_random_seed": 123})
        self.assertEqual(
            E.canonical_hash(E.canonical_contract_snapshot(parsed)), baseline)


if __name__ == "__main__":
    unittest.main(verbosity=1)
