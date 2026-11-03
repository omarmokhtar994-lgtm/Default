# Phase BG: every screen, every attack, the engine on all seven workbooks (2026-11-03)

Owner's request: deep testing of everything in the website and the engine, visuals correct, more hacking tests, more security so no client refuses it.

## Website, in a real browser (`visual_audit.py`, `probe_focus.py`, `browser_xss.py`)
Every page each of three roles can reach (admin 90, team manager 90, associate 24), at 1440, 768 and 360 px, in both looks: 1,224 page loads, then 456 again after the fixes.
Checked on each: status, console errors, CSP violations, failed requests, sideways scroll, anything past the edge, broken images, missing alt, labels and names, duplicate ids, headings, title and language, 24 px targets, text contrast.

| Found | Fix | After |
|---|---|---|
| At 768 px the account part of the top bar ran 91 px past the edge; every page scrolled sideways (334 loads) | it wraps below 900 px, where the menu folds | 0 |
| On a phone the top bar was 194 px and stuck to the top | it scrolls away below 900 px | done |
| Brand and the day's link row were 22 and 20 px tall | 24 px minimum | 0 |
| "Ctrl K" hint on touch screens | hidden where there is no hover | done |

Not problems (checked): the 13 px native tick boxes and radio buttons (browser controls are exempt from the 24 px rule); the screen-reader-only words in the progress bar (they read as low contrast but are not drawn); "This week" and "This month" both lit on the first days of a month (they are the same range then); the programmatic focus check (a real Tab walk of ten pages in both looks showed a ring on every stop: 1,200+ stops, none without).
Stored XSS: seven script payloads typed as people's names, 80 pages opened, none ran, no inline element or `on...` attribute appeared.

## Attacks (`test_bf_attacks.py` 28, `test_bg_security.py` 17, `raw_http_attacks.py`)
New this round: second sign-in path, forced password change confines the account, password change ends other sessions, files a scanner looks for, server names, header splitting, method override, odd requests, look-alike usernames, Excel formula injection through every workbook download, raw HTTP (request smuggling, duplicate and negative lengths, 400 KB headers, 5,000 headers, garbage, 40 slow connections: server stays up, nothing leaks).
Fixed: common and easy passwords refused ("Password1234", "Scheduler2026!", "abcdefghijkl", "aaaaaaaaaaaa"); `Cache-Control: no-store` on every non-static answer (downloads said only "no-cache"); the session cookie is `__Host-session` on the HTTPS site; sign-out sends `Clear-Site-Data`; `upgrade-insecure-requests`; Trusted Types (`require-trusted-types-for 'script'`, the site's script has no HTML sink); CORP and cross-domain policy headers.

## Engine on the seven shipped workbooks (QUICK, 300 s, 2 workers, run alone)
Cricut Chat, Cricut Voice, GDI, NMG SP, NMG EN+SP and AE AR B2B finish with a schedule and the independent validator passes. NMG EN (the "regression clean" workbook) stops before the solver on both the old and the new engine: Sunday 02:00 has demand and no English shift can reach it (input gap, a hard-rule shortfall schedule is written).
Phase BD and BE change nothing on these (no Preferences in them). One scare worth recording: NMG EN+SP failed twice on the new engine and passed twice on the old, while a browser crawl was using the machine; run alone, the new engine passed twice and the old twice. A timed solve starved of CPU is not a regression. Run engine checks alone.

## Left for the owner (each needs a decision)
Two-step sign-in; an idle timeout (the site keeps a person in for 12 hours of use; clients often ask for 15 to 30 minutes, which would sign out an RTA mid-shift); a stronger password hash cost (OWASP asks for scrypt N=2^17, 128 MB per sign-in; Werkzeug's default is 2^15 and the server may be small); HSTS `includeSubDomains`; re-asking for the password before deleting people or changing roles; pip-audit before each release; encrypted off-box backups with a restore test; SSH key-only, fail2ban and a patch routine on the server; a third-party penetration test.

## Second pass (owner: "why didn't you fix what you found")
Fixed after the first report: tick boxes and radio buttons now have a 24 px target (the label around them is at least 24 px tall; a tick alone in a table cell is 24 px); file names on the home page break after an underscore or dot, not inside the ending; the swapped week is listed on the Schedules page as "Tool, closer to preferences" (offered, never in use by itself).
Left as drawn, on purpose: the coloured channel bars in the channel plan are 17 px tall on a desk and 10 px on a phone. They are a pointer tool for a planner, the same cells are in a table under "Show quarter hours", and taller bars would change the approved drawing (text scales with it).
