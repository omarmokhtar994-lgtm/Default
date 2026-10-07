# © 2026 Omar Mokhtar. All rights reserved.
"""Command-line user management for the server owner.

    python -m webapp.manage --data-dir /var/lib/scheduler create-admin omar --name "Omar Mokhtar"
    python -m webapp.manage --data-dir /var/lib/scheduler add-user sara --name "Sara"
    python -m webapp.manage --data-dir /var/lib/scheduler reset-password sara
    python -m webapp.manage --data-dir /var/lib/scheduler disable-user sara

Passwords are typed at the prompt (twice), never given on the command line,
so they do not land in the shell history.
"""
from __future__ import annotations

import argparse
import getpass
import sys
from pathlib import Path
from typing import Callable, List, Optional

from .app import MIN_PASSWORD, password_problem
from .store import Store


def _new_password(username: str, ask: Callable[[str], str]) -> Optional[str]:
    first = ask(f"Password for {username}: ")
    second = ask("Same password again: ")
    problem = password_problem(first, second, username)
    if problem:
        print(problem, file=sys.stderr)
        return None
    return first


def main(argv: Optional[List[str]] = None, ask: Callable[[str], str] = getpass.getpass) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data-dir", type=Path, required=True)
    sub = ap.add_subparsers(dest="command", required=True)
    for name in ("create-admin", "add-user"):
        p = sub.add_parser(name)
        p.add_argument("username")
        p.add_argument("--name", default="")
    for name in ("reset-password", "disable-user", "enable-user"):
        sub.add_parser(name).add_argument("username")
    args = ap.parse_args(argv)

    store = Store(args.data_dir / "scheduler.db")
    username = args.username.strip().lower()
    existing = next((u for u in store.list_users() if u["username"] == username), None)

    if args.command in ("create-admin", "add-user"):
        if existing is not None:
            print(f"{username} already exists.", file=sys.stderr)
            return 1
        password = _new_password(username, ask)
        if password is None:
            return 1
        admin = args.command == "create-admin"
        # The owner typed their own password; a team member set up here
        # chooses their own at first sign-in.
        store.add_user(username, args.name, password, is_admin=admin, must_change=not admin)
        print(f"{'Admin' if admin else 'User'} {username} created.")
        return 0
    if existing is None:
        print(f"No user called {username}.", file=sys.stderr)
        return 1
    if args.command == "reset-password":
        password = _new_password(username, ask)
        if password is None:
            return 1
        store.set_password(existing["id"], password, must_change=not existing["is_admin"])
        print(f"Password for {username} reset.")
    else:
        store.set_active(existing["id"], args.command == "enable-user")
        print(f"{username} {'switched on' if args.command == 'enable-user' else 'switched off'}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

# Minimum length, kept here for the --help text readers.
__all__ = ["main", "MIN_PASSWORD"]
