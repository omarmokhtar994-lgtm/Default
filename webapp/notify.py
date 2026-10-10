# © 2026 Omar Mokhtar. All rights reserved.
"""Teams and Slack group posts for RTA changes (Phase AB; owner, 2026-10-10: "Start the Teams/Slack notifications
now", after approving samples 01 to 04 in evidence/phase_ab/samples).

Each LOB may post to one group: a Teams channel through a Workflows link ("Send webhook alerts to a channel") or a
Slack channel through an Incoming Webhooks link. A link lets anyone holding it post to the group, so it is a secret:
it is kept in the server's database, checked before it is saved and again before each send, and never shown in
full again."""
from __future__ import annotations

import json
import logging
import threading
from contextlib import contextmanager
from contextvars import ContextVar
import time
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timedelta, timezone
from typing import Any, Callable, Dict, Iterator, List, Optional, Tuple
from urllib.parse import quote_plus, urlsplit

from .day import ABSENT

log = logging.getLogger(__name__)

EGYPT = timezone(timedelta(hours=3))  # owner's rule: times in Egypt time (UTC+3)

# What can post, in the order the Notifications page lists it. Sick, unplanned leave and attendance set back to
# present are PRIVATE: never posted to a group, whatever is ticked.
KINDS = {
    "break": "Breaks and lunches moved, or put back to plan",
    "added_break": "Breaks and lunches added on the day",
    "overtime": "Overtime and VTO",
    "called_in": "Day off cancelled (called in)",
    "channel": "Channel changes",
    "aux": "Training, coaching, meetings and other aux",
    "late": "Late and left early",
}
DEFAULT_KINDS = ["break", "added_break", "overtime", "called_in", "channel"]
PRIVATE = "private"
MODES = ("off", "preview", "on")
HOLDS = {0: "At once", 120: "2 minutes", 300: "5 minutes"}  # seconds a LOB's changes wait so a burst goes as one
DEFAULT_HOLD = 120
MAX_HOLD = 600  # a busy day still posts: at most 10 minutes after the first change waiting
RETRIES = (60, 300, 900)  # a failed post is tried again after 1, 5 and 15 minutes, then shows as not posted
TIMEOUT = 10  # seconds a group may take to answer
SERVICES = {"teams": "Teams", "slack": "Slack"}

LINK_MAX = 2000
SLACK_HOST = "hooks.slack.com"
TEAMS_SUFFIXES = (".logic.azure.com", ".api.powerplatform.com")
NOT_HTTPS = "That is not a Teams or Slack group link: it has to start with https://."
NOT_GROUP = ("That is not a Teams or Slack group link. Teams links are on logic.azure.com or api.powerplatform.com; "
             "Slack links are on hooks.slack.com.")
SLACK_CHUNK = 2900  # characters per Slack section (Slack allows 3000)
SLACK_BLOCKS = 50


def check_link(url: str) -> str:
    """"teams" or "slack" for a group link this website may post to; ValueError otherwise. Only HTTPS on the groups'
    own hosts, so the website can never be pointed at its own network."""
    url = (url or "").strip()
    if not url:
        raise ValueError("Paste the group link.")
    if len(url) > LINK_MAX:
        raise ValueError("That link is too long to be a group link.")
    parts = urlsplit(url)
    if parts.scheme.lower() != "https":
        raise ValueError(NOT_HTTPS)
    try:
        port = parts.port
    except ValueError:
        raise ValueError(NOT_GROUP) from None
    host = (parts.hostname or "").lower()
    if parts.username is not None or parts.password is not None or port not in (None, 443):
        raise ValueError(NOT_GROUP)
    if host == SLACK_HOST:
        return "slack"
    if any(host.endswith(s) and len(host) > len(s) for s in TEAMS_SUFFIXES):
        return "teams"
    raise ValueError(NOT_GROUP)


def link_end(url: str) -> str:
    """The last four characters: enough for an admin to tell two links apart, too few to post with."""
    return (url or "").strip()[-4:]


def _hm(epoch: float) -> str:
    return datetime.fromtimestamp(epoch, EGYPT).strftime("%H:%M")


def _day(shift_date: str) -> str:
    return date.fromisoformat(shift_date).strftime("%a %d %b")


def _names(names: List[str]) -> str:
    return names[0] if len(names) == 1 else ", ".join(names[:-1]) + " and " + names[-1]


