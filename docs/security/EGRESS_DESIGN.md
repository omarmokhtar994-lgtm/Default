# Outbound network access: what the website needs, and a practical restriction design (2026-11-11)

Status: **a design, not installed.** Nothing here changes the live server. The cloud rule set and the host firewall were read from the evidence the owner
supplied (security list: all IPv4 egress allowed; host OUTPUT default ACCEPT); they were not probed.

## What the website itself needs (from the source)
The only outbound network client in the website is `webapp/notify.py` (urllib, HTTPS POST). A repository-wide search found no other `requests`,
`http.client`, `socket`, `smtplib` or `urlopen` use outside tests. Its limits: the link must be https on port 443 with no user-info, its host must be
`hooks.slack.com`, `*.logic.azure.com` or `*.api.powerplatform.com` (checked again at send time), redirects are not followed, the timeout is short.
The solver runs as a local child process and opens no network.

So at run time the website needs, and only if group notifications are used:
- DNS to resolve those names, and TCP 443 to the addresses they resolve to.
Without notifications it needs **no outbound access at all** (everything else is localhost: Waitress on 127.0.0.1:8080 behind Caddy).

## What else on the machine needs outbound access (not the website's account)
| Need | Who | When |
|---|---|---|
| Certificates (Let's Encrypt / ZeroSSL, ports 80/443 out) | Caddy (its own account) | at issue and renewal |
| Operating-system updates, Python packages (`pip`) | root, during maintenance | maintenance windows |
| Time (NTP), DNS resolver, Oracle's instance metadata (link-local 169.254.169.254) | OS and Oracle agents | always |
| `curl api.ipify.org` | `install.sh` only, once | first install |

## Why "allow TCP 443 anywhere" is not isolation
A compromised website process can reach any HTTPS host: it can send data out, or fetch more code, over a port that looks like normal traffic. The
current rule (all IPv4 egress) means the compromise boundary is the host, not the network.

## Design (cheapest first)
1. **Per-account rule on the host.** The website runs as its own account (`scheduler`), so the host firewall can match on it: drop everything the
   account sends except loopback. This needs no list of IP addresses, is independent of how Slack or Teams change their addresses, and leaves Caddy,
   root and the operating system untouched. nftables sketch (candidate, untested on the server):

   ```
   table inet scheduler_egress {
     chain output {
       type filter hook output priority 0; policy accept;
       meta skuid "scheduler" oifname "lo" accept
       meta skuid "scheduler" counter reject with icmpx type admin-prohibited
     }
   }
   ```
   With this, notifications stop working. They either stay off, or go through (2).
2. **Notifications through a forwarder that allows by name.** Run a small forward proxy (for example Squid or tinyproxy) on the same host, as a different
   account, allowed to reach only the approved Slack/Teams names; let the `scheduler` account reach only that proxy on loopback; point `notify.py` at it
   (`HTTPS_PROXY` in the service file; urllib honours it). The proxy enforces the allow-list by name, which the host firewall cannot. This is a code-free
   change for the website but a new component to keep patched.
3. **Cloud layer.** In the security list, change egress from "all" to: TCP 443, TCP 80, UDP/TCP 53, UDP 123 to 0.0.0.0/0 (still not isolation, but it
   removes every other port and protocol), or an Oracle Network Firewall with FQDN rules for (2)'s names. Do this after the host rules, and keep the
   SSH ingress path working so a mistake can be undone.
4. **IPv6.** Check that the subnet has no IPv6 prefix or route; if it does, every rule above needs its IPv6 twin.

## Order and rollback
Apply (1) with a 10-minute automatic revert (`systemd-run --on-active=10m nft delete table inet scheduler_egress`) so a mistake cannot lock anything
out, test that sign-in, a schedule download and a run still work, and only then make it permanent. Rollback is deleting that table.

## Not established by this review (needs the owner, InfoSec or live evidence)
- Whether the four configured Slack and two preview destinations are approved, who owns them, and what fields a post may carry (the post text is
  built from schedule and attendance data, see `Post` in `notify.py`). Webhook links are secrets stored in the database; masking in the page is not
  encryption at rest.
- Effective firewall rules beyond the collector's summary, IPv6, and any other route (the evidence shows one route to the Internet Gateway).
- That nothing on the host other than the website's account holds credentials for other systems.
