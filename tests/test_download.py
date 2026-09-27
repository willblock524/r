import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from clipfinder import download


class DownloadTests(unittest.TestCase):
    def test_urls_from_drafts(self):
        tmp = Path(tempfile.mkdtemp()) / "d.md"
        tmp.write_text("- Link: https://clips.twitch.tv/AbcDef-123\n"
                       "Original clip: https://clips.twitch.tv/AbcDef-123\n"
                       "- Link: https://www.twitch.tv/someone/clip/XyZ_9\n")
        self.assertEqual(download.urls_from_drafts(tmp),
                         ["https://clips.twitch.tv/AbcDef-123", "https://www.twitch.tv/someone/clip/XyZ_9"])

    def test_download_runs_ytdlp_then_ffmpeg(self):
        out = Path(tempfile.mkdtemp())
        calls = []
        run = lambda cmd: calls.append(cmd) or SimpleNamespace(returncode=0)
        results = download.download(["AbcDef"], out, mode="crop", run=run)
        self.assertEqual(results, [out / "AbcDef_reel.mp4"])
        self.assertIn("yt_dlp", calls[0])
        self.assertIn("https://clips.twitch.tv/AbcDef", calls[0])
        self.assertIn(download.FILTERS["crop"], calls[1])

    def test_failed_download_skips_conversion(self):
        out = Path(tempfile.mkdtemp())
        calls = []
        run = lambda cmd: calls.append(cmd) or SimpleNamespace(returncode=1)
        self.assertEqual(download.download(["x"], out, run=run), [])
        self.assertEqual(len(calls), 1)


if __name__ == "__main__":
    unittest.main()
