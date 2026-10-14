"""Phase AG samples: writes the sample pages (static HTML) next to ag.css. Made-up "Associate NN" names."""
import re
from pathlib import Path

HERE = Path(__file__).parent
ICONS = {p.stem: p.read_text() for p in (HERE / "icons").glob("*.svg")}


def ic(name):
    svg = ICONS[name]
    return re.sub(r"<svg[^>]*>", '<svg class="i" viewBox="0 0 256 256" aria-hidden="true">', svg, count=1)


def page(body, title):
    return (f'<!doctype html><html lang="en" data-theme="dark"><head><meta charset="utf-8"><title>{title}</title>'
            f'<link rel="stylesheet" href="ag.css"></head><body>{body}</body></html>')


RAIL = [("Today", [("pulse", "Day (RTA)", ""), ("lifebuoy", "Rescue the day", ""), ("television", "Wallboard", "")]),
        ("This week", [("calendar-blank", "Week", ""), ("stack", "Schedules", ""), ("headset", "Plan channels", ""),
                       ("chart-bar", "Overview", "")]),
        ("Requests", [("airplane-tilt", "Leave", "2"), ("arrows-left-right", "Swaps", "1")]),
        ("Setup", [("users-three", "Programs and people", ""), ("gear", "Settings", "")])]


def rail(on):
    out = ['<nav class="rail" aria-label="Menu"><div class="brand"><span class="mark"></span>Team Scheduler</div>']
    for group, items in RAIL:
        out.append(f'<div class="group"><p>{group}</p>')
        for icon, label, n in items:
            out.append(f'<a class="item{" on" if label == on else ""}" href="#">{ic(icon)}{label}'
                       f'{f"<span class=count>{n}</span>" if n else ""}</a>')
        out.append("</div>")
    out.append(f'<div class="me">{ic("user-circle")}<span>Omar Mokhtar<br><small class="dim">Admin</small></span>'
               f'<span class="grow"></span>{ic("moon")}</div></nav>')
    return "".join(out)


def ctx(day="Wed 14 Oct", week=False):
    step = (f'<span>{ic("caret-left")}</span><span>{"Week of 11 Oct" if week else day}</span><span>{ic("caret-right")}</span>')
    return (f'<header class="ctx"><span class="pick">SAKS <small>NMG Tier 2</small>{ic("caret-right")}</span>'
            f'<span class="step">{step}</span><span class="btn sm">Today</span>'
            f'<span class="pick">{ic("globe-hemisphere-west")}Cairo <small>UTC+3</small></span><span class="grow"></span>'
            f'<span class="goto">{ic("magnifying-glass")}Go to a page or person<kbd>Ctrl K</kbd></span>'
            f'<span class="btn quiet sm">{ic("bell")}</span></header>')


# 48 half-hours: c covered, s short, g gap, o over, - no demand
DAY = ("--cc" "cccc" "cccc" "cccc" "cocc" "cccc" "ccsc" "cccc" "cccc" "ss" "cs" "cc" "cc" "gc" "c")
DAY = (DAY + "c" * 48)[:48]
DAY = "cccc" "cccc" "cccccc" "cccooc" "cccc" "cccc" "cccs" "cccc" "ss" "sc" "cc" "cc"
DAY = (DAY + "cccccccc")[:48]
NOW = 18 * 60 + 24


def strip(cells=DAY, now=NOW, small=False, mark=()):
    out = ['<div class="cells">']
    for k, c in enumerate(cells):
        cls = {"c": "c", "s": "s", "g": "g", "o": "o"}.get(c, "")
        past = " past" if now is not None and (k + 1) * 30 <= now else ""
        x = " x" if k in mark else ""
        out.append(f'<i class="{cls}{past}{x}"></i>')
    out.append("</div>")
    if not small:
        out.append('<div class="ticks">' + "".join(f"<span>{h:02d}</span>" for h in range(0, 24, 3)) + "</div>")
        if now is not None:
            out.append(f'<span class="now" style="left:{100 * now / 1440:.2f}%"><b>Now 18:24</b></span>')
    return "".join(out)


