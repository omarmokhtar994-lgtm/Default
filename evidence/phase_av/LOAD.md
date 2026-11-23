# Phase AV: busy-hour load test (2026-10-22)

`tools/load.py`: 500 users (5 RTAs, 20 team managers, 475 associates) sign in over 90 s and use their pages for 150 s on made-up
data; the site runs as in production (waitress, 8 threads, one process, 1000 open connections). This container has 4 cores and is
not the Oracle server: read the numbers as relative. Associates look at a page about every 90 s.

| | before the day cache | after (reads only) | after (50% make changes, schedule run on every core) |
|---|---|---|---|
| sign in, typical / slowest 5% | failed (connection limit) | 0.6 s / 6.6 s | 9.7 s / 25 s |
| My day, typical / slowest 5% | 14 s / 24 s | 0.4 s / 2.1 s | 3.5 s / 8.7 s |
| My weeks | 14 s / 24 s | 0.3 s / 2.1 s | 3.4 s / 8.2 s |
| RTA timeline | 16 s / 25 s | 0.8 s / 3.5 s | 5.9 s / 9.2 s |
| ask a break change | 50 s / 79 s (first run) | n/a | 9.2 s / 28 s |
| errors | 402 sign-ins | 0 | 0 |

What changed: a built day is kept until a write to a table it is built from (`Store.generation`, `QUIET_TABLES`); a kept day
is handed out as a copy (`DayBook.page`, `shared=True` for read-only callers); the server accepts 1000 open connections
(`webapp/serve.py`). A schedule run in parallel takes the cores and slows everything; run it off the busy hours.
