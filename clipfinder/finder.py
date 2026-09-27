"""Find top-viewed Twitch clips from permitted streamers and write Instagram post drafts.

Uses the official Twitch Helix API:
  https://dev.twitch.tv/docs/api/reference/#get-clips
Clips requested by broadcaster_id come back sorted by view count, descending.
"""

import argparse
import json
import os
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

TOKEN_URL = "https://id.twitch.tv/oauth2/token"
API_BASE = "https://api.twitch.tv/helix"

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG = ROOT / "streamers.json"
DEFAULT_POSTED = ROOT / "posted.json"
DEFAULT_DRAFTS = ROOT / "drafts"


def load_env(path=ROOT / ".env"):
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip())


class TwitchClient:
    def __init__(self, client_id, client_secret, opener=urllib.request.urlopen):
        self.client_id = client_id
        self.client_secret = client_secret
        self._open = opener
        self._token = None

    def _token_value(self):
        if self._token is None:
            body = urllib.parse.urlencode({
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "grant_type": "client_credentials",
            }).encode()
            with self._open(urllib.request.Request(TOKEN_URL, data=body, method="POST")) as resp:
                self._token = json.load(resp)["access_token"]
        return self._token

    def get(self, path, params):
        url = f"{API_BASE}/{path}?{urllib.parse.urlencode(params, doseq=True)}"
        req = urllib.request.Request(url, headers={
            "Authorization": f"Bearer {self._token_value()}",
            "Client-Id": self.client_id,
        })
        with self._open(req) as resp:
            return json.load(resp)

    def user_ids(self, logins):
        if not logins:
            return {}
        data = self.get("users", {"login": logins})["data"]
        return {u["login"].lower(): u for u in data}

    def top_clips(self, broadcaster_id, started_at, ended_at, first):
        return self.get("clips", {
            "broadcaster_id": broadcaster_id,
            "started_at": started_at,
            "ended_at": ended_at,
            "first": first,
        })["data"]


def permitted_streamers(config):
    """Only streamers that are enabled AND have a recorded permission source."""
    out, skipped = [], []
    for s in config.get("streamers", []):
        if s.get("enabled") and s.get("permission_source", "").strip():
            out.append(s)
        else:
            skipped.append(s.get("login", "?"))
    return out, skipped


def select_clips(clips, settings, posted_ids):
    picked = []
    for c in clips:
        if c["id"] in posted_ids:
            continue
        if c["view_count"] < settings["min_views"]:
            continue
        if settings.get("max_duration_seconds") and c["duration"] > settings["max_duration_seconds"]:
            continue
        if settings.get("language") and c["language"] != settings["language"]:
            continue
        picked.append(c)
        if len(picked) >= settings["clips_per_streamer"]:
            break
    return picked


def build_caption(clip, streamer, hashtags):
    login = streamer["login"]
    lines = [
        clip["title"].strip(),
        "",
        f"Streamer: {clip['broadcaster_name']} (twitch.tv/{login})",
        f"Clipped by: {clip['creator_name']}",
        f"Original clip: {clip['url']}",
        "",
        " ".join(hashtags + [f"#{login}"]),
    ]
    return "\n".join(lines)


def render_markdown(drafts, generated_at):
    out = [f"# Clip drafts ({generated_at:%Y-%m-%d %H:%M} UTC)", ""]
    if not drafts:
        out.append("No clips matched the filters.")
    for i, (clip, streamer, caption) in enumerate(drafts, 1):
        out += [
            f"## {i}. {clip['broadcaster_name']}: {clip['title']}",
            "",
            f"- Clip ID: `{clip['id']}`",
            f"- Views: {clip['view_count']:,}",
            f"- Length: {clip['duration']:.0f}s",
            f"- Created: {clip['created_at']}",
            f"- Link: {clip['url']}",
            f"- Permission: {streamer['permission_source']}",
            "",
            "Caption:",
            "",
            "```",
            caption,
            "```",
            "",
            f"After posting, run: `python -m clipfinder.finder mark-posted {clip['id']}`",
            "",
        ]
    return "\n".join(out)


def read_posted(path):
    return json.loads(path.read_text()) if path.exists() else {}


def find(args, client=None, now=None):
    config = json.loads(Path(args.config).read_text())
    defaults = config.get("defaults", {})
    streamers, skipped = permitted_streamers(config)
    if skipped:
        print(f"Skipping (disabled or no permission_source): {', '.join(skipped)}", file=sys.stderr)
    if not streamers:
        print("No permitted streamers configured in streamers.json.", file=sys.stderr)
        return []

    if client is None:
        load_env()
        cid, secret = os.environ.get("TWITCH_CLIENT_ID"), os.environ.get("TWITCH_CLIENT_SECRET")
        if not cid or not secret:
            sys.exit("Set TWITCH_CLIENT_ID and TWITCH_CLIENT_SECRET (see .env.example).")
        client = TwitchClient(cid, secret)

    now = now or datetime.now(timezone.utc)
    posted = read_posted(Path(args.posted))
    users = client.user_ids([s["login"] for s in streamers])

    drafts = []
    for s in streamers:
        settings = {**defaults, **{k: v for k, v in s.items() if k in defaults and k != "hashtags"}}
        user = users.get(s["login"].lower())
        if not user:
            print(f"Twitch user not found: {s['login']}", file=sys.stderr)
            continue
        start = now - timedelta(days=settings["days"])
        clips = client.top_clips(
            user["id"],
            start.strftime("%Y-%m-%dT%H:%M:%SZ"),
            now.strftime("%Y-%m-%dT%H:%M:%SZ"),
            100,
        )
        hashtags = defaults.get("hashtags", []) + s.get("hashtags", [])
        for clip in select_clips(clips, settings, posted):
            drafts.append((clip, s, build_caption(clip, s, hashtags)))

    drafts.sort(key=lambda d: d[0]["view_count"], reverse=True)
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / f"{now:%Y-%m-%d}.md"
    out_file.write_text(render_markdown(drafts, now))
    print(f"Wrote {len(drafts)} draft(s) to {out_file}")
    return drafts


def mark_posted(args):
    path = Path(args.posted)
    posted = read_posted(path)
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    for clip_id in args.clip_ids:
        posted[clip_id] = stamp
    path.write_text(json.dumps(posted, indent=2) + "\n")
    print(f"Marked {len(args.clip_ids)} clip(s) as posted.")


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--config", default=str(DEFAULT_CONFIG))
    p.add_argument("--posted", default=str(DEFAULT_POSTED))
    sub = p.add_subparsers(dest="cmd", required=True)
    f = sub.add_parser("find", help="Find top clips and write drafts")
    f.add_argument("--out", default=str(DEFAULT_DRAFTS))
    m = sub.add_parser("mark-posted", help="Record clips you've posted so they aren't suggested again")
    m.add_argument("clip_ids", nargs="+")
    args = p.parse_args(argv)
    if args.cmd == "find":
        find(args)
    else:
        mark_posted(args)


if __name__ == "__main__":
    main()
