# © 2026 Omar Mokhtar. All rights reserved.
"""Round 3 prototype of the three looks (Phase AZ): one interactive page, made-up "Associate NN" names, no inline script or style.
    python3 build_proto.py  ->  index.html, proto.css, proto.js, bars.css"""
import sys
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parent / "samples"))
from build import ROWS, bars_css, cls  # noqa: E402  (the same made-up day as the samples)

COVER = ["c", "c", "c", "s", "c", "c", "s", "g", "s", "c", "c", "o", "c"]
WORD = {"c": "covered", "s": "short", "g": "gap", "o": "over"}
HOURS = list(range(8, 21))


def lane(who, lang, segs, extra=""):
    cells = []
    for a, b, k in segs:
        label = {"P": "Phone", "C": "Chat", "E": "Email", "B": "Break", "L": "Lunch"}[k]
        letter = k if k in "PCE" and b - a >= 1 else ""
        t0, t1 = f"{int(a):02d}:{int(a % 1 * 60):02d}", f"{int(b):02d}:{int(b % 1 * 60):02d}"
        cells.append(f'<span class="seg k-{k} {cls(a, b, k)}" title="{label}, {t0} to {t1}">{letter}'
                     f'<span class="sr">{label}, {t0} to {t1}</span></span>')
    return (f'<div class="lane{extra}" data-who="{who}"><div class="who"><b>{who}</b><small>{lang}</small></div>'
            f'<div class="track">{"".join(cells)}</div></div>')


def asks():
    items = [("Associate 03", "Swap Thursday 16 October with Associate 06", "swap"),
             ("Associate 05", "Day off on Sunday 18 October", "day off"),
             ("Associate 01", "Break moved from 11:00 to 11:30 today", "break")]
    out = []
    for i, (who, what, kind) in enumerate(items):
        out.append(f'<li class="ask" data-id="{i}" data-who="{who}" data-kind="{kind}"><div class="ask-in"><div class="ask-row">'
                   f'<div><b>{who}</b><small>{what}</small></div><span class="btns">'
                   f'<button type="button" class="ghost" data-act="decline">Decline</button>'
                   f'<button type="button" data-act="approve">Approve</button></span></div></div></li>')
    return "".join(out)


NAV = [("day", "Today"), ("home", "Home"), ("week", "Weeks"), ("requests", "Requests"), ("schedules", "Schedules"), ("wallboard", "Wallboard"), ("people", "People")]


def top(active):
    links = "".join(f'<a href="#main" data-view-pick="{k}"{" aria-current=\"page\" class=\"on\"" if k == active else ""}>{t}</a>' for k, t in NAV)
    return (f'<header class="top"><a class="brand" href="#main"><img src="static/mark.svg" alt="" width="28" height="20"><span>Team Scheduler</span></a>'
            f'<nav aria-label="Main">{links}<a href="#main">Insights</a></nav>'
            f'<button type="button" class="ghost cmdk" aria-label="Go to, Control K">Go to <kbd>Ctrl K</kbd></button><span class="who-chip">Sara</span></header>')


def view_home():
    mini = "".join(f'<i class="h-{c}"></i>' for c in "ccccsccgscccoccsccccccco")
    runs = [("week_next.xlsx", "Sun 25 Oct, 03:29", "Approved", "100%", ""), ("week_last.xlsx", "Sun 25 Oct, 03:29", "Approved", "100%", ""),
            ("week_v2.xlsx", "Sun 25 Oct, 03:29", "Approved", "100%", "Not in use"), ("week.xlsx", "Sun 25 Oct, 03:29", "Approved", "100%", "In use")]
    rows = "".join(f'<li class="run"><div><b>{n}</b>{f"<span class=chip>{t}</span>" if t else ""}<small>{d} · {st}</small></div>'
                   f'<span class="bar5" aria-hidden="true"><i></i><i></i><i></i><i></i><i class="go"></i></span><b class="pct">{p}</b></li>'
                   for n, d, st, p, t in runs)
    return f'''<div id="view-home" class="view" hidden><div class="shell">{top("home")}<main tabindex="-1">
<section class="hero"><p class="when">Wednesday 14 October</p><h1>Good afternoon, Sara</h1>
<p class="lede">SAKS, NMG Tier 2 · next schedule starts Sunday 1 November</p></section>
<div class="grid3">
 <article class="card stat"><h2>Right now</h2><p class="big">38 <span>on the floor</span></p><p class="hint">2 short on Phone until 16:00</p><a class="more" href="#main" data-view-pick="day">Open the real-time view</a></article>
 <article class="card stat"><h2>Waiting for you</h2><p class="big">3 <span>requests</span></p><p class="hint">1 leave, 1 holiday, 1 swap</p><a class="more" href="#main" data-view-pick="requests">Review requests</a></article>
 <article class="card stat"><h2>Latest schedule</h2><p class="big">100% <span>covered</span></p><p class="hint">0 below the floor, 5 to review</p><a class="more" href="#main" data-view-pick="schedules">Compare schedules</a></article>
</div>
<section class="card"><div class="card-head"><h2>Coverage this week</h2><p class="hint">Only gaps and shortfalls are coloured; calm hours stay quiet</p></div><div class="mini">{mini}</div></section>
<section class="card"><div class="card-head"><h2>Runs</h2><button type="button">New schedule</button></div><ul class="runs">{rows}</ul><p class="hint">Results are kept for 30 days, then their files are deleted. Times are Egypt time.</p></section>
</main></div></div>'''


def view_requests():
    items = [("Associate 03", "Planned leave", "Mon 26 Oct to Tue 27 Oct", "Waiting for a team manager", "Short by 0.8 from 12:00 to 14:00 and 0.5 from 15:00 to 16:00", "“Family visit”"),
             ("Associate 04", "Public holiday", "Mon 26 Oct", "Approved by Team Manager, waiting for the RTA", "Short by 0.2 from 21:00 to 22:00", "")]
    cards = "".join(f'''<li class="req"><div class="req-main"><div class="req-top"><b>{w}</b><span class="chip warn">{st}</span></div>
<p class="req-what"><strong>{k}</strong>, {d}</p>{f'<p class="quote">{q}</p>' if q else ''}<p class="impact"><i class="pip"></i>{im}</p></div>
<div class="req-act"><label>Reason, if you decline<input type="text" placeholder="Optional"></label><span class="btns"><button type="button" class="ghost">Decline</button><button type="button">Approve</button></span></div></li>'''
                    for w, k, d, st, im, q in items)
    return f'''<div id="view-requests" class="view" hidden><div class="shell">{top("requests")}<main tabindex="-1">
<section class="hero"><h1>Leave and swaps</h1><p class="lede">SAKS, NMG Tier 2. A team manager approves first, then the RTA; the RTA’s approval changes the schedule in use.</p>
<nav class="tabs" aria-label="Requests"><a href="#main" class="on" aria-current="page">Waiting <span class="count">3</span></a><a href="#main">Decided</a><a href="#main">Break changes</a><a href="#main">Coaching</a></nav></section>
<section class="card"><div class="card-head"><h2>Leave</h2><p class="hint">Each card shows what the day looks like if you approve</p></div><ul class="reqs">{cards}</ul></section>
<section class="card"><div class="card-head"><h2>Swaps</h2></div><p class="empty">No swap is waiting. Offers from associates show here.</p></section>
</main></div></div>'''


