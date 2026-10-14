# © 2026 Omar Mokhtar. All rights reserved.
"""Proposal palettes (night and day) and their measured WCAG contrast."""
P = {
 "current": {"night": dict(night="#0E1A2B", rail_bg="#0A1422", console="#15243A", console_2="#1B2D47", rail="#263954", paper="#E6EDF5", dim="#8FA3BC", edge="#627389"),
             "day": dict(night="#EAEFF5", rail_bg="#FFFFFF", console="#FFFFFF", console_2="#F3F6FA", rail="#D3DCE7", paper="#12233A", dim="#4F627A", edge="#77869A")},
 "A": {"night": dict(night="#111418", rail_bg="#0B0D10", console="#181C22", console_2="#20252D", rail="#2C333D", paper="#E7EBF0", dim="#98A2AF", edge="#68727F"),
       "day": dict(night="#F1F2F4", rail_bg="#FFFFFF", console="#FFFFFF", console_2="#F6F7F9", rail="#D8DCE2", paper="#15191F", dim="#525C68", edge="#7A838F")},
 "B": {"night": dict(night="#0A1220", rail_bg="#060B14", console="#111C2E", console_2="#18263D", rail="#23344F", paper="#EAF0F8", dim="#93A6C0", edge="#61748E"),
       "day": dict(night="#E6EDF6", rail_bg="#FFFFFF", console="#FFFFFF", console_2="#F1F5FA", rail="#C9D5E4", paper="#0F2038", dim="#4A5E79", edge="#73849A")},
}
STATUS = {"night": dict(covered="#2BC4B4", short="#F2A93B", gap="#E5534B", over="#8A7BF0", gap_ink="#FF8A82", over_text="#9086EE"),
          "day": dict(covered="#06A496", short="#C98304", gap="#D53D38", over="#7560E3", gap_ink="#B3261E", over_text="#715ED8")}

def lum(h):
    c = [int(h[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    c = [x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4 for x in c]
    return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]

def ratio(a, b):
    la, lb = sorted((lum(a), lum(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)

if __name__ == "__main__":
    for name, looks in P.items():
        for look, t in looks.items():
            s = STATUS[look]
            r = {"ink/panel": ratio(t["paper"], t["console"]), "ink/page": ratio(t["paper"], t["night"]),
                 "dim/panel": ratio(t["dim"], t["console"]), "dim/raised": ratio(t["dim"], t["console_2"]),
                 "edge/panel": ratio(t["edge"], t["console"]), "edge/page": ratio(t["edge"], t["night"]),
                 "label/button": ratio(t["night"] if look == "night" else "#FFFFFF", t["paper"])}
            for k in ("covered", "short", "gap", "over"):
                r[f"{k} fill/panel"] = ratio(s[k], t["console"])
            r["gap text/panel"] = ratio(s["gap_ink"], t["console"]); r["over text/panel"] = ratio(s["over_text"], t["console"])
            low = {k: round(v, 2) for k, v in r.items() if (v < 4.5 and ("ink" in k or "dim" in k or "text" in k or "label" in k)) or v < 3}
            print(f"{name:8s} {look:5s} min ink {min(r['ink/panel'], r['ink/page']):5.2f}  dim {r['dim/panel']:4.2f}/{r['dim/raised']:4.2f}  edge {r['edge/panel']:4.2f}  "
                  f"fills {min(r[k] for k in r if 'fill' in k):4.2f}  FAIL: {low or 'none'}")
