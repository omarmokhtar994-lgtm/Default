# © 2026 Omar Mokhtar. All rights reserved.
"""Phase V: which channels each associate can work, per program (owner, 2026-10-09: "Not everyone can work all
channels so we need somewhere to setup associates working channels", answered "website" for where it lives).

Set once and kept for every week; a program's LOBs share the list. Someone not listed can work all three, so a
program only lists the exceptions. The people offered are those on each LOB's newest schedule, plus anyone listed."""
from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional, Tuple

from .channels import CHANNELS
from .programs import ProgramBook

ALL = "PCE"
SPLIT = re.compile(r"\t|,|;")  # "Name, Yes, Yes, No", or columns copied from Excel
COLUMNS = ("C", "P", "E")  # the paste's (and the page's) column order: Chat, Phone, Email


def can_work(skills: Dict[str, str], name: str) -> str:
    """The channels ``name`` can work: their listed letters, or all three when not listed."""
    folded = {n.casefold(): letters for n, letters in skills.items()}
    return folded.get((name or "").strip().casefold(), ALL)


def channel_words(letters: str) -> str:
    """"all three", or the channels in Phone, Chat, Email order: "Phone, Chat"."""
    return "all three" if set(letters) == set(ALL) else ", ".join(CHANNELS[c] for c in ALL if c in letters)


class ChannelPeople:
    def __init__(self, store):
        self.store = store

    def skills(self, program_id: int) -> Dict[str, str]:
        """The listed people: name -> letters (P, C, E)."""
        return {r["name"]: r["channels"] for r in self.store.list_associate_channels(program_id)}

    def skills_for_unit(self, key: str) -> Dict[str, str]:
        """The list a program or LOB plans with: its program's."""
        unit = ProgramBook(self.store).unit(key) if key else None
        return self.skills(unit["program"]["id"]) if unit else {}

    def roster(self, program_id: int) -> List[Tuple[str, str]]:
        """(name, language) of everyone on each LOB's newest schedule (the version in use for that week, else the
        newest version), plus anyone listed who is not on them (language unknown), by name."""
        program = ProgramBook(self.store).program(program_id)
        seen: Dict[str, Tuple[str, str]] = {}
        for unit in program["units"]:
            versions = self.store.list_schedules(program=unit)
            if not versions:
                continue
            newest = max(v["week_start"] for v in versions)
            week_of = [v for v in versions if v["week_start"] == newest]
            chosen = next((v for v in week_of if v["in_use"]), None) or max(week_of, key=lambda v: v["id"])
            for a in json.loads(chosen["week"] or "{}").get("associates", []):
                seen.setdefault(a["name"].casefold(), (a["name"], a.get("language", "")))
        for name in self.skills(program_id):
            seen.setdefault(name.casefold(), (name, ""))
        return sorted(seen.values(), key=lambda p: p[0].casefold())

    def _program_name(self, program_id: int) -> str:
        return ProgramBook(self.store).program(program_id)["name"]

    def plan_changes(self, program_id: int, rows: Dict[str, str]) -> Dict[str, str]:
        """What saving ``rows`` (name -> letters) would change: name -> letters, for the names whose channels
        differ from now. Refused (nothing kept) for a name not on the schedule or a person with no channel."""
        known = {n.casefold(): n for n, _ in self.roster(program_id)}
        skills = self.skills(program_id)
        changes: Dict[str, str] = {}
        for name, letters in rows.items():
            canon = known.get((name or "").strip().casefold())
            if canon is None:
                raise ValueError(f"{(name or '').strip()} is not on {self._program_name(program_id)}'s schedule.")
            letters = "".join(c for c in ALL if c in (letters or "").upper())
            if not letters:
                raise ValueError(f"Tick at least one channel for {canon}.")
            if letters != can_work(skills, canon):
                changes[canon] = letters
        return changes

    def apply(self, program_id: int, changes: Dict[str, str], user_id: int) -> int:
        """Keep the changes; all three takes a person off the list (the default)."""
        if changes:
            self.store.set_associate_channels(program_id, {n: (None if set(l) == set(ALL) else l)
                                                           for n, l in changes.items()}, user_id)
        return len(changes)

    def save(self, program_id: int, rows: Dict[str, str], user_id: int) -> int:
        return self.apply(program_id, self.plan_changes(program_id, rows), user_id)

    def read_paste(self, program_id: int, text: str) -> Dict[str, str]:
        """A pasted list, one "Name, Chat, Phone, Email" per line with Yes or No (a header line is skipped): name ->
        letters. Refused as a whole, naming every wrong line."""
        known = {n.casefold(): n for n, _ in self.roster(program_id)}
        program = self._program_name(program_id)
        rows: Dict[str, str] = {}
        problems: List[str] = []
        first = True
        for n, line in enumerate((text or "").splitlines(), 1):
            if not line.strip():
                continue
            parts = [" ".join(p.split()) for p in SPLIT.split(line)]
            if first and parts[0].casefold() == "name":
                first = False
                continue
            first = False
            if len(parts) != 4 or not parts[0]:
                problems.append(f"Line {n}: give the name, then Yes or No for Chat, Phone and Email.")
                continue
            canon = known.get(parts[0].casefold())
            if canon is None:
                problems.append(f"Line {n}: {parts[0]} is not on {program}'s schedule.")
                continue
            letters, bad = "", None
            for letter, value in zip(COLUMNS, parts[1:]):
                if value.casefold() in ("yes", "y"):
                    letters += letter
                elif value.casefold() not in ("no", "n"):
                    bad = f"Line {n}: {CHANNELS[letter]} must be Yes or No; it reads {value}."
                    break
            if bad:
                problems.append(bad)
            elif not letters:
                problems.append(f"Line {n}: tick at least one channel for {canon}.")
            else:
                rows[canon] = letters
        if problems:
            raise ValueError("Nothing was changed. " + " ".join(problems))
        if not rows:
            raise ValueError("Paste at least one line: Name, Chat, Phone, Email.")
        return rows

    def paste(self, program_id: int, text: str, user_id: int) -> int:
        return self.apply(program_id, self.plan_changes(program_id, self.read_paste(program_id, text)), user_id)

    @staticmethod
    def describe(changes: Dict[str, str]) -> str:
        return "; ".join(f"{name} {channel_words(letters)}" for name, letters in sorted(changes.items()))
