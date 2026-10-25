# © 2026 Omar Mokhtar. All rights reserved.
"""Builds the three look samples (Phase AZ, owner 2026-10-25: "fancy background, floating note, change the palette, fully
redesign"). Static pages only: made-up "Associate NN" names, no inline script or style, nothing under webapp/ changes.
    python3 build.py   ->   a_aurora_*.html, b_night_*.html, c_paper_*.html, sample.css, bars.css, sample.js"""
from pathlib import Path

HERE = Path(__file__).parent
HOURS = list(range(8, 21))  # 08:00 to 20:00, one grid column per hour

ROWS = [  # name, language, [(start, end, kind)]; kind: P C E phone chat email, B break, L lunch
    ("Associate 01", "English", [(8, 11, "P"), (11, 11.25, "B"), (11.25, 13, "C"), (13, 13.5, "L"), (13.5, 17, "P")]),
    ("Associate 02", "Arabic", [(8, 10, "C"), (10, 10.25, "B"), (10.25, 12.5, "P"), (12.5, 13, "L"), (13, 17, "P")]),
    ("Associate 03", "English", [(9, 12, "E"), (12, 12.5, "L"), (12.5, 14, "E"), (14, 14.25, "B"), (14.25, 18, "P")]),
    ("Associate 04", "Arabic", [(9, 11.5, "P"), (11.5, 11.75, "B"), (11.75, 14, "C"), (14, 14.5, "L"), (14.5, 18, "C")]),
    ("Associate 05", "English", [(12, 14, "P"), (14, 14.25, "B"), (14.25, 16.5, "P"), (16.5, 17, "L"), (17, 21, "C")]),
    ("Associate 06", "English", [(12, 15, "C"), (15, 15.25, "B"), (15.25, 17, "E"), (17, 17.5, "L"), (17.5, 20, "P")]),
]
NOW = 14.6
COVER = ["c", "c", "c", "s", "c", "c", "s", "g", "s", "c", "c", "o", "c"]  # one per hour: covered, short, gap, over

THEMES = {
    "a": ("aurora", "Tide", "Light, a cool sea-glass wash behind plain panels"),
    "b": ("night", "Night watch", "Dark, deep blue with a faint grid that glows around the now line"),
    "c": ("paper", "Paper", "Light, flat and quick: a dot grid and one ink-blue accent"),
}


def cls(a, b, k):
    return f"s{str(a).replace('.', '_')}e{str(min(b, 21)).replace('.', '_')}"


def bars_css():
    seen, out = set(), []
    for _, _, segs in ROWS:
        for a, b, k in segs:
            name = cls(a, b, k)
            if name not in seen:
                seen.add(name)
                out.append(f".{name} {{ grid-column: {round((a - 8) * 4) + 1} / {round((min(b, 21) - 8) * 4) + 1}; }}")
    out.append(f".now-line {{ left: calc(var(--lab) + (100% - var(--lab)) * {(NOW - 8) / 13:.4f}); }}")
    return "\n".join(out) + "\n"


def top(theme, title, active):
    folder, name, _ = THEMES[theme]
    nav = "".join(f'<a href="#"{" class=on aria-current=page" if label == active else ""}>{label}</a>'
                  for label in ("Today", "This week", "Requests", "Insights", "Setup"))
    nav = nav.replace("class=on aria-current=page\"", 'class="on" aria-current="page"')
    return f'''<!doctype html>
<html lang="en" data-look="{theme}">
<head>
<!-- © 2026 Omar Mokhtar. All rights reserved. -->
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}: Team Scheduler</title>
<link rel="stylesheet" href="sample.css">
<link rel="stylesheet" href="bars.css">
</head>
<body class="look-{theme}">
<div class="backdrop" aria-hidden="true"></div>
'''


