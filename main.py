"""Radio Newsletter: command-line entry point."""

import argparse
import json
import os
from datetime import datetime, timedelta
from itertools import zip_longest
from pathlib import Path

from dotenv import load_dotenv

import editor
import publish
import voice
from articles import fetch_articles
from mail import fetch_newsletters

MAX_LINKS_DUMP = 40
MAX_WINDOW_DAYS = 5
FIRST_WINDOW_DAYS = 3
WORDS_PER_MINUTE = 150
# Episode languages, chosen with EPISODE_LANGUAGE. To add one, add an entry here.
LANGUAGES = {
    "en": {
        "name": "English", "voice_code": "en-US", "opening": "Opening", "closing": "Closing",
        "date": "{weekday}, {month} {day}, {year}",
        "weekdays": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"],
        "months": ["January", "February", "March", "April", "May", "June", "July", "August",
                   "September", "October", "November", "December"],
    },
    "it": {
        "name": "Italian", "voice_code": "it-IT", "opening": "Apertura", "closing": "Chiusura",
        "date": "{weekday} {day} {month} {year}",
        "weekdays": ["lunedì", "martedì", "mercoledì", "giovedì", "venerdì", "sabato", "domenica"],
        "months": ["gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno", "luglio", "agosto",
                   "settembre", "ottobre", "novembre", "dicembre"],
    },
    "fr": {
        "name": "French", "voice_code": "fr-FR", "opening": "Ouverture", "closing": "Conclusion",
        "date": "{weekday} {day} {month} {year}",
        "weekdays": ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"],
        "months": ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août",
                   "septembre", "octobre", "novembre", "décembre"],
    },
}


def language() -> dict:
    return LANGUAGES[os.environ.get("EPISODE_LANGUAGE", "en")]


def window_start(now: datetime) -> datetime:
    last = publish.last_published()
    if last is None:
        return now - timedelta(days=FIRST_WINDOW_DAYS)
    return max(last, now - timedelta(days=MAX_WINDOW_DAYS))


def date_label(now: datetime) -> str:
    lang = language()
    return lang["date"].format(weekday=lang["weekdays"][now.weekday()], day=now.day,
                               month=lang["months"][now.month - 1], year=now.year)


def dump(now: datetime) -> None:
    since = window_start(now)
    newsletters = fetch_newsletters(since)
    # Round-robin across newsletters, so that the first links do not all come from one sender.
    links = [l for row in zip_longest(*(n["links"] for n in newsletters)) for l in row if l]
    articles = fetch_articles(links[:MAX_LINKS_DUMP])
    good = [a for a in articles if a["text"]]

    lines = [f"# Dump {now:%Y-%m-%d %H:%M}", f"Window: since {since:%Y-%m-%d %H:%M}", ""]
    for n in newsletters:
        lines += [f"## Newsletter {n['id']}: {n['subject']}",
                  f"From: {n['from']} | Received: {n['received']:%Y-%m-%d %H:%M}", "",
                  n["text"], "", "Links:"]
        lines += [f"- {l['anchor']}: {l['url']}" for l in n["links"]]
        lines.append("")
    lines += ["# Articles read", ""]
    for a in good:
        lines += [f"## {a['anchor']}", f"{a['final_url']} ({a['words']} words)", "", a["text"], ""]
    lines += ["# Articles discarded", ""]
    lines += [f"- {a['anchor']}: {a['final_url']} ({a['error']})" for a in articles if not a["text"]]

    out = Path("out") / f"{now:%Y-%m-%d}" / "dump.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines), encoding="utf-8")

    print(f"Newsletters: {len(newsletters)}")
    print(f"Links: {len(links)} (opened the first {len(articles)})")
    print(f"Articles read (>= 300 words): {len(good)}")
    print(f"Discarded: {len(articles) - len(good)}")
    print(f"Dump: {out}")


