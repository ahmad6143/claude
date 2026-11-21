"""Daily entry point: pick topic -> write script -> render video -> (optionally) publish."""
import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml

from . import generate, publish, render

ROOT = Path(__file__).resolve().parent.parent


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="render only, never publish or log")
    ap.add_argument("--script-json", help="skip Claude and use this script file (for testing)")
    args = ap.parse_args()
    # Safe by default: only an explicit DRY_RUN=false publishes.
    dry = args.dry_run or os.getenv("DRY_RUN", "true").strip().lower() != "false"

    os.chdir(ROOT)
    cfg = yaml.safe_load(Path("config.yaml").read_text(encoding="utf-8"))
    topics = yaml.safe_load(Path("content/topics.yaml").read_text(encoding="utf-8"))
    hist_path = Path("state/history.json")
    history = json.loads(hist_path.read_text(encoding="utf-8")) if hist_path.exists() else []

    niche, idea = generate.pick_topic(topics, history)
    style = generate.pick_style(topics, history)
    print(f"Topic: [{niche}] {idea}\nStyle: {style}")

    if args.script_json:
        script = json.loads(Path(args.script_json).read_text(encoding="utf-8"))
    else:
        script = generate.write_script(cfg, niche, idea, style, history)
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    video = render.make_video(script, cfg, niche, ROOT / "out" / f"{today}-{niche}.mp4")
    print(f"Rendered {video}")

    tags = " ".join(script["hashtags"][: cfg["publish"]["max_hashtags"]])
    caption = f"{script['caption']}\n\n{tags}".strip()[:2200]

    if dry:
        print("\nDRY RUN - nothing published.\n--- caption ---\n" + caption)
        return 0

    results = {}
    for platform in cfg["publish"]["platforms"]:
        try:
            if platform == "instagram":
                results[platform] = publish.instagram(str(video), caption)
            elif platform == "youtube":
                results[platform] = publish.youtube(
                    str(video), script["title"], f"{caption}\n\n#Shorts", cfg["publish"]["youtube_privacy"])
            else:
                results[platform] = {"error": f"unknown platform '{platform}'"}
        except Exception as exc:  # keep going so one platform failing does not block the others
            results[platform] = {"error": str(exc)}
        print(platform, "->", results[platform])

    if any("error" not in r for r in results.values()):
        history.append({"date": today, "niche": niche, "idea": idea, "hook": script["scenes"][0]["text"],
                        "caption": script["caption"], "results": results})
        hist_path.write_text(json.dumps(history, indent=2, ensure_ascii=False), encoding="utf-8")
    return 1 if any("error" in r for r in results.values()) else 0


if __name__ == "__main__":
    sys.exit(main())
