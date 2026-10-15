# © 2026 Omar Mokhtar. All rights reserved.
"""Write webapp/static/icons.css from Phosphor's regular SVGs (Phase AG, T1).

Usage: python3 tools/build_icons_css.py <folder with Phosphor's assets/regular/*.svg>

The shapes are Phosphor Icons (MIT, webapp/static/LICENSE-phosphor), from the npm package @phosphor-icons/core
2.1.1. Each becomes a data: URI in a CSS custom property, so the site serves no third-party .svg file and the CSP
needs nothing new (img-src already allows data:). The menu draws its icons from the links' addresses, so the links'
markup does not change.
"""
import sys
from pathlib import Path
from urllib.parse import quote

OUT = Path(__file__).resolve().parents[1] / "webapp" / "static" / "icons.css"
ICONS = ["house", "gauge", "pulse", "television", "calendar-blank", "stack", "chart-line-up", "buildings",
         "download-simple", "users", "user-gear", "address-book", "headset", "bell", "tree-structure", "tray",
         "calendar-check", "plus", "check-circle", "warning", "magnifying-glass", "caret-left", "caret-right",
         "globe-hemisphere-west", "arrow-u-up-left", "airplane-tilt", "arrows-left-right", "x-circle", "clock", "sun",
         "moon", "sign-out", "gear", "lifebuoy", "user-circle", "list", "chart-bar"]
# the menu: (selector for the link, icon); later rules win, so the more specific address comes after
MENU = [('a[href="/"]', "house"), ('a[href^="/overview"]', "gauge"), ('a[href^="/day"]', "pulse"),
        ('a[href^="/day/wallboard"]', "television"), ('a[href^="/week"]', "calendar-blank"),
        ('a[href^="/schedules"]', "stack"), ('a[href^="/programs/"]', "chart-line-up"), ('a[href="/programs"]', "buildings"),
        ('a[href^="/exports"]', "download-simple"), ('a[href^="/team"]', "users"), ('a[href^="/admin/users"]', "user-gear"),
        ('a[href^="/setup/with"]', "address-book"), ('a[href^="/setup/channels"]', "headset"),
        ('a[href^="/notifications"]', "bell"), ('a[href^="/setup/programs"]', "tree-structure"),
        ('a[href^="/requests"]', "tray"), ('a[href^="/me"]', "calendar-check"), ('a[href^="/admin/roles"]', "gear")]


def main(folder: Path) -> None:
    lines = ["/* © 2026 Omar Mokhtar. All rights reserved. Icon shapes: Phosphor Icons, MIT licence (LICENSE-phosphor). */",
             "/* Written by tools/build_icons_css.py; do not edit by hand. */", ":root {"]
    for name in ICONS:
        svg = (folder / f"{name}.svg").read_text(encoding="utf-8").strip()
        if "<script" in svg or "href" in svg:
            raise ValueError(f"{name}.svg is not a plain shape")
        lines.append(f'  --i-{name}: url("data:image/svg+xml,{quote(svg, safe=" =:/,.-")}");')
    lines.append("}")
    lines.append(".ico { display: inline-block; width: 1.15em; height: 1.15em; flex: none; background: currentColor; "
                 "-webkit-mask: var(--i) center / contain no-repeat; mask: var(--i) center / contain no-repeat; "
                 "vertical-align: -0.2em; }")
    lines += [f".ico.i-{name} {{ --i: var(--i-{name}); }}" for name in ICONS]
    lines.append(".leftnav nav a::before { content: \"\"; display: inline-block; width: 1.1rem; height: 1.1rem; flex: none; "
                 "background: currentColor; opacity: .75; -webkit-mask: var(--i) center / contain no-repeat; "
                 "mask: var(--i) center / contain no-repeat; }")
    lines += [f".leftnav nav {sel}::before {{ --i: var(--i-{icon}); }}" for sel, icon in MENU]
    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main(Path(sys.argv[1]))
