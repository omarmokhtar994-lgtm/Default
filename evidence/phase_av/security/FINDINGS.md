# Phase AV: attack on the website (2026-10-22)

`pentest.py` attacks a local test copy (made-up data) as admin, supervisor, RTA, two team managers (one in another program), three
associates (one in another program) and nobody signed in. `bandit` (static) and `pip-audit` were also run.

## Found and fixed (tests in `webapp/tests/test_av_security.py`)
| Finding | Fix |
|---|---|
| A session cookie kept working after its person signed out (stateless cookie) | Sign-out ends that session on the server (`revoked_sessions`); other devices stay signed in |
| An unknown username cost two password hashes, a known one with a wrong password cost one (206 ms against 116 ms): usernames could be found by timing | One check against a fixed dummy hash for an unknown name (116 ms both) |
| A very long upload file name was a server error and left a stray folder | Names are cut to 100 characters, extension kept |
| `defusedxml` (openpyxl's guard against XML entity bombs) was not in `deploy/requirements.txt` | Pinned; the server refuses to start without it; a test shows a workbook with an entity declaration is refused |
| (earlier in this phase) uploads: other tabs, card numbers, street addresses, bank numbers, macros, outside links | `webapp/upload_guard.py`: refused and deleted, recorded by kind |

## Checked and clean
Every page by every role (441 requests): nobody reached a page without the permission; another program's people could not read a
program they do not have (pages, exports, runs); every POST refused a missing or forged CSRF token; 12,000+ injection, script,
header and path payloads over 29 parameters on 10 pages: no server error, no raw reflection, no leaked SQL or traceback; no open
redirect; no file exposure; security headers present, no caching of signed-in pages by shared caches; privilege escalation by
form posts refused; other people's requests could not be cancelled or decided; 25 wrong sign-ins from one address were held.
`bandit`: the SQL warnings are f-strings that build column lists and `?` marks from constants (no request value reaches a name);
no `|safe`, `render_template_string`, `eval`, `shell=True` or debug mode. `pip-audit`: no known vulnerabilities.

## Not covered here (the real server; this session cannot reach it)
TLS and Caddy settings, firewall and open ports, SSH keys, operating-system updates, file permissions of the data folder and
`scheduler.db`, backups (and who can read them), the secrets in the service file, log retention. Two-factor sign-in was skipped by
the owner. A site cannot be made "100% secure": this lowers the risk and shows the evidence.
