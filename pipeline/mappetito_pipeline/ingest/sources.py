"""Ingestion: turn whatever the user shares into a `SourcePost`.

Only a single link (or pasted text / screenshots) that the user explicitly hands over is
processed: there is no crawling. The manual paths (`from_caption`, `from_screenshots`) need
no extra dependency and always work; `fetch_instagram` needs the optional `media` extra.
"""

import json
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

INSTAGRAM_URL = re.compile(r"https?://(?:www\.)?instagram\.com/(?:p|reel|reels|tv)/[\w-]+/?")


class IngestionError(RuntimeError):
    """The post could not be fetched; the message tells the user what to do instead."""


@dataclass
class SourcePost:
    url: str | None = None
    caption: str = ""
    video_path: Path | None = None
    screenshot_paths: list[Path] = field(default_factory=list)


def find_instagram_url(text: str) -> str | None:
    match = INSTAGRAM_URL.search(text)
    return match.group(0) if match else None


def from_caption(caption: str, url: str | None = None) -> SourcePost:
    return SourcePost(url=url, caption=caption.strip())


def from_screenshots(paths: list[Path], url: str | None = None, caption: str = "") -> SourcePost:
    missing = [str(p) for p in paths if not Path(p).is_file()]
    if missing:
        raise IngestionError(f"screenshot not found: {', '.join(missing)}")
    return SourcePost(url=url, caption=caption.strip(), screenshot_paths=[Path(p) for p in paths])


def fetch_instagram(
    url: str, cookies_file: Path | None = None, workdir: Path | None = None
) -> SourcePost:
    """Fetch caption and video of one Instagram post with yt-dlp (optional `media` extra)."""
    if find_instagram_url(url) is None:
        raise IngestionError(f"not an Instagram post/reel link: {url}")
    ytdlp = shutil.which("yt-dlp")
    if ytdlp is None:
        raise IngestionError(
            "yt-dlp is not installed. Run `uv sync --extra media`, or paste the caption "
            "(--caption-file) or send a screenshot instead."
        )
    workdir = workdir or Path(tempfile.mkdtemp(prefix="mappetito-"))
    command = [ytdlp, "--no-playlist", "--write-info-json", "-o", str(workdir / "post.%(ext)s")]
    if cookies_file:
        command += ["--cookies", str(cookies_file)]
    result = subprocess.run([*command, url], capture_output=True, text=True, timeout=180)
    if result.returncode != 0:
        detail = (result.stderr.strip().splitlines() or ["unknown error"])[-1]
        raise IngestionError(
            f"could not fetch {url} ({detail}). "
            "Instagram often needs login cookies (INSTAGRAM_COOKIES_FILE); "
            "otherwise paste the caption or send a screenshot."
        )
    return _post_from_workdir(url, workdir)


def _post_from_workdir(url: str, workdir: Path) -> SourcePost:
    info_file = workdir / "post.info.json"
    caption = ""
    if info_file.exists():
        info = json.loads(info_file.read_text())
        caption = (info.get("description") or info.get("title") or "").strip()
    videos = sorted(p for p in workdir.glob("post.*") if p.suffix in {".mp4", ".webm", ".mov"})
    return SourcePost(url=url, caption=caption, video_path=videos[0] if videos else None)
