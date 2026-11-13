# © 2026 Omar Mokhtar. All rights reserved.
"""Phase BI samples: three pages of the volumes feature drawn with the site's own shell and charts and made-up "Program 01" numbers from the new
core (webapp/erlang.py, webapp/forecast.py). Nothing here is built into the site; these are pictures for the owner to approve first.
Run from the repository root with the web venv: python evidence/phase_bi/samples/src/make_samples.py OUT_DIR"""
import random
import sys
import threading
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, ".")
from flask import render_template_string  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402
from werkzeug.serving import make_server  # noqa: E402

from webapp import charts, erlang, forecast  # noqa: E402
from webapp.tests.test_runs import make_app  # noqa: E402

OUT = Path(sys.argv[1])
OUT.mkdir(parents=True, exist_ok=True)
STEP, SLOTS = 30, 48
DAYS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]
PY = {"Sun": 6, "Mon": 0, "Tue": 1, "Wed": 2, "Thu": 3, "Fri": 4, "Sat": 5}
rng = random.Random(5)


def hm(i):
    return f"{i * STEP // 60:02d}:{i * STEP % 60:02d}"


def curve(wd):
    """A made-up double hump; weekends lighter and shorter."""
    out = []
    for i in range(SLOTS):
        h = i / 2
        v = 0.0
        if 6 <= h < 22:
            v = 0.25 + 1.0 * pow(2.718, -((h - 10.5) ** 2) / 8) + 0.8 * pow(2.718, -((h - 15.5) ** 2) / 10)
        out.append(v * (0.6 if wd >= 5 else 1.0))
    return out


TODAY = date(2026, 11, 3)
NEXT_SUN = date(2026, 11, 8)
week_totals_true = [11200, 11400, 11650, 11900, 11800, 12150, 12400, 12480]
history = {}
for w, tot in enumerate(week_totals_true[:-1]):  # seven weeks of actuals before the week just finished
    sun = NEXT_SUN - timedelta(weeks=len(week_totals_true) - w - 0)
    for d in range(7):
        day = sun + timedelta(days=d)
        shape = [v for v in curve(day.weekday())]
        total = tot * (0.17 if day.weekday() in (0, 1) else 0.15 if day.weekday() in (2, 3, 4) else 0.11 if day.weekday() == 5 else 0.12) * rng.uniform(0.96, 1.04)
        s = sum(shape)
        history[day] = [total * v / s * rng.uniform(0.93, 1.07) for v in shape]
profile = forecast.build_profile(history, STEP, weeks=8, today=NEXT_SUN - timedelta(days=0))
suggest = forecast.suggest_total([sum(sum(history[d] for d in [x]) if False else 0 for x in []) or t for t in week_totals_true[:-1]])
WEEK_TOTAL = 12600
week = forecast.forecast_week(WEEK_TOTAL, profile)
AHT, SL, TH, SHR, OCC = 300, 0.80, 20, 0.32, 0.88


def agents(calls):
    return erlang.agents_needed(calls, AHT, STEP * 60, SL, TH, OCC)


def fte(calls):
    return erlang.fte_required(agents(calls), SHR)


app, store, *_ = make_app(start_worker=False)
store.add_user("omar", "Omar Mokhtar", "Owner-pass-123", is_admin=True, must_change=False)
from webapp.programs import ProgramBook  # noqa: E402
ProgramBook(store).add_lob(ProgramBook(store).add_program("Program 01"), "Voice")

BASE = """{% extends "base.html" %}{% block title %}Volumes on Team Scheduler{% endblock %}{% block content %}"""
TABS = """<nav class="bp-days" aria-label="Volumes"><a href="#">Actuals</a><a href="#"{a2}>Forecast and needs</a><a href="#"{a3}>How we did</a></nav>"""


def tile(label, value, note=""):
    return f'<p class="tile"><span class="tile-label">{label}</span><b>{value}</b>{note}</p>'


