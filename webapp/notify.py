# © 2026 Omar Mokhtar. All rights reserved.
"""Teams and Slack group posts for RTA changes (Phase AB; owner, 2026-10-10: "Start the Teams/Slack notifications
now", after approving samples 01 to 04 in evidence/phase_ab/samples).

Each LOB may post to one group: a Teams channel through a Workflows link ("Send webhook alerts to a channel") or a
Slack channel through an Incoming Webhooks link. A link lets anyone holding it post to the group, so it is a secret:
it is kept in the server's database, checked before it is saved and again before each send, and never shown in
full again."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Tuple
from urllib.parse import quote_plus, urlsplit

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


def teams_body(post: Post) -> Dict[str, Any]:
    """The message Teams' "Send webhook alerts to a channel" workflow posts: one Adaptive Card."""
    body: List[Dict[str, Any]] = [{"type": "TextBlock", "text": _plain(post.title), "weight": "Bolder",
                                   "size": "Medium", "wrap": True}]
    for heading, lines in post.sections:
        if heading:
            body.append({"type": "TextBlock", "text": f"**{_plain(heading)}**", "wrap": True, "spacing": "Medium"})
        if lines:
            body.append({"type": "TextBlock", "wrap": True,
                         "text": "\n".join(f"- **{_plain(n)}**: {_plain(t)}" for n, t in lines)})
    if post.footer:
        body.append({"type": "TextBlock", "text": _plain(post.footer), "isSubtle": True, "size": "Small",
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


def body_for(service: str, post: Post) -> Dict[str, Any]:
    return teams_body(post) if service == "teams" else slack_body(post)
