# © 2026 Omar Mokhtar. All rights reserved.
"""Phase BQ (owner, 2026-11-18): the site keeps working under a flood of requests.

Two guards, both in this one process (waitress serves the site from a single process, so counters in memory are
the whole picture):

- a budget of requests per minute: each signed-in person has their own (an office shares one address), and
  everyone who is not signed in is counted by address (the site's own files aside). Past it the answer is 429 with Retry-After.
- people who are not signed in can be answered on only a few of the worker threads at once; past that they get
  503 at once, so a flood of strangers never leaves staff without a thread.
"""
import threading
import time
from typing import Callable, Dict, Tuple


class Budget:
    """Requests per key per clock minute. The table holds at most ``size`` keys: past that, minutes that are over
    are dropped, and if every key is in this minute the table starts again (a flood from that many addresses is
    still held back by the busy guard)."""

    def __init__(self, per_minute: int, size: int = 20000, clock: Callable[[], float] = time.monotonic):
        self.per_minute = per_minute
        self.size = size
        self.clock = clock
        self.table: Dict[str, list] = {}  # key -> [minute, requests, refusal logged]
        self.lock = threading.Lock()

    def hit(self, key: str) -> Tuple[int, bool]:
        """Count one request. Returns (0, False) when it is inside the budget, else (seconds until the next
        minute, whether this is the key's first refusal this minute)."""
        now = self.clock()
        minute = int(now // 60)
        with self.lock:
            row = self.table.get(key)
            if row is None or row[0] != minute:
                if row is None and len(self.table) >= self.size:
                    self.table = {k: r for k, r in self.table.items() if r[0] == minute}
                    if len(self.table) >= self.size:
                        self.table = {}
                row = self.table[key] = [minute, 0, False]
            row[1] += 1
            if row[1] <= self.per_minute:
                return 0, False
            first = not row[2]
            row[2] = True
        return max(1, int((minute + 1) * 60 - now)), first


class Guard:
    def __init__(self, per_user: int, per_address: int, anon_threads: int, clock: Callable[[], float] = time.monotonic):
        self.users = Budget(per_user, clock=clock)
        self.addresses = Budget(per_address, clock=clock)
        self.anon_threads = anon_threads
        self.anon_busy = 0
        self.lock = threading.Lock()

    def enter_anonymous(self) -> bool:
        with self.lock:
            if self.anon_busy >= self.anon_threads:
                return False
            self.anon_busy += 1
            return True

    def leave_anonymous(self) -> None:
        with self.lock:
            self.anon_busy = max(0, self.anon_busy - 1)


def install(app, limits: Dict[str, int]) -> None:  # type: ignore[no-untyped-def]
    """Put the guard in front of every request of ``app``. Called before the app's own request checks, so a
    refused request costs no database work."""
    from flask import g, request, session

    guard = Guard(limits["PER_USER"], limits["PER_ADDRESS"], limits["ANON_BUSY"])
    app.extensions["flood"] = guard

    def refuse(status: int, wait: int, text: str):  # type: ignore[no-untyped-def]
        return text, status, {"Retry-After": str(wait), "Content-Type": "text/plain; charset=utf-8"}

    @app.before_request
    def _flood() -> object:
        user_id = session.get("user_id")  # the session cookie is signed: a stranger cannot claim a user
        if user_id is not None:
            kind, key, budget = "person", f"user {user_id}", guard.users
        else:  # the site's own files are not counted per address (an office shares one), only held by the busy guard
            kind, key, budget = "address", request.remote_addr or "unknown", guard.addresses
        wait, first = (0, False) if budget is guard.addresses and request.endpoint == "static" else budget.hit(key)
        if wait:
            if first:
                app.logger.warning("too many requests from %s %s: refused for %d s", kind, key, wait)
            return refuse(429, wait, f"Too many requests. Wait {wait} seconds and try again.")
        if user_id is None:
            if not guard.enter_anonymous():
                return refuse(503, 5, "The site is busy. Try again in a few seconds.")
            g.flood_anonymous = True
        return None

    @app.teardown_request
    def _flood_done(_exc) -> None:  # type: ignore[no-untyped-def]
        if g.pop("flood_anonymous", False):
            guard.leave_anonymous()
