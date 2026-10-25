# © 2026 Omar Mokhtar. All rights reserved.
"""Phase BA: contrast of the token pairs in the three looks (Night watch = :root, Tide = :root[data-theme=light], Drafting table = draft).
Text pairs need 4.5:1, controls and fills 3:1. Run from the repository root: python3 evidence/phase_ba/contrast.py"""
import re
from pathlib import Path
css = re.sub(r"/\*.*?\*/", "", Path("webapp/static/app.css").read_text(), flags=re.S)
def block(opener):
    i = css.index(opener) + len(opener) - 1
    depth = 0
    for j in range(i, len(css)):
        depth += {"{": 1, "}": -1}.get(css[j], 0)
        if depth == 0:
            return css[i + 1:j]
def toks(b): return {k[2:]: v.upper() for k, v in re.findall(r"(--[\w-]+)\s*:\s*(#[0-9A-Fa-f]{6})\b", b)}
root = toks(block(":root {"))
LOOKS = {"Night watch": root, "Tide": {**root, **toks(block(':root[data-theme="light"] {'))}, "Drafting table": {**root, **toks(block(':root[data-theme="draft"] {'))}}
def lum(h):
    r, g, b = (int(h[i:i + 2], 16) / 255 for i in (1, 3, 5)); f = lambda c: c / 12.92 if c <= .03928 else ((c + .055) / 1.055) ** 2.4
    return .2126 * f(r) + .7152 * f(g) + .0722 * f(b)
def cr(a, b):
    la, lb = lum(a), lum(b); return (max(la, lb) + .05) / (min(la, lb) + .05)
PAIRS = [("paper", "night", 4.5), ("paper", "console", 4.5), ("dim", "night", 4.5), ("dim", "console", 4.5), ("dim", "rail-bg", 4.5),
         ("edge", "console", 3), ("edge", "night", 3), ("action", "console", 4.5), ("on-action", "action", 4.5),
         ("covered-text", "console", 4.5), ("over-text", "console", 4.5), ("short-ink", "console", 4.5), ("gap-ink", "console", 4.5),
         ("on-covered", "covered", 4.5), ("on-short", "short", 4.5), ("on-gap", "gap", 4.5), ("on-over", "over", 4.5),
         ("covered", "console", 3), ("short", "console", 3), ("gap", "console", 3), ("over", "console", 3),
         ("ch-ink", "ch-phone", 4.5), ("ch-ink", "ch-chat", 4.5), ("ch-ink", "ch-email", 4.5), ("ch-phone", "console", 3), ("ch-chat", "console", 3), ("ch-email", "console", 3),
         ("on-hi", "hi", 4.5), ("paper", "selected", 4.5), ("action", "selected", 4.5)]
bad = 0
for name, t in LOOKS.items():
    print(name)
    for a, b, need in PAIRS:
        if a in t and b in t:
            c = cr(t[a], t[b]); ok = c >= need; bad += not ok
            if not ok or c < need + .6: print(f"   {'FAIL' if not ok else 'near'} {a} on {b}: {c:.2f} (need {need})  {t[a]} {t[b]}")
print("failures:", bad)
