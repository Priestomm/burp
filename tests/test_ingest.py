import json

import pytest

from burp import ingest
from burp.ingest import (
    IngestionError,
    fetch_instagram,
    find_instagram_url,
    from_caption,
    from_screenshots,
    normalize_url,
    source_key,
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
    monkeypatch.setattr(ingest.shutil, "which", lambda _: None)
    with pytest.raises(IngestionError, match="paste the caption"):
        fetch_instagram("https://www.instagram.com/p/abc/")


def test_fetch_reads_caption_and_video_from_ytdlp_output(monkeypatch, tmp_path):
    monkeypatch.setattr(ingest.shutil, "which", lambda _: "/usr/bin/yt-dlp")

    def fake_run(command, **_):
        (tmp_path / "post.info.json").write_text(json.dumps({"description": "Dal tadka"}))
        (tmp_path / "post.mp4").write_bytes(b"video")
        return type("R", (), {"returncode": 0, "stderr": ""})()

    monkeypatch.setattr(ingest.subprocess, "run", fake_run)
    post = fetch_instagram("https://www.instagram.com/reel/abc/", workdir=tmp_path)
    assert post.caption == "Dal tadka"
    assert post.video_path == tmp_path / "post.mp4"


def test_fetch_failure_points_to_manual_fallback(monkeypatch, tmp_path):
    monkeypatch.setattr(ingest.shutil, "which", lambda _: "/usr/bin/yt-dlp")
    monkeypatch.setattr(
        ingest.subprocess,
        "run",
        lambda *a, **k: type("R", (), {"returncode": 1, "stderr": "login required"})(),
    )
    with pytest.raises(IngestionError, match="screenshot"):
        fetch_instagram("https://www.instagram.com/p/abc/", workdir=tmp_path)


@pytest.mark.parametrize(
    "url",
    [
        "https://www.instagram.com/reel/C1x_-9/",
        "https://www.instagram.com/reels/C1x_-9",
        "https://instagram.com/reel/C1x_-9/?igsh=MWQ1ZGUxMzBkMA==",
        "https://m.instagram.com/reel/C1x_-9/#comments",
        "https://www.instagram.com/cucina.di.anna/reel/C1x_-9/",
    ],
)
def test_normalize_url_drops_tracking_and_author_prefix(url):
    assert normalize_url(url) == "https://www.instagram.com/reel/C1x_-9/"


def test_post_and_reel_links_of_the_same_code_share_a_source_key():
    assert source_key("https://www.instagram.com/p/C1x_-9/") == source_key(
        "https://instagram.com/reel/C1x_-9/?igsh=abc"
    )
    assert source_key("https://www.instagram.com/p/other/") != source_key(
        "https://www.instagram.com/p/C1x_-9/"
    )


def test_normalize_url_of_other_links_keeps_the_path_only():
    assert normalize_url("HTTPS://Example.com/ricetta/?utm_source=x") == (
        "https://example.com/ricetta"
    )


def test_find_instagram_url_returns_the_normalized_link():
    text = "guarda qui https://instagram.com/reels/AbC123/?igsh=xyz buonissimo"
    assert find_instagram_url(text) == "https://www.instagram.com/reel/AbC123/"


def test_manual_input_takes_the_author_from_a_prefixed_link():
    post = from_caption("ciao", url="https://www.instagram.com/cucina.di.anna/p/AbC123/")
    assert post.url == "https://www.instagram.com/p/AbC123/"
    assert post.author_handle == "cucina.di.anna"


def test_fetch_reads_the_author_handle(monkeypatch, tmp_path):
    monkeypatch.setattr(ingest.shutil, "which", lambda _: "/usr/bin/yt-dlp")

    def fake_run(command, **_):
        info = {"description": "x", "channel": "cucina.di.anna", "uploader_id": "123456"}
        (tmp_path / "post.info.json").write_text(json.dumps(info))
        return type("R", (), {"returncode": 0, "stderr": ""})()

    monkeypatch.setattr(ingest.subprocess, "run", fake_run)
    post = fetch_instagram("https://www.instagram.com/p/abc/?igsh=1", workdir=tmp_path)
    assert post.author_handle == "cucina.di.anna"
    assert post.url == "https://www.instagram.com/p/abc/"


def test_only_media_from_the_user_can_become_the_dish_photo(tmp_path, monkeypatch):
    from burp.ingest import from_video

    clip = tmp_path / "clip.mp4"
    clip.write_bytes(b"video")
    shot = tmp_path / "shot.jpg"
    shot.write_bytes(b"jpg")
    assert from_video(clip).photo_inputs == [clip]
    assert from_screenshots([shot]).photo_inputs == [shot]
    assert from_caption("ciao").photo_inputs == []

    # A reel downloaded from the link is transcribed, but never used as the photo.
    monkeypatch.setattr(ingest.shutil, "which", lambda _: "/usr/bin/yt-dlp")

    def fake_run(command, **_):
        (tmp_path / "post.mp4").write_bytes(b"video")
        return type("R", (), {"returncode": 0, "stderr": ""})()

    monkeypatch.setattr(ingest.subprocess, "run", fake_run)
    post = fetch_instagram("https://www.instagram.com/reel/abc/", workdir=tmp_path)
    assert post.video_path is not None and post.photo_inputs == []


def test_from_video_needs_the_file(tmp_path):
    from burp.ingest import from_video

    with pytest.raises(IngestionError, match="not found"):
        from_video(tmp_path / "missing.mp4")