def daystrip():
    return (f'<section class="daystrip" aria-label="The day"><div class="strip">{strip()}</div>'
            '<div class="dayfigs"><div><span class="fig">21<small class="dim"> of 24</small></span><small>hours at 90% or more</small></div>'
            '<div><span class="fig" style="color:var(--short-text)">1.5 h</span><small>short so far</small></div>'
            '<div><span class="fig">11<small class="dim"> of 12</small></span><small>on the floor now</small></div></div></section>')


def tabs(on, items, extra=""):
    out = ['<nav class="tabs">']
    for label, n in items:
        out.append(f'<a href="#" class="{"on" if label == on else ""}">{label}{f"<span class=n>{n}</span>" if n else ""}</a>')
    out.append(f'<span class="spacer"></span>{extra}</nav>')
    return "".join(out)


# timeline: hours 12..24 shown; segments (start h, end h, kind)
PEOPLE = [
    ("Associate 07", "English, Phone and Chat", [(12, 14.5, "P"), (14.5, 14.75, "brk"), (14.75, 17, "P"), (17, 17.5, "brk"), (17.5, 18.5, "C"), (18.5, 18.75, "brk"), (18.75, 21, "C")]),
    ("Associate 12", "English, Phone", [(12, 13.75, "P"), (13.75, 14, "brk"), (14, 16.5, "P"), (16.5, 17, "brk"), (17, 19.25, "P"), (19.25, 19.5, "brk"), (19.5, 21, "P")]),
    ("Associate 14", "English, Phone and Email", [(16, 18, "P"), (18, 18.25, "brk"), (18.25, 20.5, "E"), (20.5, 21, "brk"), (21, 24, "P")]),
    ("Associate 21", "French, Chat", [(14, 16, "C"), (16, 16.25, "brk"), (16.25, 18.75, "C"), (18.75, 19.25, "brk"), (19.25, 23, "C")]),
    ("Associate 25", "Bilingual, all channels", [(15, 17.5, "E"), (17.5, 17.75, "brk"), (17.75, 20, "P"), (20, 20.5, "brk"), (20.5, 24, "P")]),
    ("Associate 30", "English, Chat", [(19, 21, "C"), (21, 21.25, "brk"), (21.25, 24, "C")]),
    ("Associate 33", "English, Phone", [(18, 24, "off")]),
    ("Associate 36", "English, Phone and Chat", [(16, 18.5, "C"), (18.5, 18.75, "brk"), (18.75, 21, "P"), (21, 21.5, "brk"), (21.5, 24, "P")]),
    ("Associate 39", "French, Email", [(17, 19.5, "E"), (19.5, 19.75, "brk"), (19.75, 22, "E"), (22, 22.5, "brk"), (22.5, 24, "E")]),
]


def pos(h, lo=12, hi=24):
    return 100 * (h - lo) / (hi - lo)


def timeline():
    out = ['<section class="panel"><div class="tl-head"><span class="dim" style="font-size:.75rem">9 on shift this afternoon</span><div class="hours">']
    out += [f"<span>{h:02d}:00</span>" for h in range(12, 24)]
    out.append('</div></div><div class="tl-wrap">')
    for name, note, segs in PEOPLE:
        sick = any(k == "off" for _, _, k in segs)
        late = ' <span class="chip gap">Late, not in yet</span>' if sick else ""
        out.append(f'<div class="tl-row"><div class="who"><b>{name}{late}</b><small>{note}</small></div><div class="track">')
        for a, b, k in segs:
            out.append(f'<i class="seg {k}" style="left:{pos(a):.2f}%;width:{pos(b) - pos(a):.2f}%"></i>')
        out.append("</div></div>")
    out.append(f'<span class="tlnow" style="left:calc(190px + 14px + (100% - 218px) * {(NOW / 60 - 12) / 12:.4f})"></span></div>')
    out.append('<div class="legend"><span><i style="background:var(--phone)"></i>Phone</span><span><i style="background:var(--chat)"></i>Chat</span>'
               '<span><i style="background:var(--email)"></i>Email</span><span><i style="border:1.5px solid var(--ink)"></i>Break (drag to move)</span>'
               '<span><i class="seg off" style="position:static;display:inline-block"></i>Not on the floor</span></div></section>')
    return "".join(out)


