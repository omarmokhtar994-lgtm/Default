# © 2026 Omar Mokhtar. All rights reserved.
"""Phase AT: one address trying many usernames (password spraying). An account already locks itself for 15 minutes after
5 wrong passwords (Store.authenticate); this holds an address after too many wrong sign-ins in a row of 15 minutes.
Kept in memory: the site runs as one process, and a restart only forgives the count."""
from __future__ import annotations

import threading
import time
from typing import Dict, List, Optional


class SignInThrottle:
    def __init__(self, limit: int = 40, seconds: int = 15 * 60) -> None:
        self.limit, self.seconds = limit, seconds
        self._seen: Dict[str, List[float]] = {}
        self._lock = threading.Lock()

    def _recent(self, address: str, now: float) -> List[float]:
        recent = [t for t in self._seen.get(address, []) if now - t < self.seconds]
        if recent:
            self._seen[address] = recent
        else:
            self._seen.pop(address, None)
        return recent

    def held(self, address: str, now: Optional[float] = None) -> bool:
        now = time.time() if now is None else now
        with self._lock:
            return len(self._recent(address, now)) >= self.limit

    def failed(self, address: str, now: Optional[float] = None) -> None:
        now = time.time() if now is None else now
        with self._lock:
            for other in [a for a, times in self._seen.items() if not times or now - times[-1] >= self.seconds]:
                del self._seen[other]  # forget addresses that have been quiet for a whole window
            self._seen.setdefault(address, self._recent(address, now)).append(now)
