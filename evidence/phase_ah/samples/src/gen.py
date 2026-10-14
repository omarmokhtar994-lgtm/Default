# © 2026 Omar Mokhtar. All rights reserved.
"""Phase AH samples (not the site): the Weeks page's "Hours needed" table and the export, from real figures of the
review week (data.json, made by the review server's DayBook with a few people sick on Thu, Fri and Sat).

python gen.py <data.json> <out dir>   writes ah01_hours_needed.html (night and day looks are screenshot by shots.py)
and ah02_export.xlsx."""
import html
import json
import sys
from datetime import date
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill

SITE = Path(__file__).resolve().parents[4] / "webapp" / "static"
data = json.loads(Path(sys.argv[1]).read_text())
out = Path(sys.argv[2])
target, step = data["target"], data["step"]


def hm(m):
    m %= 1440
    return f"{m // 60:02d}:{m % 60:02d}"


def band(c):
    if c["req"] <= 0:
        return "none"
    share = c["now"] / c["req"]
    return "ok" if share >= 1 - 1e-9 else "warn" if share >= target - 1e-9 else "bad"


def hours(c):
    return round(max(0.0, (c["req"] - c["now"]) * step / 60) * 4) / 4  # to the quarter hour


days = []
for d in data["days"]:
    on = date.fromisoformat(d["date"])
    ot = {t for o in d["overtime"] for t in range(o["start"], o["end"], step)}
    do = {t for p in d["proposals"] for t in range(p["start"], p["end"], step)}
    cells = {c["t"]: dict(c, band=band(c), hours=hours(c), pct=int(100 * c["now"] / c["req"] + 1e-9) if c["req"] else None,
                          fix=" + ".join(x for x, inside in (("Day off", c["t"] in do and hours(c) > 0), ("OT", c["t"] in ot)) if inside))
             for c in d["cells"]}
    days.append({"on": on, "cells": cells, "d": d})

rows, fold = [], []
for t in range(0, 1440, step):
    if all(x["cells"][t]["band"] in ("ok", "none") for x in days):
        fold.append(t)
        continue
    if fold:
        rows.append(("fold", fold[0], fold[-1] + step)); fold = []
    rows.append(("row", t, None))
if fold:
    rows.append(("fold", fold[0], fold[-1] + step))

esc = html.escape
counts = {"all": sum(1 for x in days for c in x["cells"].values() if c["hours"] > 0),
          "ot": sum(1 for x in days for c in x["cells"].values() if "OT" in c["fix"]),
          "do": sum(1 for x in days for c in x["cells"].values() if "Day off" in c["fix"])}
head = "".join(f"<th scope='col'>{x['on']:%a %d}</th>" for x in days)
body = []
for kind, a, b in rows:
    if kind == "fold":
        body.append(f"<tr class='fold'><th scope='row'>{hm(a)} to {hm(b)}</th><td colspan='7'>Every day at 100% or more</td></tr>")
        continue
    tds = []
    for x in days:
        c = x["cells"][a]
        if c["band"] == "none":
            tds.append("<td class='hn none'></td>")
        elif c["hours"] <= 0:
            tds.append(f"<td class='hn ok'><small>{c['pct']}%</small></td>")
        else:
            tag = f"<i class='fx'>{c['fix']}</i>" if c["fix"] else ""
            tds.append(f"<td class='hn {c['band']}'><b>{c['hours']:g} h</b><small>{c['pct']}%</small>{tag}</td>")
    body.append(f"<tr><th scope='row'>{hm(a)}</th>{''.join(tds)}</tr>")
tot = lambda f: "".join(f"<td>{f(x)}</td>" for x in days)
need_of = lambda x: sum(c["hours"] for c in x["cells"].values())
foot = (f"<tr><th scope='row'>Hours needed</th>{tot(lambda x: format(need_of(x), 'g') + ' h')}</tr>"
        f"<tr><th scope='row'>Below {target:.0%}</th>{tot(lambda x: sum(1 for c in x['cells'].values() if c['band'] == 'bad'))}</tr>"
        f"<tr><th scope='row'>{target:.0%} to 99%</th>{tot(lambda x: sum(1 for c in x['cells'].values() if c['band'] == 'warn'))}</tr>")


def person(c):
    bits = [c["note"]] if c["note"] else []
    bits += c["bends"] or ["keeps every rule"]
    return f"<li><b>{esc(c['name'])}</b> <span class='dim'>{esc('; '.join(bits))}</span></li>"


