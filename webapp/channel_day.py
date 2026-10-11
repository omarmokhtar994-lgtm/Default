# © 2026 Omar Mokhtar. All rights reserved.
"""Phase V: channels on the RTA page (owner, 2026-10-09: "this some how needs to reflect in RTA view as well with
warnings when no channel coverage due to extra coaching etc considering the language as well").

From the 5-minute lists of who is on the floor (``day_view``'s ``now``) and who the schedule put there (``plan``),
each person counts for the channel of their plan block at that minute: a channel change made on the day wins; in
all-channels times they count for every channel they work; minutes outside every block (a break moved away, a shift
longer than its plan) take the block before, else the block after. Per interval: the average (as the floor) and
the lowest point (for "nobody").

A warning is an interval where today's events left a channel, or a channel's language minimum, below its need at
its lowest point and lower than planned on average: the plan's own gaps show in the table, not as warnings. Each
warning names what took people off the channel and offers fixes: a channel change for someone who can take it (and
speaks the language when one is short) without leaving their own channel short, moving the aux that caused it, or
moving the break."""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence, Tuple

from .attendance import with_text
from .channel_people import can_work
from .channel_plan import counts_for, need_at
from .channels import CHANNELS, QUARTER, blended_at, hm, inside
from .day import ABSENT, AUX, EXTRA_BREAKS, LATE_EARLY, STEP

EPS = 1e-9


def letter_at(blocks: Sequence[Tuple[int, int, str]], moves: Sequence[Dict[str, Any]], t: int,
              blended: bool) -> Optional[str]:
    """The channel a person is on at minute ``t``: A in all-channels time, a change made on the day, the plan's
    block, else the block before, else the block after; None without a plan."""
    if blended:
        return "A"
    for m in sorted(moves, key=lambda m: m.get("id") or 0, reverse=True):  # the latest change wins
        if m["start"] <= t < m["end"]:
            return m["channel"]
    for start, end, letter in blocks:
        if start <= t < end:
            return letter
    earlier = [b for b in blocks if b[1] <= t]
    if earlier:
        return max(earlier, key=lambda b: b[1])[2]
    later = [b for b in blocks if b[0] > t]
    return min(later, key=lambda b: b[0])[2] if later else None


def _join(words: List[str]) -> str:
    return words[0] if len(words) == 1 else ", ".join(words[:-1]) + " or " + words[-1]


class _Counts:
    """People per channel and per language rule, per 5-minute tick, for the people given per tick."""

    def __init__(self, day: int, per_tick, ch: Dict[str, Any], rules: List[Dict[str, Any]], moves: bool):
        self.ticks = 1440 // STEP
        self.channel = {c: [0] * self.ticks for c in "PCE"}
        self.language = [[0] * self.ticks for _ in rules]
        self.who: List[Dict[Tuple[int, str], str]] = [{} for _ in range(self.ticks)]
        setup = ch["setup"]
        for i in range(self.ticks):
            t = i * STEP
            blend = blended_at(setup, day, t)
            for seg in per_tick[i]:
                key = (seg["offset"], seg["name"])
                letter = letter_at(ch["blocks"].get(key, []), ch["moves"].get(key, []) if moves else [], t, blend)
                self.who[i][key] = letter or ""
                covered = ch["skills_of"](seg["name"]) if letter == "A" else (letter or "")
                for c in covered:
                    self.channel[c][i] += 1
                for j, rule in enumerate(rules):
                    if rule["channel"] in covered and rule["language"].casefold() in ch["speaks"](seg):
                        self.language[j][i] += 1