def nowcol():
    return f'''<aside class="panel nowcol" aria-label="Now">
<section><h3>Now <span class="fig dim" style="font-size:1rem">18:24</span></h3>
<div class="pair"><div><span class="fig">11<small class="dim"> / 12</small></span><br><small class="dim">on the floor, needed</small></div>
<div><span class="fig" style="color:var(--short-text)">1</span><br><small class="dim">short until 19:00</small></div></div></section>
<section><h3>Next hour</h3><ul class="list">
<li><time>18:30</time><span>Associate 07<small>Break 1, off Chat</small></span><span class="btn sm">Move</span></li>
<li><time>18:45</time><span>Associate 36<small>Break 1, off Chat</small></span><span class="btn sm">Move</span></li>
<li><time>19:00</time><span>Associate 30<small>Starts on Chat</small></span><span></span></li>
<li><time>19:15</time><span>Associate 12<small>Break 2, off Phone</small></span><span class="btn sm">Move</span></li></ul></section>
<section><h3>Needs attention</h3>
<div class="alert gap">{ic("warning")}<span><b>Associate 33</b> is not in yet<br><small class="dim">Shift started at 18:00. Mark late or sick.</small></span></div>
<div class="alert short">{ic("warning")}<span><b>Chat</b> short 19:00 to 20:00<br><small class="dim">Two breaks fall there. Fix the day can move one.</small></span></div>
<div class="alert gap">{ic("warning")}<span><b>French</b>: nobody 01:00 to 02:00</span></div></section>
<section><h3>Requests waiting <a class="btn sm" href="#">Open</a></h3><small class="dim">2 leave requests and 1 swap for this week.</small></section>
<section><h3>Shrinkage today</h3><div class="three"><div><span class="fig">11.1%</span><br><small class="dim">In office</small></div>
<div><span class="fig">3.8%</span><br><small class="dim">Sutherland</small></div><div><span class="fig">3.8%</span><br><small class="dim">Client</small></div></div></section>
</aside>'''


RTA_TABS = [("Floor", ""), ("Intervals", ""), ("Channels", "2"), ("Adherence", ""), ("Fix the day", ""), ("Find a time", "")]


def rta():
    body = (f'<div class="shell">{rail("Day (RTA)")}<div class="main">{ctx()}<div class="page">{daystrip()}'
            + tabs("Floor", RTA_TABS, f'<span class="btn quiet sm">{ic("arrow-u-up-left")}Undo</span><span class="btn solid sm">{ic("plus")}Add</span>')
            + f'<div class="floor">{timeline()}{nowcol()}</div></div></div></div>')
    return page(body, "Day (RTA)")


