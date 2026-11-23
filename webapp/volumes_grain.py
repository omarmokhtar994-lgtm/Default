# © 2026 Omar Mokhtar. All rights reserved.
"""The grain of volumes (Phase BM): hourly history kept in a finer program, and a grid seen at a coarser interval.

A day whose volume sits only on the hour is hourly history: an hour's volume is shared over its intervals, so the pattern does not learn that nobody
calls at half past. A grid at the program's interval can be seen at a coarser one (30 minutes as 60)."""
from typing import Any, List, Optional, Sequence

MIN_HOURS = 6  # hours with volume a day needs before zeros off the hour mean "hourly" and not "a quiet day"


def looks_hourly(slots: Sequence[float], step: int) -> bool:
    """True when the day's intervals are finer than an hour, every interval off the hour is empty and at least ``MIN_HOURS`` hours hold volume."""
    if step >= 60 or 60 % step:
        return False
    per = 60 // step
    if any(v for i, v in enumerate(slots) if i % per):
        return False
    return sum(1 for i, v in enumerate(slots) if not i % per and v) >= MIN_HOURS


def share(total: float, parts: int) -> List[int]:
    """A whole number shared over ``parts`` as evenly as whole numbers allow, the odd ones first; the sum is the rounded total."""
    whole = int(round(total))
    base, extra = divmod(whole, parts)
    return [base + (1 if i < extra else 0) for i in range(parts)]


def spread_hour(slots: Sequence[float], step: int) -> List[int]:
    """Each hour's volume (kept in its first interval) shared over the hour's intervals; the day's total is unchanged."""
    per = 60 // step
    out: List[int] = []
    for start in range(0, len(slots), per):
        out += share(sum(slots[start:start + per]), per)
    return out


def regrid(grid: Sequence[Sequence[Any]], step: int, to_step: int, combine: str,
           weights: Optional[Sequence[Sequence[Any]]] = None) -> Any:
    """``grid`` (rows of intervals at ``step`` minutes) at ``to_step`` minutes, a multiple of it. ``combine``: "sum", "max", or "mean" (weighted by
    ``weights``, the plain mean of what is there when the weights are all zero). A cell is None when all its parts are None."""
    if to_step == step:
        return grid
    if to_step < step or to_step % step:
        raise ValueError(f"{to_step} minutes is not a multiple of the {step}-minute interval.")
    per = to_step // step
    out: List[List[Any]] = []
    for r, row in enumerate(grid):
        line: List[Any] = []
        for start in range(0, len(row), per):
            cells = [(v, (weights[r][start + i] or 0) if weights is not None else 1) for i, v in enumerate(row[start:start + per]) if v is not None]
            if not cells:
                line.append(None)
            elif combine == "sum":
                line.append(sum(v for v, _ in cells))
            elif combine == "max":
                line.append(max(v for v, _ in cells))
            elif combine == "mean":
                heavy = sum(w for _, w in cells)
                line.append(round(sum(v * w for v, w in cells) / heavy, 1) if heavy else round(sum(v for v, _ in cells) / len(cells), 1))
            else:
                raise ValueError("combine is sum, max or mean")
        out.append(line)
    return out
