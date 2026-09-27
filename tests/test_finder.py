import json
import tempfile
import unittest
from argparse import Namespace
from datetime import datetime, timezone
from pathlib import Path

from clipfinder import finder


def clip(id_, views, duration=30.0, language="en", broadcaster="1"):
    return {
        "id": id_, "url": f"https://clips.twitch.tv/{id_}", "broadcaster_id": broadcaster,
        "broadcaster_name": f"Streamer{broadcaster}", "creator_name": "Clipper",
        "title": f"title {id_}", "view_count": views, "duration": duration,
        "language": language, "created_at": "2026-09-20T00:00:00Z",
    }


class FakeClient:
    def __init__(self, by_broadcaster=None, by_game=None):
        self.by_broadcaster = by_broadcaster or []
        self.by_game = by_game or {}
        self.calls = []

    def user_ids(self, logins):
        return {l.lower(): {"id": "1"} for l in logins}

    def logins_by_id(self, ids):
        return {i: f"login{i}" for i in ids}

    def game_ids(self, names, top_n):
        return {"g1": "Just Chatting"}

    def top_clips(self, started_at, ended_at, first, broadcaster_id=None, game_id=None):
        self.calls.append((started_at, ended_at, first, broadcaster_id, game_id))
        return self.by_broadcaster if broadcaster_id else self.by_game.get(game_id, [])


class FinderTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.config = {
            "defaults": {"require_permission": True, "days": 7, "min_views": 1000,
                         "max_duration_seconds": 60, "clips_per_streamer": 2,
                         "language": "en", "hashtags": ["#twitch"]},
            "streamers": [
                {"login": "allowed", "enabled": True, "permission_source": "https://example.com/ok"},
                {"login": "noperm", "enabled": True, "permission_source": ""},
                {"login": "off", "enabled": False, "permission_source": "https://example.com"},
            ],
        }
        (self.tmp / "posted.json").write_text(json.dumps({"posted1": "x"}))
        self.args = Namespace(config=self.tmp / "cfg.json", posted=self.tmp / "posted.json",
                              out=self.tmp / "drafts")
        self.now = datetime(2026, 9, 27, tzinfo=timezone.utc)

    def write_config(self):
        (self.tmp / "cfg.json").write_text(json.dumps(self.config))

    def test_permission_required(self):
        streamers, skipped = finder.permitted_streamers(self.config)
        self.assertEqual([s["login"] for s in streamers], ["allowed"])
        self.assertEqual(skipped, ["noperm", "off"])

    def test_permission_not_required(self):
        self.config["defaults"]["require_permission"] = False
        streamers, skipped = finder.permitted_streamers(self.config)
        self.assertEqual([s["login"] for s in streamers], ["allowed", "noperm"])
        self.assertEqual(skipped, ["off"])

    def test_filters_and_writes_drafts(self):
        self.config["streamers"] = self.config["streamers"][:1]
        self.write_config()
        client = FakeClient(by_broadcaster=[
            clip("posted1", 90000), clip("long", 80000, duration=120),
            clip("es", 70000, language="es"), clip("a", 60000), clip("b", 50000),
            clip("c", 40000), clip("low", 10),
        ])
        drafts = finder.find(self.args, client=client, now=self.now)
        self.assertEqual([d[0]["id"] for d in drafts], ["a", "b"])
        self.assertEqual(client.calls, [("2026-09-20T00:00:00Z", "2026-09-27T00:00:00Z", 100, "1", None)])
        text = (self.tmp / "drafts" / "2026-09-27.md").read_text()
        self.assertIn("twitch.tv/login1", text)
        self.assertIn("Clipped by: Clipper", text)
        self.assertIn("#twitch #login1", text)

    def test_discovery_caps_per_streamer_and_dedupes(self):
        self.config["streamers"] = []
        self.config["defaults"]["max_clips_per_streamer"] = 1
        self.config["discover"] = {"enabled": True, "categories": ["Just Chatting"], "top_games": 0,
                                   "clips_per_category": 5}
        self.write_config()
        client = FakeClient(by_game={"g1": [
            clip("x1", 900000, broadcaster="7"), clip("x2", 800000, broadcaster="7"),
            clip("y1", 700000, broadcaster="8"), clip("posted1", 600000, broadcaster="9"),
        ]})
        drafts = finder.find(self.args, client=client, now=self.now)
        self.assertEqual([d[0]["id"] for d in drafts], ["x1", "y1"])
        text = (self.tmp / "drafts" / "2026-09-27.md").read_text()
        self.assertIn("category: Just Chatting", text)
        self.assertIn("none recorded", text)

    def test_mark_posted(self):
        finder.mark_posted(Namespace(posted=self.tmp / "posted.json", clip_ids=["a", "b"]))
        self.assertEqual(set(json.loads((self.tmp / "posted.json").read_text())), {"posted1", "a", "b"})


if __name__ == "__main__":
    unittest.main()