cards = []
for x in days:
    need = sum(c["hours"] for c in x["cells"].values())
    if need <= 0:
        continue
    d = x["d"]
    if d["proposals"]:
        verdict = (f"Better: cancel {sum(p['people'] for p in d['proposals'])} day off, then overtime for what is left. "
                   f"A day off covers {sum(p['intervals'] for p in d['proposals'])} short intervals in one shift; the "
                   f"same by overtime would need about {sum(min(1, x['cells'][t]['hours']) for p in d['proposals'] for t in range(p['start'], p['end'], step)):g} "
                   "hours of overtime spread over several people.")
    else:
        verdict = ("Overtime is enough: no day off to cancel would cover 6 short intervals, so cancelling one would "
                   "waste most of the shift.")
    parts = [f"<h3>{x['on']:%A %d %b}: {need:g} hours needed</h3><p class='verdict'>{esc(verdict)}</p>"]
    for p in d["proposals"]:
        parts.append(f"<h4>{esc(p['text'])}</h4><p class='dim'>Covers {esc(p['covers'])}. Pick one:</p>"
                     f"<ul class='names'>{''.join(person(c) for c in p['candidates'])}</ul>")
    if d["overtime"]:
        parts.append("<h4>Overtime</h4><ul class='ot'>" + "".join(
            f"<li><b>{esc(o['text'])}</b>: " + ", ".join(f"{esc(f['name'])} <span class='dim'>({esc(f['text'])})</span>"
                                                         for f in o["offers"][:3]) + "</li>" for o in d["overtime"]) + "</ul>")
    cards.append(f"<article class='sug'>{''.join(parts)}</article>")

page = f"""<!doctype html><html lang="en" data-theme="THEME"><head><meta charset="utf-8">
<link rel="stylesheet" href="{SITE.as_uri()}/app.css"><link rel="stylesheet" href="{SITE.as_uri()}/icons.css">
<style>
body {{ padding: 24px 28px; }} .wrap {{ max-width: 1240px; }}
.bar {{ display: flex; flex-wrap: wrap; gap: 10px 18px; align-items: center; margin: 10px 0 14px; }}
.seg {{ display: inline-flex; border: 1px solid var(--edge); border-radius: 8px; overflow: hidden; }}
.seg span {{ padding: 7px 12px; }} .seg .on {{ background: var(--action); color: var(--on-action); font-weight: 700; }}
.chip {{ padding: 6px 12px; border: 1px solid var(--edge); border-radius: 999px; }} .chip.on {{ background: var(--selected); border-color: var(--action); font-weight: 700; }}
.legend {{ display: flex; gap: 16px; flex-wrap: wrap; color: var(--dim); font-size: .875rem; margin: 0 0 10px; }}
.legend i {{ display: inline-block; width: 14px; height: 14px; border-radius: 3px; vertical-align: -2px; margin-right: 6px; }}
.k-ok {{ background: var(--covered); }} .k-warn {{ background: var(--short); }} .k-bad {{ background: var(--gap); }}
table.hours {{ border-collapse: separate; border-spacing: 3px; width: 100%; font-variant-numeric: tabular-nums; }}
.hours th {{ text-align: left; padding: 4px 8px; white-space: nowrap; }} .hours thead th {{ color: var(--dim); font-weight: 600; }}
.hn {{ border-radius: 6px; padding: 5px 8px; height: 38px; vertical-align: top; position: relative; min-width: 120px; }}
.hn b {{ font: 700 semi-condensed 1.05rem var(--display); }} .hn small {{ display: block; color: var(--dim); font-size: .75rem; }}
.hn.ok {{ background: var(--covered-soft); }} .hn.ok small {{ color: var(--covered-text); }}
.hn.warn {{ background: var(--short-soft); box-shadow: inset 3px 0 0 var(--short); }} .hn.warn b {{ color: var(--short-ink); }}
.hn.bad {{ background: var(--gap-soft); box-shadow: inset 3px 0 0 var(--gap); }} .hn.bad b {{ color: var(--gap-ink); }}
.hn.none {{ background: transparent; }}
.fx {{ position: absolute; right: 6px; top: 6px; font-style: normal; font-size: .6875rem; font-weight: 700; padding: 1px 6px; border-radius: 999px; border: 1px solid var(--edge); }}
tr.fold th, tr.fold td {{ color: var(--dim); font-size: .8125rem; padding: 6px 8px; }}
tfoot th, tfoot td {{ border-top: 1px solid var(--rail); padding: 6px 8px; font-weight: 600; }}
.sugs {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(380px, 1fr)); gap: 14px; margin-top: 18px; }}
.sug {{ background: var(--console); border: 1px solid var(--rail); border-radius: 12px; padding: 14px 18px; }}
.sug h3 {{ margin: 0 0 6px; font-size: 1.1rem; }} .sug h4 {{ margin: 12px 0 4px; font-size: .95rem; }}
.verdict {{ background: var(--console-2); border-radius: 8px; padding: 8px 10px; margin: 0; }}
.names, .ot {{ margin: 4px 0 0; padding-left: 18px; }} .dim {{ color: var(--dim); }}
</style></head><body><div class="wrap">
<h1>Weeks</h1>
<p class="byline">{esc(data['program'])}, week of {date.fromisoformat(data['week']):%a %d %b}. The week's target: {target:.0%} of each interval's demand.</p>
<section class="panel"><h2>Hours needed</h2>
<div class="bar"><span class="seg"><span class="on">As recorded on the RTA</span><span>As planned</span></span>
<span class="chip on">All short intervals ({counts['all']})</span><span class="chip">Overtime needed ({counts['ot']})</span><span class="chip">Cancel a day off ({counts['do']})</span>
<a class="button" href="#">Download this table</a></div>
<p class="legend"><span><i class="k-ok"></i>100% or more</span><span><i class="k-warn"></i>{target:.0%} to 99% (at the target, short of 100%)</span><span><i class="k-bad"></i>Below {target:.0%} (below the target)</span><span>Each cell: hours needed to reach 100%, and the share on the floor</span></p>
<table class="hours"><thead><tr><th scope="col">Interval</th>{head}</tr></thead><tbody>{''.join(body)}</tbody><tfoot>{foot}</tfoot></table>
</section>
<h2 style="margin-top:22px">What to do</h2>
<div class="sugs">{''.join(cards)}</div>
<p class="dim">Counted as the RTA records it: sick and absences, overtime and called-in days, aux and shrinkage. Thu, Fri and Sat have people marked sick on the RTA.</p>
</div></body></html>"""
for theme in ("dark", "light"):
    (out / f"ah01_hours_needed_{theme}.html").write_text(page.replace("THEME", theme), encoding="utf-8")

