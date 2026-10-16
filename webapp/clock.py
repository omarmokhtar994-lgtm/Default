# © 2026 Omar Mokhtar. All rights reserved.
"""Egypt time for the whole website (owner's rule: times in Egypt time).

Egypt changes its clocks: UTC+3 in summer, UTC+2 in winter (from midnight on the last
Thursday of October to the last Friday of April). The Africa/Cairo zone follows those
changes, so every module takes EGYPT from here instead of fixing an offset. The zone
comes from the server's time zone data (the tzdata package); without it the website
stops at start-up with ZoneInfoNotFoundError rather than show times an hour out.
"""
import re
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import date, datetime, time, timedelta, timezone
from functools import lru_cache
from typing import Iterator
from zoneinfo import ZoneInfo

EGYPT = ZoneInfo("Africa/Cairo")

# Phase AF (A5, D5): the zones a page can show and a schedule's times can be in. Each is a named zone, so summer time
# follows the date; all have whole-hour offsets, so a day in any of them lines up with every interval length.
HOME = "Africa/Cairo"  # every page shows Egypt time unless someone picks another zone
ZONES = (("Africa/Cairo", "Cairo (Egypt)"), ("America/New_York", "New York (US Eastern)"),
         ("America/Chicago", "Chicago (US Central)"), ("America/Denver", "Denver (US Mountain)"),
         ("America/Los_Angeles", "Los Angeles (US Pacific)"), ("Europe/London", "London (UK)"),
         ("Europe/Paris", "Paris (Central Europe)"), ("Asia/Riyadh", "Riyadh (Saudi Arabia)"),
         ("Asia/Dubai", "Dubai (UAE)"), ("UTC", "UTC"))


def pick_zone(value: str) -> str:
    """A zone from the list, or Egypt for anything else."""
    return value if value in dict(ZONES) else HOME


def offset(zone: str, on: date) -> int:
    """Minutes ahead of UTC in ``zone`` on the date ``on`` (taken at noon, so a day keeps one offset)."""
    found = datetime.combine(on, time(12), ZoneInfo(zone)).utcoffset()
    return int(found.total_seconds() // 60) if found is not None else 0


def shift(on: date, from_zone: str, to_zone: str) -> int:
    """Minutes to add to a time of day in ``from_zone`` to read it in ``to_zone``, on the date ``on``."""
    return offset(to_zone, on) - offset(from_zone, on)


def converted(on: date, minute: int, from_zone: str, to_zone: str) -> datetime:
    """Convert an actual dated wall time, including overnight and DST transitions.

    Workbooks have no occurrence field. Repeated and nonexistent source times
    are refused rather than guessing which instant the author intended.
    """
    wall = datetime.combine(on, time()) + timedelta(minutes=minute)
    source = wall.replace(tzinfo=ZoneInfo(pick_zone(from_zone)), fold=0)
    back = source.astimezone(timezone.utc).astimezone(source.tzinfo)
    if back.replace(tzinfo=None) != wall:
        raise ValueError(f"{wall:%d %b %Y %H:%M} does not exist in {from_zone} because the clocks change.")
    if source.utcoffset() != source.replace(fold=1).utcoffset():
        raise ValueError(f"{wall:%d %b %Y %H:%M} occurs twice in {from_zone} because the clocks change. "
                         "The workbook does not identify the occurrence; use the original-zone workbook.")
    return source.astimezone(ZoneInfo(pick_zone(to_zone)))


def dated_label(value: datetime) -> str:
    """A converted clock label, including its offset when the hour repeats."""
    text = value.strftime("%H:%M")
    if value.replace(fold=0).utcoffset() != value.replace(fold=1).utcoffset():
        offset_text = value.strftime("%z")
        text += f" (UTC{offset_text[:3]}:{offset_text[3:]})"
    return text


@lru_cache(maxsize=512)
def rta_shift(on: date, from_zone: str, to_zone: str):
    """A constant RTA offset, or None when the wall-clock view cannot convert it.

    RTA can include yesterday's shift and tomorrow's hours. Check that entire
    source range, including both occurrences of a repeated hour. Its fixed
    1,440-minute layout cannot represent a changing offset within that range.
    """
    if from_zone == to_zone:
        return 0
    source_zone = ZoneInfo(pick_zone(from_zone))
    target_zone = ZoneInfo(pick_zone(to_zone))
    offsets = set()
    for minute in range(-1440, 2881, 60):
        wall = datetime.combine(on, time()) + timedelta(minutes=minute)
        for fold in (0, 1):
            source = wall.replace(tzinfo=source_zone, fold=fold)
            target = source.astimezone(timezone.utc).astimezone(target_zone)
            offsets.add(int((target.utcoffset() - source.utcoffset()).total_seconds() // 60))
            if len(offsets) > 1:
                return None
    return offsets.pop()


def minute_now(on: date, zone: str, clock=None) -> int:
    """Now in the schedule's wall-clock minutes from its anchor date."""
    current = (clock or datetime.now(timezone.utc)).astimezone(ZoneInfo(pick_zone(zone)))
    return (current.date() - on).days * 1440 + current.hour * 60 + current.minute


def zone_label(zone: str, on: date) -> str:
    """"New York (US Eastern), UTC-4": the zone's name and its offset on ``on``."""
    minutes = offset(zone, on)
    hours, rest = divmod(abs(minutes), 60)
    return f"{dict(ZONES).get(zone, zone)}, UTC{'+' if minutes >= 0 else '-'}{hours}" + (f":{rest:02d}" if rest else "")


# Phase AI (owner, 2026-10-15: "break should show in the new time zone and can be changed but ... the time should be
# based the schedule default"): while the RTA is drawn, every time of day is shown this many minutes ahead of the
# schedule's own; what is kept, logged and posted stays in the schedule's time (the default, 0).
SHOWN: ContextVar[int] = ContextVar("shown", default=0)
TIME = re.compile(r"\b([01]\d|2[0-3]):([0-5]\d)\b")


@contextmanager
def shown(minutes: int) -> Iterator[None]:
    """Times of day shown ``minutes`` ahead of the schedule's own while inside."""
    token = SHOWN.set(minutes)
    try:
        yield
    finally:
        SHOWN.reset(token)


def _clock(minute: int) -> str:
    minute %= 1440
    return f"{minute // 60:02d}:{minute % 60:02d}"


def moved_text(text: str, minutes: int) -> str:
    """``text`` with each time of day (HH:MM) read ``minutes`` later; durations ("2 h 20 min") are left as they are."""
    if not minutes:
        return text
    return TIME.sub(lambda m: _clock(int(m.group(1)) * 60 + int(m.group(2)) + minutes), text)


def to_schedule(value: str, minutes: int) -> str:
    """A time typed in the zone shown, as the schedule's own time; anything that is not a time is left for the
    caller to refuse, as before."""
    m = TIME.fullmatch((value or "").strip())
    return _clock(int(m.group(1)) * 60 + int(m.group(2)) - minutes) if m and minutes else value