def requests():
    cap = "".join(f'<div><span>{d}</span><span class="bar">{"".join("<i class=" + c + "></i>" for c in u)}</span><span>{t}</span></div>'
                  for d, u, t in (("Sun 11", "u--", "1 of 3"), ("Mon 12", "u--", "1 of 3"), ("Tue 13", "---", "0 of 3"),
                                  ("Wed 14", "u--", "1 of 3"), ("Thu 15", "uup", "2 of 3, 1 asked"), ("Fri 16", "up-", "1 of 3, 1 asked"),
                                  ("Sat 17", "uuu", "3 of 3, full")))
    cap = cap.replace("<i class=-></i>", "<i></i>")
    leave1 = strip("cccc" * 8 + "ccccssssssss" + "cccc", None, True, mark=range(32, 44))
    leave2 = strip("cccc" * 4 + "ccssssssss" + "c" * 22, None, True, mark=range(16, 26))
    swap = strip("c" * 48, None, True)
    rows = f'''
<div class="req"><div class="who"><b>Associate 14</b><small class="dim">English, Phone and Email<br>Asked today at 09:12</small></div>
<div><div class="what">Annual leave, Thu 15 and Fri 16 Oct</div>
<div class="facts"><span>Balance <b>11 days</b>, 9 after</span><span>Thu <b>2 of 3</b> places</span><span>Fri <b>1 of 3</b> places</span><span>Rules <b>kept</b></span></div>
<div class="mini"><small class="dim">Thursday if approved: short by 1 from 16:00 to 22:00 (their shift)</small>{leave1}</div></div>
<div class="acts"><div class="row"><span class="btn solid">{ic("check-circle")}Approve</span><span class="btn">Refuse</span></div>
<small class="dim">Approving marks both days as leave in the schedule in use and adds the 6 short hours to Fix the day.</small></div></div>
<div class="req"><div class="who"><b>Associate 27</b><small class="dim">French, Email<br>Asked yesterday at 16:40</small></div>
<div><div class="what">Annual leave, Sat 17 Oct <span class="chip gap">Day full</span></div>
<div class="facts"><span>Balance <b>3 days</b>, 2 after</span><span>Sat <b>3 of 3</b> places</span><span>French <b>short 5 h</b> if approved</span></div>
<div class="mini"><small class="dim">Saturday if approved: no French speaker from 08:00 to 13:00</small>{leave2}</div></div>
<div class="acts"><div class="row"><span class="btn">Approve anyway</span><span class="btn">Refuse</span></div>
<span class="btn solid">Offer Sun 18 Oct instead</span><small class="dim">Sunday has 1 of 3 places taken and keeps French covered.</small></div></div>
<div class="req"><div class="who"><b>Associate 05 and Associate 18</b><small class="dim">Shift swap, accepted by Associate 18<br>Asked today at 11:05</small></div>
<div><div class="what swapline">Fri 16 Oct {ic("arrows-left-right")} 17:00 to 02:00 for 20:00 to 05:00</div>
<div class="facts"><span>Rest between shifts <b>kept for both</b></span><span>Language <b>both English</b></span><span>Channels <b>same</b></span><span>Coverage <b>unchanged</b></span></div>
<div class="mini"><small class="dim">Friday stays as planned</small>{swap}</div></div>
<div class="acts"><div class="row"><span class="btn solid">{ic("check-circle")}Approve</span><span class="btn">Refuse</span></div>
<small class="dim">Approving swaps the two shifts in the schedule in use and tells both of them.</small></div></div>
<div class="req done"><div class="who"><b>Associate 09</b><small class="dim">Annual leave, Mon 12 Oct</small></div>
<div><span class="chip covered">{ic("check-circle")}Approved by Omar Mokhtar, Fri 9 Oct</span></div><div></div></div>'''
    body = (f'<div class="shell">{rail("Leave")}<div class="main">{ctx(week=True)}<div class="page">'
            f'<div style="display:flex;align-items:center;gap:14px"><h1 style="font-size:1.25rem">Requests</h1><span class="seg-btns"><span class="on">Waiting 3</span><span>Leave 2</span><span>Swaps 1</span><span>Decided</span></span>'
            f'<span class="grow" style="flex:1"></span><span class="btn sm">{ic("gear")}Leave rules</span></div>'
            f'<section class="panel"><div class="cap" aria-label="Places for leave each day">{cap}</div>{rows}</section></div></div></div>')
    return page(body, "Requests")