def day_page(theme):
    folder, name, blurb = THEMES[theme]
    head = top(theme, f"Real-time view, {name} look", "Today")
    nav = "".join(f'<a href="#"{(" class=\"on\" aria-current=\"page\"" if label == "Today" else "")}>{label}</a>'
                  for label in ("Today", "This week", "Requests", "Insights", "Setup"))
    hours = "".join(f"<span>{h:02d}</span>" for h in HOURS)
    rows = []
    for who, lang, segs in ROWS:
        cells = []
        for a, b, k in segs:
            label = {"P": "Phone", "C": "Chat", "E": "Email", "B": "Break", "L": "Lunch"}[k]
            letter = k if k in "PCE" and b - a >= 1 else ""
            cells.append(f'<span class="seg k-{k} {cls(a, b, k)}" title="{label}, {int(a):02d}:{int(a % 1 * 60):02d} to '
                         f'{int(b):02d}:{int(b % 1 * 60):02d}">{letter}</span>')
        rows.append(f'<div class="lane"><div class="who"><b>{who}</b><small>{lang}</small></div>'
                    f'<div class="track">{"".join(cells)}</div></div>')
    heat = "".join(f'<span class="cell h-{c}"><i class="sr">{ {"c": "covered", "s": "short", "g": "gap", "o": "over"}[c] }</i></span>'
                   for c in COVER)
    return head + f'''<div class="shell">
<header class="top">
  <a class="brand" href="#"><img src="static/mark.svg" alt="" width="28" height="20"><span>Team Scheduler</span></a>
  <nav aria-label="Main">{nav}</nav>
  <span class="who-chip">Sara</span>
</header>
<main id="main">
  <section class="hero" aria-labelledby="h1">
    <p class="when">Wednesday 14 October, 14:36 Egypt time</p>
    <h1 id="h1">SAKS, NMG Tier 2</h1>
    <ul class="pulse" aria-label="Right now">
      <li><b>38</b> on the floor</li>
      <li><b>4</b> on a break</li>
      <li class="warn"><b>2</b> short on Phone until 16:00</li>
      <li><b>1</b> late login</li>
    </ul>
  </section>
  <section class="card timeline" aria-labelledby="t1">
    <div class="card-head"><h2 id="t1">Who is on what</h2>
      <ul class="legend"><li><i class="k-P"></i>Phone</li><li><i class="k-C"></i>Chat</li><li><i class="k-E"></i>Email</li><li><i class="k-B"></i>Break</li><li><i class="k-L"></i>Lunch</li></ul></div>
    <div class="scale" aria-hidden="true">{hours}</div>
    <div class="lanes">{"".join(rows)}<span class="now-line" aria-hidden="true"><em>Now 14:36</em></span></div>
  </section>
  <section class="card" aria-labelledby="t2">
    <div class="card-head"><h2 id="t2">Coverage by hour</h2><p class="hint">Against the need for the day</p></div>
    <div class="heat">{heat}</div>
    <ul class="legend small"><li><i class="h-c"></i>Covered</li><li><i class="h-s"></i>Short</li><li><i class="h-g"></i>Gap</li><li><i class="h-o"></i>Over</li></ul>
  </section>
  <section class="card" aria-labelledby="t3">
    <div class="card-head"><h2 id="t3">Waiting for you</h2><p class="hint">3 requests</p></div>
    <ul class="asks">
      <li><div><b>Associate 03</b><small>Swap Thursday 16 October with Associate 06</small></div><span class="btns"><button type="button" class="ghost">Decline</button><button type="button">Approve</button></span></li>
      <li><div><b>Associate 05</b><small>Day off on Sunday 18 October</small></div><span class="btns"><button type="button" class="ghost">Decline</button><button type="button">Approve</button></span></li>
      <li><div><b>Associate 01</b><small>Break moved from 11:00 to 11:30 today</small></div><span class="btns"><button type="button" class="ghost">Decline</button><button type="button">Approve</button></span></li>
    </ul>
  </section>
</main>
</div>
<div class="float-note" id="note" role="status" hidden>
  <i class="pip" aria-hidden="true"></i>
  <span><b>This page is out of date.</b> Associate 04's break moved at 14:35.</span>
  <a class="refresh" href="#">Refresh</a>
  <button type="button" class="x" aria-label="Hide for now">Hide</button>
</div>
<script src="sample.js"></script>
</body></html>
'''


