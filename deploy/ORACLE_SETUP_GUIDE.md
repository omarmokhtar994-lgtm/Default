# Team Scheduler on Oracle Cloud (Always Free): setup guide

© 2026 Omar Mokhtar. All rights reserved.

This guide takes you from an empty Oracle account to a private website for your
team: everyone signs in with their own username, uploads the week's workbook,
and downloads the checked schedule. The code stays on your server; the team
only ever sees the website.

You need: the package ZIP (`RC9_2_2_PRODUCTION_PACKAGE.zip`), about 45 minutes,
and a computer with a terminal (Windows: PowerShell; Mac: Terminal).

## 1. The server

1. Sign in at <https://cloud.oracle.com>. Your home region (chosen at sign-up)
   is where the server lives.
2. Menu > **Compute** > **Instances** > **Create instance**.
3. **Image**: Change image > **Ubuntu** > *Canonical Ubuntu 24.04* (22.04 also works).
4. **Shape**: Change shape > **Ampere** > `VM.Standard.A1.Flex`, **4 OCPUs**,
   **24 GB** memory. This is inside the Always Free allowance.
   If Oracle says it is out of capacity, try again later or pick another
   availability domain.
5. **SSH keys**: *Generate a key pair for me* > **Save private key**.
   Keep this file safe, like a house key. Do not send it to anyone (not to
   a colleague, not in a chat, not to an assistant): whoever has it can enter
   the server.
6. **Create**. When it shows *Running*, copy its **Public IP address**
   (for example `129.151.1.2`).

## 2. Open the web ports in Oracle's firewall

Oracle blocks web traffic until you allow it.

1. On the instance page, click the **Subnet** link > the **Security List**
   (usually *Default Security List for ...*) > **Add Ingress Rules**.
2. Add two rules, both with Source CIDR `0.0.0.0/0` and IP protocol **TCP**:
   one with destination port range `80`, one with `443`. Save.

(The installer opens the same two ports in the server's own firewall.)

## 3. Copy the package to the server

On your computer, in the folder with the private key and the ZIP
(replace the key file name and the IP with yours):

```
scp -i ssh-key-2026-10-07.key RC9_2_2_PRODUCTION_PACKAGE.zip ubuntu@129.151.1.2:~
ssh -i ssh-key-2026-10-07.key ubuntu@129.151.1.2
```

On Mac/Linux, if ssh says the key's permissions are too open, run
`chmod 600 ssh-key-2026-10-07.key` once. On Windows, if it complains, right-click the
key > Properties > Security and leave only your own user.

## 4. Install (one command)

You are now on the server. Run:

```
sudo apt-get install -y unzip
unzip -q RC9_2_2_PRODUCTION_PACKAGE.zip -d scheduler-package
cd scheduler-package/RC9_2_2_PRODUCTION_PACKAGE
sudo bash deploy/install.sh
```

It takes 5-10 minutes. It asks for:

- **Admin username** and **your name**, then your **password twice**
  (at least 10 characters; nothing shows while you type).
- Whether to **run the safety gate now** (15-30 minutes). Say yes: then the
  first real run starts straight away instead of waiting for it.

At the end it prints your address, like `https://129-151-1-2.sslip.io`.
The HTTPS certificate is created automatically on the first visit (it can
take up to a minute the first time).

## 5. Add your team

Open the address, sign in, and go to **People**:

- **Add a person**: username, name, and a temporary password. Send them the
  address, their username and the temporary password; at first sign-in they
  choose their own.
- **Switch off** someone who leaves (their past runs stay).
- **Reset password** gives a new one-time temporary password.

## 6. Everyday use

1. Upload the week's workbook, choose **Quick** (recommended) and press
   **Check and run**. The workbook is checked in seconds; a problem names the
   cell to fix.
2. The run page shows the stages: Check, Safety gate, Schedule, Scoring,
   Result. You can close the page; the run continues on the server.
3. When it says **Approved**, download the schedule (the file to publish) or
   all results (.zip). **Not approved** shows the reason and the runner log.
4. One run at a time; others wait in the queue. **Stop** keeps the
   checkpoints; **Resume** continues later.
5. Results are kept **30 days**, then their files are deleted.

## 7. Updating to a new package

Copy the new ZIP to the server (step 3, `scp`), then:

```
sudo bash /opt/scheduler/package/deploy/update.sh ~/RC9_2_2_PRODUCTION_PACKAGE.zip
```

Users, runs and results are kept. If a run is in progress it asks first.
If the new package fails its runtime check, the old one is put back.

## 8. If something is wrong

| What you see | What to do |
|---|---|
| The address does not open | Check step 2 (ports 80 and 443). On the server: `sudo systemctl status caddy scheduler-web` |
| "Not secure" or certificate error | Wait a minute after the first visit; check that port 80 is open (step 2). |
| You forgot the admin password | On the server: `sudo runuser -u scheduler -- env PYTHONPATH=/opt/scheduler/package /opt/scheduler/venv/bin/python -m webapp.manage --data-dir /var/lib/scheduler reset-password YOUR_USERNAME` |
| A run says the safety gate failed | Nothing runs until it passes. Send the gate log named on the run page to whoever maintains the package. |
| Website log | `sudo journalctl -u scheduler-web -n 200` |

**Backup**: users and run history are in `/var/lib/scheduler/scheduler.db`;
results are in `/var/lib/scheduler/runs/`.

**Idle servers**: Oracle's Always Free terms allow it to reclaim compute
instances that stay nearly idle for a week. Regular weekly runs normally keep
it in use; check Oracle's current Always Free page if you are unsure.

## What the installer sets up

- `/opt/scheduler/package`: the package (the previous one in `package.previous`).
- `/opt/scheduler/venv`: Python with the pinned solver (`ortools==9.15.6755`).
- `/var/lib/scheduler`: users, runs, results (owned by the `scheduler` account).
- `scheduler-web` service: the website on `127.0.0.1:8080`, restarted
  automatically; only reachable through Caddy.
- Caddy: HTTPS for `<your-ip>.sslip.io`, renewed automatically.
- Firewall: ports 80 and 443 opened; nothing else.
