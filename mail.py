"""Read-only IMAP access to the Gmail newsletter label."""

import email
import email.policy
import imaplib
import os
import re
from datetime import datetime

import lxml.html
import trafilatura

# Links never worth opening. Matched against anchor text and URL before any request,
# so that e.g. an unsubscribe link is never followed.
# Applied only to short anchors: article titles are longer and may contain these words.
SKIP_ANCHOR = re.compile(
    r"\b(unsubscribe|disiscri\w*|désabonn\w*|desabonn\w*|uitschrijven|opt.?out|preferen\w*|préféren\w*|manage|gérer|"
    r"view (it )?(in|on) (your )?browser|view online|web version|apri nel browser|"
    r"forward|share|condividi|partager|subscribe|abbonati|s'abonner|sign up|"
    r"download the app|get the app|app store|google play|privacy|terms|"
    r"like|comment|reply|restack|upgrade)\b",
    re.I,
)
# Senders to ignore, e.g. newsletters whose articles are all behind a paywall.
SKIP_SENDER = re.compile(r"economist\.com", re.I)
SKIP_URL = re.compile(
    r"^(mailto|tel):|unsubscribe|optout|opt-out|preferences|list-manage\.com/profile|"
    r"/subscribe|substack\.com/@|"
    r"^https?://([^/]*\.)?(twitter|x|facebook|instagram|linkedin|tiktok|threads|bsky|youtube|"
    r"apps\.apple|play\.google)\.(com|net|app)/",
    re.I,
)


def fetch_newsletters(since: datetime) -> list[dict]:
    """Return newsletters received after `since` (timezone-aware), oldest first."""
    conn = imaplib.IMAP4_SSL("imap.gmail.com")
    conn.login(os.environ["GMAIL_ADDRESS"], os.environ["GMAIL_APP_PASSWORD"])
    try:
        # readonly=True issues EXAMINE: the server cannot change any flag.
        status, _ = conn.select(f'"{os.environ.get("GMAIL_FOLDER", "Newsletter")}"', readonly=True)
        if status != "OK":
            raise RuntimeError("IMAP folder not found: check GMAIL_FOLDER and 'Show in IMAP'")
        # IMAP SINCE has day granularity: refine with INTERNALDATE below.
        _, data = conn.uid("search", None, "SINCE", since.strftime("%d-%b-%Y"))
        newsletters = []
        for uid in data[0].split():
            _, parts = conn.uid("fetch", uid, "(INTERNALDATE BODY.PEEK[])")
            received = imaplib.Internaldate2tuple(parts[0][0])
            received = datetime(*received[:6]).astimezone() if received else None
            if received is None or received < since:
                continue
            msg = email.message_from_bytes(parts[0][1], policy=email.policy.default)
            if SKIP_SENDER.search(str(msg["From"])):
                continue
            newsletters.append({"id": uid.decode(), "received": received, **_parse(msg)})
    finally:
        conn.logout()
    return sorted(newsletters, key=lambda n: n["received"])


def _parse(msg) -> dict:
    html_part = msg.get_body(("html",))
    plain_part = msg.get_body(("plain",))
    html = html_part.get_content() if html_part else ""
    plain = plain_part.get_content() if plain_part else ""
    text = (trafilatura.extract(html, favor_recall=True) if html else None) or plain
    return {
        "from": str(msg["From"]),
        "subject": str(msg["Subject"]),
        "text": text.strip(),
        "links": _links(html) if html else [],
    }


def _links(html: str) -> list[dict]:
    links, seen = [], set()
    for a in lxml.html.fromstring(html).xpath("//a[@href]"):
        url = a.get("href").strip()
        anchor = " ".join(a.text_content().split())
        # Empty anchors are logos and image duplicates of a text link.
        if not anchor or not url.startswith("http") or url in seen:
            continue
        if (len(anchor.split()) <= 5 and SKIP_ANCHOR.search(anchor)) or SKIP_URL.search(url):
            continue
        seen.add(url)
        links.append({"anchor": anchor, "url": url})
    return links
