# Next package: agreed backlog

Recorded 2026-10-07, 23:00 Egypt time, after the first install on the Oracle
server (https://84-13-140-126.sslip.io). The owner asked to keep this list for
the next package; nothing here is built yet.

## Agreed with the owner (built in Phase J, 2026-10-08: see docs/superpowers/plans/2026-10-07-phase-j-control-room-redesign.md)

1. **Friendlier errors on the run page.**
   - *Not approved* and *Needs review* show the reason in one or two plain
     sentences at the top (for example "Sunday 14:00-16:00 is short of 2
     Spanish-speaking agents"), taken from the validator and release-gate
     reports. The raw log and verdict lines move behind a "Technical details"
     toggle.
   - Release verdict lines translated into plain words (for example
     "gate 4 protected tier: no protected minimum configured").
   - A friendly page for unexpected website errors (HTTP 500): "Something went
     wrong on our side; your run is safe. Tell your admin."
2. **Installer fixes** (seen during the first install):
   - `webapp.manage create-admin` / `add-user` accept a username with spaces
     ("Omar Mokhtar"); apply the same rule as the People page (letters,
     numbers, dots, dashes, underscores).
   - `deploy/install.sh` stops when the two passwords differ (set -e on the
     create-admin step); it should ask again instead.

## Built in Phase K (2026-10-08: see docs/superpowers/plans/2026-10-08-phase-k-program-analytics.md)

- Program name and schedule week on every run (upload form; editable on the
  run page by its owner or an admin). Runs finished before the update get
  their figures from their files when the website starts.
- Programs page (latest week per program with 12-week trends), a program's
  history page (associates per week, coverage before and after breaks, hours
  available and needed, what stops 100%, what a lower interval target would
  meet, hours that keep coming up short, written insights and suggestions,
  week-by-week table) and a Team page (runs per person and how they ended).

## Built in Phase L (2026-10-08: see docs/superpowers/plans/2026-10-08-phase-l-run-page-fixes-and-themes.md)

- A failed run's page says why it stopped and what to change in the input
  workbook, in the engine's own words (no need to open the zip); "Can't be
  scheduled" when the input must change; the shortfall schedule is offered
  for review.
- Readiness checks say "Ready to run" or "Not ready" (never "Not approved");
  a ready check starts the real run (Quick, Deep or Overnight) from the same
  workbook.
- Back and Home on every page; the workbook can be dropped on the upload area.
- Blank and example input workbooks download from the home page.
- Light and dark looks (the device's setting until a person picks one).

## Offered, waiting for the owner

- AI-written summaries on the program page (the owner chose rule-based
  insights first). Needs an Anthropic API key on the server, kept in a
  root-only file; only aggregate figures would be sent, never names.


- Site name shown on the pages ("Team Scheduler"): owner to give a name.
- Web address: DuckDNS (free) or an own domain; re-run the installer with
  `DOMAIN=<name>` (documented in the chat, not yet in the guide).
- Design refresh: done in Phase J (control room, owner's choice).
- Two runs at once: only after measuring memory and time on the 4-core server.
  The runner sizes its seed plan from `os.cpu_count()`, not `--num-workers`,
  so two runs would each plan for 4 cores; cap that first.

## Deferred minors from the Phase I final review

- A failing safety gate is retried by every queued run (15-30 min each)
  instead of once.
- `runs/_incoming` leftovers are not swept by the 30-day cleanup (only after
  a crash between upload and submit).
- The installer's `check-package` gate and a website run started during it do
  not share a lock (different processes); both would run the gate.
