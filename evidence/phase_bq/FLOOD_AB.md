<!-- © 2026 Omar Mokhtar. All rights reserved. -->
# Phase BQ: the flood guard, measured

Owner, 2026-11-18: "protect against bot attacks that stop the server by a lot of requests or overloading".
Rule written before the first run: `FLOOD_RULE.txt`. Tool: `flood_ab.py` (40 s per arm, made-up data, 200 bots
looping GET and POST on the sign-in page with made-up wrong usernames; one signed-in staff member asks for the home
page every 0.5 s). This container is not the Oracle server: compare A with B, not with production.

## Run 1: invalid, and the finding behind the second fix

`flood_ab_run1_INVALID_all_one_address.*`: every client, staff included, got 429 even with the guard off. Cause:
waitress 3.0.2 drops `X-Forwarded-For` unless told which proxy may send it (`clear_untrusted_proxy_headers` is True,
`trusted_proxy` None), so ProxyFix never saw the header and the site saw every visitor as 127.0.0.1. The same is
true on the production server today: the sign-in throttle (40 wrong passwords in 15 minutes per address) counts all
visitors as one address, so one bot's 40 wrong passwords hold sign-in for everyone for 15 minutes, and the events
say "from 127.0.0.1". Fix: waitress believes `X-Forwarded-For` from 127.0.0.1 (Caddy) only, and only that header
(`serve.PROXY`; test `TheAddress` failed with ['127.0.0.1', '127.0.0.1'] before the fix).

## Run 2 (`flood_ab_run2.txt`)

| Flood | Arm | Staff pages in 40 s | Staff median | Staff p95 | Staff max | Staff codes |
|---|---|---|---|---|---|---|
| 200 bots, 200 addresses | A guard off | 6 | 5.806 s | 8.325 s | 8.844 s | 200 x 6 |
| 200 bots, 200 addresses | B defaults | 33 | 0.315 s | 0.436 s | 0.491 s | 200 x 33 |
| 200 bots, one address | A guard off | 42 | 0.907 s | 1.138 s | 1.345 s | 200 x 42 |
| 200 bots, one address | B defaults | 80 | 0.264 s | 0.326 s | 0.352 s | 200 x 80 |

Normal use, guard on, no flood (one person, 5 tabs every 3 s and a page every 2 s, 60 s): 130 requests, 130 x 200.

Rule: 1 met (every staff request in B answered 200), 2 met (B p95 0.436 s and 0.326 s, at most 1.0 s), 3 met (F1 p95
0.436 s in B against 8.325 s in A), 4 met (no 429). The defaults are adopted: 600 requests a minute per signed-in
person, 1200 per address not signed in (the site's own files not counted), 4 of the 8 threads for people not
signed in.

## Limits found

- Signing in during a many-address flood is slow: in F1 / B the staff member's sign-in got 503 sixteen times (about
  16 s, one try a second) before it went through, because signing in is a request from someone not yet signed in.
  People already signed in are not affected (a session lasts while used; it ends after an hour idle).
- The one-address flood was already held by the sign-in throttle in A (7972 of its answers were 429); the guard
  makes the refusals cheaper (73863 refused before any work) and keeps the staff page under 0.4 s.
- Caddy's timeouts (`deploy/Caddyfile.template`) are checked against Caddy's documentation, not run here (Caddy is
  not installed in this container). `update.sh` does not rewrite `/etc/caddy/Caddyfile`, so on the existing server
  the owner adds the block by hand.
