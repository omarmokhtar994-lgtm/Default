# © 2026 Omar Mokhtar. All rights reserved.
"""Phase AY (owner, 2026-10-23: "when I change something, how long until it shows on the associate view if it is already
open?"): a page that is open asks a very small address every 30 seconds "has what I show changed?", and reloads (a page that is
read only) or shows a bar (a page where people are in the middle of something) when the answer changes.

The answer is a stamp: a short digest of what the page shows, not the write counter of the database. The write counter also
moves when someone merely opens a page (the "day seen" mark), so it would reload every open page each time anybody looked."""
import hashlib
import json
import threading
import time
from typing import Any, Callable, Dict, List

from webapp.attendance import fingerprint

KEEP = 10       # seconds a stamp is kept: at most one build per page and 10 s, however many people are asking
KINDS = ("me", "day", "requests")


def digest(x: Any) -> str:
    """A short, stable digest of plain values (a day, a list of requests)."""
    return hashlib.sha1(json.dumps(fingerprint(x), sort_keys=True, default=str).encode()).hexdigest()[:16]


def lanes_of(page: Any, name: str = "") -> List[Any]:
    """What a day shows about people: each lane's segments (status, breaks, activities); one person's with ``name``."""
    if not page:
        return []
    return [[lane["name"], lane["segments"]] for lane in page["view"]["lanes"] if not name or lane["name"] == name]


class Stamps:
    """Stamps kept for ``KEEP`` seconds, and counts of what was asked and built (written to the log now and then)."""

    def __init__(self, clock: Callable[[], float] = time.monotonic):
        self._clock, self._kept, self._lock = clock, {}, threading.Lock()
        self.asked = self.built = 0

    def get(self, key: Any, make: Callable[[], str]) -> str:
        with self._lock:
            self.asked += 1
            held = self._kept.get(key)
            if held is not None and self._clock() - held[0] < KEEP:
                return held[1]
        value = make()
        with self._lock:
            self.built += 1
            self._kept[key] = (self._clock(), value)
            if len(self._kept) > 2048:
                for old in sorted(self._kept, key=lambda k: self._kept[k][0])[:512]:
                    del self._kept[old]
        return value

    def line(self) -> str:
        return f"live stamps: {self.asked} asked, {self.built} built"
