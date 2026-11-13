# Phase AR: program walls, deleting a user, bulk users, passwords

© 2026 Omar Mokhtar. All rights reserved.

Received Wed 21 Oct 2026, while the Phase AP package was being checked and the Phase AQ A/B was running.

## The owner's words

> We need to make sure that each program has its own everything and no one can view it except if they have access, TMs
> departments names associates schedules uploads everything needs to be hidden from other Programs.
> Now i can't delete a create user i want to have this.
> And i want to be able to upload bulk users, also the password during creation is not working and i have to reset it
> each time manually and send it.

## What Claude found so far (before any code)

- **Walls:** every page already checks the program named in the address (before_request), but nothing proves that a
  list, a search or an id-based page never shows another program's names. Phase AR first builds a crawl test: two
  programs with people, team managers, departments, uploads, schedules and group links, and a user who has only one
  of them; every page and every id of the other program is requested and the response must hold none of its words.
  Findings from it are fixed test-first.
- **Passwords:** creating a person with a typed temporary password works in a test (sign in with it, then the page
  that makes them choose their own). The owner's symptom is not reproduced; the exact message seen is needed.
- **Delete:** People can only switch a person off. Their records (day log, requests, versions) name the person, so a
  row delete would break them.

## Proposal (owner decides)

1. A delete that removes the account (sign-in, programs, roster link, username freed for a new one) but keeps the
   person's display name in the history of what they did. A person with no history is removed completely.
2. Bulk users: download a template (username, name, role, programs, roster name, team manager, password optional),
   upload it, see a preview with a reason for each row that cannot be added, then confirm. Blank passwords are
   generated; the passwords are shown once on the result page and in a one-time download.
3. Creation: a blank password field generates one and shows it once, so there is nothing to type or to reset.
