# © 2026 Omar Mokhtar. All rights reserved.
"""Real DayBook checks for atomic apply and one-step Undo.

Owner B restores AM's today-owned shifts and four-field payload. The discarded
24-hour adapter tests are replaced by its scope regression in test_an_decisions.
These integration tests require the application runtime.
"""
import unittest
from unittest import mock

from webapp.tests.test_am_fix_channels import TheFix, WED


class AtomicApply(TheFix):
    def test_invalid_later_change_keeps_no_channel_or_journal_rows(self):
        plan = self.days.channel_fix_plan(self.key, WED, now=600)
        first = plan["changes"][0][:4]
        before = self.store.day_rows(self.key, [WED.isoformat()])
        actions = self.store.day_actions(self.key, WED.isoformat())
        with self.assertRaises(ValueError):
            self.days.apply_channel_fix(self.key, WED, [first, (first[0], -15, 0, "P")], self.user, now=600)
        self.assertEqual(self.store.day_rows(self.key, [WED.isoformat()]), before)
        self.assertEqual(self.store.day_actions(self.key, WED.isoformat()), actions)

    def test_write_failure_rolls_back_channel_log_and_undo_entry(self):
        plan = self.days.channel_fix_plan(self.key, WED, now=600)
        first = plan["changes"][0][:4]
        before = self.store.day_rows(self.key, [WED.isoformat()])
        actions = self.store.day_actions(self.key, WED.isoformat())
        move = self.days.channel_move
        calls = 0

        def fail_later(*args, **kwargs):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise ValueError("simulated later write failure")
            return move(*args, **kwargs)

        with mock.patch.object(self.days, "channel_move", side_effect=fail_later):
            with self.assertRaisesRegex(ValueError, "later write failure"):
                self.days.apply_channel_fix(self.key, WED, [first, first], self.user, now=600)
        self.assertEqual(self.store.day_rows(self.key, [WED.isoformat()]), before)
        self.assertEqual(self.store.day_actions(self.key, WED.isoformat()), actions)


if __name__ == "__main__":
    unittest.main()