# the export: the same table, the same colours, the suggestions on a second sheet
wb = Workbook(); ws = wb.active; ws.title = "Hours needed"
fills = {"ok": "D5F2EE", "warn": "FBE9C9", "bad": "F8D3D0"}
ws.append([f"{data['program']}, week of {data['week']}. Target {target:.0%}. Hours needed to reach 100%; share on the floor."])
ws.append(["Interval"] + [f"{x['on']:%a %d %b}" for x in days])
for kind, a, b in rows:
    if kind == "fold":
        ws.append([f"{hm(a)} to {hm(b)}", "Every day at 100% or more"]); continue
    line = [hm(a)]
    for x in days:
        c = x["cells"][a]
        line.append("" if c["band"] == "none" else f"{c['pct']}%" if c["hours"] <= 0 else
                    f"{c['hours']:g} h ({c['pct']}%){' ' + c['fix'] if c['fix'] else ''}")
    ws.append(line)
    for i, x in enumerate(days):
        c = x["cells"][a]
        if c["band"] in fills:
            ws.cell(ws.max_row, i + 2).fill = PatternFill("solid", fgColor=fills[c["band"]])
ws.append(["Hours needed"] + [sum(c["hours"] for c in x["cells"].values()) for x in days])
ws.column_dimensions["A"].width = 16
for col in "BCDEFGH":
    ws.column_dimensions[col].width = 20
ws["A1"].font = Font(bold=True)
s2 = wb.create_sheet("What to do"); s2.append(["Day", "Action", "Covers", "People"])
for x in days:
    for p in x["d"]["proposals"]:
        s2.append([f"{x['on']:%a %d %b}", p["text"], p["covers"], ", ".join(c["name"] for c in p["candidates"])])
    for o in x["d"]["overtime"]:
        s2.append([f"{x['on']:%a %d %b}", "Overtime " + o["text"], "", ", ".join(f"{f['name']} ({f['text']})" for f in o["offers"][:3])])
for col, w in zip("ABCD", (14, 34, 30, 90)):
    s2.column_dimensions[col].width = w
wb.save(out / "ah02_export.xlsx")
print("written")