def login_page(theme):
    folder, name, blurb = THEMES[theme]
    return top(theme, f"Sign in, {name} look", "") + f'''<main class="signin">
  <div class="signin-card">
    <a class="brand big" href="#"><img src="static/mark.svg" alt="" width="42" height="30"><span>Team Scheduler</span></a>
    <h1>Sign in</h1>
    <p class="lede">Schedules, breaks and the live day, in one place.</p>
    <form action="#" method="post" onsubmit="return false">
      <label>Username<input type="text" name="u" autocomplete="username" value="sara"></label>
      <label>Password<input type="password" name="p" autocomplete="current-password" value="password"></label>
      <button type="button" class="wide">Sign in</button>
    </form>
    <p class="fine">Forgot your password? Ask your admin to reset it.</p>
  </div>
</main>
</body></html>
'''.replace(' onsubmit="return false"', "")


CSS = r'''/* © 2026 Omar Mokhtar. All rights reserved. */
@font-face { font-family: "Archivo"; src: url("static/archivo.woff2") format("woff2"); font-weight: 400 800; font-stretch: 62% 125%; font-display: swap; }
@font-face { font-family: "Atkinson"; src: url("static/atkinson-hyperlegible-next.woff2") format("woff2"); font-weight: 200 800; font-display: swap; }
* { box-sizing: border-box; }
:root { --lab: 9rem; --radius: 14px; --radius-s: 8px; --font: "Atkinson", system-ui, sans-serif; --head: "Archivo", system-ui, sans-serif;
  --covered: #19B7A6; --short: #F0A52A; --gap: #E5534B; --over: #8A7BF0;
  --p: #2358C7; --c: #C2549F; --e: #2F7D5B; --brk: #8C97A8; --lunch: #A9A3C9; }
html { color-scheme: light; }
body { margin: 0; font: 1rem/1.5 var(--font); font-variant-numeric: tabular-nums; color: var(--ink); background: var(--bg); min-height: 100vh; position: relative; }
.sr { position: absolute; width: 1px; height: 1px; overflow: hidden; clip: rect(0 0 0 0); white-space: nowrap; }
.backdrop { position: fixed; inset: 0; z-index: 0; pointer-events: none; }
.shell, .signin { position: relative; z-index: 1; }
a { color: var(--accent); }
:focus-visible { outline: 3px solid var(--focus); outline-offset: 2px; }

/* top bar */
.shell { max-width: 78rem; margin: 0 auto; padding: 0 1.25rem 6rem; }
.top { display: flex; align-items: center; gap: 1.25rem; padding: 1rem 0; flex-wrap: wrap; }
.brand { display: inline-flex; align-items: center; gap: .6rem; font: 700 1.1rem/1 var(--head); color: var(--ink); text-decoration: none; letter-spacing: .01em; }
.brand.big { font-size: 1.4rem; margin-bottom: 1.4rem; }
.top nav { display: flex; gap: .25rem; flex: 1; flex-wrap: wrap; }
.top nav a { padding: .45rem .85rem; border-radius: 999px; color: var(--dim); text-decoration: none; font-weight: 600; }
.top nav a:hover { color: var(--ink); background: var(--chip); }
.top nav a.on { color: var(--on-accent); background: var(--accent); }
.who-chip { display: inline-flex; align-items: center; gap: .5rem; padding: .35rem .8rem; border-radius: 999px; background: var(--chip); font-weight: 600; }

/* hero */
.hero { padding: 1.4rem 0 1.1rem; }
.when { margin: 0; color: var(--dim); }
.hero h1 { text-wrap: balance; margin: .15rem 0 .8rem; font: 800 clamp(2rem, 5vw, 3.1rem)/1.05 var(--head); font-stretch: 88%; letter-spacing: -.01em; }
.pulse { display: flex; flex-wrap: wrap; gap: .6rem; list-style: none; margin: 0; padding: 0; }
.pulse li { padding: .45rem .9rem; border-radius: 999px; background: var(--chip); }
.pulse b { font: 800 1.15rem var(--head); margin-right: .25rem; }
.pulse .warn { background: var(--warn-bg); color: var(--warn-ink); }

/* cards */
.card { margin-top: 1rem; padding: 1.1rem 1.25rem 1.25rem; border-radius: var(--radius); background: var(--panel); border: 1px solid var(--edge); box-shadow: var(--shadow); }
.card-head { display: flex; justify-content: space-between; align-items: baseline; gap: 1rem; flex-wrap: wrap; margin-bottom: .8rem; }
.card h2 { margin: 0; font: 700 1.15rem var(--head); }
.hint { margin: 0; color: var(--dim); }
.legend { display: flex; flex-wrap: wrap; gap: .3rem 1rem; list-style: none; margin: 0; padding: 0; color: var(--dim); font-size: .9rem; }
.legend i { display: inline-block; width: .8rem; height: .8rem; border-radius: 3px; margin-right: .35rem; vertical-align: -.1rem; }
.legend.small { margin-top: .7rem; }

/* timeline */
.scale { display: grid; grid-template-columns: var(--lab) repeat(52, 1fr); color: var(--dim); font: 600 .78rem var(--head); padding: .1rem 0 .3rem; }
.scale span { grid-column: span 4; }
.scale span:first-child { grid-column: 2 / span 4; }
.lanes { position: relative; padding-bottom: 1.9rem; }
.lane { display: grid; grid-template-columns: var(--lab) 1fr; align-items: center; border-top: 1px solid var(--edge-soft); min-height: 2.9rem; }
.who { display: flex; flex-direction: column; line-height: 1.2; padding: .3rem 0; }
.who small { color: var(--dim); }
.track { display: grid; grid-template-columns: repeat(52, 1fr); height: 1.7rem; align-items: stretch; background-image: linear-gradient(to right, var(--edge-soft) 1px, transparent 1px); background-size: calc(100% / 13) 100%; }
.seg { display: grid; place-items: center; font: 800 .8rem var(--head); color: #fff; border-radius: 6px; margin: 0 1px; }
.k-P { background: var(--p); } .k-C { background: var(--c); } .k-E { background: var(--e); }
.k-B { background: var(--brk); } .k-L { background: var(--lunch); }
.now-line { position: absolute; top: 0; bottom: 0; width: 2px; background: var(--now); pointer-events: none; }
.now-line em { position: absolute; bottom: -.1rem; left: 50%; translate: -50% 0; padding: .1rem .5rem; border-radius: 999px; font: 700 .72rem var(--head); font-style: normal; background: var(--now); color: var(--on-now); white-space: nowrap; }

/* coverage */
.heat { display: grid; grid-template-columns: repeat(13, 1fr); gap: 4px; }
.cell { height: 2.2rem; border-radius: 6px; }
.h-c, .cell.h-c { background: var(--covered); } .h-s { background: var(--short); } .h-g { background: var(--gap); } .h-o { background: var(--over); }

/* requests */
.asks { list-style: none; margin: 0; padding: 0; }
.asks li { display: flex; justify-content: space-between; align-items: center; gap: 1rem; flex-wrap: wrap; padding: .75rem 0; border-top: 1px solid var(--edge-soft); }
.asks li:first-child { border-top: 0; }
.asks small { display: block; color: var(--dim); }
button { font: 700 .95rem var(--font); padding: .5rem 1rem; border-radius: 10px; border: 1px solid transparent; background: var(--accent); color: var(--on-accent); cursor: pointer; }
button { transition: transform .12s cubic-bezier(.23, 1, .32, 1), filter .12s; }
button:hover { filter: brightness(1.08); }
button:active, .float-note .refresh:active { transform: scale(.97); }
button.ghost { background: transparent; color: var(--ink); border-color: var(--edge-strong); }
.btns { display: inline-flex; gap: .5rem; }

/* the floating note: out of date page */
.float-note { position: fixed; z-index: 20; left: 0; right: 0; margin-inline: auto; width: max-content; bottom: 1.1rem; display: flex; align-items: center; gap: .8rem; max-width: min(46rem, calc(100vw - 1.5rem)); padding: .65rem .8rem .65rem 1rem; border-radius: 999px; background: var(--note-bg); color: var(--note-ink); border: 1px solid var(--note-edge); box-shadow: var(--note-shadow); backdrop-filter: blur(14px) saturate(1.4); -webkit-backdrop-filter: blur(14px) saturate(1.4); }
.float-note[hidden] { display: none; }
.float-note.show { animation: rise .28s cubic-bezier(.23, 1, .32, 1) both; }
.float-note .pip { flex: none; width: .7rem; height: .7rem; border-radius: 50%; background: var(--short); box-shadow: 0 0 0 0 var(--short); }
.float-note.show .pip { animation: ping 1.6s ease-out 3; }
.float-note .refresh { flex: none; padding: .4rem .9rem; border-radius: 999px; background: var(--accent); color: var(--on-accent); font-weight: 700; text-decoration: none; }
.float-note .x { flex: none; background: transparent; color: var(--note-ink); border: 0; padding: .4rem .5rem; font-weight: 600; opacity: .75; }
@keyframes rise { from { opacity: 0; transform: translateY(.75rem) scale(.97); } to { opacity: 1; transform: none; } }
@keyframes ping { 0% { box-shadow: 0 0 0 0 color-mix(in srgb, var(--short) 60%, transparent); } 80%, 100% { box-shadow: 0 0 0 .7rem transparent; } }

/* sign in */
.signin { min-height: 100vh; display: grid; place-items: center; padding: 1.5rem; }
.signin-card { width: min(26rem, 100%); padding: 2rem 2rem 1.6rem; border-radius: 20px; background: var(--panel); border: 1px solid var(--edge); box-shadow: var(--shadow-big); }
.signin h1 { margin: 0; font: 800 2.1rem/1.1 var(--head); font-stretch: 88%; }
.lede { margin: .35rem 0 1.4rem; color: var(--dim); }
label { display: block; font-weight: 600; margin-bottom: .9rem; }
input { display: block; width: 100%; margin-top: .3rem; padding: .65rem .8rem; border-radius: 10px; border: 1px solid var(--edge-strong); background: var(--field); color: var(--ink); font: 1rem var(--font); }
.wide { width: 100%; padding: .75rem 1rem; font-size: 1.05rem; margin-top: .3rem; }
.fine { margin: 1.1rem 0 0; color: var(--dim); font-size: .92rem; }

@media (max-width: 40rem) {
  :root { --lab: 5.4rem; }
  .scale span:nth-child(even) { visibility: hidden; }
  .who small { display: none; }
  .float-note { left: .6rem; right: .6rem; width: auto; margin-inline: 0; bottom: .6rem; border-radius: 18px; flex-wrap: wrap; font-size: .92rem; }
  .float-note > span { flex: 1 1 12rem; }
  .float-note .x { display: none; }
}
@media (prefers-reduced-motion: reduce) { * { animation: none !important; transition: none !important; } }
'''