@dataclass
class Post:
    """What a group sees: a title, sections of (name, text) lines under an optional heading, a footer and a link
    that opens the RTA ("" for none)."""
    title: str
    sections: List[Tuple[str, List[Tuple[str, str]]]] = field(default_factory=list)
    footer: str = ""
    url: str = ""


def day_url(site: str, unit: str, shift_date: str) -> str:
    return f"{site}day?program={quote_plus(unit)}&date={shift_date}" if site else ""


def change_post(label: str, shift_date: str, items: List[Dict[str, Any]], site: str, unit: str) -> Post:
    """One post for a LOB's changes on one day, oldest first, saying who made them."""
    items = sorted(items, key=lambda i: i["at"])
    people: List[str] = []
    for i in items:
        if i["by_name"] not in people:
            people.append(i["by_name"])
    last = _hm(items[-1]["at"]) if items else ""
    footer = (f"Changed on the RTA by {people[0]}, {last}." if len(people) == 1 else
              f"Changed on the RTA by {_names(people)}; last at {last}." if people else "")
    return Post(title=f"{label}: changes for {_day(shift_date)}",
                sections=[("", [(i["associate"], i["text"]) for i in items])],
                footer=footer, url=day_url(site, unit, shift_date))


def _plain(text: str) -> str:
    return " ".join(str(text).replace("*", "").split())


def _teams(text: str) -> str:
    """Card text that can never form a Markdown link: "[a](b)" becomes "[a] (b)" (Phase AC); brackets stay readable."""
    return _plain(text).replace("](", "] (")


def teams_body(post: Post) -> Dict[str, Any]:
    """The message Teams' "Send webhook alerts to a channel" workflow posts: one Adaptive Card."""
    body: List[Dict[str, Any]] = [{"type": "TextBlock", "text": _teams(post.title), "weight": "Bolder",
                                   "size": "Medium", "wrap": True}]
    for heading, lines in post.sections:
        if heading:
            body.append({"type": "TextBlock", "text": f"**{_teams(heading)}**", "wrap": True, "spacing": "Medium"})
        if lines:
            body.append({"type": "TextBlock", "wrap": True,
                         "text": "\n".join(f"- **{_teams(n)}**: {_teams(t)}" for n, t in lines)})
    if post.footer:
        body.append({"type": "TextBlock", "text": _teams(post.footer), "isSubtle": True, "size": "Small",
                     "wrap": True})
    card: Dict[str, Any] = {"$schema": "http://adaptivecards.io/schemas/adaptive-card.json", "type": "AdaptiveCard",
                            "version": "1.4", "body": body, "msteams": {"width": "Full"}}
    if post.url:
        card["actions"] = [{"type": "Action.OpenUrl", "title": "Open the RTA", "url": post.url}]
    return {"type": "message", "attachments": [{"contentType": "application/vnd.microsoft.card.adaptive",
                                                "contentUrl": None, "content": card}]}