def view_schedules():
    return f'''<div id="view-schedules" class="view" hidden><div class="shell">{top("schedules")}<main tabindex="-1">
<section class="hero"><h1>Schedules</h1><p class="lede">SAKS, NMG Tier 2. Pick a week to see every schedule for it, side by side.</p>
<nav class="tabs weekpick" aria-label="Weeks"><a href="#main">Week of 18 Oct <small>1 schedule</small></a><a href="#main" class="on" aria-current="page">Week of 25 Oct <small>2 schedules, this week</small></a><a href="#main">Week of 1 Nov <small>1 schedule</small></a></nav></section>
<section class="card"><div class="card-head"><h2>Week of 25 Oct</h2><label class="inline">Times in<select><option>Cairo (Egypt)</option><option>UTC</option></select></label></div>
<div class="compare"><div class="col head"></div>
<div class="col"><h3>week.xlsx</h3><p class="hint">Breaks planned automatically (version 2)</p><span class="chip on">In use</span></div>
<div class="col"><h3>week_v2.xlsx</h3><p class="hint">Ready schedule, uploaded</p><span class="chip">Not in use</span></div>
<div class="row-l">Hours at 100%</div><div>168 of 168</div><div>168 of 168 <small>before breaks</small></div>
<div class="row-l">Overtime needed</div><div>0 h</div><div>0 h</div>
<div class="row-l">Extra hours available</div><div>253 h</div><div>433 h <small>before breaks</small></div>
<div class="row-l">Breaks planned</div><div>Yes</div><div>Not yet</div>
<div class="row-l"></div><div class="btns"><button type="button" class="ghost">Open</button><button type="button" class="ghost">Week view</button></div><div class="btns"><button type="button" class="ghost">Open</button><button type="button">Set in use</button><button type="button" class="ghost danger">Delete…</button></div></div>
<p class="hint">Figures are compared only when every schedule has its breaks planned: a schedule without breaks always looks better than it will be.</p></section>
</main></div></div>'''


def view_wallboard():
    tiles = [("Now", "06:00 to 07:00", "+1:45", "Good buffer", "6.8 on the floor, need 5"), ("", "07:00 to 08:00", "+1:15", "Covered", "6.2 on the floor, need 5"),
             ("", "08:00 to 09:00", "+2:15", "Good buffer", "7.2 on the floor, need 5"), ("", "09:00 to 10:00", "+2:30", "Good buffer", "8.5 on the floor, need 6")]
    t = "".join(f'<article class="wtile{" now" if a else ""}"><p>{a or "&nbsp;"} <span>{b}</span></p><p class="wbig">{c}</p><span class="chip ok">{d}</span><p class="hint">{e}</p></article>' for a, b, c, d, e in tiles)
    return f'''<div id="view-wallboard" class="view wall" hidden><div class="shell wide"><header class="wtop"><a href="#main" data-view-pick="day">Back to the RTA</a><h1>SAKS, NMG Tier 2</h1><p class="clock"><span>Sun 25 Oct</span> 06:31</p></header>
<main tabindex="-1"><div class="wtiles">{t}</div><div class="grid3"><section class="card"><h2>On break now</h2><p>Associate 34 · Break 1 until 06:45</p></section><section class="card"><h2>Next 30 minutes</h2><p>07:00 Associate 22 · Break 2</p><p>07:00 Associate 39 · Break 1</p></section><section class="card"><h2>Languages now</h2><p>English 6</p></section></div></main></div></div>'''