LOOKS = r'''
/* ---------- A. Tide: light, a cool sea-glass wash behind plain panels ---------- */
.look-a { --bg: #E8EFF6; --ink: #12233A; --dim: #46556F; --accent: #12233A; --on-accent: #FFFFFF; --focus: #12233A;
  --chip: #FFFFFFB3; --panel: #FFFFFFE6; --edge: #FFFFFF; --edge-soft: #12233A1F; --edge-strong: #5B6B88; --field: #FFFFFF;
  --shadow: 0 1px 2px #12233A14, 0 12px 28px -16px #12233A40; --shadow-big: 0 2px 4px #12233A14, 0 28px 60px -28px #12233A59;
  --warn-bg: #FFE9C2; --warn-ink: #6B4200; --now: #12233A; --on-now: #fff;
  --note-bg: #FFFFFFD9; --note-ink: #12233A; --note-edge: #FFFFFF; --note-shadow: 0 2px 4px #12233A1A, 0 16px 40px -12px #12233A66; }
.look-a .backdrop { background: radial-gradient(54rem 34rem at 6% -10%, #C4DDF3 0%, transparent 62%), radial-gradient(46rem 32rem at 100% 0%, #C6EEDF 0%, transparent 60%), radial-gradient(40rem 30rem at 55% 108%, #DCE8F4 0%, transparent 62%), #E8EFF6; }
.look-a .backdrop::after { content: ""; position: absolute; inset: -20%; background: radial-gradient(30rem 22rem at 30% 40%, #9CC6EC33, transparent 65%), radial-gradient(26rem 20rem at 75% 60%, #8FDCC133, transparent 65%); animation: drift 60s ease-in-out infinite alternate; }
@keyframes drift { to { transform: translate3d(5%, -3%, 0) scale(1.06); } }

/* ---------- B. Night watch: dark deep blue, a dot grid that fades out ---------- */
.look-b { --bg: #080F1E; --ink: #E7EEFB; --dim: #9DB0CF; --accent: #E7EEFB; --on-accent: #0A1426; --focus: #E7EEFB;
  --chip: #FFFFFF14; --panel: #0F1A31E6; --edge: #7FA2E233; --edge-soft: #7FA2E21F; --edge-strong: #6C87B8; --field: #0A1426;
  --shadow: 0 1px 2px #0008, 0 18px 40px -24px #000; --shadow-big: 0 2px 4px #0008, 0 36px 80px -30px #000;
  --warn-bg: #4A3510; --warn-ink: #FFD791; --now: #E7EEFB; --on-now: #0A1426;
  --note-bg: #12203DE6; --note-ink: #E7EEFB; --note-edge: #7FA2E255; --note-shadow: 0 2px 4px #0009, 0 16px 48px -10px #000;
  --p: #4C86FF; --c: #E070BE; --e: #3FAE81; --brk: #6E7B92; --lunch: #8D86BD; }
.look-b { color-scheme: dark; }
.look-b .backdrop { background: radial-gradient(60rem 38rem at 12% -10%, #17285C 0%, transparent 62%), radial-gradient(50rem 36rem at 100% 10%, #0C3547 0%, transparent 60%), #080F1E; }
.look-b .backdrop::before { content: ""; position: absolute; inset: 0; background-image: radial-gradient(#9DB7EE2B 1px, transparent 1.2px); background-size: 26px 26px; -webkit-mask-image: radial-gradient(70% 60% at 50% 18%, #000 0%, transparent 78%); mask-image: radial-gradient(70% 60% at 50% 18%, #000 0%, transparent 78%); }
.look-b .seg { color: #06142B; }

/* ---------- C. Paper: light, flat and quick, a dot grid and ink ---------- */
.look-c { --bg: #F5F7FA; --ink: #101828; --dim: #475467; --accent: #101828; --on-accent: #fff; --focus: #101828;
  --chip: #E8ECF3; --panel: #FFFFFF; --edge: #D6DCE6; --edge-soft: #E3E7EE; --edge-strong: #667085; --field: #fff;
  --shadow: 0 1px 0 #D6DCE6; --shadow-big: 0 24px 60px -34px #10182866;
  --warn-bg: #FDEBC8; --warn-ink: #6B4200; --now: #101828; --on-now: #fff;
  --note-bg: #101828; --note-ink: #fff; --note-edge: #101828; --note-shadow: 0 2px 4px #10182833, 0 16px 40px -14px #10182899; }
.look-c .backdrop { background-color: #F5F7FA; background-image: radial-gradient(#C3CBD9 1px, transparent 1.2px); background-size: 22px 22px; -webkit-mask-image: linear-gradient(#000 60%, #0000 100%); mask-image: linear-gradient(#000 60%, #0000 100%); }
.look-c .card { border-radius: 10px; }
.look-c .float-note .refresh { background: #fff; color: #101828; }
.look-c .float-note .pip { background: #FFB53D; }
'''

JS = '''// © 2026 Omar Mokhtar. All rights reserved.
(function () {
  "use strict";
  var note = document.getElementById("note");
  if (!note) { return; }
  var hide = note.querySelector(".x");
  function show() { note.hidden = false; note.classList.add("show"); }
  window.setTimeout(show, 600);
  if (hide) { hide.addEventListener("click", function () { note.hidden = true; }); }
})();
'''


def main():
    (HERE / "sample.css").write_text(CSS + LOOKS, encoding="utf-8")
    (HERE / "bars.css").write_text("/* © 2026 Omar Mokhtar. All rights reserved. */\n" + bars_css(), encoding="utf-8")
    (HERE / "sample.js").write_text(JS, encoding="utf-8")
    for t, (folder, _, _) in THEMES.items():
        (HERE / f"{t}_{folder}_day.html").write_text(day_page(t), encoding="utf-8")
        (HERE / f"{t}_{folder}_signin.html").write_text(login_page(t), encoding="utf-8")
    print("built", sorted(p.name for p in HERE.glob("*.html")))


if __name__ == "__main__":
    main()
