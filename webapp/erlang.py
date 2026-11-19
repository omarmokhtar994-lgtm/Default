# © 2026 Omar Mokhtar. All rights reserved.
"""Phase BI: staffing arithmetic for one interval (owner, 2026-11-03: "use Erlang ... to calculate the needed associates per interval").

Voice: Erlang C to a service level (a share answered within a threshold). Chat: the same with a concurrency factor (one agent holds several
chats, so the handle time per chat is shorter). Email: the workload method (work arriving in the interval divided by the productive time an
agent has in it). Pure functions on plain numbers, no dependency; Erlang C goes through the Erlang B recursion, so large centres neither
overflow nor take noticeable time.

Standard Erlang C assumptions, stated on the page: one queue, calls wait as long as it takes (nobody abandons), arrivals random, handle time
the same for everyone. It over-staffs where callers do abandon. The answers are agents on the phone (productive); ``fte_required`` adds
shrinkage.
"""
from __future__ import annotations

import math
from typing import Optional

TOLERANCE = 1e-12   # where a comparison is exact on paper, a float may be a hair off
MAX_TRAFFIC = 50_000.0  # Erlangs in one interval: about fifty thousand agents on the phones at once, far beyond any centre; a typed total can reach
                        # this only by mistake, and the search below costs one step per agent, so it is refused in words instead of run for minutes


def _check_volume(calls: float, aht_s: float, interval_s: float) -> None:
    if calls < 0:
        raise ValueError("Volume cannot be negative.")
    if aht_s <= 0:
        raise ValueError("Handle time must be more than zero seconds.")
    if interval_s <= 0:
        raise ValueError("The interval must be more than zero seconds.")


def erlangs(calls: float, aht_s: float, interval_s: int) -> float:
    """The traffic offered in an interval, in Erlangs: handle-seconds arriving per second of the interval."""
    _check_volume(calls, aht_s, interval_s)
    return calls * aht_s / interval_s


def erlang_c(agents: int, traffic: float) -> float:
    """The probability that a call has to wait: 1.0 when agents do not exceed the traffic, 0.0 when there is no traffic."""
    if traffic <= 0:
        return 0.0
    if agents <= traffic:
        return 1.0
    b = 1.0  # Erlang B by recursion: stable for any size
    for n in range(1, int(agents) + 1):
        b = traffic * b / (n + traffic * b)
    return b / (1.0 - (traffic / agents) * (1.0 - b))


def service_level(agents: int, calls: float, aht_s: float, interval_s: int, threshold_s: float) -> float:
    """The share of calls answered within ``threshold_s`` seconds (0 to 1); 1.0 with no calls, 0.0 when the agents cannot keep up."""
    traffic = erlangs(calls, aht_s, interval_s)
    if traffic <= 0:
        return 1.0
    if agents <= traffic:
        return 0.0
    return max(0.0, 1.0 - erlang_c(agents, traffic) * math.exp(-(agents - traffic) * threshold_s / aht_s))


def average_wait(agents: int, calls: float, aht_s: float, interval_s: int) -> Optional[float]:
    """The average speed of answer in seconds, or None when the agents cannot keep up."""
    traffic = erlangs(calls, aht_s, interval_s)
    if traffic <= 0:
        return 0.0
    if agents <= traffic:
        return None
    return erlang_c(agents, traffic) * aht_s / (agents - traffic)


def agents_needed(calls: float, aht_s: float, interval_s: int, target: float, threshold_s: float,
                  max_occupancy: float = 1.0) -> int:
    """The fewest agents for ``target`` (0 to 1) answered within ``threshold_s`` seconds, with occupancy no higher than ``max_occupancy``."""
    if not 0.0 < target <= 1.0:
        raise ValueError("The service level target is more than 0 and at most 100 percent.")
    if threshold_s < 0:
        raise ValueError("The answer time cannot be negative.")
    if not 0.0 < max_occupancy <= 1.0:
        raise ValueError("The occupancy cap is more than 0 and at most 100 percent.")
    traffic = erlangs(calls, aht_s, interval_s)
    if traffic <= 0:
        return 0
    if traffic > MAX_TRAFFIC:
        raise ValueError(f"{traffic:,.0f} Erlangs in one interval is too large to staff: check the volume, the handle time and the interval length.")
    n = int(math.floor(traffic)) + 1
    # The Erlang B sum is carried from one agent count to the next (the same arithmetic in the same order as ``erlang_c``, so every answer is the
    # same as recomputing it at each step); audit 2026-11-11: recomputing made the search cost a step per agent per candidate.
    b = 1.0
    for k in range(1, n):
        b = traffic * b / (k + traffic * b)
    while True:
        b = traffic * b / (n + traffic * b)
        # Compared to 12 places, as a spreadsheet does: 23.8 / 34 is exactly 0.7 on paper and 0.7000000000000001 in a float, and 34 agents are not too many
        if not traffic / n - max_occupancy > TOLERANCE:
            wait = b / (1.0 - (traffic / n) * (1.0 - b))
            if not max(0.0, 1.0 - wait * math.exp(-(n - traffic) * threshold_s / aht_s)) < target - TOLERANCE:
                return n
        n += 1


def chat_agents_needed(calls: float, aht_s: float, interval_s: int, target: float, threshold_s: float,
                       concurrency: float, max_occupancy: float) -> int:
    """Chat: Erlang C on the handle time divided by the concurrency (an agent holding two chats serves each in half the agent time)."""
    if not 1.0 <= concurrency <= 10.0:
        raise ValueError("Concurrency is from 1 to 10 chats at a time.")
    return agents_needed(calls, aht_s / concurrency, interval_s, target, threshold_s, max_occupancy)


def workload_agents(calls: float, aht_s: float, interval_s: int, max_occupancy: float) -> float:
    """Email and other back-office work: the work that arrived, divided by the productive time one agent has in the interval."""
    _check_volume(calls, aht_s, interval_s)
    if not 0.0 < max_occupancy <= 1.0:
        raise ValueError("The occupancy cap is more than 0 and at most 100 percent.")
    return calls * aht_s / (interval_s * max_occupancy)


def fte_required(agents: float, shrinkage: float) -> float:
    """People to schedule so that ``agents`` remain after breaks, leave, training and the rest (shrinkage as 0 to 1, below 1)."""
    if not 0.0 <= shrinkage < 1.0:
        raise ValueError("Shrinkage is from 0 up to, not including, 100 percent.")
    return agents / (1.0 - shrinkage)
