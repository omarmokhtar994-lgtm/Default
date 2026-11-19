# © 2026 Omar Mokhtar. All rights reserved.
"""Email for the server's own alerts (Phase BU, owner, 2026-11-19: the disk alert and a failed nightly copy by email, sent from the owner's Gmail
with an app password). Used by disk_alert.py and db_backup.py; Python's own smtplib, nothing to install.

Settings (environment, from /etc/scheduler/disk-alert.env): ALERT_EMAIL (to; unset = email is not set up), SMTP_USER (the sending account),
SMTP_HOST (smtp.gmail.com), SMTP_PORT (587, STARTTLS). The password is the file ``smtp-password`` that systemd hands the service
(LoadCredential, from /etc/scheduler/smtp-password, root only), or SMTP_PASSWORD_FILE. It is read here, never printed or logged."""
from __future__ import annotations

import os
import re
import smtplib
import ssl
from email.message import EmailMessage
from pathlib import Path
from typing import Optional

ADDRESS = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _password() -> str:
    path = os.environ.get("SMTP_PASSWORD_FILE") or str(Path(os.environ.get("CREDENTIALS_DIRECTORY", "/nonexistent")) / "smtp-password")
    try:
        return "".join(Path(path).read_text().split())      # Google shows an app password in groups of four; the spaces are not part of it
    except OSError:
        return ""


def send(subject: str, text: str) -> Optional[bool]:
    """None when email is not set up (no ALERT_EMAIL); True when sent; False, with a line saying why, when it could not be sent."""
    to = os.environ.get("ALERT_EMAIL", "").strip()
    if not to:
        return None
    user = os.environ.get("SMTP_USER", "").strip()
    host = os.environ.get("SMTP_HOST", "smtp.gmail.com").strip()
    if not ADDRESS.match(to):
        print("email not sent: ALERT_EMAIL is not an email address", flush=True)
        return False
    if not ADDRESS.match(user):
        print("email not sent: SMTP_USER (the sending account) is not set to an email address", flush=True)
        return False
    try:
        port = int(os.environ.get("SMTP_PORT", "587"))
    except ValueError:
        print("email not sent: SMTP_PORT is not a number", flush=True)
        return False
    password = _password()
    if not password:
        print("email not sent: no password in /etc/scheduler/smtp-password (see disk_alert_setup.md)", flush=True)
        return False
    msg = EmailMessage()
    msg["From"], msg["To"], msg["Subject"] = user, to, subject
    msg.set_content(text + "\n")
    try:
        with smtplib.SMTP(host, port, timeout=20) as server:
            server.starttls(context=ssl.create_default_context())
            server.login(user, password)
            server.send_message(msg)
    except smtplib.SMTPResponseException as exc:          # the server's own words can echo what was sent: only its code is shown
        print(f"email not sent: the mail server refused it (code {exc.smtp_code})", flush=True)
        return False
    except (smtplib.SMTPException, OSError) as exc:
        print(f"email not sent: {exc.__class__.__name__}", flush=True)
        return False
    print(f"email sent to {to}", flush=True)
    return True
