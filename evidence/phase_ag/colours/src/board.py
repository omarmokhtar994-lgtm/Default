# © 2026 Omar Mokhtar. All rights reserved.
"""Side-by-side boards of the three colour options (night and day): python board.py <colours dir> <screens dir>."""
import sys
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

C, S = Path(sys.argv[1]), Path(sys.argv[2])
BOLD = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 26)
TEXT = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 18)
COLS = [("current", "Current (navy)"), ("A", "A  Graphite"), ("B", "B  Deep ocean")]
W, GAP, HEAD = 640, 24, 70


def wide(path):  # a 1440 x 900 desktop shot, scaled to the column
    im = Image.open(path).convert("RGB")
    return im.resize((W, round(im.height * W / im.width)))


def phone(path):  # the top 844 px of a phone shot, scaled down and centred in the column
    im = Image.open(path).convert("RGB")
    im = im.crop((0, 0, im.width, min(im.height, 844))).resize((320, round(min(im.height, 844) * 320 / im.width)))
    box = Image.new("RGB", (W, im.height), "#202020")
    box.paste(im, ((W - 320) // 2, 0))
    return box


def board(rows, out, bg):
    height = HEAD + sum(max(r[1][k].height for k, _ in COLS) + 48 for r in rows)
    sheet = Image.new("RGB", (GAP + 3 * (W + GAP), height), bg)
    d = ImageDraw.Draw(sheet)
    ink = "#FFFFFF" if bg != "#F4F4F4" else "#111111"
    for i, (_, label) in enumerate(COLS):
        d.text((GAP + i * (W + GAP), 22), label, font=BOLD, fill=ink)
    y = HEAD
    for title, images in rows:
        d.text((GAP, y + 8), title, font=TEXT, fill=ink)
        y += 40
        for i, (key, _) in enumerate(COLS):
            sheet.paste(images[key], (GAP + i * (W + GAP), y))
        y += max(im.height for im in images.values()) + 8
    sheet.save(out)


board([("RTA, the day", {k: wide(C / f"rta_{k}_night.png") for k, _ in COLS}),
       ("Leave and swaps", {k: wide(C / f"requests_{k}_night.png") for k, _ in COLS}),
       ("My week on a phone", {k: phone(C / f"me_{k}_night.png") for k, _ in COLS})],
      C / "board_night.png", "#202020")
board([("RTA, the day", {"current": wide(S / "ag_rta_light.png"), "A": wide(C / "rta_A_day.png"),
                         "B": wide(C / "rta_B_day.png")}),
       ("My week on a phone", {"current": phone(S / "ag_my_week_light.png"), "A": phone(C / "me_A_day.png"),
                               "B": phone(C / "me_B_day.png")})],
      C / "board_day.png", "#F4F4F4")
print("done")