def extra_rows():
    days = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]
    rows = []
    for d in range(7):
        for h in range(24):
            need = 3 + (h * 7 + d * 3) % 9
            have = need + (h + d) % 4
            rows.append((days[d], f"{h:02d}:00", need, have, 100 + (have - need) * 100 // need, (have - need)))
    return rows


def view_week():
    body = "".join(f'<tr class="prow" data-day="{d}"><td>{d}</td><td>{t}</td><td>{n}</td><td>{h}</td><td>{p}%</td><td>{x}</td></tr>' for d, t, n, h, p, x in extra_rows())
    chips = "".join(f'<button type="button" class="chipbtn{" on" if i == 0 else ""}" data-day-pick="{d}" aria-pressed="{"true" if i == 0 else "false"}">{d}</button>'
                    for i, d in enumerate(["All days", "Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]))
    return f'''<div id="view-week" class="view" hidden><div class="shell">{top("week")}<main tabindex="-1">
<section class="hero"><p class="when">Week of 25 October</p><h1>This week looks well covered</h1><p class="lede">Every hour reaches the 100% target, and no overtime is needed. A few spare hours are listed below if you need to move people.</p>
<nav class="tabs" aria-label="Week"><a href="#main" class="on" aria-current="page">Summary</a><a href="#main">Heat map</a><a href="#main">Overtime</a><a href="#main">Extra hours</a></nav></section>
<div class="grid3"><article class="card stat"><h2>Hours at 100%</h2><p class="big">165 <span>of 165</span></p></article><article class="card stat"><h2>Overtime needed</h2><p class="big">0 <span>hours</span></p></article><article class="card stat"><h2>Spare hours</h2><p class="big">252 <span>hours</span></p></article></div>
<section class="card" id="extra" data-pager data-size="10"><div class="card-head"><h2>Spare hours, by hour</h2><p class="hint" data-pager-label>1 to 10 of 168</p></div>
<div class="chips" role="group" aria-label="Day">{chips}</div>
<div class="tablewrap"><table class="grid"><thead><tr><th>Day</th><th>Hour</th><th>Needed</th><th>On shift</th><th>Covered</th><th>Spare</th></tr></thead><tbody>{body}</tbody></table></div>
<p class="empty" data-pager-empty hidden>No hours match. Pick another day.</p>
<div class="pager"><button type="button" class="ghost" data-pager-prev>Previous</button><span class="hint" data-pager-page>Page 1 of 17</span><button type="button" class="ghost" data-pager-next>Next</button></div></section>
</main></div></div>'''


def view_people():
    roles = ["Associate", "Planner", "Team manager", "Associate", "Associate"]
    rows = "".join(f'<li class="person prow" data-text="associate {n:02d} {roles[n % 5].lower()}"><div class="avatar" aria-hidden="true">{n:02d}</div><div><b>Associate {n:02d}</b><small>{roles[n % 5]}, SAKS NMG Tier 2</small></div>'
                   f'<label class="switch"><input type="checkbox" {"checked" if n % 7 else ""}><span>{"On" if n % 7 else "Off"}</span></label><button type="button" class="ghost">Edit</button></li>' for n in range(1, 41))
    return f'''<div id="view-people" class="view" hidden><div class="shell">{top("people")}<main tabindex="-1">
<section class="hero"><h1>People</h1><p class="lede">Add people, switch accounts on or off, and change roles. A person switched off cannot sign in; their history stays.</p></section>
<section class="card" data-pager data-size="8"><div class="card-head"><h2>Everyone</h2><span class="btns"><button type="button" class="ghost">Add from a file</button><button type="button">Add a person</button></span></div>
<div class="toolrow"><label class="search">Find a person<input type="search" data-pager-search placeholder="Type a name or a role"></label><p class="hint" data-pager-label>1 to 8 of 40</p></div>
<ul class="people">{rows}</ul>
<p class="empty" data-pager-empty hidden>Nobody matches that. Check the spelling or clear the search.</p>
<div class="pager"><button type="button" class="ghost" data-pager-prev>Previous</button><span class="hint" data-pager-page>Page 1 of 5</span><button type="button" class="ghost" data-pager-next>Next</button></div></section>
</main></div></div>'''


def page():
    hours = "".join(f"<span>{h:02d}</span>" for h in HOURS)
    many = [(f"Associate {n + 1:02d}", ROWS[n % len(ROWS)][1], ROWS[(n * 5 + 1) % len(ROWS)][2]) for n in range(24)]
    lanes = "".join(lane(*r) for r in many)
    heat = "".join(f'<button type="button" class="cell h-{c}" aria-label="{h:02d}:00, {WORD[c]}" title="{h:02d}:00, {WORD[c]}"></button>'
                   for h, c in zip(HOURS, COVER))
    return f'''<!doctype html>
<html lang="en">
<head>
<!-- © 2026 Omar Mokhtar. All rights reserved. -->
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Team Scheduler looks</title>
<link rel="stylesheet" href="proto.css">
<link rel="stylesheet" href="bars.css">
</head>
<body data-look="a" data-view="day">
<a class="skip" href="#main">Skip to content</a>
<div class="backdrop" aria-hidden="true"></div>

<div class="protobar" role="region" aria-label="Prototype controls">
  <div class="group" role="group" aria-label="Look">
    <button type="button" data-look-pick="a" aria-pressed="true">A Tide</button>
    <button type="button" data-look-pick="b" aria-pressed="false">B Night watch</button>
    <button type="button" data-look-pick="c" aria-pressed="false">C Paper</button>
  </div>
  <div class="group" role="group" aria-label="Page">
    <button type="button" data-view-pick="day" aria-pressed="true">Real-time view</button>
    <button type="button" data-view-pick="home" aria-pressed="false">Home</button>
    <button type="button" data-view-pick="week" aria-pressed="false">Weeks</button>
    <button type="button" data-view-pick="requests" aria-pressed="false">Requests</button>
    <button type="button" data-view-pick="schedules" aria-pressed="false">Schedules</button>
    <button type="button" data-view-pick="wallboard" aria-pressed="false">Wallboard</button>
    <button type="button" data-view-pick="people" aria-pressed="false">People</button>
    <button type="button" data-view-pick="signin" aria-pressed="false">Sign in</button>
  </div>
  <button type="button" class="try" data-try="stale">Someone changes a break</button>
</div>

<div id="view-day" class="view">
  <div class="shell">
    {top("day")}
    <main id="main" tabindex="-1">
      <section class="hero" aria-labelledby="h1">
        <p class="when">Wednesday 14 October, 14:36 Egypt time</p>
        <h1 id="h1">SAKS, NMG Tier 2</h1>
        <nav class="tabs" aria-label="Today"><a href="#main" aria-current="page" class="on">Real-time view</a><a href="#main">Overview</a><a href="#main">Wallboard</a></nav>
        <ul class="pulse" aria-label="Right now">
          <li><b>38</b> on the floor</li><li><b>4</b> on a break</li>
          <li class="warn"><b>2</b> short on Phone until 16:00</li><li><b>1</b> late login</li>
        </ul>
      </section>
      <section class="card timeline" aria-labelledby="t1">
        <div class="card-head"><h2 id="t1">Who is on what</h2>
          <ul class="legend"><li><i class="k-P"></i>Phone</li><li><i class="k-C"></i>Chat</li><li><i class="k-E"></i>Email</li><li><i class="k-B"></i>Break</li><li><i class="k-L"></i>Lunch</li></ul></div>
        <div class="toolrow"><label class="search">Find a person<input type="search" id="lane-find" placeholder="Type a name"></label>
          <p class="hint" id="lane-count">24 people</p><button type="button" class="ghost" id="jump-now">Jump to now</button></div>
        <div class="lanes scroll" id="lane-scroll" tabindex="0" role="region" aria-label="Who is on what, scrolls"><div class="scale sticky" aria-hidden="true">{hours}</div>{lanes}<span class="now-line" aria-hidden="true"><em>Now 14:36</em></span></div>
      </section>
      <section class="card" aria-labelledby="t2">
        <div class="card-head"><h2 id="t2">Coverage by hour</h2><p class="hint">Against the need for the day</p></div>
        <div class="heat">{heat}</div>
        <ul class="legend small"><li><i class="h-c"></i>Covered</li><li><i class="h-s"></i>Short</li><li><i class="h-g"></i>Gap</li><li><i class="h-o"></i>Over</li></ul>
      </section>
      <section class="card" aria-labelledby="t3">
        <div class="card-head"><h2 id="t3">Waiting for you</h2><p class="hint" id="askcount">3 requests</p></div>
        <ul class="asks" id="asks">{asks()}</ul>
        <p class="empty" id="empty" hidden>All caught up. New requests will show up here.</p>
      </section>
    </main>
  </div>
</div>

{view_home()}{view_week()}{view_people()}{view_requests()}{view_schedules()}{view_wallboard()}
<div id="view-signin" class="view" hidden>
  <main class="signin" id="signin-main">
    <div class="signin-card">
      <a class="brand big" href="#signin-main"><img src="static/mark.svg" alt="" width="42" height="30"><span>Team Scheduler</span></a>
      <h1>Sign in</h1>
      <p class="lede">Schedules, breaks and the live day, in one place.</p>
      <form id="form" novalidate>
        <label for="u">Username<input id="u" type="text" name="u" autocomplete="username" value="sara"></label>
        <label for="p">Password<input id="p" type="password" name="p" autocomplete="current-password" aria-describedby="perr"></label>
        <p class="field-error" id="perr" role="alert" hidden>Type your password to sign in.</p>
        <button type="submit" class="wide">Sign in</button>
      </form>
      <p class="fine">Forgot your password? Ask your admin to reset it.</p>
    </div>
  </main>
</div>

<div class="float-note" id="note" role="status" aria-live="polite">
  <i class="pip" aria-hidden="true"></i>
  <span class="msg" id="note-msg"></span>
  <button type="button" class="act" id="note-act">Refresh</button>
  <button type="button" class="x" id="note-x" aria-label="Hide this message">Hide</button>
</div>
<script src="proto.js"></script>
</body></html>
'''


CSS = r'''/* © 2026 Omar Mokhtar. All rights reserved. */
/* ===== fonts ===== */
@font-face { font-family: "Archivo"; src: url("static/archivo.woff2") format("woff2"); font-weight: 400 800; font-stretch: 62% 125%; font-display: swap; }
@font-face { font-family: "Atkinson"; src: url("static/atkinson-hyperlegible-next.woff2") format("woff2"); font-weight: 200 800; font-display: swap; }

/* ===== tokens: primitives (state and channel colours mean the same in every look) ===== */
:root {
  --covered: #19B7A6; --short: #F0A52A; --gap: #E5534B; --over: #8A7BF0;
  --channel-phone: #2358C7; --channel-chat: #C2549F; --channel-email: #2F7D5B; --channel-break: #8C97A8; --channel-lunch: #A9A3C9;
  --font-body: "Atkinson", system-ui, sans-serif; --font-head: "Archivo", system-ui, sans-serif;
  --text-sm: .875rem; --text-md: 1rem; --text-lg: 1.15rem; --text-xl: 1.5rem; --text-2xl: clamp(2rem, 5vw, 3.1rem);
  --space-1: .25rem; --space-2: .5rem; --space-3: .75rem; --space-4: 1rem; --space-5: 1.5rem; --space-6: 2.5rem;
  --label-w: 9rem;
  /* motion: strong curves, short times (Emil Kowalski's table); the RTA is used all day, so little moves */
  --ease-out: cubic-bezier(.23, 1, .32, 1); --ease-in-out: cubic-bezier(.77, 0, .175, 1);
  --t-press: 120ms; --t-hover: 140ms; --t-note-in: 220ms; --t-note-out: 160ms; --t-row: 220ms; --t-look: 200ms;
}

/* ===== tokens: semantic, per look (named for the role, not the colour) ===== */
body[data-look="a"] {
  --bg: #E8EFF6; --text: #12233A; --text-dim: #46556F; --action: #12233A; --on-action: #FFFFFF; --focus: #12233A;
  --chip: #FFFFFFB3; --surface: #FFFFFFE6; --edge: #FFFFFF; --rule: #12233A1F; --edge-strong: #5B6B88; --field: #FFFFFF;
  --lift: 0 1px 2px #12233A14, 0 12px 28px -16px #12233A40; --lift-big: 0 2px 4px #12233A14, 0 28px 60px -28px #12233A59;
  --warn-bg: #FFE9C2; --warn-text: #6B4200; --now: #12233A; --on-now: #FFFFFF; --changed: #12233A14;
  --note-bg: #FFFFFFD9; --note-text: #12233A; --note-edge: #FFFFFF; --note-lift: 0 2px 4px #12233A1A, 0 16px 40px -12px #12233A66; --pip: #F0A52A;
  --radius: 16px; --scheme: light;
}
body[data-look="b"] {
  --bg: #080F1E; --text: #E7EEFB; --text-dim: #9DB0CF; --action: #E7EEFB; --on-action: #0A1426; --focus: #E7EEFB;
  --chip: #FFFFFF14; --surface: #0F1A31E6; --edge: #7FA2E233; --rule: #7FA2E21F; --edge-strong: #6C87B8; --field: #0A1426;
  --lift: 0 1px 2px #0008, 0 18px 40px -24px #000; --lift-big: 0 2px 4px #0008, 0 36px 80px -30px #000;
  --warn-bg: #4A3510; --warn-text: #FFD791; --now: #E7EEFB; --on-now: #0A1426; --changed: #E7EEFB1A;
  --note-bg: #12203DE6; --note-text: #E7EEFB; --note-edge: #7FA2E255; --note-lift: 0 2px 4px #0009, 0 16px 48px -10px #000; --pip: #F0A52A;
  --channel-phone: #4C86FF; --channel-chat: #E070BE; --channel-email: #3FAE81; --channel-break: #6E7B92; --channel-lunch: #8D86BD;
  --radius: 14px; --scheme: dark;
}
body[data-look="c"] {
  --bg: #F5F7FA; --text: #101828; --text-dim: #475467; --action: #101828; --on-action: #FFFFFF; --focus: #101828;
  --chip: #E8ECF3; --surface: #FFFFFF; --edge: #D6DCE6; --rule: #E3E7EE; --edge-strong: #667085; --field: #FFFFFF;
  --lift: none; --lift-big: 0 24px 60px -34px #10182866;
  --warn-bg: #FDEBC8; --warn-text: #6B4200; --now: #101828; --on-now: #FFFFFF; --changed: #10182714;
  --note-bg: #101828; --note-text: #FFFFFF; --note-edge: #101828; --note-lift: 0 2px 4px #10182833, 0 16px 40px -14px #10182899; --pip: #FFB53D;
  --radius: 8px; --scheme: light;
}

/* ===== base ===== */
* { box-sizing: border-box; }
html { color-scheme: light dark; }
body { margin: 0; color-scheme: var(--scheme); font: var(--text-md)/1.5 var(--font-body); font-variant-numeric: tabular-nums; color: var(--text); background: var(--bg); min-height: 100vh; position: relative; -webkit-font-smoothing: antialiased; }
.sr { position: absolute; width: 1px; height: 1px; overflow: hidden; clip: rect(0 0 0 0); white-space: nowrap; }
.skip { position: absolute; left: var(--space-3); top: -4rem; z-index: 60; padding: var(--space-2) var(--space-4); border-radius: 10px; background: var(--action); color: var(--on-action); font-weight: 700; }
.skip:focus { top: var(--space-3); }
.backdrop { position: fixed; inset: 0; z-index: 0; pointer-events: none; }
.view { position: relative; z-index: 1; }
[hidden] { display: none !important; }
a { color: inherit; }
:focus-visible { outline: 3px solid var(--focus); outline-offset: 2px; }
main:focus { outline: none; }
button { font: 700 .95rem var(--font-body); padding: var(--space-2) var(--space-4); border-radius: 10px; border: 1px solid transparent; background: var(--action); color: var(--on-action); cursor: pointer; transition: transform var(--t-press) var(--ease-out), filter var(--t-hover) ease, background-color var(--t-hover) ease; }
button.ghost { background: transparent; color: var(--text); border-color: var(--edge-strong); }
button:active { transform: scale(.97); }
@media (hover: hover) and (pointer: fine) { button:hover { filter: brightness(1.08); } button.ghost:hover { background: var(--chip); filter: none; } }

/* ===== looks: the background ===== */
body[data-look="a"] .backdrop { background: radial-gradient(54rem 34rem at 6% -10%, #C4DDF3 0%, transparent 62%), radial-gradient(46rem 32rem at 100% 0%, #C6EEDF 0%, transparent 60%), radial-gradient(40rem 30rem at 55% 108%, #DCE8F4 0%, transparent 62%), #E8EFF6; }
body[data-look="b"] .backdrop { background: radial-gradient(60rem 38rem at 12% -10%, #17285C 0%, transparent 62%), radial-gradient(50rem 36rem at 100% 10%, #0C3547 0%, transparent 60%), #080F1E; }
body[data-look="b"] .backdrop::before { content: ""; position: absolute; inset: 0; background-image: radial-gradient(#9DB7EE2B 1px, transparent 1.2px); background-size: 26px 26px; -webkit-mask-image: radial-gradient(70% 60% at 50% 18%, #000 0%, transparent 78%); mask-image: radial-gradient(70% 60% at 50% 18%, #000 0%, transparent 78%); }
body[data-look="c"] .backdrop { background-color: #F5F7FA; background-image: radial-gradient(#C3CBD9 1px, transparent 1.2px); background-size: 22px 22px; -webkit-mask-image: linear-gradient(#000 55%, #0000 100%); mask-image: linear-gradient(#000 55%, #0000 100%); }

/* ===== prototype bar (not part of the product) ===== */
.protobar { position: sticky; top: 0; z-index: 40; display: flex; flex-wrap: wrap; gap: var(--space-3); align-items: center; padding: var(--space-2) var(--space-4); background: #0B1220F2; color: #fff; font-size: var(--text-sm); }
.protobar .group { display: inline-flex; gap: 2px; padding: 2px; border-radius: 10px; background: #FFFFFF1F; }
.protobar button { padding: .3rem .7rem; font-size: var(--text-sm); background: transparent; color: #fff; border-radius: 8px; }
.protobar button[aria-pressed="true"] { background: #fff; color: #0B1220; }
.protobar .try { margin-left: auto; background: #fff; color: #0B1220; }
.protobar :focus-visible { outline-color: #fff; }

/* ===== top bar, hero, tabs ===== */
.shell { max-width: 78rem; margin: 0 auto; padding: 0 1.25rem 7rem; }
.top { display: flex; align-items: center; gap: var(--space-5); padding: var(--space-4) 0; flex-wrap: wrap; }
.brand { display: inline-flex; align-items: center; gap: .6rem; font: 700 1.1rem/1 var(--font-head); text-decoration: none; letter-spacing: .01em; }
.brand.big { font-size: 1.4rem; margin-bottom: var(--space-5); }
.top nav { display: flex; gap: var(--space-1); flex: 1; flex-wrap: wrap; }
.top nav a { padding: .45rem .85rem; border-radius: 999px; color: var(--text-dim); text-decoration: none; font-weight: 600; transition: background-color var(--t-hover) ease, color var(--t-hover) ease; }
.top nav a.on { color: var(--on-action); background: var(--action); }
@media (hover: hover) and (pointer: fine) { .top nav a:not(.on):hover { color: var(--text); background: var(--chip); } }
.who-chip { padding: .35rem .8rem; border-radius: 999px; background: var(--chip); font-weight: 600; }
.hero { padding: var(--space-5) 0 var(--space-4); }
.when { margin: 0; color: var(--text-dim); }
.hero h1 { text-wrap: balance; margin: .15rem 0 var(--space-3); font: 800 var(--text-2xl)/1.05 var(--font-head); font-stretch: 88%; letter-spacing: -.01em; }
.tabs { display: flex; gap: var(--space-5); margin: 0 0 var(--space-4); border-bottom: 1px solid var(--rule); }
.tabs a { padding: var(--space-2) 0; margin-bottom: -1px; border-bottom: 2px solid transparent; color: var(--text-dim); text-decoration: none; font-weight: 600; transition: color var(--t-hover) ease; }
.tabs a.on { color: var(--text); border-bottom-color: var(--action); }
@media (hover: hover) and (pointer: fine) { .tabs a:not(.on):hover { color: var(--text); } }
.pulse { display: flex; flex-wrap: wrap; gap: var(--space-3) var(--space-2); list-style: none; margin: 0; padding: 0; }
.pulse li { padding: .45rem .9rem; border-radius: 999px; background: var(--chip); }
.pulse b { font: 800 1.15rem var(--font-head); margin-right: .25rem; }
.pulse .warn { background: var(--warn-bg); color: var(--warn-text); }

/* ===== cards: A soft, B edged, C plain sections with a rule ===== */
.card { margin-top: var(--space-4); padding: 1.1rem 1.25rem 1.25rem; border-radius: var(--radius); background: var(--surface); border: 1px solid var(--edge); box-shadow: var(--lift); }
body[data-look="c"] .card { background: transparent; border: 0; border-top: 1px solid var(--edge-strong); border-radius: 0; padding-inline: 0; margin-top: var(--space-5); }
.card-head { display: flex; justify-content: space-between; align-items: baseline; gap: var(--space-4); flex-wrap: wrap; margin-bottom: var(--space-3); }
.card h2 { margin: 0; font: 700 var(--text-lg) var(--font-head); }
.hint { margin: 0; color: var(--text-dim); }
.legend { display: flex; flex-wrap: wrap; gap: .3rem 1rem; list-style: none; margin: 0; padding: 0; color: var(--text-dim); font-size: .9rem; }
.legend i { display: inline-block; width: .8rem; height: .8rem; border-radius: 3px; margin-right: .35rem; vertical-align: -.1rem; }
.legend.small { margin-top: var(--space-3); }

/* ===== timeline ===== */
.scale { display: grid; grid-template-columns: var(--label-w) repeat(52, 1fr); color: var(--text-dim); font: 600 .78rem var(--font-head); padding: .1rem 0 .3rem; }
.scale span { grid-column: span 4; }
.scale span:first-child { grid-column: 2 / span 4; }
.lanes { position: relative; padding-bottom: 1.9rem; }
.lane { display: grid; grid-template-columns: var(--label-w) 1fr; align-items: center; border-top: 1px solid var(--rule); min-height: 2.9rem; }
.who { display: flex; flex-direction: column; line-height: 1.2; padding: .3rem 0; }
.who small { color: var(--text-dim); }
.track { display: grid; grid-template-columns: repeat(52, 1fr); height: 1.7rem; background-image: linear-gradient(to right, var(--rule) 1px, transparent 1px); background-size: calc(100% / 13) 100%; }
.seg { display: grid; place-items: center; font: 800 .8rem var(--font-head); color: #fff; border-radius: 6px; margin: 0 1px; }
body[data-look="b"] .seg { color: #06142B; }
.k-P { background: var(--channel-phone); } .k-C { background: var(--channel-chat); } .k-E { background: var(--channel-email); } .k-B { background: var(--channel-break); } .k-L { background: var(--channel-lunch); }
.now-line { position: absolute; top: 0; bottom: 0; width: 2px; background: var(--now); pointer-events: none; left: calc(var(--label-w) + (100% - var(--label-w)) * 0.5077); }
.now-line em { position: absolute; bottom: -.1rem; left: 50%; translate: -50% 0; padding: .1rem .5rem; border-radius: 999px; font: 700 .72rem var(--font-head); font-style: normal; background: var(--now); color: var(--on-now); white-space: nowrap; }
/* what changed after a refresh: a tint that fades, so the eye finds the row (occasional, state indication) */
.lane.flash { animation: flash 1.6s var(--ease-out) both; }
@keyframes flash { from { background-color: var(--changed); } to { background-color: transparent; } }

/* ===== coverage ===== */
.heat { display: grid; grid-template-columns: repeat(13, 1fr); gap: 4px; }
.cell { height: 2.2rem; padding: 0; border-radius: 6px; border: 0; }
.cell.h-c, .h-c { background: var(--covered); } .h-s { background: var(--short); } .h-g { background: var(--gap); } .h-o { background: var(--over); }
.cell:active { transform: none; }
@media (hover: hover) and (pointer: fine) { .cell:hover { filter: brightness(1.12); } }

/* ===== requests: a row collapses when it is answered (the list closes the gap instead of jumping) ===== */
.asks { list-style: none; margin: 0; padding: 0; }
.ask { display: grid; grid-template-rows: 1fr; opacity: 1; transition: grid-template-rows var(--t-row) var(--ease-out), opacity var(--t-row) var(--ease-out); border-top: 1px solid var(--rule); }
.ask:first-child { border-top: 0; }
.ask-in { overflow: hidden; min-height: 0; }
.ask-row { display: flex; justify-content: space-between; align-items: center; gap: var(--space-4); flex-wrap: wrap; padding: var(--space-3) 0; }
.ask small { display: block; color: var(--text-dim); }
.ask.gone { grid-template-rows: 0fr; opacity: 0; border-top-color: transparent; }
.btns { display: inline-flex; gap: var(--space-2); }
.empty { margin: 0; padding: var(--space-3) 0; color: var(--text-dim); }

/* ===== the floating note: out of date, and confirmations ===== */
.float-note { position: fixed; z-index: 50; left: 0; right: 0; margin-inline: auto; width: max-content; max-width: min(46rem, calc(100vw - 1.5rem)); bottom: 1.1rem; display: flex; align-items: center; gap: var(--space-3); padding: .65rem .8rem .65rem 1rem; border-radius: 999px; background: var(--note-bg); color: var(--note-text); border: 1px solid var(--note-edge); box-shadow: var(--note-lift); backdrop-filter: blur(14px) saturate(1.4); -webkit-backdrop-filter: blur(14px) saturate(1.4);
  opacity: 0; transform: translateY(.75rem) scale(.97); visibility: hidden; pointer-events: none;
  transition: opacity var(--t-note-out) var(--ease-out), transform var(--t-note-out) var(--ease-out), visibility 0s linear var(--t-note-out); }
.float-note.on { opacity: 1; transform: none; visibility: visible; pointer-events: auto; transition: opacity var(--t-note-in) var(--ease-out), transform var(--t-note-in) var(--ease-out), visibility 0s; }
.float-note .pip { flex: none; width: .7rem; height: .7rem; border-radius: 50%; background: var(--pip); }
.float-note[data-kind="done"] .pip { background: var(--covered); }
.float-note .msg b { font-weight: 700; }
.float-note .act { flex: none; padding: .4rem .9rem; border-radius: 999px; background: var(--action); color: var(--on-action); }
body[data-look="c"] .float-note .act { background: #fff; color: #101828; }
.float-note .x { flex: none; background: transparent; color: var(--note-text); border: 0; padding: .4rem .5rem; font-weight: 600; opacity: .75; }
.float-note .act[hidden] { display: none; }

/* ===== sign in ===== */
.signin { min-height: calc(100vh - 3rem); display: grid; place-items: center; padding: var(--space-5); }
.signin-card { width: min(26rem, 100%); padding: 2rem 2rem 1.6rem; border-radius: calc(var(--radius) + 6px); background: var(--surface); border: 1px solid var(--edge); box-shadow: var(--lift-big); }
.signin h1 { margin: 0; font: 800 2.1rem/1.1 var(--font-head); font-stretch: 88%; }
.lede { margin: .35rem 0 var(--space-5); color: var(--text-dim); }
label { display: block; font-weight: 600; margin-bottom: .9rem; }
input { display: block; width: 100%; margin-top: .3rem; padding: .65rem .8rem; border-radius: 10px; border: 1px solid var(--edge-strong); background: var(--field); color: var(--text); font: 1rem var(--font-body); }
input[aria-invalid="true"] { border-color: var(--gap); box-shadow: 0 0 0 1px var(--gap); }
.field-error { margin: -.3rem 0 .9rem; color: var(--text); font-weight: 600; padding-left: .6rem; border-left: 1px solid var(--gap); }
.field-error:not([hidden]) { animation: rise .18s var(--ease-out) both; }
.wide { width: 100%; padding: .75rem 1rem; font-size: 1.05rem; margin-top: .3rem; }
.fine { margin: 1.1rem 0 0; color: var(--text-dim); font-size: .92rem; }
/* the one authored moment: the mark's three bars slide in, then the card's text rises (a first look per session, so it earns it) */
.signin.in .brand img { animation: bars .42s var(--ease-out) both; }
.signin.in .signin-card > :not(.brand) { animation: rise .32s var(--ease-out) both; }
.signin.in .signin-card > :nth-child(3) { animation-delay: 50ms; } .signin.in .signin-card > :nth-child(4) { animation-delay: 90ms; }
.signin.in .signin-card > :nth-child(5) { animation-delay: 130ms; } .signin.in .signin-card > :nth-child(6) { animation-delay: 170ms; }
@keyframes bars { from { opacity: 0; transform: translateX(-8px); } to { opacity: 1; transform: none; } }
@keyframes rise { from { opacity: 0; transform: translateY(8px); } to { opacity: 1; transform: none; } }

/* ===== look switch: a short cross-fade of the whole page (a rare action) ===== */
::view-transition-old(root), ::view-transition-new(root) { animation-duration: var(--t-look); animation-timing-function: var(--ease-out); }

/* ===== small screens ===== */
@media (max-width: 40rem) {
  :root { --label-w: 5.4rem; }
  .scale span:nth-child(even) { visibility: hidden; }
  .who small { display: none; }
  .tabs { gap: var(--space-4); overflow-x: auto; }
  .protobar { font-size: .8rem; }
  .protobar .try { margin-left: 0; }
  .float-note { left: .6rem; right: .6rem; width: auto; margin-inline: 0; bottom: .6rem; border-radius: 18px; flex-wrap: wrap; font-size: .92rem; }
  .float-note .msg { flex: 1 1 12rem; }
  .float-note .x { display: none; }
}


/* ===== round 3b: more pages ===== */
.cmdk { padding: .35rem .7rem; font-weight: 600; } .cmdk kbd { font: 600 .72rem var(--font-head); margin-left: .4rem; padding: .05rem .35rem; border-radius: 5px; border: 1px solid var(--edge-strong); color: var(--text-dim); }
.top nav { flex: 1; } .lede { color: var(--text-dim); margin: .2rem 0 0; max-width: 62ch; }
.grid3 { display: grid; grid-template-columns: repeat(3, 1fr); gap: var(--space-4); margin-top: var(--space-4); } .grid3 .card { margin-top: 0; }
.stat .big { margin: .2rem 0 .1rem; font: 800 2.4rem/1 var(--font-head); } .stat .big span { font: 500 1rem var(--font-body); color: var(--text-dim); }
.more { display: inline-block; margin-top: var(--space-2); font-weight: 600; text-underline-offset: .2em; }
.mini { display: grid; grid-template-columns: repeat(24, 1fr); gap: 3px; } .mini i { height: 1.6rem; border-radius: 4px; }
.mini .h-c { background: var(--rule); } .mini .h-s { background: var(--short); } .mini .h-g { background: var(--gap); } .mini .h-o { background: color-mix(in srgb, var(--over) 38%, transparent); }
.runs { list-style: none; margin: 0; padding: 0; } .run { display: grid; grid-template-columns: 1fr 9rem 4.5rem; gap: var(--space-4); align-items: center; padding: var(--space-3) 0; border-top: 1px solid var(--rule); }
.run small { display: block; color: var(--text-dim); } .pct { text-align: right; font-family: var(--font-head); }
.bar5 { display: grid; grid-template-columns: repeat(5, 1fr); gap: 3px; } .bar5 i { height: .4rem; border-radius: 3px; background: var(--edge-strong); opacity: .5; } .bar5 i.go { background: var(--covered); opacity: 1; }
.chip { display: inline-block; margin-left: .5rem; padding: .1rem .55rem; border-radius: 999px; background: var(--chip); border: 1px solid var(--rule); font: 600 .78rem var(--font-body); color: var(--text-dim); }
.chip.on { background: var(--action); color: var(--on-action); border-color: transparent; } .chip.warn { background: var(--warn-bg); color: var(--warn-text); border-color: transparent; } .chip.ok { margin: 0; background: color-mix(in srgb, var(--covered) 18%, transparent); color: var(--covered); border-color: transparent; }
.count { display: inline-block; min-width: 1.35rem; padding: 0 .35rem; margin-left: .3rem; border-radius: 999px; background: var(--short); color: #2A1A00; font: 800 .75rem/1.35rem var(--font-head); text-align: center; }
.reqs { list-style: none; margin: 0; padding: 0; } .req { display: grid; grid-template-columns: 1fr 17rem; gap: var(--space-5); padding: var(--space-4) 0; border-top: 1px solid var(--rule); } .req:first-child { border-top: 0; }
.req-top { display: flex; gap: var(--space-3); align-items: center; } .req-top .chip { margin: 0; } .req-what { margin: .3rem 0; } .quote { margin: 0 0 .3rem; color: var(--text-dim); }
.impact { margin: .3rem 0 0; padding: .45rem .7rem; border-radius: 10px; background: var(--warn-bg); color: var(--warn-text); font-weight: 600; } .pip { display: inline-block; width: .55rem; height: .55rem; border-radius: 50%; background: currentColor; margin-right: .5rem; }
.req-act label { font-size: .9rem; margin-bottom: .6rem; } .req-act .btns { justify-content: flex-end; width: 100%; display: flex; }
.weekpick a { padding: .6rem .9rem; margin: 0 0 -1px; } .weekpick small { display: block; font-weight: 400; color: var(--text-dim); }
.inline { display: inline-flex; gap: .5rem; align-items: center; margin: 0; } .inline select { padding: .4rem .6rem; border-radius: 8px; border: 1px solid var(--edge-strong); background: var(--field); color: var(--text); font: inherit; }
.compare { display: grid; grid-template-columns: 11rem 1fr 1fr; } .compare > * { padding: .7rem .8rem; border-top: 1px solid var(--rule); } .compare .head, .compare .col { border-top: 0; }
.compare h3 { margin: 0; font: 700 1.1rem var(--font-head); } .compare .col .chip { margin: .4rem 0 0; } .compare small { color: var(--text-dim); } .row-l { color: var(--text-dim); font-weight: 600; }
.compare .col:nth-child(2) { background: var(--changed); border-radius: 10px 10px 0 0; } button.danger { color: var(--gap); border-color: var(--gap); }
.wall .shell.wide { max-width: 90rem; } .wtop { display: grid; grid-template-columns: 1fr auto 1fr; align-items: center; padding: 1.5rem 0; } .wtop h1 { margin: 0; font: 800 2.4rem var(--font-head); } .clock { text-align: right; margin: 0; font: 800 2.6rem var(--font-head); } .clock span { font: 500 1.2rem var(--font-body); color: var(--text-dim); }
.wtiles { display: grid; grid-template-columns: repeat(4, 1fr); gap: var(--space-4); } .wtile { padding: 1.2rem; border-radius: var(--radius); background: var(--surface); border: 1px solid var(--edge); box-shadow: var(--lift); border-top: 6px solid var(--covered); } .wtile p { margin: 0; color: var(--text-dim); } .wtile.now p:first-child { color: var(--text); font-weight: 700; } .wbig { font: 800 3.6rem/1.1 var(--font-head); color: var(--covered) !important; margin: .3rem 0 !important; }
@media (max-width: 52rem) { .grid3, .wtiles { grid-template-columns: 1fr 1fr; } .req { grid-template-columns: 1fr; } .compare { grid-template-columns: 7rem 1fr 1fr; } }
@media (max-width: 40rem) { .grid3, .wtiles { grid-template-columns: 1fr; } .run { grid-template-columns: 1fr 4rem; } .bar5 { display: none; } .wtop { grid-template-columns: 1fr; gap: .5rem; } .clock { text-align: left; } .cmdk { display: none; } }


/* ===== round 4: friendlier, and no very long lists (scroll panels and pages) ===== */
.scroll { max-height: 26rem; overflow: auto; overscroll-behavior: contain; border-radius: calc(var(--radius) - 4px); scrollbar-width: thin; scrollbar-color: var(--edge-strong) transparent; }
.scroll.short { max-height: 21rem; } .scroll:focus-visible { outline: 3px solid var(--focus); outline-offset: 2px; }
.lanes.scroll { padding-bottom: 2.2rem; position: relative; } .lane[hidden] { display: none !important; }
.lanes.scroll .now-line { top: 0; bottom: 0; }
.toolrow { display: flex; align-items: end; gap: var(--space-4); flex-wrap: wrap; margin: 0 0 var(--space-3); } .toolrow .hint { margin: 0 0 .6rem; flex: 1; }
.search { margin: 0; min-width: 15rem; font-size: .9rem; } .search input { margin-top: .25rem; padding: .5rem .8rem; border-radius: 999px; }
.chips { display: flex; flex-wrap: wrap; gap: .4rem; margin: 0 0 var(--space-3); } .chipbtn { background: var(--chip); color: var(--text); border: 1px solid var(--rule); padding: .3rem .8rem; border-radius: 999px; font-weight: 600; }
.chipbtn[aria-pressed="true"] { background: var(--action); color: var(--on-action); border-color: transparent; }
table.grid { width: 100%; border-collapse: separate; border-spacing: 0; font-variant-numeric: tabular-nums; } .grid th { position: sticky; top: 0; z-index: 1; text-align: left; padding: .55rem .8rem; background: var(--surface); color: var(--text-dim); font-weight: 600; border-bottom: 1px solid var(--edge-strong); }
body[data-look="c"] .grid th { background: var(--bg); } .grid td { padding: .5rem .8rem; border-bottom: 1px solid var(--rule); }
.pager { display: flex; align-items: center; justify-content: space-between; gap: var(--space-3); margin-top: var(--space-3); } .pager button[disabled] { opacity: .4; cursor: default; filter: none; }
.prow[hidden] { display: none !important; }
.people { list-style: none; margin: 0; padding: 0; } .person { display: grid; grid-template-columns: 2.6rem 1fr auto auto; gap: var(--space-4); align-items: center; padding: .65rem 0; border-top: 1px solid var(--rule); } .person small { display: block; color: var(--text-dim); }
.avatar { width: 2.6rem; height: 2.6rem; border-radius: 50%; display: grid; place-items: center; background: var(--chip); border: 1px solid var(--rule); font: 800 .85rem var(--font-head); }
.switch { margin: 0; display: inline-flex; align-items: center; gap: .5rem; font-weight: 600; } .switch input { width: 2.4rem; height: 1.4rem; margin: 0; accent-color: var(--covered); } 
body[data-look="a"] { --radius: 20px; } body[data-look="b"] { --radius: 16px; }
@media (max-width: 40rem) { .person { grid-template-columns: 2.6rem 1fr auto; } .person .ghost { display: none; } .search { min-width: 0; flex: 1; } }


.scale.sticky { position: sticky; top: 0; z-index: 3; background: var(--surface); padding-top: .2rem; }
body[data-look="c"] .scale.sticky { background: var(--bg); }
.lanes.scroll .now-line { z-index: 2; }
@media (max-width: 40rem) {
  .top { gap: .5rem var(--space-3); } .brand { flex: 1; } .top nav { order: 3; flex: 1 1 100%; flex-wrap: nowrap; overflow-x: auto; scrollbar-width: none; padding-bottom: .2rem; } .top nav a { white-space: nowrap; }
  .card-head .btns { flex-wrap: wrap; } .protobar .group { flex-wrap: wrap; } .protobar button { white-space: nowrap; }
}

/* ===== reduced motion: keep what explains a change, drop the movement ===== */
@media (prefers-reduced-motion: reduce) {
  .float-note, .float-note.on { transform: none; transition: opacity .12s linear, visibility 0s; }
  .ask { transition: opacity .12s linear; }
  .ask.gone { grid-template-rows: 1fr; }
  .signin.in .brand img, .signin.in .signin-card > :not(.brand), .field-error:not([hidden]) { animation: none; }
  .lane.flash { animation: none; }
  button:active { transform: none; }
  ::view-transition-group(*), ::view-transition-old(*), ::view-transition-new(*) { animation: none !important; }
}
@media (forced-colors: active) { .seg, .cell, .pulse li, .card { border: 1px solid CanvasText; } .float-note { border: 1px solid CanvasText; } }
'''

JS = '''// © 2026 Omar Mokhtar. All rights reserved.
(function () {
  "use strict";
  var body = document.body, note = document.getElementById("note"), msg = document.getElementById("note-msg"),
      act = document.getElementById("note-act"), noteTimer = 0, noteAction = null;
  var reduce = window.matchMedia("(prefers-reduced-motion: reduce)");

  function store(key, value) { try { if (value === undefined) { return window.localStorage.getItem(key); } window.localStorage.setItem(key, value); } catch (e) { return null; } return null; }

  /* ---- look and page ---- */
  function pressed(attr, value) {
    Array.prototype.forEach.call(document.querySelectorAll("[" + attr + "]"), function (b) { b.setAttribute("aria-pressed", b.getAttribute(attr) === value ? "true" : "false"); });
  }
  function setLook(look) {
    var change = function () { body.setAttribute("data-look", look); pressed("data-look-pick", look); };
    if (document.startViewTransition && !reduce.matches) { document.startViewTransition(change); } else { change(); }
    store("look", look);
  }
  function setView(view) {
    Array.prototype.forEach.call(document.querySelectorAll(".view"), function (v) { v.hidden = v.id !== "view-" + view; });
    window.scrollTo(0, 0);
    body.setAttribute("data-view", view);
    pressed("data-view-pick", view);
    var s = document.getElementById("signin-main");
    s.classList.remove("in");
    if (view === "signin") { void s.offsetWidth; s.classList.add("in"); }
  }

  /* ---- the floating note ---- */
  function showNote(text, kind, label, action, ms) {
    window.clearTimeout(noteTimer);
    msg.innerHTML = text;
    note.setAttribute("data-kind", kind);
    act.hidden = !label;
    act.textContent = label || "";
    noteAction = action || null;
    note.classList.add("on");
    if (ms) { noteTimer = window.setTimeout(hideNote, ms); }
  }
  function hideNote() { window.clearTimeout(noteTimer); note.classList.remove("on"); }
  act.addEventListener("click", function () { var f = noteAction; hideNote(); if (f) { f(); } });
  document.getElementById("note-x").addEventListener("click", hideNote);
  document.addEventListener("keydown", function (e) { if (e.key === "Escape") { hideNote(); } });

  /* ---- a change by someone else, then Refresh ---- */
  function stale() {
    showNote("<b>This page is out of date.</b> Associate 04\\u2019s break moved at 14:35.", "stale", "Refresh", function () {
      var lane = document.querySelector('.lane[data-who="Associate 04"]');
      if (lane) { lane.classList.remove("flash"); void lane.offsetWidth; lane.classList.add("flash"); }
    });
  }

  /* ---- answer a request: the row closes, and the note offers Undo ---- */
  var asks = document.getElementById("asks"), count = document.getElementById("askcount"), empty = document.getElementById("empty");
  function left() { return asks.querySelectorAll(".ask:not(.gone)").length; }
  function refreshCount() {
    var n = left();
    count.textContent = n + (n === 1 ? " request" : " requests");
    empty.hidden = n !== 0;
  }
  asks.addEventListener("click", function (e) {
    var b = e.target.closest("button[data-act]");
    if (!b) { return; }
    var row = b.closest(".ask"), verb = b.getAttribute("data-act") === "approve" ? "Approved" : "Declined", who = row.getAttribute("data-who");
    row.classList.add("gone");
    refreshCount();
    showNote("<b>" + verb + "</b> " + who + "\\u2019s " + row.getAttribute("data-kind") + ".", "done", "Undo", function () { row.classList.remove("gone"); refreshCount(); }, 6000);
  });

  /* ---- sign in ---- */
  var form = document.getElementById("form"), pw = document.getElementById("p"), perr = document.getElementById("perr");
  form.addEventListener("submit", function (e) {
    e.preventDefault();
    if (!pw.value) { perr.hidden = false; pw.setAttribute("aria-invalid", "true"); pw.focus(); return; }
    perr.hidden = true; pw.removeAttribute("aria-invalid");
    setView("day");
    showNote("<b>Signed in.</b> Welcome back, Sara.", "done", "", null, 3000);
  });
  pw.addEventListener("input", function () { if (pw.value) { perr.hidden = true; pw.removeAttribute("aria-invalid"); } });


  /* ---- long lists: pages with a filter, and the lane list scrolls inside its own box ---- */
  Array.prototype.forEach.call(document.querySelectorAll("[data-pager]"), function (box) {
    var rows = Array.prototype.slice.call(box.querySelectorAll(".prow")), size = parseInt(box.getAttribute("data-size"), 10) || 10, page = 0, day = "", text = "";
    var label = box.querySelector("[data-pager-label]"), pg = box.querySelector("[data-pager-page]"), prev = box.querySelector("[data-pager-prev]"),
        next = box.querySelector("[data-pager-next]"), none = box.querySelector("[data-pager-empty]"), wrap = box.querySelector(".scroll");
    function draw() {
      var hit = rows.filter(function (r) { return (!day || r.getAttribute("data-day") === day) && (!text || (r.getAttribute("data-text") || r.textContent).toLowerCase().indexOf(text) !== -1); });
      var pages = Math.max(1, Math.ceil(hit.length / size)); page = Math.min(page, pages - 1);
      rows.forEach(function (r) { r.hidden = true; });
      hit.slice(page * size, page * size + size).forEach(function (r) { r.hidden = false; });
      var from = hit.length ? page * size + 1 : 0, to = Math.min(hit.length, page * size + size);
      label.textContent = hit.length ? from + " to " + to + " of " + hit.length : "0 results";
      pg.textContent = "Page " + (page + 1) + " of " + pages; prev.disabled = page === 0; next.disabled = page >= pages - 1; none.hidden = hit.length !== 0;
      if (wrap) { wrap.scrollTop = 0; }
    }
    prev.addEventListener("click", function () { page -= 1; draw(); }); next.addEventListener("click", function () { page += 1; draw(); });
    Array.prototype.forEach.call(box.querySelectorAll("[data-day-pick]"), function (b) {
      b.addEventListener("click", function () {
        day = b.getAttribute("data-day-pick") === "All days" ? "" : b.getAttribute("data-day-pick"); page = 0;
        Array.prototype.forEach.call(box.querySelectorAll("[data-day-pick]"), function (o) { o.setAttribute("aria-pressed", o === b ? "true" : "false"); });
        draw();
      });
    });
    var find = box.querySelector("[data-pager-search]");
    if (find) { find.addEventListener("input", function () { text = find.value.trim().toLowerCase(); page = 0; draw(); }); }
    draw();
  });
  var laneFind = document.getElementById("lane-find"), laneBox = document.getElementById("lane-scroll"), laneCount = document.getElementById("lane-count");
  function laneFilter() {
    var t = laneFind.value.trim().toLowerCase(), n = 0;
    Array.prototype.forEach.call(laneBox.querySelectorAll(".lane"), function (l) { var ok = !t || l.getAttribute("data-who").toLowerCase().indexOf(t) !== -1; l.hidden = !ok; if (ok) { n += 1; } });
    laneCount.textContent = n === 1 ? "1 person" : n + " people";
  }
  laneFind.addEventListener("input", laneFilter);
  document.getElementById("jump-now").addEventListener("click", function () { laneBox.scrollTop = 0; laneBox.focus(); });

  /* ---- controls ---- */
  Array.prototype.forEach.call(document.querySelectorAll("[data-look-pick]"), function (b) { b.addEventListener("click", function () { setLook(b.getAttribute("data-look-pick")); }); });
  Array.prototype.forEach.call(document.querySelectorAll("[data-view-pick]"), function (b) { b.addEventListener("click", function () { setView(b.getAttribute("data-view-pick")); }); });
  document.querySelector("[data-try]").addEventListener("click", function () { setView("day"); window.setTimeout(stale, 350); });

  var saved = store("look"), dark = window.matchMedia("(prefers-color-scheme: dark)").matches;
  var start = /^[abc]$/.test(saved || "") ? saved : (dark ? "b" : "a");
  body.setAttribute("data-look", start); pressed("data-look-pick", start);
  var q = /[?&]look=([abc])/.exec(window.location.search);
  if (q) { body.setAttribute("data-look", q[1]); pressed("data-look-pick", q[1]); }
  var v = /[?&]view=(day|home|week|people|requests|schedules|wallboard|signin)/.exec(window.location.search);
  if (v) { setView(v[1]); }
}());
'''


def main():
    (HERE / "index.html").write_text(page(), encoding="utf-8")
    (HERE / "proto.css").write_text(CSS, encoding="utf-8")
    (HERE / "proto.js").write_text(JS, encoding="utf-8")
    (HERE / "bars.css").write_text("/* © 2026 Omar Mokhtar. All rights reserved. */\n" + bars_css().replace(f".now-line {{", ".now-line-unused {"), encoding="utf-8")
    print("built", [p.name for p in sorted(HERE.glob("*")) if p.is_file()])


if __name__ == "__main__":
    main()
