"""Ingestion: turn whatever the user shares into a `SourcePost`.

Only a single link (or pasted text / screenshots) that the user explicitly hands over is
processed: there is no crawling. The manual paths (`from_caption`, `from_screenshots`) need
no extra dependency and always work; `fetch_instagram` needs the optional `media` extra.
"""

import json
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

# Also matches m.instagram.com and links prefixed by the author, e.g. /username/reel/CODE/.
INSTAGRAM_URL = re.compile(
    r"https?://(?:www\.|m\.)?instagram\.com/(?:(?P<author>[\w.]+)/)?"
    r"(?P<kind>p|reels?|tv)/(?P<code>[\w-]+)/?\S*"
)


class IngestionError(RuntimeError):
    """The post could not be fetched; the message tells the user what to do instead."""


@dataclass
class SourcePost:
    url: str | None = None
    caption: str = ""
    video_path: Path | None = None
    screenshot_paths: list[Path] = field(default_factory=list)
    author_handle: str | None = None
    # True only for a video the user sent: a downloaded reel never becomes the dish photo.
    video_from_user: bool = False

    @property
    def downloaded_video(self) -> Path | None:
        """The post's own video, downloaded with the link (not something the user sent)."""
        return self.video_path if self.video_path and not self.video_from_user else None

    @property
    def photo_inputs(self) -> list[Path]:
        """What the user handed over that can become the dish photo."""
        video = [self.video_path] if self.video_path and self.video_from_user else []
        return [*self.screenshot_paths, *video]


def find_instagram_url(text: str) -> str | None:
    """The first Instagram post/reel link in `text`, normalized."""
    match = INSTAGRAM_URL.search(text)
    return normalize_url(match.group(0)) if match else None


def normalize_url(url: str) -> str:
    """Canonical form of a link: no tracking query (?igsh=...), fragment or author prefix."""
    url = url.strip()
    match = INSTAGRAM_URL.fullmatch(url)
    if match:
        kind = "reel" if match["kind"] == "reels" else match["kind"]
        return f"https://www.instagram.com/{kind}/{match['code']}/"
    parts = urlsplit(url)
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), parts.path.rstrip("/"), "", ""))


def source_key(url: str) -> str:
    """Identity of the shared post, used to deduplicate. A post and its reel share a code."""
    match = INSTAGRAM_URL.fullmatch(url.strip())
    return f"instagram:{match['code']}" if match else normalize_url(url)


def _author_from_url(url: str | None) -> str | None:
    match = INSTAGRAM_URL.fullmatch(url.strip()) if url else None
    return match["author"] if match and match["author"] else None


def _post(url: str | None, **fields) -> SourcePost:
    return SourcePost(
        url=normalize_url(url) if url else None, author_handle=_author_from_url(url), **fields
    )


def from_caption(caption: str, url: str | None = None) -> SourcePost:
    return _post(url, caption=caption.strip())


def from_video(path: Path, url: str | None = None, caption: str = "") -> SourcePost:
    """A video the user sent (a screen recording, a clip): transcribed, and a source of frames."""
    if not Path(path).is_file():
        raise IngestionError(f"video not found: {path}")
    return _post(url, caption=caption.strip(), video_path=Path(path), video_from_user=True)


def from_screenshots(paths: list[Path], url: str | None = None, caption: str = "") -> SourcePost:
    missing = [str(p) for p in paths if not Path(p).is_file()]
    if missing:
        raise IngestionError(f"screenshot not found: {', '.join(missing)}")
    return _post(url, caption=caption.strip(), screenshot_paths=[Path(p) for p in paths])


def fetch_instagram(
    url: str, cookies_file: Path | None = None, workdir: Path | None = None
) -> SourcePost:
    """Fetch caption and video of one Instagram post with yt-dlp (optional `media` extra)."""
    if find_instagram_url(url) is None:
        raise IngestionError(f"not an Instagram post/reel link: {url}")
    # Next to this Python too: `uv run` puts the venv on PATH, running .venv/bin/burp does not.
    ytdlp = shutil.which("yt-dlp") or shutil.which("yt-dlp", path=str(Path(sys.executable).parent))
    if ytdlp is None:
        raise IngestionError(
            "yt-dlp is not installed. Run `uv sync --extra media`, or paste the caption "
            "(--caption-file) or send a screenshot instead."
        )
    shared_url, url = url, normalize_url(url)
    workdir = workdir or Path(tempfile.mkdtemp(prefix="burp-"))
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
    post = _post_from_workdir(url, workdir)
    post.author_handle = post.author_handle or _author_from_url(shared_url)
    return post


def _post_from_workdir(url: str, workdir: Path) -> SourcePost:
    info_file = workdir / "post.info.json"
    info = json.loads(info_file.read_text()) if info_file.exists() else {}
    caption = (info.get("description") or info.get("title") or "").strip()
    videos = sorted(p for p in workdir.glob("post.*") if p.suffix in {".mp4", ".webm", ".mov"})
    return SourcePost(
        url=url,
        caption=caption,
        video_path=videos[0] if videos else None,
        author_handle=_author_from_info(info),
    )


def _author_from_info(info: dict) -> str | None:
    """yt-dlp puts the Instagram username in `channel`; `uploader_id` may be a numeric id."""
    for key in ("channel", "uploader_id"):
        value = str(info.get(key) or "").lstrip("@")
        if value and not value.isdigit():
            return value
    return None