def forecast_page():
    mon = week[PY["Mon"]]
    rows = []
    for i in range(12, 46):
        calls = mon[i]
        a = agents(calls)
        e = erlang.erlangs(calls, AHT, STEP * 60)
        sl = erlang.service_level(a, calls, AHT, STEP * 60, TH) * 100 if calls else 100
        rows.append(f"<tr><th scope=row>{hm(i)}</th><td>{profile.shares[PY['Mon']][i] * 100:.1f}%</td><td>{calls}</td><td>{e:.1f}</td>"
                    f"<td><b>{a}</b></td><td>{erlang.fte_required(a, SHR):.1f}</td><td>{sl:.0f}%</td></tr>")
    day_rows = "".join(
        f"<tr><th scope=row>{d}</th><td>{profile.day_shares[PY[d]] * 100:.1f}%</td><td>{sum(week[PY[d]]):,}</td><td><input type=text value='' placeholder='{sum(week[PY[d]]):,}' aria-label='{d} calls'></td>"
        f"<td>{max(agents(c) for c in week[PY[d]])}</td></tr>" for d in DAYS)
    chart = charts.lines([hm(i) for i in range(12, 46)], [("Forecast calls, Monday", charts.BLUE, [mon[i] for i in range(12, 46)])],
                         y_max=int(max(mon) * 1.2), unit="", label="Forecast calls, Monday") + charts.lines(
        [hm(i) for i in range(12, 46)], [("Needed on the floor, Monday", charts.ORANGE, [agents(mon[i]) for i in range(12, 46)])],
        y_max=max(agents(c) for c in mon) + 4, unit="", label="People needed on the floor, Monday")
    mid, lo, hi = suggest if suggest else (0, 0, 0)
    return BASE + f"""
<div class="phead"><div><h1>Volumes: forecast and people needed</h1>
<p class="byline">Program 01, Voice. Type the calls you expect for the week; the site spreads them over days and intervals the way this program's last eight weeks did, and works out the people needed on the floor with Erlang C. <b>Sample with made-up numbers.</b></p></div></div>
{TABS.format(a2=' class="on" aria-current="page"', a3='')}
<form class="panel ins-filter" aria-label="Choose the week"><div class="exp-row">
  <label>Program <select><option>Program 01, Voice</option></select></label>
  <label>Channel <select><option>Phone</option><option>Chat</option><option>Email</option></select></label>
  <label>Week starting <select><option>Sun 08 Nov 2026</option></select></label>
  <label>Calls expected this week <input type="text" inputmode="numeric" value="{WEEK_TOTAL:,}" aria-describedby="sug"></label>
</div>
<p id="sug" class="dim">Suggested {mid:,} calls ({lo:,} to {hi:,}) from the last {len(week_totals_true) - 1} weeks: {week_totals_true[-2]:,} last week, climbing about 1.5% a week. <button type="button" class="quiet">Use the suggestion</button></p>
<p><button class="primary" type="submit">Work it out</button> <button type="button">Save this forecast</button></p></form>
<section class="tiles" aria-label="The week in numbers">
 {tile('Calls forecast', f'{WEEK_TOTAL:,}', '<small>Sun 08 to Sat 14 Nov</small>')}
 {tile('Busiest interval', f'Mon {hm(max(range(SLOTS), key=lambda i: mon[i]))}', f'<small>{max(mon)} calls</small>')}
 {tile('Needed on the floor at the peak', f'{max(agents(c) for d in week.values() for c in d)}', '<small>FT Wise; the engine adds shrinkage</small>')}
 {tile('Hours needed on the floor', f'{sum(agents(c) for d in week.values() for c in d) / 2:,.0f} h', f'<small>{sum(fte(c) for d in week.values() for c in d) / 2:,.0f} h with 32% shrinkage</small>')}
</section>
<div class="panel"><h2>Days</h2><p class="dim">Share of the week from the last 8 weeks ({', '.join(str(profile.weeks_used[PY[d]]) for d in DAYS)} weeks used per day). Type a day's calls to fix it; the rest share what is left.</p>
<table class="edgrid"><thead><tr><th scope=col>Day</th><th scope=col>Usual share</th><th scope=col>Calls</th><th scope=col>Your number</th><th scope=col>Peak agents</th></tr></thead><tbody>{day_rows}</tbody></table>
<p class="dim">Left out of the shape: {', '.join(d for d, _ in profile.excluded) or 'no days'}. Thin history on: {', '.join(DAYS[[PY[x] for x in DAYS].index(w)] for w in profile.thin) or 'none'}.</p></div>
<div class="panel"><h2>Monday, interval by interval</h2>
<p class="dim">Phone, 30 minutes. AHT 300 s, service level 80% in 20 s, occupancy at most 88%. The download's FT Wise tab is the number needed on the floor; the engine adds the program's own shrinkage when it builds the schedule. Erlang C: one queue, nobody abandons, so it can over-staff where callers do abandon.</p>
{chart}
<div class="scroll panel-scroll" role="region" tabindex="0" aria-label="Monday by interval (scrolls)"><table class="edgrid"><thead><tr><th scope=col>Interval</th><th scope=col>Share of day</th><th scope=col>Calls</th><th scope=col>Erlangs</th><th scope=col>Needed on the floor (FT Wise)</th><th scope=col>With 32% shrinkage</th><th scope=col>Service level</th></tr></thead><tbody>{''.join(rows)}</tbody></table></div>
<p><a class="button" href="#">Download the requirement tabs (Excel)</a> <span class="dim">FT Wise 30 Min and Phone 30 Min, laid out for the input workbook.</span></p></div>
{{% endblock %}}"""


