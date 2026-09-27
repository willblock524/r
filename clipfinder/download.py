"""Download Twitch clips with yt-dlp and convert them to vertical 9:16 video for Reels.

Note: Twitch's Terms of Service prohibit downloading and distributing content
except where Twitch expressly permits it. See the README before using this.
"""

import re
import shutil
import subprocess
import sys
from pathlib import Path

W, H = 1080, 1920

# "blur": full frame centered over a blurred, zoomed copy of itself.
# "crop": zoom to fill the height and cut off the sides.
FILTERS = {
    "blur": (
        f"[0:v]split[a][b];"
        f"[a]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},boxblur=20:5[bg];"
        f"[b]scale={W}:-2[fg];"
        f"[bg][fg]overlay=(W-w)/2:(H-h)/2,setsar=1[v]"
    ),
    "crop": f"[0:v]scale=-2:{H},crop={W}:{H},setsar=1[v]",
}

CLIP_URL = re.compile(r"https://(?:clips\.twitch\.tv/|www\.twitch\.tv/[^/\s]+/clip/)[\w-]+")


def ffmpeg_exe():
    found = shutil.which("ffmpeg")
    if found:
        return found
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except ImportError:
        sys.exit("ffmpeg not found. Install ffmpeg or `pip install imageio-ffmpeg`.")


def clip_id(url):
    return url.rstrip("/").rsplit("/", 1)[-1]


def urls_from_drafts(path):
    """Clip links from a drafts file, in order, without duplicates."""
    seen, out = set(), []
    for url in CLIP_URL.findall(Path(path).read_text()):
        if url not in seen:
            seen.add(url)
            out.append(url)
    return out


def normalize(target):
    if target.startswith("http"):
        return target
    return f"https://clips.twitch.tv/{target}"


def download_cmd(url, dest):
    return [sys.executable, "-m", "yt_dlp", "--no-playlist", "-f", "best[ext=mp4]/best",
            "-o", str(dest), url]


def vertical_cmd(ffmpeg, src, dest, mode):
    return [ffmpeg, "-y", "-loglevel", "error", "-i", str(src),
            "-filter_complex", FILTERS[mode], "-map", "[v]", "-map", "0:a?",
            "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", str(dest)]


def download(targets, out_dir, mode="blur", run=subprocess.run):
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    ffmpeg = ffmpeg_exe() if mode != "none" else None
    results = []
    for target in targets:
        url = normalize(target)
        cid = clip_id(url)
        raw = out_dir / f"{cid}.mp4"
        if not raw.exists():
            if run(download_cmd(url, raw)).returncode != 0:
                print(f"Download failed: {url}", file=sys.stderr)
                continue
        final = raw
        if mode != "none":
            final = out_dir / f"{cid}_reel.mp4"
            if run(vertical_cmd(ffmpeg, raw, final, mode)).returncode != 0:
                print(f"Conversion failed: {raw}", file=sys.stderr)
                continue
        print(f"Ready: {final}")
        results.append(final)
    return results
