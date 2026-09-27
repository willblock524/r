# Streamer clip finder

Finds the most-viewed recent Twitch clips and writes Instagram post drafts (link, stats, caption with credit, hashtags). You review the drafts and post them yourself.

> **Risk:** `require_permission` is set to `false`, so the tool suggests clips from any streamer. Reposting clips without permission can lead to copyright takedowns and, for repeat cases, removal of the Instagram account. Set it to `true` to only use streamers with a recorded `permission_source`.

## How it works

- Uses the official Twitch API [Get Clips](https://dev.twitch.tv/docs/api/reference/#get-clips) endpoint. When you request clips by broadcaster or by category, Twitch returns them sorted by view count, highest first.
- **Discovery** (`discover` in `streamers.json`): searches the named categories (Just Chatting, IRL) plus Twitch's current top games by live viewers, so it finds viral clips from any streamer. Category names must exactly match Twitch's; unknown names are ignored.
- **Streamer list** (`streamers`): optionally add specific streamers to always check. With `require_permission: true`, only ones with a `permission_source` are searched.
- `max_clips_per_streamer` stops one streamer from filling the whole batch.
- Filters: time window (`days`), minimum views, max length, language, and clips per streamer. You can override any default per streamer.
- Clips you've already posted are recorded in `posted.json` so they aren't suggested again.

## Setup

1. Register an app at the [Twitch developer console](https://dev.twitch.tv/console/apps) to get a Client ID and Client Secret.
2. `cp .env.example .env` and fill both values in.
3. Add streamers to `streamers.json`, with a link to where they give permission (a public statement, their clipping program, or written permission you received).
4. Python 3.9+ with no extra packages.

## Usage

```
python -m clipfinder.finder find                    # writes drafts/YYYY-MM-DD.md
python -m clipfinder.finder mark-posted <clip_id>   # after you post it
python -m unittest                                  # run tests
```

## Getting the video file

`download` pulls clips straight from Twitch with [yt-dlp](https://github.com/yt-dlp/yt-dlp) and makes a 1080x1920 vertical version with ffmpeg.

```
pip install -r requirements.txt
python -m clipfinder.finder download --from-drafts drafts/2026-09-27.md   # every clip in a drafts file
python -m clipfinder.finder download <clip_url_or_id> --mode crop        # specific clips
```

Files go to `clips/`: `<id>.mp4` is the original, `<id>_reel.mp4` is the vertical version. Modes: `blur` (default, full frame over a blurred background), `crop` (fill the screen, sides cut off), `none` (original only).

> **Terms of Service:** Twitch's [Terms of Service](https://legal.twitch.com/en/legal/terms-of-service/) say users may not engage in "downloading (except page caching) of any portion of the Twitch Services ... except as expressly permitted on the Twitch Services" or "distribution, public performance or public display of any Materials." This command does both. The only official download route, [Get Clips Download](https://dev.twitch.tv/docs/api/reference/#get-clips-download), is limited to a streamer's channel editors.

## Posting checklist

- Confirm the streamer's permission still applies and follow any rules they set (watermarks, tags, link in bio).
- Crop to vertical 9:16 for Reels.
- Keep the credit lines in the caption.
