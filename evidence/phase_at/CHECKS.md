# © 2026 Omar Mokhtar. All rights reserved.
# Phase AT: security pass

Owner request (2026-10-21): every rule matches in every tab; no person sees another program; no small manual change
(cookie, form field, hidden input, script) signs in as another account or raises a role.

## What was checked

`webapp/tests/test_at_security.py` (25 tests, all pass):

- Roles: every GET and POST route, for every role, against the permission matrix, the associate allowlist and the
  admin-only pages. An admin changing a role changes every route that role reaches.
- Session: cookie signed with another key, cookie edited by hand, one signature character flipped, copy of a cookie
  after a password change / switch-off / delete, role taken away, cookie flags (HttpOnly, SameSite, Secure, HSTS on
  HTTPS), secret key file mode 0600 from creation.
- Forms: a supervisor cannot make an admin or grant all programs; nobody raises their own role or programs; an
  associate's request always carries their own name; every POST route refuses a missing token and another session's token.
- Redirects: `next` never leaves the site.
- Answers: CSP (no unsafe, base-uri, form-action, object-src, frame-ancestors), X-Frame-Options, nosniff, referrer,
  no-store, permissions policy; no trace or path in an error page; typed names are escaped on every page; no `|safe`,
  no `autoescape false`, no request data in SQL names.
- Exports: every kind holds nothing of another program for A users; `program=`, `pick=key:`, `pick=group:` for B are 403.

## Defects found and fixed

1. Exports "person" filter accepted a user of another program and printed their name in the header. Now 403.
2. Secret key file was created world-readable before chmod. Now created 0600.
3. Missing `base-uri`, `form-action`, `object-src` in the CSP; no `no-store`; no permissions policy. Added.

## Not done

No rate limit on sign-in (new behaviour; owner decides). No dependency audit tool (new dependency; owner decides).
