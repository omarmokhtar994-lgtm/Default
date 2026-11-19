# © 2026 Omar Mokhtar. All rights reserved.
"""Sample al01: four other Email colours on the Timeline, next to the one installed, light and dark (made-up rows)."""
import sys
from playwright.sync_api import sync_playwright
ROWS = [("Associate 01", [(0, 180, "P"), (180, 300, "E"), (300, 420, "C"), (420, 540, "P")], [(120, 15), (260, 30), (400, 15)]),
        ("Associate 02", [(0, 240, "E"), (240, 360, "P"), (360, 540, "C")], [(150, 15), (300, 30), (450, 15)]),
        ("Associate 03", [(0, 120, "C"), (120, 330, "P"), (330, 540, "E")], [(100, 15), (240, 30), (420, 15)])]
OPTS = {
    "Now": ("What is installed: light green Email", "Phone #1A47A8, Chat #C2549F, Email #A6D96A",
          {"bar": "#9AA1AA", "P": "#1A47A8", "C": "#C2549F", "E": "#A6D96A"}, "letters"),
    "A": ("Recommended: paper white Email", "Email #E9E4D8 with a dark E (13:1). Dark Phone, mid Chat, light Email: told apart by lightness, and no hue the status colours use",
          {"bar": "#9AA1AA", "P": "#1A47A8", "C": "#C2549F", "E": "#E9E4D8"}, "letters"),
    "B": ("Ice blue Email", "Email #C9E2F2 with a dark E (12:1). Light, but in the blue family of Phone",
          {"bar": "#9AA1AA", "P": "#1A47A8", "C": "#C2549F", "E": "#C9E2F2"}, "letters"),
    "C": ("Deep green Email", "Email #2F7D5B with a white E (5:1). Calmer than the light green, still green, and dark like Phone",
          {"bar": "#9AA1AA", "P": "#1A47A8", "C": "#C2549F", "E": "#2F7D5B"}, "letters"),
    "D": ("Brown Email", "Email #8A5A3B with a white E (5.8:1). Warm and dark; sits between the amber and red status hues, but much duller",
          {"bar": "#9AA1AA", "P": "#1A47A8", "C": "#C2549F", "E": "#8A5A3B"}, "letters"),
}
LIGHT_E = {"#A6D96A", "#E9E4D8", "#C9E2F2"}
def svg(rows, c, mode):
    out = []
    for name, runs, breaks in rows:
        s = [f'<rect x="0" y="5" width="540" height="16" rx="3" fill="{c["bar"]}"/>']
        for a, b, ch in runs:
            s.append(f'<rect x="{a}" y="5" width="{b-a}" height="16" rx="3" fill="{c[ch]}"/>')
            if mode == "letters" and b - a >= 30:
                s.append(f'<text x="{(a+b)/2}" y="17" font-size="11" font-weight="700" fill="{'#1B1F24' if ch == 'E' and c['E'] in LIGHT_E else '#fff'}" text-anchor="middle">{ch}</text>')
        for t, m in breaks:
            s.append(f'<rect x="{t}" y="1" width="{m}" height="24" rx="2" fill="#2B2F35"/>')
        out.append(f'<div class="row"><span>{name}</span><svg viewBox="0 0 540 26">{"".join(s)}</svg></div>')
    return "".join(out)
html = ""
for k, (title, note, c, mode) in OPTS.items():
    key = "".join(f'<span><i style="background:{c[x]}"></i>{n}</span>' for x, n in (("P", "Phone"), ("C", "Chat"), ("E", "Email")))
    html += f'<div class="opt"><h2>{"" if k == "Now" else "Option " + k + ": "} {title}</h2><p>{note}</p>{svg(ROWS, c, mode)}<div class="key">{key}</div></div>'
with sync_playwright() as p:
    b = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
    pg = b.new_page(viewport={"width": 1040, "height": 900})
    pg.goto("file://" + sys.argv[1])
    for look in ("light", "dark"):
        pg.evaluate("([h, l]) => { document.getElementById('out').innerHTML = h; document.body.className = l; }", [html, look])
        pg.screenshot(path=f"al01_email_colour_{look}.png", full_page=True)
    b.close()