def week():
    rows = []
    pats = {"Sun": "cc", "Mon": "cs", "Tue": "co", "Wed": "cs", "Thu": "sg", "Fri": "cc", "Sat": "gs"}
    import random
    random.seed(7)
    for d, p in pats.items():
        cells = []
        for k in range(48):
            r = random.random()
            c = "c" if r < .72 else ("s" if r < .86 else ("o" if r < .93 else "g"))
            if k < 12 and r < .3:
                c = "-"
            cells.append(f'<i class="{c if c != "-" else ""}"></i>')
        rows.append(f"<b>{d}</b>" + "".join(cells))
    grid = '<div class="weekgrid">' + "".join(rows) + "</div>"
    outlook = '''<table class="t"><thead><tr><th>Day</th><th>Known absences</th><th>Short</th><th>To fix it</th></tr></thead><tbody>
<tr><td><b>Thu 15</b></td><td>2<br><small class="dim">1 sick, 1 leave asked</small></td><td class="n">9.5 h</td><td>Cancel 1 day off, 16:00 to 01:00<br><small class="dim">Associate 03 or 14</small></td></tr>
<tr><td><b>Fri 16</b></td><td>1</td><td class="n">4 h</td><td>Overtime 22:00 to 02:00, 1 person</td></tr>
<tr><td><b>Sat 17</b></td><td>0</td><td class="n">0 h</td><td class="dim">Nothing</td></tr></tbody></table>'''
    body = (f'<div class="shell">{rail("Week")}<div class="main">{ctx(week=True)}<div class="page">'
            + tabs("Coverage", [("Coverage", ""), ("Schedules", "2"), ("Channels", ""), ("Breaks", "")],
                   f'<span class="btn sm">{ic("stack")}Download</span><span class="btn solid sm">New schedule</span>')
            + f'''<div class="split"><section class="panel"><div style="display:flex;gap:26px;padding:14px 16px 0;align-items:flex-end">
<div><span class="fig" style="font-size:2.25rem">151<small class="dim"> of 168</small></span><br><small class="dim">hours at 90% or more</small></div>
<div><span class="fig" style="font-size:2.25rem;color:var(--short-text)">13.5 h</span><br><small class="dim">overtime needed for 100%</small></div>
<div><span class="fig" style="font-size:2.25rem">26</small></span><br><small class="dim">associates, 2 on leave</small></div>
<span style="flex:1"></span><span class="chip covered">In use: week.xlsx</span></div>{grid}
<div class="legend"><span><i style="background:var(--covered)"></i>At target</span><span><i style="background:var(--short)"></i>Below target</span><span><i style="background:var(--gap)"></i>Below the floor</span><span><i style="background:var(--over)"></i>Over-staffed</span><span>Each cell is a half hour; click one to open that day.</span></div></section>
<aside class="panel"><div style="padding:14px 16px 6px"><h2>The rest of the week</h2><small class="dim">From what is known today; also on Overview.</small></div>{outlook}
<div style="padding:14px 16px;border-top:1px solid var(--line)"><h3>Requests for this week</h3><small class="dim">2 leave requests and 1 swap are waiting.</small> <a class="btn sm" href="#" style="margin-top:8px">Open requests</a></div></aside></div>'''
            + "</div></div></div>")
    return page(body, "Week")


def goto():
    pal = f'''<div class="scrim"><div class="palette" role="dialog" aria-label="Go to">
<div class="q">{ic("magnifying-glass")}<span>Associate 14</span><kbd>Esc</kbd></div>
<div class="sec"><p>People</p>
<div class="opt on">{ic("user-circle")}Associate 14<small>Today 16:00 to 01:00, English, Phone and Email</small></div>
<div class="opt">{ic("user-circle")}Associate 140<small>Off today</small></div></div>
<div class="sec" style="border-top:1px solid var(--line)"><p>Do it now</p>
<div class="opt">{ic("airplane-tilt")}Open Associate 14's leave request<small>Thu 15 and Fri 16 Oct</small></div>
<div class="opt">{ic("warning")}Mark Associate 14 sick today</div>
<div class="opt">{ic("arrows-left-right")}Swap Associate 14's shift</div></div>
<div class="sec" style="border-top:1px solid var(--line)"><p>Pages</p>
<div class="opt">{ic("pulse")}Day (RTA)<small>SAKS NMG Tier 2</small></div></div></div></div>'''
    return rta().replace("</body>", pal + "</body>")


