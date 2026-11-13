# © 2026 Omar Mokhtar. All rights reserved.
"""Phase BA: what the 3D costs. The same page with and without it (?flat): bytes, compositor layers, CPU time over 6 seconds (Chrome's task, script,
layout and style times), frames drawn in 3 seconds, and the JS heap. Run: python3 measure.py"""
import json, gzip, sys
from pathlib import Path
from playwright.sync_api import sync_playwright
here = Path(__file__).parent; url = "file://" + str(here / "index.html")
def gz(n): return len(gzip.compress((here / n).read_bytes(), 9))
print("bytes gzip: css", gz("max3d.css"), "js", gz("max3d.js"), "html", gz("index.html"))
RATE = int(sys.argv[1]) if len(sys.argv) > 1 else 1
rows = {}
with sync_playwright() as p:
    b = p.chromium.launch(executable_path="/opt/pw-browsers/chromium", args=["--enable-gpu-rasterization"])
    for label, q in (("flat", "?flat"), ("3D", "")):
        ctx = b.new_context(viewport={"width": 1360, "height": 900}); pg = ctx.new_page(); cdp = ctx.new_cdp_session(pg)
        layers = {"n": 0}
        cdp.send("LayerTree.enable"); cdp.on("LayerTree.layerTreeDidChange", lambda e: layers.update(n=len(e.get("layers") or layers["n"] and []) or layers["n"]) if e.get("layers") else None)
        cdp.send("Performance.enable"); cdp.send("Emulation.setCPUThrottlingRate", {"rate": RATE}); pg.goto(url + q); pg.wait_for_timeout(1500)
        m0 = {x["name"]: x["value"] for x in cdp.send("Performance.getMetrics")["metrics"]}
        pg.wait_for_timeout(6000)
        m1 = {x["name"]: x["value"] for x in cdp.send("Performance.getMetrics")["metrics"]}
        frames = pg.evaluate("new Promise(r => { let n = 0; const t0 = performance.now(); function f() { n++; if (performance.now() - t0 < 3000) requestAnimationFrame(f); else r(n); } requestAnimationFrame(f); })")
        d = lambda k: round((m1[k] - m0[k]) * 1000)
        rows[label] = dict(layers=layers["n"], task_ms=d("TaskDuration"), script_ms=d("ScriptDuration"), layout_ms=d("LayoutDuration"), style_ms=d("RecalcStyleDuration"), frames_3s=frames, heap_kb=round(m1["JSHeapUsedSize"] / 1024))
        ctx.close()
    b.close()
print("CPU slowed", RATE, "x"); print(json.dumps(rows))
