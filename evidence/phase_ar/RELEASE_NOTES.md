# What is new in this package: Phase AR (program walls, people)

© 2026 Omar Mokhtar. All rights reserved.

## Program walls

Each program's people, team managers, departments, uploads, schedules and group links are hidden from people who do not
have the program. A new test makes two programs and asks every page and every form as someone who has only one. It found
and fixed these leaks:

- The New schedule picker on Home listed every program, and a person could upload into a program they do not have.
  It lists, and accepts, only the programs a person has (admins have all).
- A person could move their own run into another program from Run details. Now refused.
- Exports "Changes by" listed everyone in the system. It lists the people in your programs.
- The "not one of your programs" page named the real program. It is generic now, so it does not say whether the program
  exists.

## People

- **Delete a person.** On People, Delete (with a tick box). The account, sign-in, programs and team link go and the
  username is free again; their name stays in the history of what they did. You cannot delete yourself or the last
  admin. A supervisor deletes only people they manage.
- **Add people from a file.** On People, "Add many people from a file": download the template, fill one row for each
  person, upload it. Each row is checked and the ones that cannot be added are listed with the reason; then "Add N
  people" adds the good ones. Excel or CSV. A supervisor adds only planners, associates and team managers of their own
  programs.
- **Passwords.** Leave the temporary password blank (on one person or in a file) and one is made up and shown once, on
  the page and in a one-time download. A typed or pasted password with spaces around it works.

## For the server

- No new packages. The database adds a column on its own.
