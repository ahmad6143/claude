# Daily Reels

A GitHub-hosted automation that writes, renders and posts one short vertical video a day about ERP software for **FMCG distributors, fast food outlets and cafes**. It runs on GitHub Actions, so no server is needed.

Each run:

1. Picks the least recently used topic from `content/topics.yaml` (niches are interleaved: distribution, fast food, cafe).
2. Asks Claude to write a 20-30 second script, caption and hashtags, then checks the result (no invented percentages, no "guaranteed" claims) and retries if it fails.
3. Renders a 1080x1920 MP4 of text cards with ffmpeg and Pillow, ending on your call-to-action.
4. Publishes to Instagram Reels (and optionally YouTube Shorts).
5. Commits `state/history.json` so topics and hooks do not repeat.

It starts in **dry-run mode**: it renders the video and uploads it as a downloadable workflow artifact, but publishes nothing, until you switch it on.

## What is and is not automated

| Platform | Status | Notes |
|---|---|---|
| Instagram Reels | Fully automated | Official Meta Content Publishing API. Needs a Professional (Business or Creator) account linked to a Facebook Page. |
| YouTube Shorts | Automated, but private until audited | Uploads from a new Google Cloud project are forced to private until the project passes YouTube's API compliance audit. |
| TikTok | Not included | TikTok's API keeps posts from unaudited apps private. Download the rendered video from the workflow artifact and post it by hand, or use a scheduler that already holds TikTok's audit. |

## Quick start

You need: a GitHub repo, the [GitHub CLI](https://cli.github.com), an Anthropic API key from [console.anthropic.com](https://console.anthropic.com) (this is separate from a claude.ai subscription), and the Instagram credentials below.

```bash
cp .env.example .env            # fill in ANTHROPIC_API_KEY and the Instagram values
./scripts/setup_github.sh       # loads .env as GitHub secrets, sets dry-run on, enables the workflow
gh workflow run "Daily reel" -f dry_run=true
```

Open the run in the **Actions** tab, download the `reel-...` artifact and check the video and caption. When you are happy:

```bash
gh variable set REEL_DRY_RUN --body false
```

From then on the scheduled run publishes. To test a real post once without changing the default: `gh workflow run "Daily reel" -f dry_run=false`.

Before the first run, edit `config.yaml` (brand name, call to action, website, audience) and skim `content/topics.yaml`.

### Run locally

```bash
pip install -r requirements.txt     # also needs ffmpeg installed
export ANTHROPIC_API_KEY=...
python -m reelbot.main --dry-run    # writes out/<date>-<niche>.mp4
```

## Instagram setup

1. Convert the Instagram account to **Professional** and link it to a Facebook Page.
2. At [developers.facebook.com](https://developers.facebook.com), create an app and add the Instagram API product with Facebook Login for Business (Meta's resumable video upload requires it).
3. In the Graph API Explorer, generate a user token with `instagram_basic`, `instagram_content_publish`, `pages_show_list` and `pages_read_engagement`.
4. Run the helper, which prints your `IG_USER_ID` and a long-lived Page token:
   ```bash
   APP_ID=... APP_SECRET=... SHORT_TOKEN=... python scripts/ig_token.py
   ```
5. Put both values in `.env`, then run `./scripts/setup_github.sh` again.

For your own account, an app in Development mode generally works; Meta's app review is for publishing to other people's accounts. Page tokens made from a long-lived user token typically do not expire. If posts start failing with an OAuth error, rerun the helper and update the secret.

## YouTube Shorts (optional)

1. In Google Cloud, create a project, enable **YouTube Data API v3** and create an OAuth client.
2. Obtain a refresh token for the `youtube.upload` scope and set `YT_CLIENT_ID`, `YT_CLIENT_SECRET`, `YT_REFRESH_TOKEN`.
3. Add `"youtube"` to `publish.platforms` in `config.yaml`.

Videos stay private (`youtube_privacy: "private"`) until your project passes the audit; you can make them public by hand in YouTube Studio only after that.

## Configuration

| File | What to change |
|---|---|
| `config.yaml` | Brand name, call to action, website, audience, market, language, platforms, hashtag limit |
| `content/topics.yaml` | Topic ideas per niche and the rotating content formats |
| `.github/workflows/daily-reel.yml` | Posting time (cron is in UTC; the default 14:00 UTC is 19:00 Pakistan time) |
| `assets/music.mp3` | Optional background track. Use audio you have the rights to. Without it the video has a silent audio track |
| `assets/fonts/bold.ttf` | Optional custom font |

Set `CLAUDE_MODEL` (secret) to override the default model.

## Content rules built in

The prompt and validator reject invented statistics, percentages, testimonials, guarantees and competitor names. They keep advice general ("what good software lets you do"), which keeps the videos accurate and avoids claims you would have to substantiate. The validator is a safety net, not a guarantee: review the first week of dry-run videos before going live, and check each platform's current rules on labelling AI-assisted content.

## Project layout

```
.github/workflows/daily-reel.yml   schedule, secrets, artifact upload, history commit
reelbot/generate.py                topic rotation + Claude script generation + validation
reelbot/render.py                  Pillow cards + ffmpeg video
reelbot/publish.py                 Instagram Reels and YouTube Shorts publishers
reelbot/main.py                    daily entry point
content/topics.yaml                ideas and formats
config.yaml                        brand and settings
state/history.json                 what has been posted
scripts/setup_github.sh            loads secrets and enables the workflow
scripts/ig_token.py                Instagram token and user-ID helper
```

## Limitations and troubleshooting

- Text is rendered with Latin script only (English or Roman Urdu). Urdu or Arabic script needs a shaping-capable font setup and is not supported yet.
- Videos are text cards, not footage. Swap in your own clips by extending `render.py`.
- GitHub may start scheduled runs a few minutes late, and can pause schedules in public repos after 60 days without activity (re-enable in the Actions tab).
- `Instagram processing failed`: check the video is under Instagram's Reels limits and that the token has the permissions above.
- A failed platform does not block the others; the run is marked failed so GitHub emails you.
- Never commit `.env`. It is in `.gitignore`.

## License

Add a license before making the repository public.
