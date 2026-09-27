# Streamer clip finder

Finds the most-viewed recent Twitch clips from streamers who allow their clips to be reposted, and writes Instagram post drafts (link, stats, caption with credit, hashtags). You review the drafts and post them yourself.

## How it works

- Uses the official Twitch API [Get Clips](https://dev.twitch.tv/docs/api/reference/#get-clips) endpoint. When you request clips by broadcaster, Twitch returns them sorted by view count, highest first.
- Only streamers with `"enabled": true` **and** a filled-in `permission_source` in `streamers.json` are searched. Everyone else is skipped.
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

The Twitch API's [Get Clips Download](https://dev.twitch.tv/docs/api/reference/#get-clips-download) endpoint only works for users the streamer has made an **editor** on their channel. So the tool gives you the clip link, and you get the file from the streamer or their clipping program, or through editor access if they grant it.

## Posting checklist

- Confirm the streamer's permission still applies and follow any rules they set (watermarks, tags, link in bio).
- Crop to vertical 9:16 for Reels.
- Keep the credit lines in the caption.
