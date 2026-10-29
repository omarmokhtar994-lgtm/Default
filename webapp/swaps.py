# © 2026 Omar Mokhtar. All rights reserved.
"""Shift swaps (Phase AG, T6; the owner's answer 6 of 2026-10-14).

Two associates working the same day swap that day: each takes the other's shift, its breaks and its channel
stretches. A swap is offered only when it keeps the rules:
- the rest gap between shifts, for both;
- the same language, unless swapping changes no language coverage (worked out on the day as if swapped);
- channels: each must work every channel the other's shift needs (Chat and Phone against all three is fine only
  when the shift needs no Email).
The colleague accepts, then a supervisor or an admin approves; the rules and the shifts are checked again then, and
the swap is saved as a new version of the schedule, set in use (the earlier one kept).
"""
from __future__ import annotations

import json
import logging
import time
from datetime import date, timedelta
from typing import Any, Callable, Dict, List, Optional, Tuple

from .access import Access
from .attendance import day_index, hm
from .channel_people import ChannelPeople, can_work, channel_words
from .approvals import is_backup, may_approve_for, team_manager_of
from .leave import WAITING as LEAVE_WAITING, nice
from .versions import DAYS, shift_span


def _day_words(row: Dict[str, Any]) -> str:
    return date.fromisoformat(row['day']).strftime('%a %d %b')


OPEN = ("waiting_other", "waiting_tm", "applying")
STATUS_WORDS = {"waiting_other": "waiting for the colleague", "waiting_tm": "accepted, waiting for the TM",
                "applying": "being approved", "approved": "approved", "declined": "declined", "refused": "refused",
                "cancelled": "cancelled"}


def _languages(text: Optional[str]) -> frozenset:
    return frozenset(p.strip().casefold() for p in (text or "").replace(";", ",").split(",") if p.strip())


