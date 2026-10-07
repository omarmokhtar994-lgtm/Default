# © 2026 Omar Mokhtar. All rights reserved.
"""Small server-side SVG charts for the analytics pages.

No chart library: the page's CSP allows scripts from the site only, and an
SVG drawn here needs no script to show. Every mark carries a ``data-tip``
(the site's tooltip shows it on hover or tap; the numbers are also in each
chart's table view). Series colours are the palette validated on the dark
surface #15243A; text uses the page's ink colours through CSS classes, never
a series colour. Labels and names are escaped.
"""
from __future__ import annotations

import math
from typing import List, Optional, Sequence, Tuple

from markupsafe import Markup, escape

BLUE, AQUA, ORANGE, YELLOW = "#3987e5", "#199e70", "#d95926", "#c98500"
HEAT = ("#1f3350", "#4a3a2c", "#7a4224", "#a94b22", "#d95926")  # one hue, faint to strong
W, BAR_MAX, RADIUS = 640, 24, 4
EMPTY = Markup('<p class="chart-empty">No data yet</p>')


def _num(value: float) -> str:
    value = round(value, 1)
    return str(int(value)) if float(value).is_integer() else str(value)


def _change(delta: Optional[float]) -> str:
    if delta is None:
        return ""
    if delta > 0:
        return f" (up {_num(delta)})"
    if delta < 0:
        return f" (down {_num(abs(delta))})"
    return " (unchanged)"


def _svg(height: int, label: str, body: List[str]) -> Markup:
    return Markup(f'<svg class="chart" viewBox="0 0 {W} {height}" role="img" aria-label="{escape(label)}" '
                  f'preserveAspectRatio="xMidYMid meet">' + "".join(body) + "</svg>")


def nice(top: float) -> float:
    if top <= 0:
        return 1
    step = 10 ** math.floor(math.log10(top))
    for m in (1, 2, 2.5, 5, 10):
        if top <= m * step:
            return m * step
    return 10 * step


def _every(n: int, room: int) -> int:
    return max(1, math.ceil(n / room))


def columns(labels: Sequence[str], values: Sequence[Optional[float]], unit: str = "",
            deltas: Optional[Sequence[Optional[float]]] = None, colour: str = BLUE,
            label: str = "Column chart", y_max: Optional[float] = None) -> Markup:
    """One column per label, from a zero baseline; the change from the previous
    column is in the tip."""
    if not labels or all(v is None for v in values):
        return EMPTY
    h, left, right, top, bottom = 220, 44, 12, 22, 30
    plot_w, plot_h = W - left - right, h - top - bottom
    y_max = y_max or nice(max(v for v in values if v is not None) * 1.1)
    slot = plot_w / len(labels)
    bar = min(BAR_MAX, slot * 0.6)
    base = top + plot_h
    out = []
    for t in (0, y_max / 2, y_max):
        y = base - plot_h * t / y_max
        out.append(f'<line class="grid" x1="{left}" x2="{W - right}" y1="{y:.1f}" y2="{y:.1f}"/>'
                   f'<text class="ax" x="{left - 6}" y="{y + 4:.1f}" text-anchor="end">{_num(t)}</text>')
    every = _every(len(labels), 10)
    for i, (name, value) in enumerate(zip(labels, values)):
        cx = left + slot * (i + 0.5)
        if i % every == 0 or i == len(labels) - 1:
            out.append(f'<text class="ax" x="{cx:.1f}" y="{h - 10}" text-anchor="middle">{escape(name)}</text>')
        if value is None:
            continue
        bh = max(plot_h * value / y_max, 1 if value else 0)
        x = cx - bar / 2
        tip = f"{name}: {_num(value)}{unit}{_change(deltas[i] if deltas else None)}"
        if bh:
            out.append(f'<rect class="bar" x="{x:.1f}" y="{base - bh:.1f}" width="{bar:.1f}" height="{bh:.1f}" '
                       f'rx="{RADIUS}" fill="{colour}"/>')
            if bh > RADIUS:  # square foot: the bar sits on the baseline, only its data end is rounded
                out.append(f'<rect x="{x:.1f}" y="{base - RADIUS:.1f}" width="{bar:.1f}" height="{RADIUS}" '
                           f'fill="{colour}"/>')
        if len(labels) <= 12:
            out.append(f'<text class="val" x="{cx:.1f}" y="{base - bh - 6:.1f}" text-anchor="middle">'
                       f'{_num(value)}</text>')
        out.append(f'<rect class="hit" x="{cx - slot / 2:.1f}" y="{top}" width="{slot:.1f}" height="{plot_h}" '
                   f'data-tip="{escape(tip)}"/>')
    return _svg(h, label, out)


