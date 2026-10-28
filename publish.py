"""Episode assembly (M4A with chapters), upload to Cloudflare R2 and podcast feed."""

import json
import os
import subprocess
import tempfile
import xml.etree.ElementTree as ET
from datetime import datetime
from email.utils import format_datetime, parsedate_to_datetime
from pathlib import Path
from xml.sax.saxutils import escape

import boto3
import requests
from botocore.config import Config

import voice

SILENCE_SECONDS = 0.7
FEED_EPISODES = 14
FEED_TITLE = "Radio Newsletter"


def _prefix() -> str:
    return os.environ["R2_SECRET_PREFIX"].strip()


def _public_root() -> str:
    return os.environ["R2_PUBLIC_BASE_URL"].strip().rstrip("/")


def feed_url() -> str:
    return f"{_public_root()}/{_prefix()}/feed.xml"


def _s3():
    return boto3.client(
        "s3",
        endpoint_url=os.environ["R2_ENDPOINT"].strip(),
        aws_access_key_id=os.environ["R2_ACCESS_KEY_ID"].strip(),
        aws_secret_access_key=os.environ["R2_SECRET_ACCESS_KEY"].strip(),
        region_name="auto",
        config=Config(request_checksum_calculation="when_required"),
    )


def last_published() -> datetime | None:
    """Latest pubDate in the feed, or None if the feed does not exist yet."""
    resp = requests.get(feed_url(), timeout=15)
    if resp.status_code == 404:
        return None
    resp.raise_for_status()
    dates = [parsedate_to_datetime(e.text) for e in ET.fromstring(resp.content).iter("pubDate")]
    return max(dates, default=None)


def _meta_escape(text: str) -> str:
    """Escape a value for an ffmetadata file."""
    for ch in ("\\", "=", ";", "#", "\n"):
        text = text.replace(ch, "\\" + ch)
    return text


def assemble(segments: list[tuple[str, bytes]], title: str, path: Path) -> float:
    """Join PCM segments with silence, write an M4A with one chapter per segment. Returns seconds."""
    bytes_per_second = voice.PCM_RATE * 2
    silence = bytes(int(SILENCE_SECONDS * voice.PCM_RATE) * 2)
    pcm, chapters, start = b"", [], 0
    for i, (chapter_title, audio) in enumerate(segments):
        if i:
            pcm += silence
        pcm += audio
        chapters.append((start, len(pcm), chapter_title))
        start = len(pcm)

    lines = [";FFMETADATA1", f"title={_meta_escape(title)}", f"artist={FEED_TITLE}"]
    for begin, end, chapter_title in chapters:
        lines += ["[CHAPTER]", "TIMEBASE=1/1000",
                  f"START={begin * 1000 // bytes_per_second}", f"END={end * 1000 // bytes_per_second}",
                  f"title={_meta_escape(chapter_title)}"]

    with tempfile.TemporaryDirectory() as tmp:
        meta = Path(tmp) / "meta.txt"
        meta.write_text("\n".join(lines), encoding="utf-8")
        subprocess.run(
            ["ffmpeg", "-loglevel", "error", "-y", "-f", "s16le", "-ar", str(voice.PCM_RATE), "-ac", "1",
             "-i", "-", "-i", str(meta), "-map", "0:a", "-map_metadata", "1", "-map_chapters", "1",
             "-codec:a", "aac", "-b:a", "64k", "-movflags", "+faststart", str(path)],
            input=pcm, check=True,
        )
    return len(pcm) / bytes_per_second


def _description(meta: dict) -> str:
    items = []
    for s in meta["stories"]:
        source = escape(s["source"])
        if s.get("url"):
            source = '<a href="' + escape(s["url"]) + '">' + source + "</a>"
        items.append(f"<li>{escape(s['chapter_title'])} ({source})</li>")
    return f"<p>{escape(meta['summary'])}</p><p>Sources:</p><ul>{''.join(items)}</ul>"


def _write_feed(s3) -> None:
    """Rebuild feed.xml from the episodes present in the bucket (latest FEED_EPISODES)."""
    bucket, prefix = os.environ["R2_BUCKET"].strip(), _prefix()
    episodes = []
    for page in s3.get_paginator("list_objects_v2").paginate(Bucket=bucket, Prefix=f"{prefix}/episodes/"):
        episodes += [o for o in page.get("Contents", []) if o["Key"].endswith("/episode.m4a")]
    episodes = sorted(episodes, key=lambda o: o["Key"], reverse=True)[:FEED_EPISODES]

    items = []
    for ep in episodes:
        folder = ep["Key"].rsplit("/", 1)[0]
        meta = json.loads(s3.get_object(Bucket=bucket, Key=f"{folder}/script.json")["Body"].read())
        url = f"{_public_root()}/{ep['Key']}"
        items.append(f"""    <item>
      <title>{escape(meta['title'])}</title>
      <description><![CDATA[{_description(meta).replace(']]>', ']]]]><![CDATA[>')}]]></description>
      <enclosure url="{escape(url)}" length="{ep['Size']}" type="audio/x-m4a"/>
      <guid isPermaLink="false">{escape(ep['Key'])}</guid>
      <pubDate>{format_datetime(ep['LastModified'])}</pubDate>
      <itunes:duration>{meta['duration_seconds']}</itunes:duration>
      <itunes:explicit>false</itunes:explicit>
    </item>""")

    feed = f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd">
  <channel>
    <title>{FEED_TITLE}</title>
    <link>{escape(feed_url())}</link>
    <description>My newsletters, read aloud.</description>
    <language>{os.environ.get('EPISODE_LANGUAGE', 'en')}</language>
    <itunes:author>{FEED_TITLE}</itunes:author>
    <itunes:explicit>false</itunes:explicit>
    <itunes:type>episodic</itunes:type>
    <itunes:category text="News"/>
{chr(10).join(items)}
  </channel>
</rss>
"""
    s3.put_object(Bucket=bucket, Key=f"{prefix}/feed.xml", Body=feed.encode("utf-8"),
                  ContentType="application/rss+xml; charset=utf-8", CacheControl="no-cache")


def publish(audio: Path, script: dict, title: str, seconds: float, now: datetime) -> str:
    """Upload the episode and its script, then rebuild the feed. Returns the feed URL."""
    s3, bucket = _s3(), os.environ["R2_BUCKET"].strip()
    folder = f"{_prefix()}/episodes/{now.astimezone():%Y%m%d-%H%M%S}"
    meta = {**script, "title": title, "duration_seconds": round(seconds)}
    s3.upload_file(str(audio), bucket, f"{folder}/episode.m4a", ExtraArgs={"ContentType": "audio/x-m4a"})
    s3.put_object(Bucket=bucket, Key=f"{folder}/script.json", ContentType="application/json",
                  Body=json.dumps(meta, ensure_ascii=False, indent=2).encode("utf-8"))
    _write_feed(s3)
    return feed_url()