class SwapBook:
    def __init__(self, store, days, skills: Optional[Callable[[str], Dict[str, str]]] = None):
        self.store, self.days = store, days  # days: the DayBook (its .book is the ScheduleBook)
        self.skills = skills or ChannelPeople(store).skills_for_unit

    # ------------------------------------------------------------------ the rules
    def check(self, program: str, on: date, a: str, b: str, one_may_be_off: bool = False) -> Dict[str, Any]:
        """Whether ``a`` and ``b`` may swap ``on``: problems (empty when it keeps every rule) and facts. With
        ``one_may_be_off`` (Phase AO, a full-week swap) one of them may have the day off: then they exchange the
        shift and the day off, and the rules are checked for the one who takes the shift."""
        cells = dict(self.days.roster(program, on))
        out: Dict[str, Any] = {"ok": False, "blocked": False, "problems": [], "facts": [],
                               "a_cell": cells.get(a, ""), "b_cell": cells.get(b, "")}
        problems, facts = out["problems"], out["facts"]
        works = [n for n in (a, b) if shift_span(cells.get(n, ""))]
        if one_may_be_off and works:
            works = [a, b]
        for name in (a, b):
            if name not in works:
                problems.append(f"{name} does not work on {nice(on)}.")
        if problems:
            out["blocked"] = True  # Phase AO: nothing to swap, so no warning can make it a swap
            return out
        if out["a_cell"].strip().casefold() == out["b_cell"].strip().casefold():
            problems.append("They work the same shift that day.")
            out["blocked"] = True
            return out
        row = self.days.version(program, on)[0]
        week = json.loads(row["week"] or "{}")
        rest = int(float((week.get("settings") or {}).get("rest_gap_hours") or 0) * 60)
        for name, cell in ((a, out["b_cell"]), (b, out["a_cell"])):
            if not shift_span(cell):
                continue  # takes a day off: no shift to rest before
            lo, hi = shift_span(cell)
            try:
                self.days._rest(program, on, row, name, lo, hi, rest)
            except ValueError as exc:
                problems.append(str(exc))
        if not problems:
            facts.append("Rest between shifts kept for both")
        speaks = {p["name"]: _languages(p.get("language")) for p in week.get("associates", [])}
        if speaks.get(a) == speaks.get(b):
            facts.append("Same language")
        else:
            gaps = self._new_language_gaps(program, on, a, b)
            problems += gaps
            if not gaps:
                facts.append("Languages differ; no language coverage changes")
        skills = self.skills(program)
        needs = {name: {c["channel"] for c in week.get("channels") or []
                        if c.get("associate") == name and c.get("day") == DAYS[day_index(on)]} & set("PCE")
                 for name in (a, b)}
        before = len(problems)
        for taker, giver in ((a, b), (b, a)):
            missing = needs[giver] - set(can_work(skills, taker))
            if missing:
                problems.append(f"{taker} does not work {channel_words(''.join(sorted(missing)))}, which {giver}'s "
                                "shift needs.")
        if len(problems) == before:
            facts.append("Channels kept")
        out["ok"] = not problems
        return out

    def _new_language_gaps(self, program: str, on: date, a: str, b: str) -> List[str]:
        base, after = self.days.page(program, on), self.days.page(program, on, extra={"swap": (a, b)})
        step = after["view"].get("interval", 60)
        had = {l["name"]: {c["t"] for c in l["cells"] if c["cls"] == "bad"} for l in base["view"]["languages"]}
        out = []
        for lang in after["view"]["languages"]:
            new = sorted(c["t"] for c in lang["cells"] if c["cls"] == "bad" and c["t"] not in had.get(lang["name"], set()))
            if new:
                out.append(f"Swapping leaves no {lang['name']} speaker from {hm(new[0])} to {hm(new[-1] + step)}.")
        return out

    def candidates(self, program: str, on: date, name: str) -> List[Dict[str, Any]]:
        """Everyone else working ``on`` on another shift, each with whether a swap with ``name`` keeps the rules."""
        cells = dict(self.days.roster(program, on))
        mine = cells.get(name, "")
        if not shift_span(mine):
            return []
        out = []
        for other, cell in sorted(cells.items()):
            if other == name or not shift_span(cell) or cell.strip().casefold() == mine.strip().casefold():
                continue
            found = self.check(program, on, name, other)
            out.append({"name": other, "cell": cell, "ok": found["ok"], "problems": found["problems"],
                        "facts": found["facts"], "has_account": self.account(program, other) is not None})
        return out

    # ------------------------------------------------------------------ a whole week (Phase AO)
    def week_check(self, program: str, first: date, a: str, b: str, today: date) -> Dict[str, Any]:
        """Each day of the week from Sunday ``first``: what a full-week swap of ``a`` and ``b`` does that day.
        ``status`` is "swap" (they exchange their shift or day off; ``problems`` say what rule it breaks), or why the
        day is left as it is: "past", "leave" (either has Leave), "same" (the same shift or both off), "none" (no
        schedule, or nothing for either)."""
        days = []
        for i in range(7):
            on = first + timedelta(days=i)
            cells = dict(self.days.roster(program, on))
            ca, cb = cells.get(a, ""), cells.get(b, "")
            day = {"date": on, "day": DAYS[i], "a_cell": ca, "b_cell": cb, "status": "swap", "problems": [],
                   "facts": []}
            if on < today:
                day["status"] = "past"
            elif "leave" in (ca.strip().casefold(), cb.strip().casefold()):
                day["status"] = "leave"
            elif self.days.version(program, on)[0] is None or not (shift_span(ca) or shift_span(cb)):
                day["status"] = "none"
            elif ca.strip().casefold() == cb.strip().casefold():
                day["status"] = "same"
            else:
                found = self.check(program, on, a, b, one_may_be_off=True)
                day["problems"], day["facts"] = found["problems"], found["facts"]
            days.append(day)
        return {"days": days, "swap": [d for d in days if d["status"] == "swap"]}

    def week_candidates(self, program: str, first: date, name: str, today: date) -> List[Dict[str, Any]]:
        """Everyone else on the week's schedule with whom a full-week swap changes at least one day, with the days
        it changes and each day's warnings."""
        names = set()
        for i in range(7):
            names |= set(dict(self.days.roster(program, first + timedelta(days=i))))
        out = []
        for other in sorted(names - {name}):
            found = self.week_check(program, first, name, other, today)
            if found["swap"]:
                out.append({"name": other, "swap_days": len(found["swap"]),
                            "problems": [f"{nice(d['date'])}: {p}" for d in found["swap"] for p in d["problems"]],
                            "has_account": self.account(program, other) is not None})
        return out

    def _open_days(self, program: str, who: List[str]) -> Dict[str, set]:
        """The days each of ``who`` already has a swap waiting for (a day swap's day, or a week swap's days)."""
        taken: Dict[str, set] = {w: set() for w in who}
        for row in self.store.list_swaps(program=program, statuses=list(OPEN)):
            days = ({d["date"] for d in json.loads(row.get("detail") or "{}").get("days", [])}
                    if row.get("scope") == "week" else {row["day"]})
            for w in who:
                if w in (row["asker"], row["other"]):
                    taken[w] |= days
        return taken

    def offer_week(self, program: str, first: date, name: str, user_id: int, other: str, note: str, today: date,
                   allow_warnings: bool = False) -> int:
        """A full-week swap request for the week from Sunday ``first``: one request holding each day it changes."""
        found = self.week_check(program, first, name, other, today)
        swap = found["swap"]
        if not swap:
            raise ValueError("Nothing to swap in that week from today on.")
        problems = [f"{nice(d['date'])}: {p}" for d in swap for p in d["problems"]]
        if problems and not allow_warnings:
            raise ValueError(" ".join(problems))
        if self.account(program, other) is None:
            raise ValueError(f"{other} has no account to accept it. Ask your TM to swap you instead.")
        dates = {d["date"].isoformat() for d in swap}
        for who, taken in self._open_days(program, [name, other]).items():
            if taken & dates:
                raise ValueError(f"{who} already has a swap waiting for a day that week.")
        for who in (name, other):
            for row in self.store.list_leave(program=program, associate=who, statuses=[*LEAVE_WAITING, "approved"]):
                if any(row["first_day"] <= d <= row["last_day"] for d in dates):
                    raise ValueError(f"{who} has asked for leave in that week.")
        detail = {"week": first.isoformat(),
                  "days": [{"date": d["date"].isoformat(), "day": d["day"], "a": d["a_cell"], "b": d["b_cell"],
                            "warnings": d["problems"]} for d in swap],
                  "skipped": [{"date": d["date"].isoformat(), "why": d["status"]} for d in found["days"]
                              if d["status"] != "swap"]}
        return self.store.add_swap(program=program, day=swap[0]["date"].isoformat(), asker=name, asker_user=user_id,
                                   other=other, asker_cell=f"{len(swap)} days", other_cell=f"{len(swap)} days",
                                   note=" ".join((note or "").split())[:200], warnings="\n".join(problems),
                                   scope="week", detail=json.dumps(detail))

    # ------------------------------------------------------------------ asking and answering
    def account(self, program: str, name: str) -> Optional[Dict[str, Any]]:
        """The associate account linked to ``name`` on ``program``, if any."""
        for user in self.store.list_users():
            if (user["is_associate"] and user["active"] and user["roster_name"] == name
                    and Access(self.store, user).can_open(program)):
                return user
        return None

    def offer(self, program: str, on: date, name: str, user_id: int, other: str, note: str, today: date,
              allow_warnings: bool = False) -> int:
        """Phase AO: with ``allow_warnings`` a swap that breaks a rule is kept with its warnings, which the approvers
        see; two people with nothing to swap (one is off, or the same shift) are never kept."""
        if on < today:
            raise ValueError("Pick today or a later day.")
        found = self.check(program, on, name, other)
        if found["blocked"] or (not found["ok"] and not allow_warnings):
            raise ValueError(" ".join(found["problems"]))
        if self.account(program, other) is None:
            raise ValueError(f"{other} has no account to accept it. Ask your TM to swap you instead.")
        for who, taken in self._open_days(program, [name, other]).items():
            if on.isoformat() in taken:
                raise ValueError(f"{who} already has a swap waiting for {nice(on)}.")
        for who in (name, other):
            for row in self.store.list_leave(program=program, associate=who, statuses=[*LEAVE_WAITING, "approved"]):
                if row["first_day"] <= on.isoformat() <= row["last_day"]:
                    raise ValueError(f"{who} has asked for leave on {nice(on)}.")
        return self.store.add_swap(program=program, day=on.isoformat(), asker=name, asker_user=user_id, other=other,
                                   asker_cell=found["a_cell"], other_cell=found["b_cell"],
                                   note=" ".join((note or "").split())[:200], warnings="\n".join(found["problems"]))

    def _get(self, swap_id: int) -> Dict[str, Any]:
        row = self.store.get_swap(swap_id)
        if row is None:
            raise KeyError(swap_id)
        return row

    def _decided(self, swap_id: int) -> str:
        return f"This swap was already decided: {STATUS_WORDS.get(self._get(swap_id)['status'], '')}."

    def answer(self, swap_id: int, user: Dict[str, Any], accept: bool) -> str:
        row = self._get(swap_id)
        if not user.get("is_associate") or user.get("roster_name") != row["other"]:
            raise ValueError(f"Only {row['other']} can answer this.")
        if not self.store.move_swap(swap_id, "waiting_other", status="waiting_tm" if accept else "declined",
                                    answered_at=time.time()):
            raise ValueError(self._decided(swap_id))
        return "Accepted. Your TM decides next." if accept else "Declined."

    def cancel(self, swap_id: int, user_id: int) -> None:
        row = self._get(swap_id)
        if row["asker_user"] != user_id:
            raise ValueError("Only the person who asked can cancel it.")
        if row["status"] not in ("waiting_other", "waiting_tm") or not self.store.move_swap(
                swap_id, row["status"], status="cancelled"):
            raise ValueError(self._decided(swap_id))

    # ------------------------------------------------------------------ approvals (Phase AK: both team managers)
    def _sides(self, row: Dict[str, Any]) -> List[Tuple[Optional[int], str, str]]:
        """(associate's account id, name, the field that keeps who approved that side) for both people."""
        other = self.account(row["program"], row["other"])
        return [(row["asker_user"], row["asker"], "tm_a_id"), (other["id"] if other else None, row["other"], "tm_b_id")]

    def _mine(self, row: Dict[str, Any], user: Dict[str, Any]) -> List[Tuple[Optional[int], str, str]]:
        """The sides still waiting that ``user`` may approve."""
        return [s for s in self._sides(row) if row.get(s[2]) is None and may_approve_for(self.store, user, s[0])]

    def may_decide(self, row: Dict[str, Any], user: Dict[str, Any]) -> bool:
        return row["status"] == "waiting_tm" and bool(self._mine(row, user))

    def waiting_on(self, row: Dict[str, Any]) -> str:
        """Where a swap waits, in words: the colleague, then each team manager still to approve."""
        if row["status"] == "waiting_other":
            return f"Waiting for {row['other']} to accept"
        if row["status"] != "waiting_tm":
            return ""
        left: Dict[str, List[str]] = {}  # each team manager still to approve, with their people
        for uid, name, field in self._sides(row):
            if row.get(field) is None:
                manager = team_manager_of(self.store, uid)
                left.setdefault(manager["display_name"] if manager else "a team manager", []).append(name)
        return "Waiting for " + " and ".join(f"{who} ({' and '.join(names)})" for who, names in left.items())

    def decide(self, swap_id: int, user: Dict[str, Any], approve: bool, reason: str = "") -> str:
        """Phase AK: each person's team manager approves their side (one approval when they share one); an admin or
        a supervisor approves both at once; a refusal by any of them ends it. A final answer is posted to the group too
        (Phase AU)."""
        said = self._decide(swap_id, user, approve, reason)
        row = self._get(swap_id)
        if row["status"] in ("approved", "refused"):
            self._tell_the_group(row, user)
        return said

    def _tell_the_group(self, row: Dict[str, Any], user: Dict[str, Any]) -> None:
        notifier = getattr(self.days, "notifier", None)
        if notifier is None:
            return
        try:
            for who, other in ((row["asker"], row["other"]), (row["other"], row["asker"])):
                text = f"Swap with {other} on {_day_words(row)}: {row['status']}" + (
                    f" (“{row['reason']}”)" if row["status"] == "refused" and row["reason"] else "")
                notifier.queue(None, row["program"], row["day"], who, "request", text, user["display_name"],
                               ref=f"swap:{row['id']}")
        except Exception:  # noqa: BLE001 (the answer stands; the group post is what is lost, and logged)
            logging.getLogger(__name__).exception("group posts: could not queue the answer to swap %s", row["id"])

    def _decide(self, swap_id: int, user: Dict[str, Any], approve: bool, reason: str = "") -> str:
        row = self._get(swap_id)
        if row["status"] != "waiting_tm":
            raise ValueError(self._decided(swap_id))
        mine = self._mine(row, user)
        if not mine:
            raise ValueError(f"{self.waiting_on(row)}.")
        now = time.time()
        if not approve:
            if not self.store.move_swap(swap_id, "waiting_tm", status="refused", decided_by=user["id"], decided_at=now,
                                        reason=" ".join((reason or "").split())[:200]):
                raise ValueError(self._decided(swap_id))
            return "Refused."
        if not is_backup(self.store, user):
            for _, _, field in mine:
                if not self.store.move_swap(swap_id, "waiting_tm", **{field: user["id"]}):
                    raise ValueError(self._decided(swap_id))
            row = self._get(swap_id)
            if any(row.get(field) is None for _, _, field in self._sides(row)):
                return f"Approved for {' and '.join(name for _, name, _ in mine)}. {self.waiting_on(row)}."
        if not self.store.move_swap(swap_id, "waiting_tm", status="applying", decided_by=user["id"], decided_at=now):
            raise ValueError(self._decided(swap_id))
        try:
            outcome = self._apply(row, user["id"])
        except Exception:
            self.store.move_swap(swap_id, "applying", status="waiting_tm", decided_by=None, decided_at=None)
            raise
        self.store.move_swap(swap_id, "applying", status="approved", outcome=outcome)
        return f"Approved: {outcome}"

    def _apply_week(self, row: Dict[str, Any], user_id: int) -> str:
        program, a, b = row["program"], row["asker"], row["other"]
        detail = json.loads(row["detail"] or "{}")
        versions = set()
        for d in detail["days"]:
            on = date.fromisoformat(d["date"])
            cells = dict(self.days.roster(program, on))
            for name, was in ((a, d["a"]), (b, d["b"])):
                if cells.get(name, "") != was:
                    raise ValueError(f"The schedule changed since it was asked: {name} now has "
                                     f"{cells.get(name) or 'nothing'} on {nice(on)}.")
            found = self.check(program, on, a, b, one_may_be_off=True)
            if found["blocked"] or (not found["ok"] and not row.get("warnings")):
                raise ValueError(f"The swap no longer keeps the rules on {nice(on)}: " + " ".join(found["problems"]))
            versions.add(self.days.version(program, on)[0]["id"])
        if len(versions) != 1:
            raise ValueError("That week is on more than one schedule version, so it cannot be swapped as one. "
                             "Ask the TM to swap them one day at a time.")
        book = self.days.book
        new_id = book.swap_week_days(versions.pop(), user_id, a, b, [d["day"] for d in detail["days"]],
                                     reason=f"Week swap approved (request {row['id']})",
                                     label=f"Week swap of {a} and {b}")
        book.set_in_use(new_id, user_id)
        kept = f" Warnings kept: {' '.join(row['warnings'].splitlines())}" if row.get("warnings") else ""
        return (f"{a} and {b} swapped {len(detail['days'])} day{'s' if len(detail['days']) != 1 else ''} "
                f"({', '.join(nice(date.fromisoformat(d['date'])) for d in detail['days'])}), each with the other's "
                "breaks and channels." + kept)

    def _apply(self, row: Dict[str, Any], user_id: int) -> str:
        if row.get("scope") == "week":
            return self._apply_week(row, user_id)
        program, on, a, b = row["program"], date.fromisoformat(row["day"]), row["asker"], row["other"]
        cells = dict(self.days.roster(program, on))
        for name, was in ((a, row["asker_cell"]), (b, row["other_cell"])):
            if cells.get(name, "") != was:
                raise ValueError(f"The schedule changed since it was asked: {name} now has "
                                 f"{cells.get(name) or 'nothing'} on {nice(on)}.")
        found = self.check(program, on, a, b)
        if found["blocked"] or (not found["ok"] and not row.get("warnings")):
            raise ValueError("The swap no longer keeps the rules: " + " ".join(found["problems"]))
        version = self.days.version(program, on)[0]
        book = self.days.book
        new_id = book.swap_day(version["id"], user_id, a, b, DAYS[day_index(on)], reason=f"Swap approved (request "
                               f"{row['id']})", label=f"Swap of {a} and {b}")
        book.set_in_use(new_id, user_id)
        kept = f" Warning kept: {' '.join(found['problems'])}" if found["problems"] else ""
        return (f"{a} works {row['other_cell']} and {b} works {row['asker_cell']} on {nice(on)}, each with the "
                "other's breaks and channels." + kept)

    # ------------------------------------------------------------------ lists
    def _label(self, row: Dict[str, Any]) -> Dict[str, Any]:
        on = date.fromisoformat(row["day"])
        what = (f"Week from {nice(on)}: {row['asker_cell']}" if row.get("scope") == "week"
                else f"{nice(on)}: {row['asker_cell']} for {row['other_cell']}")
        return dict(row, label=what,
                    warning_list=[w for w in (row.get("warnings") or "").split("\n") if w],
                    status_words=STATUS_WORDS.get(row["status"], row["status"]), waiting_on=self.waiting_on(row))

    def waiting(self, program: str) -> List[Dict[str, Any]]:
        return [self._label(r) for r in self.store.list_swaps(program=program, statuses=["waiting_other", "waiting_tm"])]

    def decided(self, program: str, limit: Optional[int] = 20) -> List[Dict[str, Any]]:
        rows = self.store.list_swaps(program=program, statuses=["approved", "declined", "refused", "cancelled"])
        rows.sort(key=lambda r: -(r["decided_at"] or r["answered_at"] or r["asked"]))
        return [self._label(r) for r in rows[:limit]]

    def mine(self, program: str, name: str) -> List[Dict[str, Any]]:
        return [self._label(r) for r in self.store.list_swaps(program=program) if name in (r["asker"], r["other"])]

    def count_for(self, program: str, user: Dict[str, Any]) -> int:
        return sum(1 for r in self.store.list_swaps(program=program, statuses=["waiting_tm"]) if self.may_decide(r, user))
