"""B-6: how many associates are genuinely interchangeable?

Symmetry breaking is only sound between associates that are identical in every
input the model reads. If their languages, skills, fixed requests, leave,
preferences or carry-in differ, swapping them is not a symmetry and forcing an
order on them would remove real solutions.

This counts the true orbits: associates grouped by the full tuple of inputs the
model distinguishes them by.
"""
import json, sys
from collections import Counter, defaultdict
from math import factorial
from pathlib import Path

sys.path.insert(0, sys.argv[1])
import l632_universal_scheduler as E


def signature(parsed, a):
    assoc = parsed.associates[a]
    return (
        E.norm(getattr(assoc, "language", "")),
        tuple(sorted(E.norm(s) for s in (getattr(assoc, "skills", None) or []))),
        tuple(E.norm(x) for x in (getattr(assoc, "fixed_schedule", None) or [])),
        tuple(E.norm(x) for x in (getattr(assoc, "preferences", None) or [])),
        E.norm(getattr(assoc, "previous_saturday", "")),
        int(getattr(assoc, "max_shift_variety", 0) or 0),
    )


rows = []
for book in sorted(Path(sys.argv[2]).glob("*.xlsx")):
    try:
        parsed = E.parse_input(book)
    except Exception as exc:
        rows.append({"workbook": book.name, "error": type(exc).__name__})
        continue
    orbits = defaultdict(list)
    for a in range(len(parsed.associates)):
        orbits[signature(parsed, a)].append(a)
    sizes = sorted((len(v) for v in orbits.values()), reverse=True)
    interchangeable = sum(n for n in sizes if n > 1)
    # Permutations the orbits admit: the product of factorials of orbit sizes.
    perms = 1
    for n in sizes:
        perms *= factorial(n)
    rows.append({
        "workbook": book.name,
        "associates": len(parsed.associates),
        "distinct_orbits": len(orbits),
        "associates_in_a_group_of_2_or_more": interchangeable,
        "largest_orbit": sizes[0] if sizes else 0,
        "orbit_size_histogram": dict(sorted(Counter(sizes).items())),
        "equivalent_permutations": f"{perms:.3e}" if perms > 10**6 else perms,
    })
for r in rows:
    print(json.dumps(r))