def _slack(text: str) -> str:
    """Slack's control characters escaped (no mention or link can be made from a name) and its bold marks removed."""
    return _plain(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def slack_body(post: Post) -> Dict[str, Any]:
    """An Incoming Webhooks message: the title, the lines in sections of at most 2900 characters, the footer."""
    lines: List[str] = []
    for heading, rows in post.sections:
        if heading:
            lines.append(f"*{_slack(heading)}*")
        lines += [f"• *{_slack(n)}*: {_slack(t)}" for n, t in rows]
    chunks: List[str] = []
    for line in lines:
        if chunks and len(chunks[-1]) + 1 + len(line) <= SLACK_CHUNK:
            chunks[-1] += "\n" + line
        else:
            chunks.append(line[:SLACK_CHUNK])
    room = SLACK_BLOCKS - 2  # the title and the footer
    if len(chunks) > room:
        left = sum(c.count("\n") + 1 for c in chunks[room - 1:])
        chunks = chunks[:room - 1] + [f"… and {left} more lines: open the RTA to see them."]
    blocks: List[Dict[str, Any]] = [{"type": "section", "text": {"type": "mrkdwn", "text": f"*{_slack(post.title)}*"}}]
    blocks += [{"type": "section", "text": {"type": "mrkdwn", "text": c}} for c in chunks]
    foot = _slack(post.footer) + (f" <{post.url}|Open the RTA>" if post.url else "")
    if foot.strip():
        blocks.append({"type": "context", "elements": [{"type": "mrkdwn", "text": foot.strip()}]})
    return {"text": _plain(post.title), "blocks": blocks}


def _clock_text(m: int) -> str:
    return f"{m // 60 % 24:02d}:{m % 60:02d}"


def breaks_post(label: str, unit: str, on: date, page: Dict[str, Any], site: str, at: float,
                changes_follow: bool) -> Post:
    """The day's breaks for a group (approved sample 04): one section per shift in start order, each person's breaks
    as they stand (a moved break at its new time). People marked sick or on unplanned leave are left out."""
    shifts: Dict[Tuple[int, str], List[Tuple[str, str]]] = {}
    for lane in page["view"]["lanes"]:
        for seg in lane["segments"]:
            if seg["offset"] != 0 or seg["status"] in ABSENT:
                continue
            breaks = sorted(seg["breaks"], key=lambda b: b["start"])
            text = ", ".join(f"{b['kind']} {_clock_text(b['start'])}" for b in breaks) or "No breaks planned"
            shifts.setdefault((seg["start"], seg["label"]), []).append((lane["name"], text))
    sections = []
    for (_, shift), people in sorted(shifts.items()):
        n = len(people)
        sections.append((f"{shift.replace(' - ', ' to ')} ({n} {'person' if n == 1 else 'people'})", sorted(people)))
    footer = f"As planned at {_hm(at)}." + (" Changes during the day are posted as they happen." if changes_follow
                                           else "")
    return Post(title=f"{label}: breaks for {on:%a %d %b}", sections=sections, footer=footer,
                url=day_url(site, unit, on.isoformat()))


def body_for(service: str, post: Post) -> Dict[str, Any]:
    return teams_body(post) if service == "teams" else slack_body(post)


# The RTA's "Post to the group" tick, unticked for one change (Phase AB, sample 03b). Set for the request that makes
# the change; read where the change is logged. A ContextVar, so each request thread sees only its own.
_LEFT_OUT: ContextVar[bool] = ContextVar("group_post_left_out", default=False)


@contextmanager
def leave_out(flag: bool) -> Iterator[None]:
    token = _LEFT_OUT.set(bool(flag))
    try:
        yield
    finally:
        _LEFT_OUT.reset(token)


def left_out_now() -> bool:
    return _LEFT_OUT.get()


# ----------------------------------------------------------------------------------------------- sending
class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """A group link that answers with a redirect is not followed: the answer is reported as it came."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):  # type: ignore[no-untyped-def]
        return None


_OPENER = urllib.request.build_opener(_NoRedirect)


def send_json(url: str, body: Dict[str, Any], timeout: float = TIMEOUT) -> Tuple[bool, int]:
    """POST ``body`` as JSON: (True, code) for a 2xx answer, (False, code) otherwise, (False, 0) when the group
    could not be reached in ``timeout`` seconds."""
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST",
                                 headers={"Content-Type": "application/json", "User-Agent": "TeamScheduler"})
    try:
        with _OPENER.open(req, timeout=timeout) as answer:
            code = answer.status
    except urllib.error.HTTPError as exc:
        code = exc.code
    except (urllib.error.URLError, OSError, ValueError):
        return False, 0
    return 200 <= code < 300, code


def post_json(url: str, body: Dict[str, Any]) -> Tuple[bool, int]:
    """The real transport: the link is checked again first, so only a Teams or Slack group is ever posted to."""
    check_link(url)
    return send_json(url, body)


def reason_for(service: str, code: int) -> str:
    """Why a post did not go, in words an admin can act on (never the link itself)."""
    name = SERVICES.get(service, "The group")
    if code == 0:
        return f"{name} could not be reached"
    if code == 400:
        return f"{name} refused the message (400)"
    if code in (401, 403):
        return f"{name} says this link may not post ({code}); replace the link"
    if code in (404, 410):
        return f"{name} says the link no longer works ({code}); replace the link"
    if code == 429:
        return f"{name} asked to slow down (429)"
    if 500 <= code < 600:
        return f"{name} had a problem ({code})"
    return f"{name} answered {code}"


# ----------------------------------------------------------------------------------------------- the queue
class Notifier:
    """Keeps each RTA change a LOB may post, sends a LOB's changes for a day as one post once they have waited the
    LOB's hold, and tries a failed post again. Everything it knows lives in the database, so a restart loses
    nothing and sends nothing twice. RTA requests only queue; the sending happens on the notifier's own thread."""

    def __init__(self, store, transport: Callable[[str, Dict[str, Any]], Tuple[bool, int]] = post_json,
                 clock: Callable[[], float] = time.time, label: Optional[Callable[[str], Optional[str]]] = None,
                 days=None) -> None:
        self.store, self.transport, self.clock, self.days = store, transport, clock, days
        self._label = label
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None

    def label(self, unit: str) -> str:
        return (self._label(unit) if self._label else None) or unit

    # ------------------------------------------------------------------ queue
    def queue(self, log_id: Optional[int], unit: str, shift_date: str, associate: str, kind: str, text: str,
              by_name: str, ref: str = "", before: str = "", after: str = "", left_out: bool = False) -> None:
        """Keep one RTA change for the LOB's group, or say why it will not be posted. A LOB that posts nowhere
        keeps nothing."""
        settings = self.store.get_notify(unit)
        if not settings or settings["mode"] not in ("on", "preview"):
            return
        ticked = [k for k in settings["kinds"].split(",") if k]
        if kind == PRIVATE:
            status, reason = "skipped", "kept private"
        elif left_out:
            status, reason = "skipped", "left out on the RTA"
        elif kind not in ticked:
            status, reason = "skipped", "not ticked for this LOB"
        else:
            status, reason = "waiting", ""
        with self._lock:
            made = self.store.add_notify_item(log_id=log_id, unit=unit, shift_date=shift_date, associate=associate,
                                              kind=kind, text=text, ref=ref, before=before, after=after,
                                              by_name=by_name, at=self.clock(), status=status, reason=reason)
            if ref:  # back where it was before anything was posted: nothing to tell the group
                same = [i for i in self.store.notify_items(unit=unit, shift_date=shift_date, status="waiting")
                        if i["ref"] == ref and i["id"] != made]
                if same and same[0]["before"] == after:
                    self.store.set_notify_items([i["id"] for i in same] + ([made] if status == "waiting" else []),
                                                status="skipped", reason="undone before it was posted")

    # ------------------------------------------------------------------ send
    def run_once(self, now: Optional[float] = None) -> int:
        """Send what is due; returns how many posts were tried. One LOB's trouble never stops another."""
        now = self.clock() if now is None else now
        with self._lock:  # with queue(): an item is either still waiting (and can be undone) or in a post
            for settings in self.store.list_notify():
                try:
                    self._batch(settings, now)
                except Exception:  # noqa: BLE001 (kept going for the other LOBs; the cause goes to the log)
                    log.exception("group posts: could not prepare the posts of %s", settings["unit"])
        for settings in self.store.list_notify():
            try:
                self._morning(settings, now)
            except Exception:  # noqa: BLE001
                log.exception("group posts: could not prepare the day's breaks of %s", settings["unit"])
        tried = 0  # sending holds no lock: an RTA change never waits for a slow group
        for post in reversed(self.store.notify_posts(status="waiting")):
            if (post["next_at"] or 0) > now:
                continue
            try:
                tried += self._attempt(post, now)
            except Exception:  # noqa: BLE001
                log.exception("group posts: could not send post %s", post["id"])
        return tried

    def _due(self, items: List[Dict[str, Any]], hold: int) -> float:
        return min(max(i["at"] for i in items) + hold, min(i["at"] for i in items) + MAX_HOLD)

    def _batch(self, settings: Dict[str, Any], now: float) -> None:
        unit = settings["unit"]
        waiting = self.store.notify_items(unit=unit, status="waiting")
        if not waiting:
            return
        if settings["mode"] not in ("on", "preview"):
            self.store.set_notify_items([i["id"] for i in waiting], status="skipped", reason="posting was turned off")
            return
        days: Dict[str, List[Dict[str, Any]]] = {}
        for i in waiting:
            days.setdefault(i["shift_date"], []).append(i)
        for shift_date, items in sorted(days.items()):
            if now < self._due(items, int(settings["hold"])):
                continue
            post = change_post(self.label(unit), shift_date, items, settings["site"], unit)
            preview = settings["mode"] == "preview"
            made = self.store.add_notify_post(unit=unit, shift_date=shift_date, what="changes",
                                              service=settings["service"], count=len(items),
                                              status="preview" if preview else "waiting", tries=0, next_at=now,
                                              body=json.dumps(asdict(post)), made_at=now)
            self.store.set_notify_items([i["id"] for i in items], status="preview" if preview else "sending",
                                        post_id=made)

    MORNING_WINDOW = 2 * 3600  # a day's breaks post goes within two hours of its time, or not that day

    def _morning(self, settings: Dict[str, Any], now: float) -> None:
        """The day's breaks post (sample 04): once per LOB and day, from its set time to two hours after it."""
        if not settings["morning"] or settings["mode"] not in ("on", "preview") or self.days is None:
            return
        local = datetime.fromtimestamp(now, EGYPT)
        hh, mm = (int(x) for x in settings["morning"].split(":"))
        set_at = local.replace(hour=hh, minute=mm, second=0, microsecond=0)
        if not set_at <= local < set_at + timedelta(seconds=self.MORNING_WINDOW):
            return
        on = local.date() + timedelta(days=1 if settings["morning_day"] == "before" else 0)
        unit = settings["unit"]
        if self.store.notify_posts(unit=unit, what="morning", shift_date=on.isoformat(), limit=1):
            return
        common = {"unit": unit, "shift_date": on.isoformat(), "what": "morning", "service": settings["service"],
                  "made_at": now}
        try:
            page = self.days.page(unit, on)
        except ValueError as exc:  # the day cannot be worked out: said once, on the Notifications page
            self.store.add_notify_post(**common, status="skipped", reason=str(exc))
            return
        if page is None:
            self.store.add_notify_post(**common, status="skipped", reason="there is no schedule in use for that day")
            return
        changes_follow = settings["mode"] == "on" and bool(settings["kinds"])
        post = breaks_post(self.label(unit), unit, on, page, settings["site"], now, changes_follow)
        people = sum(len(lines) for _, lines in post.sections)
        self.store.add_notify_post(**common, count=people, status="preview" if settings["mode"] == "preview"
                                   else "waiting", tries=0, next_at=now, body=json.dumps(asdict(post)))

    def _finish(self, post: Dict[str, Any], status: str, reason: str = "", **fields: Any) -> None:
        self.store.set_notify_post(post["id"], status=status, reason=reason, **fields)
        self.store.set_notify_items([i["id"] for i in self.store.notify_items(post_id=post["id"])],
                                    status=status, reason=reason)

    def _attempt(self, post: Dict[str, Any], now: float) -> int:
        settings = self.store.get_notify(post["unit"])
        if not settings or settings["mode"] != "on":
            self._finish(post, "failed", "posting was turned off")
            return 0
        if not settings["link"]:
            self._finish(post, "failed", "the group link was removed")
            return 0
        try:
            service = check_link(settings["link"])
        except ValueError:
            self._finish(post, "failed", "the saved group link is not a Teams or Slack link")
            return 0
        body = body_for(service, Post(**json.loads(post["body"])))
        try:
            ok, code = self.transport(settings["link"], body)
        except Exception:  # noqa: BLE001 (an unexpected network failure is a failed try like any other)
            log.exception("group posts: sending post %s failed", post["id"])
            ok, code = False, 0
        if ok:
            self._finish(post, "sent", service=service, sent_at=now)
            return 1
        tries = int(post["tries"]) + 1
        reason = reason_for(service, code)
        if tries > len(RETRIES):
            self._finish(post, "failed", reason, service=service, tries=tries)
        else:
            self.store.set_notify_post(post["id"], service=service, tries=tries, reason=reason,
                                       next_at=now + RETRIES[tries - 1])
        return 1

    # ------------------------------------------------------------------ what the RTA shows
    def statuses(self, unit: str, shift_date: str) -> Dict[int, Dict[str, str]]:
        """For each day-log line of the LOB's day that the group rule saw: its state and the words the RTA shows."""
        items = self.store.notify_items(unit=unit, shift_date=shift_date)
        if not items:
            return {}
        settings = self.store.get_notify(unit) or {"hold": DEFAULT_HOLD}
        waiting = [i for i in items if i["status"] == "waiting"]
        due = self._due(waiting, int(settings["hold"])) if waiting else 0
        posts = {p["id"]: p for p in self.store.notify_posts(unit=unit, shift_date=shift_date)}
        out: Dict[int, Dict[str, str]] = {}
        for i in items:
            if i["log_id"] is None:
                continue
            post = posts.get(i["post_id"] or 0, {})
            name = SERVICES.get(post.get("service", ""), "the group")
            if i["status"] == "waiting":
                out[i["log_id"]] = {"state": "waiting", "text": f"Waiting: posts by {_hm(due)}"}
            elif i["status"] == "sending" and not post.get("tries"):
                out[i["log_id"]] = {"state": "waiting", "text": "Posting now"}
            elif i["status"] == "sending":
                out[i["log_id"]] = {"state": "waiting",
                                    "text": f"Waiting: {name} did not take it, trying again at {_hm(post['next_at'])}"}
            elif i["status"] == "sent":
                out[i["log_id"]] = {"state": "sent", "text": f"Posted to {name}, {_hm(post['sent_at'])}"}
            elif i["status"] == "preview":
                out[i["log_id"]] = {"state": "preview", "text": "Preview only: not sent"}
            else:
                out[i["log_id"]] = {"state": i["status"], "text": f"Not posted: {i['reason']}"}
        return out

    # ------------------------------------------------------------------ the Notifications page
    def send_test(self, unit: str, by_name: str) -> Tuple[bool, str]:
        """Post a short test to the LOB's saved group now (an admin pressed Send test message, so the answer is shown
        at once); the result is kept with the LOB's posts. Returns (posted, what to tell the admin)."""
        settings = self.store.get_notify(unit)
        if not settings or not settings["link"]:
            return False, "Save a group link first."
        try:
            service = check_link(settings["link"])
        except ValueError:
            return False, "The saved link is not a Teams or Slack group link: paste the link again."
        now = self.clock()
        post = Post(title=f"{self.label(unit)}: test from Team Scheduler",
                    footer=f"Sent by {by_name} at {_hm(now)}. RTA changes for this LOB post here.")
        try:
            ok, code = self.transport(settings["link"], body_for(service, post))
        except Exception:  # noqa: BLE001
            log.exception("group posts: the test message for %s failed", unit)
            ok, code = False, 0
        reason = "" if ok else reason_for(service, code)
        self.store.add_notify_post(unit=unit, shift_date=datetime.fromtimestamp(now, EGYPT).date().isoformat(),
                                   what="test", service=service, count=0, status="sent" if ok else "failed",
                                   sent_at=now if ok else None, reason=reason, body=json.dumps(asdict(post)),
                                   made_at=now)
        return ok, (f"Test message posted to {SERVICES[service]}." if ok else f"Test message not posted: {reason}.")

    # ------------------------------------------------------------------ the thread
    def start(self, every: float = 15) -> None:
        """Send on a daemon thread every ``every`` seconds; an error is logged and the loop goes on."""
        if self._thread is not None:
            return

        def loop() -> None:
            while not self._stop.wait(every):
                try:
                    self.run_once()
                except Exception:  # noqa: BLE001
                    log.exception("group posts: a round failed")

        self._thread = threading.Thread(target=loop, name="group-posts", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()


# ----------------------------------------------------------------------------------------------- page words
MODE_WORDS = {"on": "On", "preview": "Preview only", "off": "Off"}


def _changes(count: int) -> str:
    return f"{count} change{'' if count == 1 else 's'}"


def post_what(p: Dict[str, Any]) -> str:
    """What a kept post was, as the Notifications page lists it."""
    return {"test": "Test message", "morning": "Day's breaks"}.get(p["what"], _changes(int(p["count"] or 0)))


def post_result(p: Dict[str, Any]) -> Tuple[str, str]:
    """(state, words) for a kept post: sent, waiting, preview, skipped or failed."""
    name = SERVICES.get(p["service"], "the group")
    tries = int(p["tries"] or 0)
    if p["status"] == "sent":
        return "sent", f"Posted to {name}" + (f" after {tries} retr{'y' if tries == 1 else 'ies'}" if tries else "")
    if p["status"] == "preview":
        return "preview", "Preview only: not sent"
    if p["status"] == "waiting":
        return "waiting", f"Waiting: trying again at {_hm(p['next_at'])}" if tries else "Waiting"
    return p["status"], f"Not posted: {p['reason']}"


def last_line(p: Dict[str, Any]) -> str:
    """A LOB's newest post in a few words, for the list of LOBs."""
    at = _hm(p["sent_at"] or p["made_at"])
    what = {"test": "the test message", "morning": "the day's breaks"}.get(p["what"], _changes(int(p["count"] or 0)))
    if p["status"] == "sent":
        return f"Posted {what} at {at}"
    if p["status"] == "preview":
        return f"{what[0].upper() + what[1:]} would have been posted at {at}"
    if p["status"] == "waiting":
        return "Waiting to post"
    return f"Not posted at {at}: {p['reason']}"