WAIT = '<span class="chip short">Waiting</span>'


def phone_today():
    segs = [(16, 18, "P"), (18, 18.25, "brk"), (18.25, 20.5, "C"), (20.5, 21, "brk"), (21, 23.5, "P"), (23.5, 23.75, "brk"), (23.75, 25, "E")]
    band = "".join(f'<i class="seg {k}" style="left:{pos(a, 16, 25):.2f}%;width:{pos(b, 16, 25) - pos(a, 16, 25):.2f}%"></i>' for a, b, k in segs)
    days = [("Sun", "11", "Off", ""), ("Mon", "12", "16:00 to 01:00", "Phone and Chat"), ("Tue", "13", "16:00 to 01:00", "Phone"),
            ("Wed", "14", "16:00 to 01:00", "Phone, Chat, Email"), ("Thu", "15", "16:00 to 01:00", "Leave asked, waiting"),
            ("Fri", "16", "17:00 to 02:00", "Swap offered to Associate 18"), ("Sat", "17", "Off", "")]
    rows = "".join(f'<div class="day{" is-today" if d == "Wed" else ""}"><span class="d">{d}<small>{n} Oct</small></span>'
                   f'<span class="s">{s}<small>{note}</small></span>'
                   f'<span>{WAIT if "waiting" in note or "offered" in note else ""}</span></div>'
                   for d, n, s, note in days)
    return f'''<div class="phone" style="position:relative"><div class="ph-top"><h1>My week</h1><small class="dim">11 to 17 Oct</small>{ic("bell")}</div>
<div class="ph-body"><div class="today"><small class="dim">Today, Wednesday</small><span class="fig">16:00 to 01:00</span>
<div class="bandrow">{band}</div><div style="display:flex;justify-content:space-between"><small class="dim">16:00</small><small class="dim">01:00</small></div>
<div class="note"><b>Now on Chat until 20:30.</b> Then lunch, 30 minutes, and Phone from 21:00.</div></div>
<div class="days">{rows}</div><div class="actbar"><span class="btn">{ic("airplane-tilt")}Request leave</span><span class="btn">{ic("arrows-left-right")}Offer a swap</span></div></div>
<nav class="ph-nav"><a class="on" href="#">{ic("calendar-blank")}My week</a><a href="#">{ic("airplane-tilt")}Leave</a><a href="#">{ic("arrows-left-right")}Swaps</a><a href="#">{ic("user-circle")}Me</a></nav>'''


def myweek():
    return page(phone_today() + "</div>", "My week")


def leave_sheet():
    sheet = f'''<div class="scrim" style="position:absolute;padding:0"></div><div class="sheet" role="dialog" aria-label="Request leave"><span class="grab"></span>
<h2>Request leave</h2>
<label class="field">Type<span class="box">Annual leave<span>{ic("caret-right")}</span></span><small>11 days left this year</small></label>
<div class="two"><label class="field">From<span class="box">Thu 15 Oct</span></label><label class="field">To<span class="box">Fri 16 Oct</span></label></div>
<div class="note">Thursday has 2 of 3 places taken, Friday 1 of 3. Your supervisor sees how it changes the floor before deciding.</div>
<label class="field">Note for your supervisor <small>Optional</small><span class="box" style="color:var(--dim)">Family visit</span></label>
<span class="btn solid" style="justify-content:center;padding:.85rem">Send the request</span><span class="btn quiet" style="justify-content:center">Cancel</span></div>'''
    return page(phone_today() + sheet + "</div>", "Request leave")