def channel_view(day: int, step: int, now, plan, pieces, lanes: Dict[str, Any], ch: Dict[str, Any]) -> Dict[str, Any]:
    """``view["channels"]``: rows (per channel and language rule, per interval: need, have, low, plan, cls),
    warnings (text, causes, fixes), the moment's figures (``now``) and who is on the floor with no channel."""
    setup = ch["setup"]
    rules = [r for r in setup["languages"] if r["active"] and r["minimum"] > 0]
    languages: Dict[str, set] = {}

    def speaks(seg: Dict[str, Any]) -> set:
        if seg["name"] not in languages:
            languages[seg["name"]] = counts_for(seg.get("language", ""), ch["language_rows"])
        return languages[seg["name"]]

    ch = {**ch, "speaks": speaks, "skills_of": lambda name: can_work(ch["skills"], name),
          "language_of": {seg["name"]: seg.get("language", "") for tick in now for seg in tick}}
    today = _Counts(day, now, ch, rules, moves=True)
    planned = _Counts(day, plan, ch, rules, moves=False)
    letters = [c for c in "PCE" if c in setup["need"]]
    rows, issues = [], {}
    after = ch.get("after", 0)
    for c in letters:
        cells = []
        for t in range(0, 1440, step):
            idx = range(t // STEP, (t + step) // STEP)
            need = need_at(setup, c, day, t)
            have = sum(today.channel[c][i] for i in idx) / len(idx)
            low = min(today.channel[c][i] for i in idx)
            was = sum(planned.channel[c][i] for i in idx) / len(idx)
            cls = "none" if not need else ("ok" if low >= need else ("bad" if low == 0 else "warn"))
            cells.append({"t": t, "need": need, "have": round(have, 2), "low": low, "plan": round(was, 2), "cls": cls})
            if need and low < need and have < was - EPS and t + step > after:
                issues.setdefault(t, []).append(("nobody", c) if low == 0 else ("short", c, low, need))
        rows.append({"name": CHANNELS[c], "letter": c, "cells": cells})
    for j, rule in enumerate(rules):
        cells = []
        for t in range(0, 1440, step):
            if not inside(rule["days"], rule["start"], rule["end"], day, t):
                cells.append({"t": t, "need": 0, "have": None, "low": None, "plan": None, "cls": "none"})
                continue
            idx = range(t // STEP, (t + step) // STEP)
            have = sum(today.language[j][i] for i in idx) / len(idx)
            low = min(today.language[j][i] for i in idx)
            was = sum(planned.language[j][i] for i in idx) / len(idx)
            cells.append({"t": t, "need": rule["minimum"], "have": round(have, 2), "low": low, "plan": round(was, 2),
                          "cls": "ok" if low >= rule["minimum"] else "bad"})
            if low < rule["minimum"] and have < was - EPS and t + step > after:
                issues.setdefault(t, []).append(("language", j, low))
        rows.append({"name": f"{CHANNELS[rule['channel']]} · {rule['language']} (at least {rule['minimum']})",
                     "letter": rule["channel"], "language": rule["language"], "cells": cells})
    warnings = []
    for t0, t1, parts in _windows(issues, step):
        blend = all(blended_at(setup, day, t) for t in range(t0, t1, STEP))
        warnings.append({"t0": t0, "t1": t1, "text": f"{hm(t0)} to {hm(t1)}{' (all channels)' if blend else ''}: "
                                                     + _said(parts, rules),
                         "causes": _causes(t0, t1, parts, rules, plan, today, planned, pieces, lanes, ch),
                         "fixes": _fixes(day, step, t0, t1, parts, rules, now, today, planned, pieces, ch)})
    i = after // STEP if ch.get("today") and 0 <= after < 1440 else None
    moment = {c: {"have": today.channel[c][i], "need": need_at(setup, c, day, after)} for c in letters} \
        if i is not None else {}
    loose = sorted({key[1] for i in range(today.ticks) for key, letter in today.who[i].items() if not letter})
    changes = sorted(({"id": m["id"], "name": name, "start": m["start"], "end": m["end"], "channel": m["channel"]}
                      for (offset, name), ms in ch["moves"].items() if offset == 0 for m in ms if m.get("id")),
                     key=lambda m: (m["start"], m["name"]))
    return {"rows": rows, "warnings": warnings, "now": moment, "unplanned": loose, "changes": changes,
            "planned": any(ch["blocks"].values()),  # Phase AC: whether the schedule has a channel plan at all
            "timelines": _timelines(pieces, today), "hold": ChannelHold(day, step, setup, rules, today, ch)}


def _timelines(pieces, today: "_Counts") -> Dict[str, List[str]]:
    """Each person's day as it stands, in time order: "12:00 Phone", "14:00 Break 1", ... (this day's shifts)."""
    names = {**{c: n for c, n in CHANNELS.items()}, "A": "All channels"}
    out: Dict[str, List[str]] = {}
    for seg, status, away, breaks, acts in pieces:
        if seg["offset"] != 0:
            continue
        key, line, last = (0, seg["name"]), [], None
        for t in range(max(seg["start"], 0), min(seg["end"], 1440), STEP):
            letter = today.who[t // STEP].get(key)
            if letter is not None:
                label = names.get(letter, "No channel planned")
            elif status in ABSENT:
                label = status
            elif any(b["start"] <= t < b["start"] + b["minutes"] for b in breaks):
                label = next(b["kind"] for b in breaks if b["start"] <= t < b["start"] + b["minutes"])
            elif any(a["start"] <= t < a["end"] for a in acts):
                label = next(a["kind"] for a in acts if a["start"] <= t < a["end"])
            elif status != "Present" and away[0] <= t < away[1]:
                label = status
            else:
                label = "Off the floor"
            if label != last:
                line.append(f"{hm(t)} {label}")
                last = label
        out[seg["name"]] = line
    return out


class ChannelHold:
    """For re-planning breaks (``day.replan``): whether moving a person's break (a per-tick change of +1 where they
    come back, -1 where they leave) keeps every channel and language minimum they count for at its need, and the
    counts once a move is kept."""

    def __init__(self, day: int, step: int, setup: Dict[str, Any], rules: List[Dict[str, Any]], counts: "_Counts",
                 ch: Dict[str, Any]):
        self.day, self.step, self.setup, self.rules, self.ch = day, step, setup, rules, ch
        self.channel = {c: list(v) for c, v in counts.channel.items()}
        self.language = [list(v) for v in counts.language]
        self.who = counts.who

    def _covered(self, name: str, i: int) -> str:
        t = i * STEP
        key = (0, name)
        letter = self.who[i].get(key) or letter_at(self.ch["blocks"].get(key, []), self.ch["moves"].get(key, []), t,
                                                   blended_at(self.setup, self.day, t))
        return self.ch["skills_of"](name) if letter == "A" else (letter or "")

    def _langs(self, name: str, covered: str) -> List[int]:
        seg = {"name": name, "language": self.ch["language_of"].get(name, "")}
        return [j for j, r in enumerate(self.rules) if r["channel"] in covered
                and r["language"].casefold() in self.ch["speaks"](seg)]

    def limits(self, name: str, i: int) -> List[Tuple[Tuple[str, Any], float]]:
        """Phase AD (Rescue the day): the counters ``name`` counts toward at 5-minute tick ``i`` (("ch", channel) or
        ("lang", rule index)) and the least each must keep: the same needs ``holds`` checks a move against."""
        if not 0 <= i < len(self.who):
            return []
        t = i * STEP
        covered = self._covered(name, i)
        out: List[Tuple[Tuple[str, Any], float]] = [(("ch", c), need_at(self.setup, c, self.day, t)) for c in covered
                                                    if c in self.setup["need"]]
        for j in self._langs(name, covered):
            rule = self.rules[j]
            if inside(rule["days"], rule["start"], rule["end"], self.day, t):
                out.append((("lang", j), rule["minimum"]))
        return out

    def current(self, key: Tuple[str, Any], i: int) -> float:
        """How many count toward counter ``key`` at tick ``i`` now."""
        return self.channel[key[1]][i] if key[0] == "ch" else self.language[key[1]][i]

    def holds(self, name: str, change: Dict[int, int]) -> bool:
        for i, d in change.items():
            if d >= 0 or not 0 <= i < len(self.who):
                continue
            t = i * STEP
            covered = self._covered(name, i)
            for c in covered:
                if c in self.setup["need"] and self.channel[c][i] + d < need_at(self.setup, c, self.day, t):
                    return False
            for j in self._langs(name, covered):
                rule = self.rules[j]
                if inside(rule["days"], rule["start"], rule["end"], self.day, t) and \
                        self.language[j][i] + d < rule["minimum"]:
                    return False
        return True

    def apply(self, name: str, change: Dict[int, int]) -> None:
        for i, d in change.items():
            if not 0 <= i < len(self.who):
                continue
            covered = self._covered(name, i)
            for c in covered:
                self.channel[c][i] += d
            for j in self._langs(name, covered):
                self.language[j][i] += d


def _windows(issues: Dict[int, list], step: int) -> List[Tuple[int, int, list]]:
    out: List[Tuple[int, int, list]] = []
    for t in sorted(issues):
        parts = sorted(issues[t], key=lambda p: ({"nobody": 0, "short": 1, "language": 2}[p[0]],
                                                 "PCE".index(p[1]) if p[0] != "language" else p[1]))
        if out and out[-1][1] == t and out[-1][2] == parts:
            out[-1] = (out[-1][0], t + step, parts)
        else:
            out.append((t, t + step, parts))
    return out


def _said(parts: list, rules: List[Dict[str, Any]]) -> str:
    said = []
    nobody = [CHANNELS[p[1]] for p in parts if p[0] == "nobody"]
    if nobody:
        said.append("nobody on " + _join(nobody))
    for p in parts:
        if p[0] == "short":
            said.append(f"{CHANNELS[p[1]]} {p[2]:g} of {p[3]:g}")
        elif p[0] == "language":
            rule = rules[p[1]]
            said.append(f"no {rule['language']} speaker on {CHANNELS[rule['channel']]}" if p[2] == 0 else
                        f"{CHANNELS[rule['channel']]} · {rule['language']} {p[2]} of {rule['minimum']}")
    return ", and ".join(said)


def _targets(parts: list, rules: List[Dict[str, Any]]) -> List[Tuple[str, Optional[str]]]:
    """(channel, language or None) each part asks for."""
    out = []
    for p in parts:
        if p[0] in ("nobody", "short"):
            out.append((p[1], None))
        else:
            out.append((rules[p[1]]["channel"], rules[p[1]]["language"].casefold()))
    return out


def _reason(seg: Dict[str, Any], t: int, piece, lane_seg: Dict[str, Any], now_letter: str) -> Optional[str]:
    _, status, away, breaks, acts = piece
    name = seg["name"]
    if status in ABSENT:
        return f"{name} is off ({status.lower()})"
    if status in LATE_EARLY and away[0] <= t < away[1]:
        return f"{name} is late" if status == "Late" else f"{name} left early"
    if status in AUX and away[0] <= t < away[1]:
        return f"{name} is in {status}" + with_text(lane_seg.get("with_whom", ""), lane_seg.get("why", ""),
                                                   lane_seg.get("with_dept", ""))
    for a in acts:
        if a["start"] <= t < a["end"]:
            if a["kind"] in AUX:
                return f"{name} is booked for {a['kind']}" + with_text(a.get("with_whom", ""), a.get("why", ""),
                                                                       a.get("with_dept", ""))
            if a["kind"] in EXTRA_BREAKS:
                return f"{name} is on {a['kind']} (added on the day)"
            if a["kind"] == "VTO":
                return f"{name} took VTO"
    for b in breaks:
        if b["start"] <= t < b["start"] + b["minutes"]:
            return f"{name} is on {b['kind']}" + (f" (moved to {hm(b['start'])})" if b["moved"] else "")
    if now_letter and now_letter != "A":
        return f"{name} was moved to {CHANNELS.get(now_letter, now_letter)}"
    return None


def _causes(t0, t1, parts, rules, plan, today, planned, pieces, lanes, ch) -> List[str]:
    wanted = _targets(parts, rules)
    by_key = {(p[0]["offset"], p[0]["name"]): p for p in pieces}
    said: List[str] = []
    for i in range(t0 // STEP, t1 // STEP):
        for seg in plan[i]:
            key = (seg["offset"], seg["name"])
            was = planned.who[i].get(key, "")
            covered = ch["skills_of"](seg["name"]) if was == "A" else was
            if not any(c in covered and (lang is None or lang in ch["speaks"](seg)) for c, lang in wanted):
                continue
            now_letter = today.who[i].get(key)
            now_covered = ch["skills_of"](seg["name"]) if now_letter == "A" else (now_letter or "")
            if now_letter is not None and all(c in now_covered for c, _ in wanted if c in covered):
                continue
            lane_seg = next((x for x in lanes.get(seg["name"], {}).get("segments", [])
                             if x["offset"] == seg["offset"]), {})
            text = _reason(seg, i * STEP, by_key[key], lane_seg, now_letter or "")
            if text and text not in said:
                said.append(text)
    return said


def _ok_without(today: _Counts, letter: str, langs: List[int], ticks: range, day: int, step: int,
                setup: Dict[str, Any], rules: List[Dict[str, Any]]) -> bool:
    """Whether taking one person off ``letter`` (and the language rules ``langs``) in ``ticks`` leaves every interval
    it touches at its need."""
    for i in ticks:
        t = i * STEP
        if letter in setup["need"] and today.channel[letter][i] - 1 < need_at(setup, letter, day, t - t % step):
            return False
        for j in langs:
            rule = rules[j]
            if inside(rule["days"], rule["start"], rule["end"], day, t) and today.language[j][i] - 1 < rule["minimum"]:
                return False
    return True


def _fixes(day, step, t0, t1, parts, rules, now, today, planned, pieces, ch) -> List[Dict[str, Any]]:
    setup = ch["setup"]
    wanted = _targets(parts, rules)
    ticks = range(t0 // STEP, t1 // STEP)
    fixes: List[Dict[str, Any]] = []
    # 1. a channel change for someone on the floor throughout who can take the channel (and the language)
    if not any(blended_at(setup, day, i * STEP) for i in ticks):
        target, lang = next(((c, l) for c, l in wanted if l), wanted[0])
        order = list(reversed(setup["rules"]["order"]))
        on_all = None
        for i in ticks:
            here = {(s["offset"], s["name"]): s for s in now[i]}
            on_all = here if on_all is None else {k: v for k, v in on_all.items() if k in here}
        found = []
        for key, seg in (on_all or {}).items():
            letters = {today.who[i].get(key) for i in ticks}
            if len(letters) != 1:
                continue
            letter = letters.pop()
            if letter in (None, "", "A", target) or target not in ch["skills_of"](seg["name"]):
                continue
            if lang and lang not in ch["speaks"](seg):
                continue
            langs = [j for j, r in enumerate(rules) if r["channel"] == letter
                     and r["language"].casefold() in ch["speaks"](seg)]
            if _ok_without(today, letter, langs, ticks, day, step, setup, rules):
                found.append((order.index(letter) if letter in order else 9, seg["name"], seg, letter))
        for _, name, seg, letter in sorted(found, key=lambda f: (f[0], f[1]))[:2]:
            fixes.append({"kind": "swap", "who": name, "offset": seg["offset"], "start": t0, "end": t1,
                          "channel": target, "from": letter,
                          "text": f"{name}: {CHANNELS[letter]} → {CHANNELS[target]} from {hm(t0)} to {hm(t1)}"})
    # 2. moving what took people off (an aux or a break added on the day; a planned break): the nearest time, on
    # quarter hours, that leaves no interval below its need where it lands
    by_key = {(p[0]["offset"], p[0]["name"]): p for p in pieces}
    seen = set()
    for i in ticks:
        for key, piece in by_key.items():
            seg, status, away, breaks, acts = piece
            if key[0] != 0 or status in ABSENT:
                continue
            for a in acts:
                if a["id"] and a["start"] <= i * STEP < a["end"] and (a["kind"] in AUX or a["kind"] in EXTRA_BREAKS) \
                        and ("a", a["id"]) not in seen:
                    seen.add(("a", a["id"]))
                    s = _new_time(seg, a["start"], a["end"] - a["start"], breaks, acts, a, key, today, planned, day,
                                  step, setup, rules, ch, t0, t1)
                    if s is not None:
                        fixes.append({"kind": "activity", "id": a["id"], "who": seg["name"], "start": hm(s),
                                      "text": f"Move {seg['name']}'s {a['kind']} to {hm(s)}"})
            for b in breaks:
                if b["start"] <= i * STEP < b["start"] + b["minutes"] and ("b", key, b["idx"]) not in seen:
                    seen.add(("b", key, b["idx"]))
                    s = _new_time(seg, b["start"], b["minutes"], breaks, acts, b, key, today, planned, day, step,
                                  setup, rules, ch, t0, t1, gaps=ch.get("gaps"))
                    if s is not None:
                        fixes.append({"kind": "break", "who": seg["name"], "idx": b["idx"], "start": hm(s),
                                      "text": f"Move {seg['name']}'s {b['kind']} to {hm(s)}"})
    return fixes


def _new_time(seg, start, minutes, breaks, acts, item, key, today, planned, day, step, setup, rules, ch, t0, t1,
              gaps=None) -> Optional[int]:
    """The nearest quarter-hour start (within 4 hours) for ``item`` inside the shift, clear of the person's other
    breaks and activities, where taking the person off their channel leaves every interval at its need, and the
    window [t0, t1) is no longer short of the person."""
    letter_of = lambda i: today.who[i].get(key) or planned.who[i].get(key) or ""  # noqa: E731
    others = [(b["start"], b["start"] + b["minutes"]) for b in breaks if b is not item] + \
             [(a["start"], a["end"]) for a in acts if a is not item]
    candidates = sorted((s for s in range(seg["start"] - seg["start"] % QUARTER, seg["end"] - minutes + 1, QUARTER)
                         if s != start and abs(s - start) <= 240 and seg["start"] <= s),
                        key=lambda s: (abs(s - start), s))
    lo_gap, hi_gap = gaps or (None, None)
    for s in candidates:
        if any(a < s + minutes and s < b for a, b in others):
            continue
        if not (s + minutes <= t0 or s >= t1):
            continue  # still inside the window it should leave
        if gaps is not None and others:
            ordered = sorted([(a, b) for a, b in [(b["start"], b["start"] + b["minutes"]) for b in breaks
                                                   if b is not item]] + [(s, s + minutes)])
            spaces = [b2[0] - b1[1] for b1, b2 in zip(ordered, ordered[1:])]
            if (lo_gap is not None and any(x < lo_gap for x in spaces)) or \
                    (hi_gap is not None and any(x > hi_gap for x in spaces)):
                continue
        ticks = range(s // STEP, (s + minutes) // STEP)
        fine = True
        for i in ticks:
            if i >= today.ticks:
                break
            letter = letter_of(i)
            covered = ch["skills_of"](seg["name"]) if letter == "A" else letter
            langs = [j for j, r in enumerate(rules) if r["channel"] in covered
                     and r["language"].casefold() in ch["speaks"](seg)]
            if not all(_ok_without(today, c, langs, range(i, i + 1), day, step, setup, rules)
                       for c in (covered or "") if c in setup["need"]):
                fine = False
                break
        if fine:
            return s
    return None
