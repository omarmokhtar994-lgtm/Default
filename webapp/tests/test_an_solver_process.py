# © 2026 Omar Mokhtar. All rights reserved.
"""A native solver failure must not kill the web server or replace a saved draft."""
import json
import subprocess
import sys
import unittest
from unittest import mock

from ortools.sat.python import cp_model

from webapp import channel_solver
from webapp.tests.test_channel_page import _Page


class TheSolverProcess(unittest.TestCase):
    def model(self):
        model = cp_model.CpModel()
        value = model.NewIntVar(0, 10, "value")
        model.Add(value <= 7)
        model.Maximize(value)
        return model, value

    def settings(self):
        return {"num_workers": 1, "max_time_in_seconds": 2.0, "random_seed": 9000}

    def test_the_real_child_preserves_the_model_and_parameters(self):
        model, value = self.model()
        direct = cp_model.CpSolver()
        for key, item in self.settings().items():
            setattr(direct.parameters, key, item)
        status = direct.Solve(model)
        before = str(model.Proto())
        found = channel_solver.solve(model, self.settings())
        self.assertEqual(found.status, status)
        self.assertEqual(found.status_name, direct.StatusName(status))
        self.assertEqual(found.value(value), direct.Value(value))
        self.assertEqual(found.parameters, str(direct.parameters))
        self.assertEqual(str(model.Proto()), before)

    def test_infeasibility_is_not_reported_as_a_crash(self):
        model, value = self.model()
        model.Add(value >= 9)
        found = channel_solver.solve(model, self.settings())
        self.assertEqual(found.status, cp_model.INFEASIBLE)
        self.assertEqual(found.values, [])

    def test_invalid_models_keep_their_own_status(self):
        model = cp_model.CpModel()
        model.NewIntVar(2, 1, "empty_domain")
        found = channel_solver.solve(model, self.settings())
        self.assertEqual(found.status, cp_model.MODEL_INVALID)

    def test_a_native_child_crash_is_reported_and_the_parent_survives(self):
        command = [sys.executable, "-c", "import os, signal; os.kill(os.getpid(), signal.SIGSEGV)"]
        model, value = self.model()
        with mock.patch.object(channel_solver, "_command", return_value=command):
            with self.assertLogs("webapp.channel_solver", level="ERROR") as logged:
                with self.assertRaisesRegex(channel_solver.SolverStopped, "stopped unexpectedly"):
                    channel_solver.solve(model, self.settings())
        self.assertIn("-11", " ".join(logged.output))
        self.assertEqual(channel_solver.solve(model, self.settings()).value(value), 7)

    def test_a_hung_child_is_killed_and_reaped(self):
        command = [sys.executable, "-c", "import time; time.sleep(30)"]
        launched = []
        popen = subprocess.Popen

        def track(*args, **kwargs):
            child = popen(*args, **kwargs)
            launched.append(child)
            return child

        with mock.patch.object(channel_solver, "_command", return_value=command), \
                mock.patch.object(channel_solver, "STARTUP_GRACE", 0.2), \
                mock.patch.object(channel_solver.subprocess, "Popen", side_effect=track):
            with self.assertLogs("webapp.channel_solver", level="ERROR"):
                with self.assertRaisesRegex(channel_solver.SolverStopped, "time allowed"):
                    channel_solver.solve(self.model()[0], {"max_time_in_seconds": 0.01})
        self.assertEqual(len(launched), 1)
        self.assertIsNotNone(launched[0].poll())

    def test_an_incomplete_answer_is_never_used(self):
        def command(request, response):
            body = json.dumps({"status": 4, "status_name": "OPTIMAL", "values": [], "parameters": ""})
            return [sys.executable, "-c", "import pathlib,sys; pathlib.Path(sys.argv[1]).write_text(sys.argv[2])",
                    str(response), body]

        with mock.patch.object(channel_solver, "_command", side_effect=command):
            with self.assertLogs("webapp.channel_solver", level="ERROR"):
                with self.assertRaises(channel_solver.SolverStopped):
                    channel_solver.solve(self.model()[0], self.settings())


class TheCrashOnThePage(_Page):
    @classmethod
    def setUpClass(cls):
        cls.start()

    def test_a_solver_crash_keeps_the_existing_draft_and_the_site_alive(self):
        kept = {"blocks": {}, "breaks": {}, "moved": [], "note": "Keep this draft"}
        self.store.set_channel_draft(self.version["id"], "Wed", kept, 1)
        before = self.store.get_channel_draft(self.version["id"])
        week = self.store.get_schedule(self.version["id"])["week"]
        command = [sys.executable, "-c", "import os, signal; os.kill(os.getpid(), signal.SIGSEGV)"]
        with mock.patch.object(channel_solver, "_command", return_value=command):
            with self.assertLogs("webapp.channel_solver", level="ERROR"):
                response = self.post(action="suggest", move="1")
        self.assertEqual(response.status_code, 303)
        self.assertEqual(self.store.get_channel_draft(self.version["id"]), before)
        self.assertEqual(self.store.get_schedule(self.version["id"])["week"], week)
        code, page = self.page()
        self.assertEqual(code, 200)
        self.assertIn("Channel planning stopped unexpectedly", page)


if __name__ == "__main__":
    unittest.main()
