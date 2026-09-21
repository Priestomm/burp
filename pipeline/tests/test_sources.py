import json

import pytest

from mappetito_pipeline.ingest import sources
from mappetito_pipeline.ingest.sources import (
    IngestionError,
    fetch_instagram,
    find_instagram_url,
    from_caption,
    from_screenshots,
)


def test_from_caption_strips_and_keeps_url():
    post = from_caption("  ciao \n", url="https://www.instagram.com/p/abc/")
    assert post.caption == "ciao"
    assert post.url == "https://www.instagram.com/p/abc/"
    assert post.video_path is None


def test_from_screenshots_requires_existing_files(tmp_path):
    image = tmp_path / "a.png"
    image.write_bytes(b"x")
    assert from_screenshots([image]).screenshot_paths == [image]
    with pytest.raises(IngestionError, match="not found"):
        from_screenshots([tmp_path / "missing.png"])


@pytest.mark.parametrize(
    "text",
    [
        "guarda https://www.instagram.com/reel/C1x_-9/ che buono",
        "https://instagram.com/p/AbC123",
    ],
)
def test_find_instagram_url(text):
    assert find_instagram_url(text) is not None


def test_find_instagram_url_ignores_other_links():
    assert find_instagram_url("https://example.com/reel/abc/") is None


def test_fetch_rejects_non_instagram_links():
    with pytest.raises(IngestionError, match="not an Instagram"):
        fetch_instagram("https://example.com/video")


def test_fetch_without_ytdlp_explains_the_fallback(monkeypatch):
    monkeypatch.setattr(sources.shutil, "which", lambda _: None)
    with pytest.raises(IngestionError, match="paste the caption"):
        fetch_instagram("https://www.instagram.com/p/abc/")


def test_fetch_reads_caption_and_video_from_ytdlp_output(monkeypatch, tmp_path):
    monkeypatch.setattr(sources.shutil, "which", lambda _: "/usr/bin/yt-dlp")

    def fake_run(command, **_):
        (tmp_path / "post.info.json").write_text(json.dumps({"description": "Dal tadka"}))
        (tmp_path / "post.mp4").write_bytes(b"video")
        return type("R", (), {"returncode": 0, "stderr": ""})()

    monkeypatch.setattr(sources.subprocess, "run", fake_run)
    post = fetch_instagram("https://www.instagram.com/reel/abc/", workdir=tmp_path)
    assert post.caption == "Dal tadka"
    assert post.video_path == tmp_path / "post.mp4"


def test_fetch_failure_points_to_manual_fallback(monkeypatch, tmp_path):
    monkeypatch.setattr(sources.shutil, "which", lambda _: "/usr/bin/yt-dlp")
    monkeypatch.setattr(
        sources.subprocess,
        "run",
        lambda *a, **k: type("R", (), {"returncode": 1, "stderr": "login required"})(),
    )
    with pytest.raises(IngestionError, match="screenshot"):
        fetch_instagram("https://www.instagram.com/p/abc/", workdir=tmp_path)