def swap_sheet():
    sheet = f'''<div class="scrim" style="position:absolute;padding:0"></div><div class="sheet" role="dialog" aria-label="Offer a swap"><span class="grab"></span>
<h2>Offer a swap</h2><small class="dim">Your Friday shift, 17:00 to 02:00. Only people who can take it within the rules are listed.</small>
<div class="mate on"><span><b>Associate 18</b><small>Works 20:00 to 05:00 that day, English, Phone and Chat</small></span>{ic("check-circle")}</div>
<div class="mate"><span><b>Associate 31</b><small>Works 16:00 to 01:00 that day, English, Phone</small></span></div>
<div class="mate"><span><b>Associate 22</b><small>Off that day: takes your shift, you take the day off</small></span></div>
<div class="note">Associate 18 accepts or declines first, then your supervisor approves. Nothing changes before that.</div>
<span class="btn solid" style="justify-content:center;padding:.85rem">Send the offer</span></div>'''
    return page(phone_today() + sheet + "</div>", "Offer a swap")


def board():
    sw = lambda items: '<div class="sw">' + "".join(f'<div><i style="background:{c}"></i><span>{n}<br><b>{h}</b></span></div>' for n, c, h in items) + "</div>"
    base = [("Canvas", "var(--canvas)", "#0C1320 / #EEF2F7"), ("Surface", "var(--surface)", "#121C2B / #FFFFFF"),
            ("Line", "var(--line)", "#24324A / #D3DBE6"), ("Ink", "var(--ink)", "#EBF0F7 / #12203A")]
    state = [("Covered", "var(--covered)", "at target"), ("Short", "var(--short)", "below target"),
             ("Gap", "var(--gap)", "below the floor"), ("Over", "var(--over)", "over-staffed")]
    body = f'''<div class="board"><section class="panel" style="padding:20px;display:flex;flex-direction:column;gap:16px"><h2>Colour</h2>
<small class="dim">The base, night and day. Ink is every action; nothing else is decoration.</small>{sw(base)}
<small class="dim">State, unchanged from Phase Y (measured, colour-blind checked).</small>{sw(state)}
<small class="dim">Channels, unchanged.</small>{sw([("Phone", "var(--phone)", "#3E6FD8"), ("Chat", "var(--chat)", "#B4479A"), ("Email", "var(--email)", "#4D7D8D"), ("Break", "transparent;border:1.5px solid var(--ink)", "ink outline")])}</section>
<section class="panel spec" style="padding:20px;display:flex;flex-direction:column;gap:12px"><h2>Type</h2>
<span class="a">Wednesday on the floor</span><small class="dim">Archivo, wide (width 112, weight 700): headings</small>
<span class="b">21 of 24 &nbsp;18:24 &nbsp;11.1%</span><small class="dim">Archivo, condensed (width 75, weight 650, tabular): every figure</small>
<span class="c">Associate 33 is not in yet. Shift started at 18:00. Mark late or sick.</span><small class="dim">Atkinson Hyperlegible Next: text and labels, built to be read all day</small></section>
<section class="panel" style="padding:20px;display:flex;flex-direction:column;gap:14px;grid-column:1 / -1"><h2>The day strip</h2>
<small class="dim">On every day page, small inside requests and on the phone: one cell per interval, coloured by state, with the live now marker. Click an hour to jump there.</small>
<div style="display:grid;grid-template-columns:minmax(0,1fr) auto;gap:22px;align-items:end"><div class="strip" style="position:relative;padding-top:22px">{strip()}</div></div>
<div style="display:flex;gap:10px;flex-wrap:wrap;align-items:center"><span class="btn solid">{ic("check-circle")}Approve</span><span class="btn">Refuse</span><span class="btn quiet">Cancel</span>
<span class="chip covered">Covered</span><span class="chip short">Waiting</span><span class="chip gap">Day full</span><span class="chip line">Off</span><kbd>Ctrl K</kbd></div>
{tabs("Floor", RTA_TABS)}</section></div>'''
    return page(body, "Design board")


for name, fn in (("board", board), ("rta", rta), ("requests", requests), ("week", week), ("goto", goto),
                 ("myweek", myweek), ("leave", leave_sheet), ("swap", swap_sheet)):
    (HERE / f"{name}.html").write_text(fn(), encoding="utf-8")
print("written")