def how_page():
    last = week
    actual = {d: [max(0, round(c * rng.uniform(0.9, 1.22) * (1.07 if 8 <= i / 2 < 12 else 1.0))) for i, c in enumerate(last[d])] for d in range(7)}
    otf_days = []
    for d in DAYS:
        a, f = sum(actual[PY[d]]), sum(last[PY[d]])
        o = forecast.otf(a, f)
        otf_days.append((d, a, f, o, forecast.band(o)))
    day = PY["Mon"]
    a_mon, f_mon = actual[day], last[day]
    system = [round(max(0.0, agents(c) * 0.97 + rng.uniform(-0.5, 0.5)), 1) for c in f_mon]   # what the schedule's requirement tab said (needed on the floor)
    at_actual = [float(agents(c)) for c in a_mon]
    scheduled = [round(max(0.0, s / (1 - SHR) * rng.uniform(0.95, 1.08)), 1) for s in system]  # people on shift, before breaks and absences
    floor = [round(max(0.0, s * rng.uniform(0.9, 1.08)), 1) for s in system]
    sl_model = [erlang.service_level(int(f + 0.5), a_mon[i], AHT, STEP * 60, TH) * 100 if a_mon[i] else None for i, f in enumerate(floor)]
    idx = list(range(12, 46))
    c1 = charts.lines([hm(i) for i in idx], [("Forecast", charts.BLUE, [f_mon[i] for i in idx]), ("Actual", charts.ORANGE, [a_mon[i] for i in idx])],
                      y_max=int(max(a_mon) * 1.15), unit="", label="Calls, forecast and actual, Monday")
    c2 = charts.lines([hm(i) for i in idx], [("Needed in the system", charts.BLUE, [system[i] for i in idx]), ("Needed at actual calls", charts.AQUA, [at_actual[i] for i in idx]),
                                             ("On shift", charts.YELLOW, [scheduled[i] for i in idx]), ("On the floor", charts.ORANGE, [floor[i] for i in idx])],
                      y_max=int(max(at_actual + scheduled) * 1.15), unit="", label="People needed, scheduled and on the floor, Monday")
    c3 = charts.lines([hm(i) for i in idx], [("Service level the staffing gave (modelled)", charts.AQUA, [sl_model[i] for i in idx]), ("Target 80%", charts.BLUE, [80] * len(idx))],
                      y_max=100, unit="%", label="Modelled service level, Monday")
    weeks_otf = [98.2, 101.5, 99.4, 103.8, 104.9, 100.7, 102.3, forecast.otf_total([sum(actual[d]) for d in range(7)], [sum(last[d]) for d in range(7)])]
    c0 = charts.columns([f"wk {n}" for n in range(37, 45)], weeks_otf, unit="%", label="Offered over forecast, last 8 weeks", y_max=120)
    day_rows = "".join(
        f"<tr><th scope=row>{d}</th><td>{f:,}</td><td>{a:,}</td><td class='ot-{b}'>{'-' if o is None else f'{o:.0f}%'}</td><td>{'under the forecast' if b == 'under' else 'more than forecast' if b == 'over' else 'on target'}</td></tr>"
        for d, a, f, o, b in otf_days)
    week_otf = forecast.otf_total([sum(actual[d]) for d in range(7)], [sum(last[d]) for d in range(7)])
    return BASE + f"""
<div class="phead"><div><h1>Volumes: how did we do</h1>
<p class="byline">Program 01, Voice, week of Sun 01 Nov 2026. Offered against the forecast, and the people needed at the calls that really came, against what the schedule's requirement said and who was on the floor. <b>Sample with made-up numbers.</b></p></div></div>
{TABS.format(a2='', a3=' class="on" aria-current="page"')}
<section class="tiles" aria-label="The week in numbers">
 {tile('Offered over forecast', f'{week_otf:.0f}%', '<small>within 90 to 110%: on target</small>')}
 {tile('Calls offered', f'{sum(sum(v) for v in actual.values()):,}', f'<small>forecast {WEEK_TOTAL:,}</small>')}
 {tile('Intervals within 90 to 110%', f'{sum(1 for d in range(7) for i in range(SLOTS) if last[d][i] and forecast.band(forecast.otf(actual[d][i], last[d][i])) == "on") * 100 // sum(1 for d in range(7) for i in range(SLOTS) if last[d][i])}%', '<small>of intervals with a forecast</small>')}
 {tile('Modelled service level', f'{sum(s for s in sl_model if s is not None) / len([s for s in sl_model if s is not None]):.0f}%', '<small>Monday, from staffing and calls</small>')}
</section>
<div class="panel"><h2>Offered over forecast, last 8 weeks</h2>{c0}</div>
<div class="panel"><h2>Days</h2><table class="edgrid"><thead><tr><th scope=col>Day</th><th scope=col>Forecast</th><th scope=col>Offered</th><th scope=col>Offered over forecast</th><th scope=col>Reading</th></tr></thead><tbody>{day_rows}</tbody></table></div>
<div class="panel"><h2>Monday, interval by interval</h2><h3>Calls</h3>{c1}<h3>People</h3>
<p class="dim">Needed in the system: the requirement tab of the schedule in use. Needed at actual calls: Erlang C on the calls that came and the AHT. On shift: the schedule. On the floor: the RTA's day, after breaks, absences and aux.</p>{c2}
<h3>Service level</h3><p class="dim">The ACD's own service level is not in the upload, so this is modelled: Erlang C on the people on the floor and the calls and AHT that came. It reads high where callers abandon.</p>{c3}</div>
<p class="dim">For a program counted by interval compliance the Erlang lines and the service level are left out: it shows calls, OTF and the system's requirement against the floor.</p>
{{% endblock %}}"""


