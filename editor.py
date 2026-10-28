"""LLM calls: story selection and script writing."""

import json
import os
from pathlib import Path

import requests

NEWSLETTER_CHARS = 4000
ARTICLE_WORDS = 2500
API_URL = "https://api.anthropic.com/v1/messages"

# Token counts across all calls of this run, retries included.
usage = {"input": 0, "output": 0}


def _prompt(name: str, **values: str) -> str:
    text = (Path("prompts") / f"{name}.md").read_text(encoding="utf-8")
    # The prompts contain JSON braces: str.format would choke on them.
    for key, value in values.items():
        text = text.replace("{" + key + "}", value)
    return text


def _call(model_var: str, prompt: str, max_tokens: int) -> dict:
    """Call the model and parse its JSON answer; one more try if it is not valid JSON."""
    for attempt in (1, 2):
        resp = requests.post(
            API_URL,
            headers={
                "x-api-key": os.environ["ANTHROPIC_API_KEY"],
                "anthropic-version": "2023-06-01",
            },
            json={
                "model": os.environ[model_var],
                "max_tokens": max_tokens,
                "messages": [{"role": "user", "content": prompt}],
            },
            timeout=300,
        )
        if not resp.ok:
            raise RuntimeError(f"Anthropic API error ({resp.status_code}): {resp.text[:300]}")
        body = resp.json()
        usage["input"] += body["usage"]["input_tokens"]
        usage["output"] += body["usage"]["output_tokens"]
        # The answer may be preceded by non-text blocks (e.g. reasoning).
        answer = "".join(b["text"] for b in body["content"] if b["type"] == "text")
        try:
            return json.loads(answer)
        except json.JSONDecodeError:
            if attempt == 2:
                raise RuntimeError(
                    f"{model_var}: answer is not valid JSON, even on the second try "
                    f"(stop_reason={body.get('stop_reason')}, {len(answer)} characters). "
                    f"End of the answer: ...{answer[-300:]!r}")


def select_stories(newsletters: list[dict]) -> tuple[list[dict], dict[str, dict]]:
    """Return the candidate stories and the numbered links (L1, L2...) they refer to."""
    links, blocks = {}, []
    for n in newsletters:
        lines = [f"### Newsletter {n['id']}: {n['subject']}",
                 f"From: {n['from']} | Received: {n['received']:%Y-%m-%d %H:%M}", "",
                 n["text"][:NEWSLETTER_CHARS], "", "Links:"]
        for l in n["links"]:
            link_id = f"L{len(links) + 1}"
            links[link_id] = l
            lines.append(f"{link_id}: {l['anchor']}")
        blocks.append("\n".join(lines))
    prompt = _prompt("selection", newsletters="\n\n".join(blocks))
    answer = _call("MODEL_SELECTION", prompt, 16000)
    # The model sometimes returns the bare list instead of {"candidates": [...]}.
    return (answer["candidates"] if isinstance(answer, dict) else answer), links


def write_script(candidates: list[dict], date_label: str, language: str) -> dict:
    """`candidates` carry a "text" key: the article, or the newsletter when there is no link."""
    blocks = []
    for c in candidates:
        words = c["text"].split()
        text = " ".join(words[:ARTICLE_WORDS]) if len(words) > ARTICLE_WORDS else c["text"]
        blocks.append(f"### Candidate {c['id']}: {c['working_title']}\n"
                      f"Source: {c['source']}\nURL: {c.get('url') or 'null'}\n\n{text}")
    prompt = _prompt("script", language=language, date=date_label, candidates="\n\n".join(blocks))
    return _call("MODEL_SCRIPT", prompt, 32000)
