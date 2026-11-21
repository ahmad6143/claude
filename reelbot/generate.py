"""Pick a topic and have Claude write the reel script as JSON."""
import itertools
import json
import os
import re

import anthropic

DEFAULT_MODEL = "claude-sonnet-5-5"

SYSTEM = """You write scripts for short vertical business reels (about 20-30 seconds).
The viewer is a busy small-business owner scrolling quickly. Be concrete, practical and plain-spoken.

Hard rules:
- Never invent statistics, percentages, savings figures, customer stories or testimonials.
- Never promise guaranteed results. Do not name competitor products.
- Give general operational advice only; describe what good software lets you do.
- Scene 1 is the hook: a question or bold statement of at most 9 words.
- 4 to 6 scenes in total. Each scene is on-screen text of at most 14 words, 3 to 5 seconds long.
- Write in the requested language and Latin script only.

Reply with ONLY a JSON object, no markdown fences, with exactly these keys:
{"title": "<under 70 chars>",
 "scenes": [{"text": "...", "seconds": 4}],
 "caption": "<2-4 short sentences, ends with a question that invites comments>",
 "hashtags": ["#tag1", "#tag2"]}"""

BANNED = re.compile(r"\d+\s*%|\bguarantee", re.I)


def pick_topic(topics: dict, history: list) -> tuple[str, str]:
    """Interleave niches, then choose the least recently used idea."""
    last_used = {(h["niche"], h["idea"]): h["date"] for h in history}
    columns = [[(n, i) for i in ideas] for n, ideas in topics["niches"].items()]
    combos = [c for c in itertools.chain.from_iterable(itertools.zip_longest(*columns)) if c]
    combos.sort(key=lambda c: last_used.get(c, ""))  # never used ("") first, then oldest
    return combos[0]


def pick_style(topics: dict, history: list) -> str:
    styles = topics["styles"]
    return styles[len(history) % len(styles)]


def _validate(data: dict) -> str | None:
    """Return a problem description, or None if the script is acceptable."""
    scenes = data.get("scenes")
    if not isinstance(scenes, list) or not 4 <= len(scenes) <= 6:
        return "scenes must be a list of 4 to 6 items"
    for s in scenes:
        if not isinstance(s.get("text"), str) or len(s["text"].split()) > 16:
            return "each scene text must be a string of at most 14 words"
        if not isinstance(s.get("seconds"), (int, float)) or not 2 <= s["seconds"] <= 6:
            return "each scene needs seconds between 2 and 6"
    if not isinstance(data.get("caption"), str) or len(data["caption"]) > 1500:
        return "caption must be a string under 1500 characters"
    tags = data.get("hashtags")
    if not isinstance(tags, list) or not all(isinstance(t, str) for t in tags):
        return "hashtags must be a list of strings"
    blob = " ".join([data.get("title", ""), data["caption"]] + [s["text"] for s in scenes])
    if BANNED.search(blob):
        return "remove percentages and any 'guarantee' wording"
    return None


def write_script(cfg: dict, niche: str, idea: str, style: str, history: list) -> dict:
    client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY
    model = os.getenv("CLAUDE_MODEL") or DEFAULT_MODEL
    recent_hooks = [h.get("hook", "") for h in history[-15:]]
    brief = {
        "audience": cfg["audience"],
        "market": cfg["market"],
        "language": cfg["language"],
        "niche": niche.replace("_", " "),
        "topic": idea,
        "format": style,
        "target_total_seconds": cfg["video"]["total_seconds_target"],
        "avoid_repeating_these_hooks": recent_hooks,
    }
    messages = [{"role": "user", "content": json.dumps(brief, ensure_ascii=False)}]
    problem = "no attempt made"
    for _ in range(3):
        resp = client.messages.create(model=model, max_tokens=1200, system=SYSTEM, messages=messages)
        text = "".join(b.text for b in resp.content if b.type == "text").strip()
        text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text)
        try:
            data = json.loads(text)
            problem = _validate(data)
        except (json.JSONDecodeError, AttributeError, TypeError, KeyError) as exc:
            data, problem = None, f"invalid JSON ({exc})"
        if problem is None:
            return data
        messages += [
            {"role": "assistant", "content": text},
            {"role": "user", "content": f"Fix this and reply with JSON only: {problem}"},
        ]
    raise RuntimeError(f"Claude did not return a valid script: {problem}")
