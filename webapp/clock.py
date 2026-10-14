# © 2026 Omar Mokhtar. All rights reserved.
"""Egypt time for the whole website (owner's rule: times in Egypt time).

Egypt changes its clocks: UTC+3 in summer, UTC+2 in winter (from midnight on the last
Thursday of October to the last Friday of April). The Africa/Cairo zone follows those
changes, so every module takes EGYPT from here instead of fixing an offset. The zone
comes from the server's time zone data (the tzdata package); without it the website
stops at start-up with ZoneInfoNotFoundError rather than show times an hour out.
"""
from datetime import date, datetime, time
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


def zone_label(zone: str, on: date) -> str:
    """"New York (US Eastern), UTC-4": the zone's name and its offset on ``on``."""
    minutes = offset(zone, on)
    hours, rest = divmod(abs(minutes), 60)
    return f"{dict(ZONES).get(zone, zone)}, UTC{'+' if minutes >= 0 else '-'}{hours}" + (f":{rest:02d}" if rest else "")
