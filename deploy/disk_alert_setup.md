# Backups and the disk alert

© 2026 Omar Mokhtar. All rights reserved.

Two jobs run on the server by themselves (Phase BT, 2026-11-19). `install.sh` and `update.sh` set them up; on a server that already runs, a patch
that brings them is followed by one command:

```
sudo bash /opt/scheduler/package/deploy/setup_timers.sh
```

It is safe to run again. It makes the first copy straight away and lists both timers.

## Nightly copy of the database

- **What:** `/var/lib/scheduler/scheduler.db` (users, runs, schedules, volumes, the Teams and Slack group links). Run result files in
  `/var/lib/scheduler/runs/` are not copied (they are kept 30 days and can be produced again).
- **When:** every night at 23:30 UTC (01:30 Egypt time in winter, 02:30 in summer). A night missed while the server was off runs when it starts.
- **Where:** `/var/backups/scheduler/scheduler-YYYY-MM-DD-HHMMSS.db.gz`, the newest 14 kept. Folder readable by root only: the copies hold the
  group links.
- **How:** SQLite's own backup (a consistent copy while the website runs), checked with `integrity_check`, then compressed. If the database is
  missing or damaged, or the disk is too full for a copy, nothing is written and no older copy is deleted; the job says why and fails.
- **Limits:** the copies are on the same server. They protect against a bad change or a damaged database, not against losing the server.

Check it:

```
sudo ls -l /var/backups/scheduler
sudo journalctl -u scheduler-backup -n 20 --no-pager
```

Make a copy now: `sudo systemctl start scheduler-backup`.

**Putting a copy back** (this replaces everything since that copy: users, runs, settings):

```
sudo systemctl stop scheduler-web
sudo cp -a /var/lib/scheduler/scheduler.db /root/scheduler-before-restore.db
sudo bash -c 'gunzip -c /var/backups/scheduler/scheduler-YYYY-MM-DD-HHMMSS.db.gz > /var/lib/scheduler/scheduler.db'
sudo chown --reference=/root/scheduler-before-restore.db /var/lib/scheduler/scheduler.db
sudo chmod --reference=/root/scheduler-before-restore.db /var/lib/scheduler/scheduler.db
sudo systemctl start scheduler-web
```

## Disk alert every 15 minutes

- **What:** how full the disk under `/var/lib/scheduler` is. One line in the journal every time; a post to a Teams or Slack group at 80 % (a
  warning, again every 24 hours while it lasts), at 90 % (critical, again every 6 hours), and once when it is back to normal.
- **Which group:** in `/etc/scheduler/disk-alert.env`, remove the `#` before `ALERT_UNIT=` and type a LOB's name exactly as on the
  Notifications page. The alert uses the group link the website already keeps for that LOB: never put a link in this file. With no
  `ALERT_UNIT`, it writes the journal line only.

```
sudo nano /etc/scheduler/disk-alert.env
sudo systemd-run --wait --pipe -p User=scheduler -p EnvironmentFile=/etc/scheduler/disk-alert.env \
  -p LoadCredential=smtp-password:/etc/scheduler/smtp-password \
  -E PYTHONPATH=/opt/scheduler/package -E SCHEDULER_DATA_DIR=/var/lib/scheduler -E PYTHONDONTWRITEBYTECODE=1 \
  /opt/scheduler/venv/bin/python /opt/scheduler/package/deploy/disk_alert.py --test
sudo journalctl -u disk-alert -n 20 --no-pager
```

The second command posts a test message to the named group (and emails it, when email is set up) whatever the level (it reads the settings file the same way the timer does,
so a LOB name with spaces needs no quotes). `WARN` and `CRIT` in the same file change the two levels.

## Email (Phase BU)

The same disk alerts, and a nightly copy that failed, can also come by email. The owner's choice (2026-11-19): a Gmail account sends to itself
with a Google **App password** (a 16-letter password for this server only; it cannot be used to sign in to Google, and it can be revoked at any
time from the Google account).

1. In the Google account: turn on 2-Step Verification, then Security > App passwords > create one named "Team Scheduler server". Keep the page
   open: Google shows it once.
2. On the server, put the two addresses in the settings file (remove the `#` in front of these lines and fill them in):

   ```
   sudo nano /etc/scheduler/disk-alert.env
   ```
   ```
   ALERT_EMAIL=you@gmail.com
   SMTP_USER=you@gmail.com
   SMTP_HOST=smtp.gmail.com
   SMTP_PORT=587
   ```
3. Type the app password into the root-only file. It is not shown, not kept in the shell history and never on a command line:

   ```
   sudo bash -c 'umask 077; read -rs -p "App password: " P; echo; printf %s "$P" > /etc/scheduler/smtp-password'
   ```
4. Send a test with the `--test` command above: an email "Team Scheduler server: disk alert test" arrives.

The password never appears in the journal; a refused sign-in shows only the mail server's code (535 means the app password is wrong or was
revoked). To stop the emails, put the `#` back in front of `ALERT_EMAIL`. To change the password, run step 3 again.

## What it installs

- `/etc/systemd/system/scheduler-backup.service` and `.timer` (as root; may write only `/var/backups/scheduler`).
- `/etc/systemd/system/disk-alert.service` and `.timer` (as the `scheduler` account; may write only `/var/lib/scheduler`).
- `/etc/scheduler/disk-alert.env`, made once and never overwritten.
- `/etc/scheduler/smtp-password`, empty, root only (600), made once and never overwritten.
- `/var/backups/scheduler`, root only (700).

Both timers: `systemctl list-timers scheduler-backup.timer disk-alert.timer`.
