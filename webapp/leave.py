# © 2026 Omar Mokhtar. All rights reserved.
"""Leave requests and their approval (Phase AG, T5; the owner's answers of 2026-10-14).

An associate asks for Planned leave, a Public holiday or Exam leave (Phase AI) for a run of days. There is no fixed number of places a day:
each day shows what the floor loses if it is approved, and the approvers decide. Two approvals: the TM (a supervisor
or an admin) first, then the RTA (another staff member of the program). The RTA's approval writes Leave on the days
the person works into a new version of the schedule and sets it in use (the earlier version is kept); days off and
days with no schedule yet are said, not changed. A Planned leave balance per person and year, typed or pasted by
managers, is shown to the approvers: it warns, it does not refuse.
"""
from __future__ import annotations

import json
import time
from datetime import date, timedelta
from typing import Any, Dict, List, Optional

from .approvals import may_approve_for, who_approves
from .permissions import allowed
from .attendance import day_index, hm
from .versions import DAYS, shift_span

KINDS = ("Planned leave", "Public holiday", "Exam leave")
WAITING = ("waiting_tm", "waiting_rta")
MAX_DAYS = 31
NOTE_MAX = 200
ABSENT_FOR_IMPACT = {"status": "Unplanned leave", "from": None, "to": None, "billable": False}


def nice(on: date) -> str:
    return f"{on:%a %d %b}"


def joined(texts: List[str]) -> str:
    """A, B and C."""
    return " and ".join([", ".join(texts[:-1]), texts[-1]]) if len(texts) > 1 else "".join(texts)


def number(value: float) -> str:
    return f"{value:g}"


def span_text(first: date, last: date) -> str:
    return nice(first) if first == last else f"{nice(first)} to {nice(last)}"