def lines(labels: Sequence[str], series: Sequence[Tuple[str, str, Sequence[Optional[float]]]],
          y_max: float = 100, unit: str = "%", y_min: Optional[float] = None,
          label: str = "Line chart") -> Markup:
    """Lines on one axis; a missing value breaks the line (nothing is drawn for
    it). A legend appears for two or more series."""
    points = [v for _, _, vals in series for v in vals if v is not None]
    if not labels or not points:
        return EMPTY
    if y_min is None:  # zoom in on the band the values use; the axis says where it starts
        y_min = max(0.0, min(y_max - 10, math.floor((min(points) - 5) / 10) * 10))
    legend = len(series) > 1
    h, left, right, top, bottom = 230, 44, 50, 34 if legend else 14, 30
    plot_w, plot_h = W - left - right, h - top - bottom
    slot = plot_w / len(labels)

    def xy(i: int, v: float) -> Tuple[float, float]:
        v = min(max(v, y_min), y_max)
        return left + slot * (i + 0.5), top + plot_h * (1 - (v - y_min) / (y_max - y_min))

    out = []
    for t in (y_min, (y_min + y_max) / 2, y_max):
        y = xy(0, t)[1]
        out.append(f'<line class="grid" x1="{left}" x2="{W - right}" y1="{y:.1f}" y2="{y:.1f}"/>'
                   f'<text class="ax" x="{left - 6}" y="{y + 4:.1f}" text-anchor="end">{_num(t)}{escape(unit)}</text>')
    every = _every(len(labels), 10)
    for i, name in enumerate(labels):
        if i % every == 0 or i == len(labels) - 1:
            out.append(f'<text class="ax" x="{xy(i, y_min)[0]:.1f}" y="{h - 10}" text-anchor="middle">'
                       f'{escape(name)}</text>')
        parts = [f"{s} {_num(vals[i])}{unit}" for s, _, vals in series if i < len(vals) and vals[i] is not None]
        if parts:  # crosshair column: every series at this week in one tip
            out.append(f'<rect class="hit" x="{xy(i, y_min)[0] - slot / 2:.1f}" y="{top}" width="{slot:.1f}" '
                       f'height="{plot_h}" data-tip="{escape(name + ": " + " · ".join(parts))}"/>')
    for s, colour, vals in series:
        path, pen = [], "M"
        for i, v in enumerate(vals):
            if v is None:
                pen = "M"
                continue
            x, y = xy(i, v)
            path.append(f"{pen}{x:.1f} {y:.1f}")
            pen = "L"
        out.append(f'<path class="line" d="{" ".join(path)}" stroke="{colour}" fill="none"/>')
        for i, v in enumerate(vals):
            if v is not None:
                x, y = xy(i, v)
                out.append(f'<circle class="dot" cx="{x:.1f}" cy="{y:.1f}" r="4" fill="{colour}" '
                           f'data-tip="{escape(f"{labels[i]}: {s} {_num(v)}{unit}")}"/>')
        last = max((i for i, v in enumerate(vals) if v is not None), default=None)
        if last is not None:
            x, y = xy(last, vals[last])
            out.append(f'<text class="val" x="{x + 8:.1f}" y="{y + 4:.1f}">{_num(vals[last])}{escape(unit)}</text>')
    if legend:
        x, items = left, []
        for s, colour, _ in series:
            items.append(f'<line x1="{x}" x2="{x + 18}" y1="12" y2="12" stroke="{colour}" stroke-width="3"/>'
                         f'<text class="leg" x="{x + 24}" y="16">{escape(s)}</text>')
            x += 40 + 8 * len(s)
        out.append('<g class="legend">' + "".join(items) + "</g>")
    return _svg(h, label, out)