def script_only(now: datetime) -> dict:
    newsletters = fetch_newsletters(window_start(now))
    by_id = {n["id"]: n for n in newsletters}
    candidates, links = editor.select_stories(newsletters)

    # Open only the links the selection chose; unreadable articles are dropped silently.
    link_ids = list(dict.fromkeys(c["link"] for c in candidates if c["link"] in links))
    articles = dict(zip(link_ids, fetch_articles([links[i] for i in link_ids])))
    ready = []
    for c in candidates:
        # The model sometimes writes the newsletter id as "N16" instead of "16".
        nid = "".join(ch for ch in str(c["newsletter_id"]) if ch.isdigit())
        if c["link"] is None and nid in by_id:
            ready.append({**c, "url": None, "text": by_id[nid]["text"]})
        elif c["link"] in articles and articles[c["link"]]["text"]:
            a = articles[c["link"]]
            ready.append({**c, "url": a["final_url"], "text": a["text"]})

    script = editor.write_script(ready, date_label(now), language()["name"])

    out = Path("out") / f"{now:%Y-%m-%d}"
    out.mkdir(parents=True, exist_ok=True)
    (out / "selection.json").write_text(
        json.dumps(candidates, ensure_ascii=False, indent=2), encoding="utf-8")
    (out / "script.json").write_text(
        json.dumps(script, ensure_ascii=False, indent=2), encoding="utf-8")

    counts = [len(s["text"].split()) for s in script["stories"]]
    print(script["summary"], "\n")
    for s, n in zip(script["stories"], counts):
        print(f"## {s['chapter_title']} ({n} words, {s['source']})\n\n{s['text']}\n")
    print(script["closing"], "\n")

    words = len(script["summary"].split()) + sum(counts) + len(script["closing"].split())
    print(f"Newsletters: {len(newsletters)} | candidates: {len(candidates)} | with text: {len(ready)}")
    print(f"Stories: {len(counts)} (expected 5) | words in stories: {sum(counts)} (expected 2,700-3,300)")
    print(f"LLM tokens: {editor.usage['input']} input, {editor.usage['output']} output")
    print(f"Estimated audio: {words / WORDS_PER_MINUTE:.1f} minutes")
    print(f"Files: {out}/selection.json, {out}/script.json")
    return script


def publish_episode(script: dict, now: datetime) -> None:
    lang = language()
    segments = [(lang["opening"], script["summary"])]
    segments += [(s["chapter_title"], s["text"]) for s in script["stories"]]
    segments.append((lang["closing"], script["closing"]))
    audio = [(title, voice.synthesize(text, lang["voice_code"])) for title, text in segments]

    title = f"{publish.FEED_TITLE} — {date_label(now)}"
    out = Path("out") / f"{now:%Y-%m-%d}"
    out.mkdir(parents=True, exist_ok=True)
    m4a = out / "episode.m4a"
    seconds = publish.assemble(audio, title, m4a)
    url = publish.publish(m4a, script, title, seconds, now)

    minutes = voice.usage["seconds"] / 60
    print(f"Episode: {seconds / 60:.1f} minutes, {m4a.stat().st_size / 1e6:.1f} MB, {len(audio)} chapters")
    print(f"Voice: {minutes:.1f} minutes generated (estimated cost: ${minutes * voice.COST_PER_MINUTE:.2f})")
    print(f"Feed: {url}")


def voice_sample(now: datetime) -> None:
    out = Path("out") / f"{now:%Y-%m-%d}"
    script = json.loads((out / "script.json").read_text(encoding="utf-8"))
    story = script["stories"][0]
    voice.write_wav(voice.synthesize(story["text"], language()["voice_code"]), out / "sample.wav")

    minutes = voice.usage["seconds"] / 60
    print(f"Story: {story['chapter_title']} ({len(story['text'].split())} words)")
    print(f"Audio generated: {minutes:.1f} minutes (estimated cost: ${minutes * voice.COST_PER_MINUTE:.2f})")
    print(f"File: {out}/sample.wav")


def main() -> None:
    load_dotenv()
    parser = argparse.ArgumentParser(description="Radio Newsletter")
    parser.add_argument("--dump", action="store_true", help="save newsletters and articles, no LLM")
    parser.add_argument("--script-only", action="store_true",
                        help="selection and script, saved to files, no voice")
    parser.add_argument("--voice-sample", action="store_true",
                        help="synthesize the first story of out/<today>/script.json")
    parser.add_argument("--publish", action="store_true",
                        help="voice and publishing of out/<today>/script.json, no LLM calls")
    args = parser.parse_args()
    now = datetime.now().astimezone()
    if args.voice_sample:
        voice_sample(now)
    elif args.publish:
        out = Path("out") / f"{now:%Y-%m-%d}"
        publish_episode(json.loads((out / "script.json").read_text(encoding="utf-8")), now)
    elif args.script_only:
        script_only(now)
    elif args.dump:
        dump(now)
    else:
        publish_episode(script_only(now), now)


if __name__ == "__main__":
    main()