def interval_page():
    weeks_otf = [98.2, 101.5, 99.4, 103.8, 104.9, 100.7, 102.3, 103.1]
    c0 = charts.columns([f"wk {n}" for n in range(37, 45)], weeks_otf, unit="%", label="Offered over forecast, last 8 weeks", y_max=120)
    peaks = [18.0, 18.5, 19.0, 19.5, 19.0, 20.5, 21.0, 21.5]
    need = [17.5, 17.5, 18.5, 19.0, 19.0, 20.0, 20.0, 20.5]
    floor = [17.8, 17.9, 18.4, 18.2, 18.7, 19.6, 20.9, 20.4]
    c1 = charts.lines([f"wk {n}" for n in range(37, 45)], [("Busiest interval: needed (system)", charts.BLUE, need), ("Busiest interval: on the floor", charts.ORANGE, floor)],
                      y_max=24, unit="", label="Busiest interval, needed and on the floor, 8 weeks")
    return BASE + f"""
<div class="phead"><div><h1>Volumes: how did we do</h1>
<p class="byline">Program 02, Chat, counted by interval compliance: trends only, no Erlang. <b>Sample with made-up numbers.</b></p></div></div>
{TABS.format(a2='', a3=' class="on" aria-current="page"')}
<section class="tiles" aria-label="The week in numbers">
 {tile('Offered over forecast', '103%', '<small>on target (90 to 110%)</small>')}
 {tile('Chats offered', '6,420', '<small>forecast 6,230</small>')}
 {tile('Intervals at 100% or more', '91%', '<small>of the system requirement, on the floor</small>')}
 {tile('Weeks over forecast', '5 of 8', '<small>about 3% over on average</small>')}
</section>
<div class="panel"><h2>Offered over forecast, last 8 weeks</h2>{c0}</div>
<div class="panel"><h2>The busiest interval of each week</h2>{c1}<p class="dim">Needed is the schedule's own requirement tab; nothing is recomputed for a program counted by interval compliance.</p></div>
{{% endblock %}}"""


pages = {"forecast": forecast_page(), "howdid": how_page(), "interval": interval_page()}
for name, src in pages.items():
    app.add_url_rule(f"/_sample/{name}", f"sample_{name}", (lambda s: (lambda: render_template_string(s)))(src))
server = make_server("127.0.0.1", 0, app, threaded=True)
base = f"http://127.0.0.1:{server.server_port}"
threading.Thread(target=server.serve_forever, daemon=True).start()
with sync_playwright() as p:
    b = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
    for scheme in ("dark", "light"):
        ctx = b.new_context(viewport={"width": 1320, "height": 900}, color_scheme=scheme)
        pg = ctx.new_page()
        pg.goto(base + "/login"); pg.fill("input[name=username]", "omar"); pg.fill("input[name=password]", "Owner-pass-123")
        with pg.expect_navigation(): pg.keyboard.press("Enter")
        for name in pages:
            pg.goto(f"{base}/_sample/{name}"); pg.wait_for_load_state("networkidle")
            pg.screenshot(path=str(OUT / f"bi_{name}_{scheme}.png"), full_page=True)
        ctx.close()
    b.close()
print("done", sorted(p.name for p in OUT.iterdir()))