def hbars(rows: Sequence[Tuple[str, float, str]], unit: str = "", label: str = "Bar chart") -> Markup:
    """Horizontal bars, longest first as given; values written at the bar end."""
    if not rows:
        return EMPTY
    row_h, left, right = 30, 330, 50
    h = row_h * len(rows) + 8
    top_value = max(v for _, v, _ in rows) or 1
    plot_w = W - left - right
    out = []
    for i, (name, value, colour) in enumerate(rows):
        y = 4 + i * row_h
        bw = plot_w * value / top_value
        out.append(f'<text class="ax lbl" x="{left - 10}" y="{y + 19}" text-anchor="end">{escape(name)}</text>')
        if bw:
            out.append(f'<rect class="bar" x="{left}" y="{y + 6}" width="{max(bw, 2):.1f}" height="16" '
                       f'rx="{RADIUS}" fill="{colour}"/>')
        out.append(f'<text class="val" x="{left + bw + 8:.1f}" y="{y + 19}">{_num(value)}</text>'
                   f'<rect class="hit" x="0" y="{y}" width="{W}" height="{row_h}" '
                   f'data-tip="{escape(f"{name}: {_num(value)}{unit}")}"/>')
    return _svg(h, label, out)


def heat(rows: Sequence[str], cols: Sequence[str], grid: Sequence[Sequence[Optional[int]]],
         tip_unit: str = "", label: str = "Heat map") -> Markup:
    """A grid of counts on one faint-to-strong hue; an empty cell (None) means
    no data for that cell, not zero."""
    if not rows or not cols:
        return EMPTY
    top_value = max((v for line in grid for v in line if v), default=0)
    left, top, gap = 44, 22, 2
    cell = min(28.0, (W - left - 8) / len(cols))
    h = int(top + len(rows) * cell + 8)
    out = []
    every = _every(len(cols), 12)
    for j, name in enumerate(cols):
        if j % every == 0:
            out.append(f'<text class="ax" x="{left + cell * (j + 0.5):.1f}" y="14" text-anchor="middle">'
                       f'{escape(name)}</text>')
    for i, name in enumerate(rows):
        y = top + i * cell
        out.append(f'<text class="ax" x="{left - 8}" y="{y + cell / 2 + 4:.1f}" text-anchor="end">{escape(name)}</text>')
        for j, col in enumerate(cols):
            v = grid[i][j] if j < len(grid[i]) else None
            x = left + j * cell
            if v is None:
                out.append(f'<rect class="cell none" x="{x:.1f}" y="{y:.1f}" width="{cell - gap:.1f}" '
                           f'height="{cell - gap:.1f}" rx="3"/>')
                continue
            level = 0 if not v or not top_value else min(4, 1 + int(3 * (v - 1) / max(1, top_value - 1) + 0.5))
            out.append(f'<rect class="cell" x="{x:.1f}" y="{y:.1f}" width="{cell - gap:.1f}" height="{cell - gap:.1f}" '
                       f'rx="3" fill="{HEAT[level]}" data-tip="{escape(f"{name} {col}: {v}{tip_unit}")}"/>')
    return _svg(h, label, out)


def spark(values: Sequence[Optional[float]], colour: str = AQUA, label: str = "Trend") -> Markup:
    """A word-sized trend line for tables; the latest value gets a dot."""
    points = [(i, v) for i, v in enumerate(values) if v is not None]
    if len(points) < 2:
        return Markup("")
    w, h, pad = 96, 26, 4
    low, high = min(v for _, v in points), max(v for _, v in points)
    span = (high - low) or 1
    step = (w - 2 * pad) / max(1, len(values) - 1)

    def xy(i: int, v: float) -> str:
        return f"{pad + i * step:.1f} {h - pad - (h - 2 * pad) * (v - low) / span:.1f}"

    path, pen = [], "M"
    for i, v in enumerate(values):
        if v is None:
            pen = "M"
            continue
        path.append(pen + xy(i, v))
        pen = "L"
    x, y = xy(*points[-1]).split()
    return Markup(f'<svg class="spark" viewBox="0 0 {w} {h}" role="img" aria-label="{escape(label)}">'
                  f'<path d="{" ".join(path)}" stroke="{colour}" fill="none"/>'
                  f'<circle cx="{x}" cy="{y}" r="3" fill="{colour}"/></svg>')
