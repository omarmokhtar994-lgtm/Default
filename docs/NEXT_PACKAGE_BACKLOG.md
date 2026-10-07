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

## Offered, waiting for the owner

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
