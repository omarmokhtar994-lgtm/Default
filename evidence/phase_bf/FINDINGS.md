# Phase BF: attacks against the website, and what they found (2026-11-02)

Owner's request: "maximize the security so it can pass any client test ... do some tests if someone tried hacking, what are the weak areas to be improved."
Tests: `webapp/tests/test_bf_attacks.py` (28 attacks; outsider, session, login form, forms/CSRF, injection, uploads, headers). Static scan: bandit on `webapp/` (medium and up).

## Weak areas found and fixed
| # | Weak area | Attack | Fix |
|---|---|---|---|
| 1 | A workbook with forbidden or broken XML (an XXE attempt) made the upload route crash with a 500 | upload a zip whose XML declares an external entity | The entity was already refused by the XML guard; the route now says "That file could not be read as an Excel workbook" and keeps nothing |
| 2 | Sign-in page told an outsider which usernames exist: a real account locked after five wrong tries read differently from an unknown name; a switched-off account was named without its password | five wrong tries against a real and an unknown name, then compare | Locked reads like any wrong password; "switched off" is shown only with the right password |
| 3 | A locked account was refused faster than an unknown one (timing hint) | time the two | A locked account now spends the same hash time |
| 4 | No `Cross-Origin-Resource-Policy` | another site embeds an answer | `same-origin` on every response, plus `X-Permitted-Cross-Domain-Policies: none` |

## Attacked and held (no change needed)
Outsider reaching any page or form; PUT/DELETE/PATCH and odd verbs (none registered); stack traces and paths in errors; stolen cookie replay after sign-out; forged and edited cookies; session change at sign-in; cookie flags (HttpOnly, SameSite=Lax; Secure in production); lock after five wrong passwords; 40 wrong tries from one address block the address; open redirect through `next` (nine forms); CSRF on every POST route, token from another session, JSON body; SQL, template, XSS and traversal payloads in every query name on every page; downloads with `../`; zip bomb, non-zip and HTML uploads; oversize body; hostile file names (stored under a random name); CSP without inline script or style; CORS closed; forged Host or X-Forwarded-Host not echoed.
bandit: 58 "SQL string" notes are column or table names taken from Python keyword names and constants, never from a request (checked every caller that splats `**fields`); the two `Markup` uses escape their labels; the SHA-1 is a cache digest, not a secret.

## Left for the owner (each needs a decision)
- Two-step sign-in (an authenticator code or a mailed code). Clients often ask for it. It is a new sign-in flow, so it needs a sample first.
- A common-password and leaked-password check at set time (needs a word list, or a small bundled one).
- `includeSubDomains` / preload on the HSTS header (only if no subdomain is served without HTTPS).
- A Python dependency audit (pip-audit) before each release: a new dependency.
- Off-box, encrypted backups of `scheduler.db` and a tested restore; server patching routine; SSH hardening (key-only, no root login) and fail2ban on the server. These live on the server, which the owner installs.
- A penetration test by a third party before a client signs off.
