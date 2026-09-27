import json
import tempfile
import unittest
from argparse import Namespace
from datetime import datetime, timezone
from pathlib import Path

from clipfinder import finder


def clip(id_, views, duration=30.0, language="en"):
    return {
        "id": id_, "url": f"https://clips.twitch.tv/{id_}", "broadcaster_name": "Streamer",
        "creator_name": "Clipper", "title": f"title {id_}", "view_count": views,
        "duration": duration, "language": language, "created_at": "2026-09-20T00:00:00Z",
    }


class FakeClient:
    def __init__(self, clips):
        self.clips = clips
        self.calls = []

    def user_ids(self, logins):
        return {l.lower(): {"id": "1"} for l in logins}

    def top_clips(self, broadcaster_id, started_at, ended_at, first):
        self.calls.append((broadcaster_id, started_at, ended_at, first))
        return self.clips


class FinderTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.config = {
            "defaults": {"days": 7, "min_views": 1000, "max_duration_seconds": 60,
                         "clips_per_streamer": 2, "language": "en", "hashtags": ["#twitch"]},
            "streamers": [
                {"login": "allowed", "enabled": True, "permission_source": "https://example.com/ok"},
                {"login": "noperm", "enabled": True, "permission_source": ""},
                {"login": "off", "enabled": False, "permission_source": "https://example.com"},
            ],
        }
        (self.tmp / "cfg.json").write_text(json.dumps(self.config))
        (self.tmp / "posted.json").write_text(json.dumps({"posted1": "x"}))
        self.args = Namespace(config=self.tmp / "cfg.json", posted=self.tmp / "posted.json",
                              out=self.tmp / "drafts")

    def test_only_permitted_streamers(self):
        streamers, skipped = finder.permitted_streamers(self.config)
        self.assertEqual([s["login"] for s in streamers], ["allowed"])
        self.assertEqual(skipped, ["noperm", "off"])

    def test_filters_and_writes_drafts(self):
        client = FakeClient([
            clip("posted1", 90000), clip("long", 80000, duration=120),
            clip("es", 70000, language="es"), clip("a", 60000), clip("b", 50000),
            clip("c", 40000), clip("low", 10),
        ])
        now = datetime(2026, 9, 27, tzinfo=timezone.utc)
        drafts = finder.find(self.args, client=client, now=now)
        self.assertEqual([d[0]["id"] for d in drafts], ["a", "b"])
        self.assertEqual(client.calls, [("1", "2026-09-20T00:00:00Z", "2026-09-27T00:00:00Z", 100)])
        text = (self.tmp / "drafts" / "2026-09-27.md").read_text()
        self.assertIn("twitch.tv/allowed", text)
        self.assertIn("Clipped by: Clipper", text)
        self.assertIn("#twitch #allowed", text)

    def test_mark_posted(self):
        finder.mark_posted(Namespace(posted=self.tmp / "posted.json", clip_ids=["a", "b"]))
        self.assertEqual(set(json.loads((self.tmp / "posted.json").read_text())), {"posted1", "a", "b"})


if __name__ == "__main__":
    unittest.main()