class LeaveBook:
    def __init__(self, store, days):
        self.store, self.days = store, days  # days: the DayBook (its .book is the ScheduleBook)

    # ------------------------------------------------------------------ the schedule
    def names(self, program: str) -> List[str]:
        """Names on the schedules of ``program``'s last four kept weeks (Phase AO: not only the newest, which may be
        partly filled)."""
        found = set()
        for week in self.days.book.kept_weeks(program)[-4:]:
            for v in self.store.list_schedules(program=program, week_start=week["week"]):
                found |= {a["name"] for a in json.loads(v["week"] or "{}").get("associates", [])}
        return sorted(found)

    def days_of(self, program: str, name: str, first: date, last: date) -> List[Dict[str, Any]]:
        """Each day with the person's cell on the schedule holding it: a shift, OFF, Leave, or "" (no schedule kept
        for that day, or not on it)."""
        out, on = [], first
        while on <= last:
            out.append({"date": on, "cell": dict(self.days.roster(program, on)).get(name, ""),
                        "kept": self.days.version(program, on)[0] is not None})
            on += timedelta(days=1)
        return out

    @staticmethod
    def counted(days: List[Dict[str, Any]]) -> int:
        """Days a request uses: days worked (or already Leave), and days with no schedule yet."""
        return sum(1 for d in days if shift_span(d["cell"]) or d["cell"].casefold() == "leave" or not d["kept"])

    # ------------------------------------------------------------------ asking
    def ask(self, program: str, name: str, user_id: int, kind: str, first: date, last: date, note: str,
            today: date) -> int:
        if kind not in KINDS:
            raise ValueError("Pick Planned leave, Public holiday or Exam leave.")
        if first < today:
            raise ValueError("Pick today or a later day.")
        if last < first:
            raise ValueError("The last day must be on or after the first.")
        if (last - first).days >= MAX_DAYS:
            raise ValueError(f"Ask for {MAX_DAYS} days at most.")
        days = self.days_of(program, name, first, last)
        kept = [d for d in days if d["kept"]]
        if kept and not any(d["cell"] for d in kept):
            raise ValueError(f"{name} is not on this program's schedule.")
        if kept and len(kept) == len(days) and not any(shift_span(d["cell"]) for d in kept):
            raise ValueError(f"{name} does not work on any of these days.")
        for other in self.store.list_leave(program=program, associate=name, statuses=[*WAITING, "applying", "approved"]):
            lo, hi = max(first.isoformat(), other["first_day"]), min(last.isoformat(), other["last_day"])
            if lo <= hi:
                raise ValueError(f"{name} already asked for leave on {nice(date.fromisoformat(lo))}.")
        return self.store.add_leave(program=program, associate=name, user_id=user_id, kind=kind,
                                    first_day=first.isoformat(), last_day=last.isoformat(),
                                    note=" ".join((note or "").split())[:NOTE_MAX])

    def recover(self) -> int:
        """Phase AI: requests left "applying" by a server stopped during the RTA's approval go back to the RTA, who
        approves again to finish them (days already Leave are not changed twice). Run when the website starts."""
        return sum(1 for row in self.store.list_leave(statuses=["applying"])
                   if self.store.move_leave(row["id"], "applying", status="waiting_rta", rta_id=None, rta_at=None))

    def cancel(self, request_id: int, user_id: int) -> None:
        row = self._get(request_id)
        if row["user_id"] != user_id:
            raise ValueError("Only the person who asked can cancel it.")
        if row["status"] not in WAITING or not self.store.move_leave(request_id, row["status"], status="cancelled"):
            raise ValueError(self._decided(request_id))

    # ------------------------------------------------------------------ deciding
    def _get(self, request_id: int) -> Dict[str, Any]:
        row = self.store.get_leave(request_id)
        if row is None:
            raise KeyError(request_id)
        return row

    def _decided(self, request_id: int) -> str:
        status = self._get(request_id)["status"]
        return f"This request was already decided: {'being applied' if status == 'applying' else status}."

    def decide(self, request_id: int, user: Dict[str, Any], approve: bool, reason: str = "") -> str:
        """The TM's approval (the first) or the RTA's (the second, which changes the schedule); a refusal ends it."""
        row = self._get(request_id)
        if row["status"] not in WAITING:
            raise ValueError(self._decided(request_id))
        reason, now = " ".join((reason or "").split())[:NOTE_MAX], time.time()
        if row["status"] == "waiting_tm":
            if not may_approve_for(self.store, user, row["user_id"]):  # Phase AK: their team manager, or a backup
                raise ValueError(f"{self.waiting_on(row)}.")
            moved = self.store.move_leave(request_id, "waiting_tm", status="waiting_rta" if approve else "refused",
                                          tm_id=user["id"], tm_at=now, reason="" if approve else reason)
            if not moved:
                raise ValueError(self._decided(request_id))
            return "Approved by the TM: the RTA decides next." if approve else "Refused."
        if user["id"] == row["tm_id"]:
            raise ValueError("Someone other than the TM gives the RTA's approval.")
        if not allowed(self.store, user, "approve_rta"):  # Phase AK: the roles an admin allows on Roles
            raise ValueError("Your role does not give the RTA's approval.")
        if not approve:
            if not self.store.move_leave(request_id, "waiting_rta", status="refused", rta_id=user["id"], rta_at=now,
                                         reason=reason):
                raise ValueError(self._decided(request_id))
            return "Refused."
        if not self.store.move_leave(request_id, "waiting_rta", status="applying", rta_id=user["id"], rta_at=now):
            raise ValueError(self._decided(request_id))
        try:
            outcome = self._apply(row, user["id"])
        except Exception:
            self.store.move_leave(request_id, "applying", status="waiting_rta", rta_id=None, rta_at=None)
            raise
        self.store.move_leave(request_id, "applying", status="approved", outcome=outcome)
        return f"Approved: {outcome}"

    def _apply(self, row: Dict[str, Any], user_id: int) -> str:
        """Leave on the days worked, as one new version per week, set in use. Says what changed and what did not."""
        program, name = row["program"], row["associate"]
        days = self.days_of(program, name, date.fromisoformat(row["first_day"]), date.fromisoformat(row["last_day"]))
        leave, off, missing = [], [], []
        by_version: Dict[int, List[date]] = {}
        for d in days:
            version = self.days.version(program, d["date"])[0]
            if version is None:
                missing.append(d["date"])
            elif shift_span(d["cell"]):
                by_version.setdefault(version["id"], []).append(d["date"])
                leave.append(d["date"])
            elif d["cell"].casefold() == "leave":
                leave.append(d["date"])
            else:
                off.append(d["date"])
        book = self.days.book
        for version_id, dates in by_version.items():
            new_id = book.change_many(version_id, user_id, [(name, DAYS[day_index(on)], "Leave") for on in dates],
                                      reason=f"{row['kind']} approved (request {row['id']})",
                                      label=f"{row['kind']} for {name}")
            book.set_in_use(new_id, user_id)
        said = []
        if leave:
            said.append(f"Leave on {joined([nice(d) for d in leave])}.")
        if off:
            said.append(f"{joined([nice(d) for d in off])} {'is a day off' if len(off) == 1 else 'are days off'}.")
        if missing:
            said.append(f"{joined([nice(d) for d in missing])} {'has' if len(missing) == 1 else 'have'} no schedule "
                        "yet: it is kept, and marked Leave when that week's schedule is uploaded.")
        return " ".join(said)

    # ------------------------------------------------------------------ leave for a week not yet planned (Phase AO)
    def _applied_path(self, run_id: str):
        return self.days.book.root / run_id / "leave_after_run.json"

    def last_applied(self, run_id: str) -> Optional[Dict[str, Any]]:
        """What the last run of ``apply_waiting`` did for this run's week, or None when it never had leave to apply."""
        try:
            return json.loads(self._applied_path(run_id).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None

    def apply_waiting(self, run: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Leave the RTA approved while this run's week had no schedule: once the week's schedule is kept, each approved
        day the person works is marked Leave in a new version set in use (the engine did not consider it when it built
        the week). A name not on the schedule, or a day already off, is said and never stops anything. Safe to run
        again: days already Leave are left alone. Nothing is done for a week with no approved leave."""
        program = run.get("program") or ""
        try:
            first = date.fromisoformat(run.get("week_start") or "")
        except ValueError:
            return None
        last = first + timedelta(days=6)
        rows = [r for r in self.store.list_leave(program=program, statuses=["approved"])
                if r["first_day"] <= last.isoformat() and r["last_day"] >= first.isoformat()]
        version = self.days.version(program, first)[0] if rows else None
        if version is None:
            return None
        names = {a["name"] for a in json.loads(version["week"] or "{}").get("associates", [])}
        out: Dict[str, Any] = {"week": first.isoformat(), "applied": [], "skipped": [], "notes": []}
        changes: List[Any] = []
        by: Dict[str, Any] = {}
        for row in rows:
            name = row["associate"]
            if name not in names:
                out["skipped"].append({"name": name, "request": row["id"], "dates": [],
                                       "why": f"{name} is not on the schedule uploaded for the week of {nice(first)}, "
                                              "so the approved leave was not applied."})
                continue
            marked, off = [], []
            for i in range(7):
                on = first + timedelta(days=i)
                if not row["first_day"] <= on.isoformat() <= row["last_day"]:
                    continue
                cell = dict(self.days.roster(program, on)).get(name, "")
                if shift_span(cell):
                    changes.append((name, DAYS[i], "Leave"))
                    marked.append(on.isoformat())
                elif cell.strip().casefold() != "leave":
                    off.append(on.isoformat())
            if marked:
                out["applied"].append({"name": name, "request": row["id"], "dates": marked})
                by[name] = row.get("rta_id") or row.get("tm_id") or row["user_id"]
            if off:
                out["notes"].append({"name": name, "request": row["id"], "dates": off,
                                     "why": f"{', '.join(nice(date.fromisoformat(d)) for d in off)}: already a day off."})
        if changes:
            book = self.days.book
            new_id = book.change_many(version["id"], next(iter(by.values())), changes,
                                      reason="Leave approved before this week was planned",
                                      label=f"Approved leave for {len(out['applied'])} "
                                            f"{'person' if len(out['applied']) == 1 else 'people'}")
            book.set_in_use(new_id, next(iter(by.values())))
        if out["applied"] or out["skipped"] or out["notes"]:
            self._applied_path(run["id"]).write_text(json.dumps(out), encoding="utf-8")
        return out

    # ------------------------------------------------------------------ what it costs
    def impact(self, program: str, name: str, on: date, base: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """What the floor loses on ``on`` if ``name`` is away: intervals newly short (or shorter), language gaps
        and channel warnings that appear. Worked out, never recorded."""
        cell = dict(self.days.roster(program, on)).get(name, "")
        out: Dict[str, Any] = {"cell": cell, "short": [], "languages": [], "channels": []}
        if self.days.version(program, on)[0] is None:
            return dict(out, text="No schedule kept for this day yet.")
        if not shift_span(cell):
            return dict(out, text="Already on leave." if cell.casefold() == "leave" else "Day off: nothing changes.")
        base = base or self.days.page(program, on)
        after = self.days.page(program, on, extra=dict(ABSENT_FOR_IMPACT, name=name))
        step = after["view"]["interval"]
        before = {c["t"]: c for c in base["view"]["cells"]}
        runs: List[List[Any]] = []  # [first t, last t, worst shortfall]
        for c in after["view"]["cells"]:
            b = before.get(c["t"])
            if b is not None and c["now"] < c["need"] and c["now"] < b["now"]:
                by = round(c["need"] - c["now"], 1)
                if runs and runs[-1][1] + step == c["t"]:
                    runs[-1][1], runs[-1][2] = c["t"], max(runs[-1][2], by)
                else:
                    runs.append([c["t"], c["t"], by])
        out["short"] = [(lo, hi + step, by) for lo, hi, by in runs]
        out["text"] = ("Coverage holds." if not runs else "Short by " + "; ".join(
            f"{number(by)} from {hm(lo)} to {hm(hi)}" for lo, hi, by in out["short"]) + ".")
        gaps = {l["name"]: {c["t"] for c in l["cells"] if c["cls"] == "bad"} for l in base["view"]["languages"]}
        for lang in after["view"]["languages"]:
            new = sorted(c["t"] for c in lang["cells"] if c["cls"] == "bad" and c["t"] not in gaps.get(lang["name"], set()))
            if new:
                out["languages"].append(f"No {lang['name']} speaker from {hm(new[0])} to {hm(new[-1] + step)}")
        if after["view"].get("channels") and base["view"].get("channels"):
            had = {w["text"] for w in base["view"]["channels"]["warnings"]}
            out["channels"] = [w["text"] for w in after["view"]["channels"]["warnings"] if w["text"] not in had]
        return out

    # ------------------------------------------------------------------ balances
    def balance(self, program: str, name: str, year: int, asked: int = 0) -> Optional[Dict[str, Any]]:
        days = self.store.get_leave_balance(program, name, year)
        if days is None:
            return None
        used = sum(self.counted(self.days_of(program, name, date.fromisoformat(r["first_day"]),
                                             date.fromisoformat(r["last_day"])))
                   for r in self.store.list_leave(program=program, associate=name, statuses=["approved"])
                   if r["kind"] == "Planned leave" and r["first_day"][:4] == str(year))
        return {"days": days, "used": used, "asked": asked, "left": days - used - asked}

    def set_balances(self, program: str, year: int, rows: Dict[str, float], user_id: int) -> int:
        if not 2000 <= year <= 2100:
            raise ValueError("Give a year like 2026.")
        known = set(self.names(program))
        for name, days in rows.items():
            if name not in known:
                raise ValueError(f"{name} is not on this program's schedule.")
            if not 0 <= days <= 366:
                raise ValueError(f"{name}: give between 0 and 366 days.")
        for name, days in rows.items():
            self.store.set_leave_balance(program, name, year, days, user_id)
        return len(rows)

    def approved_on(self, program: str, on: date) -> Dict[str, str]:
        """Who has an approved request covering ``on``, and its kind (Phase AI: shrinkage counts each by its kind)."""
        day = on.isoformat()
        return {r["associate"]: r["kind"] for r in self.store.list_leave(program=program, statuses=["approved"])
                if r["first_day"] <= day <= r["last_day"]}

    # ------------------------------------------------------------------ the inbox
    def may_decide(self, row: Dict[str, Any], user: Dict[str, Any]) -> bool:
        if row["status"] == "waiting_tm":
            return may_approve_for(self.store, user, row["user_id"])
        return row["status"] == "waiting_rta" and row["tm_id"] != user["id"] and allowed(self.store, user, "approve_rta")

    def waiting_on(self, row: Dict[str, Any]) -> str:
        """Phase AK: where a request waits, in words."""
        if row["status"] == "waiting_tm":
            return "Waiting for " + who_approves(self.store, row["user_id"], row["associate"])
        if row["status"] == "waiting_rta":
            by = self.store.get_user(row["tm_id"]) if row["tm_id"] else None
            return f"Approved by {by['display_name'] if by else 'the TM'}, waiting for the RTA"
        return ""

    def waiting(self, program: str) -> List[Dict[str, Any]]:
        """Requests waiting for a decision, each day with its cell and what it costs, and the balance."""
        pages: Dict[date, Any] = {}
        out = []
        for row in self.store.list_leave(program=program, statuses=list(WAITING)):
            first, last = date.fromisoformat(row["first_day"]), date.fromisoformat(row["last_day"])
            days = self.days_of(program, row["associate"], first, last)
            for d in days:
                if shift_span(d["cell"]):
                    if d["date"] not in pages:
                        pages[d["date"]] = self.days.page(program, d["date"])
                    d["impact"] = self.impact(program, row["associate"], d["date"], base=pages[d["date"]])
            asked = self.counted(days)
            balance = self.balance(program, row["associate"], first.year, asked) \
                if row["kind"] == "Planned leave" else None
            text = ""
            if row["kind"] == "Planned leave":
                text = (f"No balance set for {first.year}." if balance is None else
                        f"Asks {asked} day{'s' if asked != 1 else ''}; {number(balance['days'] - balance['used'])} "
                        "left this year.")
            out.append(dict(row, days=days, balance=balance, balance_text=text, waiting_on=self.waiting_on(row),
                            label=f"{row['kind']}, {span_text(first, last)}", short=balance is not None
                            and balance["left"] < 0, step="tm" if row["status"] == "waiting_tm" else "rta"))
        return out

    def decided(self, program: str, limit: Optional[int] = 20) -> List[Dict[str, Any]]:
        rows = self.store.list_leave(program=program, statuses=["approved", "refused", "cancelled"])
        rows.sort(key=lambda r: -(r["rta_at"] or r["tm_at"] or r["asked"]))
        return [dict(r, label=f"{r['kind']}, {span_text(date.fromisoformat(r['first_day']), date.fromisoformat(r['last_day']))}")
                for r in rows[:limit]]

    def count_for(self, program: str, user: Dict[str, Any]) -> int:
        """Requests on ``program`` this person may decide now (the menu's count)."""
        return sum(1 for r in self.store.list_leave(program=program, statuses=list(WAITING)) if self.may_decide(r, user))

    def mine(self, program: str, name: str) -> List[Dict[str, Any]]:
        return [dict(r, waiting_on=self.waiting_on(r), label=f"{r['kind']}, {span_text(date.fromisoformat(r['first_day']), date.fromisoformat(r['last_day']))}")
                for r in self.store.list_leave(program=program, associate=name)]
