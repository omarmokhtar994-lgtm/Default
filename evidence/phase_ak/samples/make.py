# © 2026 Omar Mokhtar. All rights reserved.
"""Sample ak01: three ways to show Phone, Chat and Email on the Timeline bars, light and dark (made-up rows)."""
import sys
from playwright.sync_api import sync_playwright
ROWS = [("Associate 01", [(0, 180, "P"), (180, 300, "E"), (300, 420, "C"), (420, 540, "P")], [(120, 15), (260, 30), (400, 15)]),
        ("Associate 02", [(0, 240, "E"), (240, 360, "P"), (360, 540, "C")], [(150, 15), (300, 30), (450, 15)]),
        ("Associate 03", [(0, 120, "C"), (120, 330, "P"), (330, 540, "E")], [(100, 15), (240, 30), (420, 15)])]
OPTS = {
    "A": ("Grey bar, the channel fills the whole bar", "Bar grey when a channel plan exists; Phone blue, Chat magenta, Email amber",
          {"bar": "#8A929C", "P": "#2F6FE0", "C": "#B4479A", "E": "#D98A1C"}, "full"),
    "B": ("Keep the blue bar, stronger channel stripe", "Blue bar; Phone orange, Chat purple, Email green, stripe as tall as the bar",
          {"bar": "#3E6FD8", "P": "#E07B24", "C": "#8A4FD8", "E": "#2E9E6A"}, "full"),
    "C": ("Grey bar, channel fills the bar, with its letter", "As A, plus P, C or E written on each stretch of 30 minutes or more",
          {"bar": "#8A929C", "P": "#2F6FE0", "C": "#B4479A", "E": "#D98A1C"}, "letters"),
    "D": ("Recommended: dark Phone, mid Chat, light Email, with letters",
          "Dark blue Phone, pink Chat, light green Email: apart by lightness too, and clear of the status colours (amber means short)",
          {"bar": "#9AA1AA", "P": "#1A47A8", "C": "#C2549F", "E": "#A6D96A"}, "letters"),
}
def svg(rows, c, mode):
    out = []
    for name, runs, breaks in rows:
        s = [f'<rect x="0" y="5" width="540" height="16" rx="3" fill="{c["bar"]}"/>']
        for a, b, ch in runs:
            s.append(f'<rect x="{a}" y="5" width="{b-a}" height="16" rx="3" fill="{c[ch]}"/>')
            if mode == "letters" and b - a >= 30:
                s.append(f'<text x="{(a+b)/2}" y="17" font-size="11" font-weight="700" fill="{'#1B1F24' if ch == 'E' else '#fff'}" text-anchor="middle">{ch}</text>')
        for t, m in breaks:
            s.append(f'<rect x="{t}" y="1" width="{m}" height="24" rx="2" fill="#2B2F35"/>')
        out.append(f'<div class="row"><span>{name}</span><svg viewBox="0 0 540 26">{"".join(s)}</svg></div>')
    return "".join(out)
html = ""
for k, (title, note, c, mode) in OPTS.items():
    key = "".join(f'<span><i style="background:{c[x]}"></i>{n}</span>' for x, n in (("P", "Phone"), ("C", "Chat"), ("E", "Email")))
    html += f'<div class="opt"><h2>Option {k}: {title}</h2><p>{note}</p>{svg(ROWS, c, mode)}<div class="key">{key}</div></div>'
with sync_playwright() as p:
    b = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
    pg = b.new_page(viewport={"width": 1040, "height": 900})
    pg.goto("file://" + sys.argv[1])
    for look in ("light", "dark"):
        pg.evaluate("([h, l]) => { document.getElementById('out').innerHTML = h; document.body.className = l; }", [html, look])
        pg.screenshot(path=f"ak01_channel_colours_{look}.png", full_page=True)
    b.close()
